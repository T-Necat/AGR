from fastapi import FastAPI, HTTPException, Security, Request, Depends, UploadFile, File, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import uuid
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc
import pandas as pd
import io
from celery.result import AsyncResult
import asyncio

from src.config import get_settings
from src.vector_db.embedding_service import AgentEmbeddingService
from src.rag.rag_pipeline import RAGPipeline
from src.evaluation.evaluator import AgentEvaluator, EvaluationResult, EvaluationMetrics, OutlierAnalysis, MetricEvaluation
from src.logging_config import setup_logging
from src.database.database import SessionLocal, init_db
from src.database.models import EvaluationSession, MetricResult as MetricResultDB
from src.celery_app import celery_app
from src.tasks import batch_evaluate_task

# Logger'ı yapılandır
setup_logging()

# Rate Limiting
limiter = Limiter(key_func=get_remote_address)

# API Anahtarı için Header tanımı
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Logging ayarları
logger = logging.getLogger(__name__)

# FastAPI uygulamasını başlat
app = FastAPI(
    title="AI Agent Evaluation API",
    description="Provides a chat interface for an AI agent and evaluates its responses in real-time.",
    version="2.0.0"
)

# Prometheus Instrumentator'ü ekle
Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def central_error_handling_middleware(request: Request, call_next):
    """
    Tüm beklenmedik hataları yakalayan ve standart bir formatta yanıtlayan
    merkezi bir middleware.
    """
    try:
        return await call_next(request)
    except Exception as e:
        error_id = uuid.uuid4()
        logger.error(f"Beklenmedik hata oluştu: error_id={error_id}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Sunucuda beklenmedik bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
                "error_id": str(error_id)
            }
        )

# Veritabanı oturumunu yönetmek için bir dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Rate Limiting Middleware'i ekle
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Güvenlik ---

async def get_api_key(api_key: str = Security(api_key_header)):
    """API anahtarını doğrular."""
    settings = get_settings()
    if not settings.API_KEY:
        raise HTTPException(status_code=500, detail="Sunucu tarafında API anahtarı yapılandırılmamış.")
    
    if api_key == settings.API_KEY:
        return api_key
    else:
        raise HTTPException(status_code=403, detail="Geçersiz veya eksik API anahtarı.")

# --- Pydantic Modelleri ---

class MetricResultSchema(BaseModel):
    metric_name: str
    score: float
    reasoning: str

    class Config:
        orm_mode = True

class EvaluationSessionSchema(BaseModel):
    id: int
    session_id: str
    created_at: str  # Datetime'ı string olarak göstermek daha basit
    agent_id: str
    user_query: str
    agent_response: Optional[str] = None
    rag_context: Optional[str] = None
    agent_goal: str
    agent_persona: str
    user_feedback: Optional[str] = None
    feedback_sentiment: Optional[str] = None
    metric_results: List[MetricResultSchema] = []

    class Config:
        orm_mode = True

class SandboxRequest(BaseModel):
    agent_id: str = Field(..., description="The unique identifier for the agent being evaluated.")
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Kullanıcının sormak istediği soru."
    )
    agent_goal: str = Field(
        "Kullanıcının sorusunu, sağlanan bilgi tabanına dayanarak doğru ve eksiksiz bir şekilde yanıtlamak.",
        min_length=10,
        max_length=500,
        description="Agent'ın bu etkileşimdeki ana hedefi."
    )
    agent_persona: str = Field(
        "Yardımsever, profesyonel ve net bir yapay zeka asistanı.",
        min_length=10,
        max_length=500,
        description="Agent'ın benimsemesi gereken kişilik."
    )
    save_to_db: bool = Field(True, description="Değerlendirme sonuçlarının veritabanına kaydedilip kaydedilmeyeceği.")

class SandboxResponse(BaseModel):
    agent_response: str
    rag_context: str
    tool_calls: Optional[List[Dict]]
    evaluation: EvaluationResult
    session_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str
    
class BatchEvaluationResponse(BaseModel):
    task_id: str
    
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[float] = None
    result: Optional[Any] = None

class SystemStatusResponse(BaseModel):
    status: str
    services: List[str]
    collection_name: Optional[str] = None
    total_chunks: Optional[int] = None

class AgentStat(BaseModel):
    metric_name: str
    average_score: float

class AgentStatsResponse(BaseModel):
    agent_id: str
    total_evaluations: int
    overall_average_score: float
    metrics: List[AgentStat]

# --- Global Servisler ---
embedding_service: Optional[AgentEmbeddingService] = None
rag_pipeline: Optional[RAGPipeline] = None
evaluator: Optional[AgentEvaluator] = None

