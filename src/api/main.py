from fastapi import FastAPI, HTTPException, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import uuid
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import get_settings
from src.vector_db.embedding_service import AgentEmbeddingService
from src.rag.rag_pipeline import RAGPipeline
from src.evaluation.evaluator import AgentEvaluator, EvaluationMetrics
from src.logging_config import setup_logging

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

# Rate Limiting Middleware'i ekle
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

class ChatRequest(BaseModel):
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

class ChatResponse(BaseModel):
    agent_response: str
    rag_context: str
    tool_calls: Optional[List[Dict]]
    evaluation: EvaluationMetrics

class SystemStatusResponse(BaseModel):
    status: str
    services: List[str]
    collection_name: Optional[str] = None
    total_chunks: Optional[int] = None

# --- Global Servisler ---
embedding_service: Optional[AgentEmbeddingService] = None
rag_pipeline: Optional[RAGPipeline] = None
evaluator: Optional[AgentEvaluator] = None

@app.on_event("startup")
def startup_event():
    """Uygulama başladığında servisleri başlatır"""
    global embedding_service, rag_pipeline, evaluator
    try:
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

@app.post("/chat_and_evaluate", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat_and_evaluate(request: ChatRequest, api_key: str = Security(get_api_key)):
    """
    Kullanıcı sorgusunu işler, bir yanıt üretir ve bu yanıtı anında değerlendirir.
    Bu endpoint API anahtarı ile korunmaktadır.
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
        # RAG pipeline'ından gelen tool_calls'u doğrudan kullan
        tool_calls_data = pipeline_output.get("tool_calls")

        evaluation_result = await evaluator.evaluate_conversation(
            user_query=request.query,
            agent_response=pipeline_output["agent_response"],
            agent_goal=request.agent_goal,
            rag_context=pipeline_output["rag_context"],
            agent_persona=request.agent_persona,
            tool_calls=tool_calls_data
        )

        if not evaluation_result:
            raise HTTPException(status_code=500, detail="Yanıt üretildi ancak değerlendirme yapılamadı.")

        # 3. Sonucu birleştir ve döndür
        return ChatResponse(
            agent_response=pipeline_output["agent_response"],
            rag_context=pipeline_output["rag_context"],
            tool_calls=pipeline_output["tool_calls"],
            evaluation=evaluation_result
        )

    except Exception as e:
        logger.error(f"Chat/evaluate işleminde hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"İç sunucu hatası: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 