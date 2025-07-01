from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
import os
from dotenv import load_dotenv

# Çevre değişkenlerini yükle
load_dotenv()

# Modülleri import et
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_db.embedding_service import AgentEmbeddingService
from rag.rag_pipeline import RAGPipeline, GeneratedResponse
from evaluation.evaluator import AgentEvaluator, EvaluationMetrics

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI uygulamasını başlat
app = FastAPI(
    title="AI Agent Evaluation API",
    description="Provides a chat interface for an AI agent and evaluates its responses in real-time.",
    version="2.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Modelleri ---

class ChatRequest(BaseModel):
    query: str
    agent_goal: str = Field(
        "Kullanıcının sorusunu, sağlanan bilgi tabanına dayanarak doğru ve eksiksiz bir şekilde yanıtlamak.",
        description="Agent'ın bu etkileşimdeki ana hedefi."
    )
    agent_persona: str = Field(
        "Yardımsever, profesyonel ve net bir yapay zeka asistanı.",
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
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, "chroma_db_openai")
        
        logger.info(f"Veritabanı yolu: {db_path}")

        embedding_service = AgentEmbeddingService(persist_directory=db_path)
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
async def root():
    """Ana endpoint"""
    return {
        "message": "AI Agent Evaluation API",
        "version": app.version,
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health", response_model=SystemStatusResponse)
async def health_check():
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
async def chat_and_evaluate(request: ChatRequest):
    """
    Kullanıcı sorgusunu işler, bir yanıt üretir ve bu yanıtı anında değerlendirir.
    """
    if not all([rag_pipeline, evaluator]):
        raise HTTPException(status_code=503, detail="Bir veya daha fazla servis kullanılamıyor. Lütfen logları kontrol edin.")
    
    try:
        # 1. RAG pipeline'ı çalıştırarak yanıt üret
        pipeline_output = rag_pipeline.execute_pipeline(
            user_query=request.query,
            agent_goal=request.agent_goal,
            agent_persona=request.agent_persona
        )

        # 2. Üretilen yanıtı değerlendir
        evaluation_result = evaluator.evaluate_conversation(
            user_query=request.query,
            agent_response=pipeline_output["agent_response"],
            agent_goal=request.agent_goal,
            rag_context=pipeline_output["rag_context"],
            agent_persona=request.agent_persona,
            tool_calls=pipeline_output["tool_calls"]
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