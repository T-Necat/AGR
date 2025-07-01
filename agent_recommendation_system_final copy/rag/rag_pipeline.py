import os
import logging
from typing import Dict, List, Optional

import instructor
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Çevre değişkenlerini yükle
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Modelleri ---

class ToolCall(BaseModel):
    """Agent'ın bir görevi yerine getirmek için kullanabileceği bir aracı temsil eder."""
    tool_name: str = Field(..., description="Kullanılacak aracın adı, örn: 'search_database'.")
    parameters: Dict = Field(..., description="Araca geçirilecek parametreler.")

class GeneratedResponse(BaseModel):
    """
    LLM tarafından üretilen yanıtı ve potansiyel araç çağrılarını yapılandırır.
    """
    response_text: str = Field(
        ...,
        description="Kullanıcıya gösterilecek nihai, insan dostu metin yanıtı."
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        None,
        description="Eğer gerekliyse, yanıtı desteklemek için yapılması gereken araç çağrıları."
    )

class RAGPipeline:
    """
    Bir kullanıcı sorgusuna yanıt vermek için RAG ve LLM'i birleştiren pipeline.
    1. Bağlamı alır (Retrieve)
    2. Yanıtı üretir (Generate)
    """

    def __init__(self,
                 embedding_service,
                 llm_model: str = "o4-mini-2025-04-16",
                 temperature: float = 0.1):

        self.embedding_service = embedding_service
        self.llm_model = llm_model
        self.temperature = temperature

        # OpenAI istemcisini `instructor` ile yapılandır
        self.client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

        logger.info(f"RAG Pipeline başlatıldı: LLM={self.llm_model}")

    def _get_relevant_context(self, query: str, top_k: int = 5, score_threshold: float = 0.5) -> str:
        """
        Verilen sorgu için vektör veritabanından ilgili bağlamı arar.
        """
        logger.info(f"'{query}' sorgusu için ilgili bağlam aranıyor...")
        try:
            similar_chunks = self.embedding_service.search_similar_agents(
                query=query,
                top_k=top_k,
                score_threshold=score_threshold
            )
            logger.info(f"Vektör veritabanından {len(similar_chunks)} adet chunk bulundu.")

            if not similar_chunks:
                logger.warning("İlgili bağlam bulunamadı.")
                return "Bilgi tabanında bu konuyla ilgili bilgi bulunamadı."

            # Bağlamı tek bir metin bloğu olarak birleştir
            context_text = "\n---\n".join([chunk['content'] for chunk in similar_chunks])
            return context_text
        except Exception as e:
            logger.error(f"Bağlam alınırken hata oluştu: {e}", exc_info=True)
            return "Hata: Bilgi tabanına erişilemedi."

    def execute_pipeline(self,
                         user_query: str,
                         agent_goal: str,
                         agent_persona: str) -> Dict:
        """
        RAG pipeline'ını uçtan uca çalıştırır.
        
        Args:
            user_query (str): Kullanıcının orijinal sorgusu.
            agent_goal (str): Agent'ın bu etkileşimdeki ana hedefi.
            agent_persona (str): Agent'ın benimsemesi gereken kişilik.
            
        Returns:
            Bir sözlük:
            - agent_response (str): Üretilen yanıt metni.
            - rag_context (str): Yanıt için kullanılan bağlam.
            - tool_calls (Optional[List[Dict]]): Yapılan araç çağrıları.
        """
        try:
            # 1. Adım: Bağlamı Al (Retrieve)
            rag_context = self._get_relevant_context(user_query)

            # 2. Adım: Yanıtı Üret (Generate)
            prompt = f"""
            Sen, belirli bir görevi olan bir yapay zeka asistanısın. Aşağıdaki kurallara kesinlikle uymalısın:
            1.  **Persona**: Dilin ve üslubun "{agent_persona}" tanımına uygun olmalı.
            2.  **Görev (Goal)**: Ana hedefin: "{agent_goal}". Tüm yanıtların bu hedefi desteklemelidir.
            3.  **Bilgi Kaynağı**: Yanıtlarını SADECE aşağıda sağlanan 'Bilgi Tabanı'na dayandırmalısın. Bilgi tabanında olmayan hiçbir şeyi varsayma veya uydurma. Eğer bilgi yoksa, 'Bu konuda bilgim yok' de.
            4.  **Araç Kullanımı**: Eğer kullanıcının isteğini yanıtlamak için ek bilgiye veya bir eyleme ihtiyaç duyuyorsan (örn: sipariş durumu kontrolü, veritabanı sorgusu), uygun araçları `tool_calls` alanında belirt. Gerekmiyorsa bu alanı boş bırak.

            --- Bilgi Tabanı (RAG Context) ---
            {rag_context}
            
            --- Kullanıcı Sorusu ---
            "{user_query}"

            Şimdi yukarıdaki kurallara göre kullanıcıya yanıt ver ve gerekli araçları belirle.
            """

            # `instructor` kullanarak yapılandırılmış yanıt al
            generated_output = self.client.chat.completions.create(  # type: ignore
                model=self.llm_model,
                response_model=GeneratedResponse,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that follows instructions precisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
            )

            logger.info(f"Yanıt üretildi. Araç çağrıları: {generated_output.tool_calls}")

            return {
                "agent_response": generated_output.response_text,
                "rag_context": rag_context,
                "tool_calls": [tc.model_dump() for tc in generated_output.tool_calls] if generated_output.tool_calls else None
            }

        except Exception as e:
            logger.error(f"RAG pipeline çalıştırılırken hata oluştu: {e}", exc_info=True)
            return {
                "agent_response": f"Bir hata oluştu: {e}",
                "rag_context": "",
                "tool_calls": None
            }

# Örnek kullanım (test için)
if __name__ == "__main__":
    # Gerçek bir embedding_service mock'u veya örneği gerekir.
    # Bu basit test için sahte bir servis oluşturalım.
    class MockEmbeddingService:
        def search_similar_agents(self, query: str, top_k: int, score_threshold: float) -> List[Dict]:
            print(f"Mock arama yapılıyor: '{query}'")
            if "fatura" in query:
                return [
                    {'content': 'Fatura sorunları için müşteri hizmetleri ile görüşebilirsiniz. Telefon: 444 1 555'},
                    {'content': 'Geçmiş faturalarınızı online panelinizden görüntüleyebilirsiniz.'}
                ]
            return [{'content': "Standart karşılama mesajımız: Jotform'a hoş geldiniz!"}]

    embedding_service = MockEmbeddingService()
    rag_pipeline = RAGPipeline(embedding_service=embedding_service)

    test_query = "Geçen ayki faturamı bulamıyorum, ne yapmalıyım?"
    test_goal = "Kullanıcıların fatura sorunlarını çözmelerine yardımcı olmak."
    test_persona = "Sakin, profesyonel ve çözüm odaklı bir müşteri temsilcisi."

    result = rag_pipeline.execute_pipeline(
        user_query=test_query,
        agent_goal=test_goal,
        agent_persona=test_persona
    )

    print("\n--- RAG Pipeline Çıktısı ---")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False)) 