@app.on_event("startup")
def startup_event():
    """Uygulama başladığında servisleri başlatır ve veritabanını oluşturur"""
    global embedding_service, rag_pipeline, evaluator
    try:
        # Veritabanı ve tabloları oluştur
        init_db()
        logger.info("Veritabanı başarıyla başlatıldı ve tablolar kontrol edildi.")
        
        settings = get_settings()
        logger.info(f"Veritabanı yolu: {settings.CHROMA_PERSIST_DIRECTORY}")

        embedding_service = AgentEmbeddingService()
        rag_pipeline = RAGPipeline(embedding_service=embedding_service)
        evaluator = AgentEvaluator()
        
        logger.info("Tüm servisler başarıyla başlatıldı.")
        
    except Exception as e:
        logger.error(f"Başlangıç sırasında kritik hata: {e}", exc_info=True)
        # Hata durumunda servislerin None kalmasını sağla
        embedding_service = None
        rag_pipeline = None
        evaluator = None

# --- API Endpoints ---

@app.get("/api/evaluations", response_model=List[EvaluationSessionSchema])
@limiter.limit("30/minute")
async def get_all_evaluations(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Veritabanında saklanan tüm değerlendirme oturumlarını ve metriklerini listeler.
    Sayfalama destekler (skip, limit).
    """
    try:
        evaluations = db.query(EvaluationSession).order_by(EvaluationSession.id.desc()).offset(skip).limit(limit).all()
        # Pydantic şemasının `created_at` alanını string'e dönüştürmesi için manuel ayar
        results = []
        for eval_session in evaluations:
            session_data = EvaluationSessionSchema.from_orm(eval_session)
            session_data.created_at = eval_session.created_at.isoformat()
            results.append(session_data)
        return results
    except Exception as e:
        logger.error(f"Değerlendirme verileri alınırken hata oluştu: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Değerlendirme verileri alınırken sunucu hatası oluştu.")

@app.get("/api/sessions/{session_id}", response_model=EvaluationSessionSchema)
@limiter.limit("30/minute")
async def get_session_analysis(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Belirtilen session_id için detaylı oturum analizini döner."""
    try:
        session = db.query(EvaluationSession).filter(EvaluationSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
        
        session_data = EvaluationSessionSchema.from_orm(session)
        session_data.created_at = session.created_at.isoformat()
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Oturum analizi alınırken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Oturum analizi alınırken bir hata oluştu.")

@app.get("/api/metrics/stats")
@limiter.limit("30/minute")
async def get_metric_statistics(
    request: Request,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Metrik ortalamalarını ve dağılımlarını hesaplar."""
    try:
        query = db.query(
            MetricResultDB.metric_name,
            sql_func.avg(MetricResultDB.score).label('average_score'),
            sql_func.count(MetricResultDB.id).label('count')
        )
        if agent_id:
            query = query.join(EvaluationSession).filter(EvaluationSession.agent_id == agent_id)
        
        stats = query.group_by(MetricResultDB.metric_name).all()
        
        return {stat.metric_name: {"average_score": stat.average_score, "count": stat.count} for stat in stats}
    except Exception as e:
        logger.error(f"Metrik istatistikleri alınırken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Metrik istatistikleri alınırken bir hata oluştu.")

@app.post("/api/feedback", status_code=204)
@limiter.limit("20/minute")
async def save_feedback(
    feedback_request: FeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Kullanıcı geri bildirimini veritabanına kaydeder."""
    try:
        session = db.query(EvaluationSession).filter(EvaluationSession.session_id == feedback_request.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
        
        session.user_feedback = feedback_request.feedback
        # TODO: Burada basit bir duygu analizi modeli çağrılabilir.
        session.feedback_sentiment = "pending"
        
        db.commit()
        logger.info(f"Oturum {session.session_id} için geri bildirim kaydedildi.")
        return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geri bildirim kaydedilirken hata: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Geri bildirim kaydedilirken bir hata oluştu.")

@app.post("/api/evaluate/batch", response_model=BatchEvaluationResponse)
@limiter.limit("5/minute")
async def start_batch_evaluation(
    request: Request,
    file: UploadFile = File(...),
    api_key: str = Security(get_api_key)
):
    """CSV dosyasını yükleyip toplu değerlendirme için bir Celery görevi başlatır."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Geçersiz dosya türü. Lütfen bir CSV dosyası yükleyin.")
    
    try:
        contents = await file.read()
        buffer = io.StringIO(contents.decode('utf-8'))
        df = pd.read_csv(buffer)
        
        # DataFrame'i JSON'a çevir
        batch_data_json = df.to_json(orient='split', index=False)
        
        # Celery task'ını başlat
        task = batch_evaluate_task.delay(batch_data_json)
        
        logger.info(f"Toplu değerlendirme görevi başlatıldı. Task ID: {task.id}")
        return BatchEvaluationResponse(task_id=task.id)
    except Exception as e:
        logger.error(f"Toplu değerlendirme başlatılırken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dosya işlenirken veya görev başlatılırken hata: {e}")

@app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
@limiter.limit("60/minute")
async def get_task_status(
    task_id: str,
    request: Request,
    api_key: str = Security(get_api_key)
):
    """Bir Celery görevinin durumunu döner."""
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        progress = None
        if task_result.state == 'PROGRESS':
            progress = task_result.info.get('progress', 0)

        result = task_result.result if task_result.ready() else None

        return TaskStatusResponse(
            task_id=task_id,
            status=task_result.state,
            progress=progress,
            result=result
        )
    except Exception as e:
        logger.error(f"Task durumu alınırken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Task durumu sorgulanırken bir hata oluştu.")

@app.get("/", response_model=Dict)
@limiter.limit("20/minute")
async def root(request: Request):
    """Ana endpoint"""
    return {
        "message": "AI Agent Evaluation API",
        "version": app.version,
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health", response_model=SystemStatusResponse)
@limiter.limit("20/minute")
async def health_check(request: Request):
    """Sistem ve servislerin sağlık durumunu kontrol eder."""
    active_services = []
    if embedding_service: active_services.append("EmbeddingService")
    if rag_pipeline: active_services.append("RAGPipeline")
    if evaluator: active_services.append("AgentEvaluator")
    
    status = "healthy" if all([embedding_service, rag_pipeline, evaluator]) else "degraded"

    stats = {}
    if embedding_service:
        try:
            stats = embedding_service.get_collection_stats()
        except Exception:
            stats = {} # Hata durumunda boş kalsın
            
    return SystemStatusResponse(
        status=status,
        services=active_services,
        collection_name=stats.get('collection_name'),
        total_chunks=stats.get('total_chunks')
    )

@app.get("/api/agents", response_model=List[str])
@limiter.limit("30/minute")
async def get_all_agents(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Veritabanındaki tüm benzersiz agent_id'leri listeler."""
    try:
        agents = db.query(EvaluationSession.agent_id).distinct().all()
        return [agent[0] for agent in agents]
    except Exception as e:
        logger.error(f"Agent listesi alınırken hata oluştu: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent listesi alınırken bir hata oluştu.")

@app.get("/agent-stats/{agent_id}", response_model=AgentStatsResponse)
@limiter.limit("30/minute")
async def get_agent_stats(
    agent_id: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Belirli bir agent için performans istatistiklerini hesaplar."""
    try:
        # Toplam değerlendirme sayısı
        total_evaluations = db.query(EvaluationSession).filter(EvaluationSession.agent_id == agent_id).count()
        if total_evaluations == 0:
            raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found or has no evaluations.")

        # Metrik bazında ortalama skorlar
        metric_stats_query = db.query(
            MetricResultDB.metric_name,
            sql_func.avg(MetricResultDB.score).label('average_score')
        ).join(EvaluationSession).filter(EvaluationSession.agent_id == agent_id).group_by(MetricResultDB.metric_name).all()
        
        metric_stats = [AgentStat(metric_name=name, average_score=avg_score) for name, avg_score in metric_stats_query]

        # Genel ortalama skor
        overall_avg_score = sum(s.average_score for s in metric_stats) / len(metric_stats) if metric_stats else 0

        return AgentStatsResponse(
            agent_id=agent_id,
            total_evaluations=total_evaluations,
            overall_average_score=round(overall_avg_score, 3),
            metrics=metric_stats
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent istatistikleri alınırken hata oluştu: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent istatistikleri hesaplanırken bir hata oluştu.")

@app.post("/api/evaluate/sandbox", response_model=SandboxResponse)
@limiter.limit("10/minute")
async def evaluate_sandbox(request: SandboxRequest, api_key: str = Security(get_api_key), db: Session = Depends(get_db)):
    """
    Kullanıcı sorgusunu işler, bir yanıt üretir ve bu yanıtı anında değerlendirir (Sandbox modu).
    Sonuçlar `save_to_db` parametresine göre veritabanına kaydedilir.
    """
    if not all([rag_pipeline, evaluator]):
        raise HTTPException(status_code=503, detail="Bir veya daha fazla servis kullanılamıyor. Lütfen logları kontrol edin.")
    
    assert rag_pipeline is not None
    assert evaluator is not None
    
    try:
        # 1. RAG pipeline'ı çalıştırarak yanıt üret
        pipeline_output = await rag_pipeline.execute_pipeline(
            user_query=request.query,
            agent_goal=request.agent_goal,
            agent_persona=request.agent_persona
        )

        # 2. Üretilen yanıtı değerlendir
        tool_calls_data = pipeline_output.get("tool_calls")

        evaluation_result = await evaluator.evaluate_conversation(
            user_query=request.query,
            agent_response=pipeline_output["agent_response"],
            agent_goal=request.agent_goal,
            rag_context=pipeline_output["rag_context"],
            agent_persona=request.agent_persona,
            tool_calls=tool_calls_data,
            enable_outlier_analysis=True,
            outlier_threshold=0.6,
            enable_g_eval=True
        )

        if not evaluation_result:
            raise HTTPException(status_code=500, detail="Yanıt üretildi ancak değerlendirme yapılamadı.")

        session_id_str = None
        # 3. Sonuçları veritabanına kaydet (eğer istenirse)
        if request.save_to_db:
            try:
                # Yeni bir EvaluationSession nesnesi oluştur
                new_session = EvaluationSession(
                    agent_id=request.agent_id,
                    user_query=request.query,
                    agent_response=pipeline_output["agent_response"],
                    rag_context=pipeline_output["rag_context"],
                    agent_goal=request.agent_goal,
                    agent_persona=request.agent_persona,
                )
                db.add(new_session)
                db.flush() # ID'nin atanması için
                session_id_str = new_session.session_id

                # Her bir metrik için MetricResult nesneleri oluştur
                for metric_name, metric_value in evaluation_result.metrics:
                    if metric_value and isinstance(metric_value, MetricEvaluation):
                        metric_db = MetricResultDB(
                            session_id=new_session.id,
                            metric_name=metric_name,
                            score=metric_value.score,
                            reasoning=metric_value.reasoning
                        )
                        db.add(metric_db)
                
                db.commit()
                logger.info(f"Sandbox oturumu {new_session.session_id} ve metrikleri veritabanına başarıyla kaydedildi.")

            except Exception as e:
                logger.error(f"Değerlendirme sonuçları veritabanına kaydedilirken hata oluştu: {e}", exc_info=True)
                db.rollback()
                # Hata olsa bile kullanıcıya sonucu döndürmeye devam et, sadece logla
            
        # 4. Sonucu birleştir ve döndür
        return SandboxResponse(
            agent_response=pipeline_output["agent_response"],
            rag_context=pipeline_output["rag_context"],
            tool_calls=pipeline_output["tool_calls"],
            evaluation=evaluation_result,
            session_id=session_id_str
        )

    except Exception as e:
        logger.error(f"Chat/evaluate işleminde hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"İç sunucu hatası: {str(e)}")

@app.websocket("/ws/evaluation/{client_id}")
async def evaluation_websocket(websocket: WebSocket, client_id: str):
    """
    Değerlendirme görevlerinin durumunu gerçek zamanlı olarak izlemek için WebSocket bağlantısı.
    Şu anda periyodik olarak task durumunu kontrol eder. İdealde bu, bir pub/sub
    mekanizması (örn. Redis Pub/Sub) ile daha verimli hale getirilebilir.
    """
    await websocket.accept()
    logger.info(f"WebSocket bağlantısı kuruldu: client_id={client_id}")
    
    # client_id'nin bir task_id olduğunu varsayıyoruz.
    task_id = client_id
    
    try:
        while True:
            task_result = AsyncResult(task_id, app=celery_app)
            status = task_result.state
            
            response = {"task_id": task_id, "status": status, "progress": 0, "result": None}

            if status == 'PROGRESS':
                response['progress'] = task_result.info.get('progress', 0)
            elif task_result.ready():
                response['result'] = task_result.result
                await websocket.send_json(response)
                break  # Görev tamamlandı, döngüyü sonlandır.

            await websocket.send_json(response)
            await asyncio.sleep(2) # 2 saniyede bir durum kontrolü
            
    except Exception as e:
        logger.warning(f"WebSocket hatası (client_id={client_id}): {e}")
    finally:
        await websocket.close()
        logger.info(f"WebSocket bağlantısı kapatıldı: client_id={client_id}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    ) 