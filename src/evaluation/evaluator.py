import logging
import asyncio
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import instructor
import openai
from pathlib import Path
import os

from src.config import get_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Pydantic Modelleri ---
# Değerlendirme metrikleri için yapılandırılmış veri modelleri

class MetricEvaluation(BaseModel):
    """Her bir metrik için puan ve gerekçeyi içeren model."""
    score: float = Field(..., description="0.0 ile 1.0 arasında bir puan (veya belirtilen durumlarda 0/1).")
    reasoning: str = Field(..., description="Bu puanın neden verildiğini açıklayan kısa ve net bir gerekçe.")

class EvaluationMetrics(BaseModel):
    """
    Bu model, bir agent yanıtının belirtilen kriterlere göre değerlendirme sonuçlarını içerir.
    Her bir metrik, bir puan ve o puanın gerekçesini içerir.
    """
    goal_adherence: MetricEvaluation = Field(..., description="Agent'ın ana görevine sadakati.")
    groundedness: MetricEvaluation = Field(..., description="Yanıtın sağlanan bilgiye dayanması.")
    answer_relevance: MetricEvaluation = Field(..., description="Yanıtın kullanıcı sorusuna uygunluğu.")
    persona_compliance: MetricEvaluation = Field(..., description="Agent'ın tanımlanan personaya uyumu.")
    tool_accuracy: MetricEvaluation = Field(..., description="Araç kullanımının doğruluğu.")
    knowledge_boundary_violation: MetricEvaluation = Field(..., description="Bilgi sınırlarının ihlali.")
    security_policy_violation: MetricEvaluation = Field(..., description="Güvenlik politikası ihlali.")
    style_and_courtesy: MetricEvaluation = Field(..., description="Üslup ve nezaket.")
    conciseness: MetricEvaluation = Field(..., description="Yanıtın özlülüğü.")


class AgentEvaluator:
    """
    LLM-as-a-judge (Yargıç olarak LLM) yaklaşımını kullanarak 
    agent konuşmalarını değerlendiren sınıf. Bu sınıf, modüler bir prompt
    yönetim sistemi kullanarak esneklik ve kolay bakım sağlar.
    """
    def __init__(self, model: Optional[str] = None):
        """
        Değerlendiriciyi başlatır.
        """
        settings = get_settings()
        self.model = model or settings.LLM_MODEL
        self.async_client = instructor.patch(openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY))
        self.base_prompt_path = Path(__file__).parent.parent / "prompts"
        logger.info(f"AgentEvaluator başlatıldı. Model: {self.model}, Prompt Dizini: {self.base_prompt_path}")

    def _load_prompt_template(self, file_path: Path) -> str:
        """Belirtilen yoldan bir prompt şablonu yükler."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt dosyası bulunamadı: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Prompt dosyası okunurken hata oluştu: {file_path}, Hata: {e}")
            raise

    def _assemble_evaluation_prompt(self, main_prompt_name: str, **kwargs) -> str:
        """
        Tüm metrik prompt'larını okur, birleştirir ve ana prompt şablonuna enjekte eder.
        """
        # 1. Ana (orkestratör) prompt şablonunu yükle
        main_template_path = self.base_prompt_path / "evaluation" / f"{main_prompt_name}.md"
        main_template = self._load_prompt_template(main_template_path)

        # 2. Tüm metrik dosyalarını birleştir
        metrics_dir = self.base_prompt_path / "evaluation" / "metrics"
        metric_files = sorted(metrics_dir.glob("*.md"))
        
        criteria_parts = []
        for metric_file in metric_files:
            criteria_parts.append(self._load_prompt_template(metric_file))
        
        criteria_section = "\n\n".join(criteria_parts)

        # 3. Ana şablonu ve metrikler bölümünü formatla
        # Önce metrikler bölümü, sonra tüm prompt
        formatted_criteria = criteria_section.format(**kwargs)
        final_prompt = main_template.format(criteria_section=formatted_criteria, **kwargs)
        
        return final_prompt

    async def evaluate_conversation(
        self,
        user_query: str,
        agent_response: str,
        agent_goal: str,
        rag_context: str,
        agent_persona: str,
        tool_calls: Optional[List[dict]] = None
    ) -> Optional[EvaluationMetrics]:
        """
        Bir konuşma turunu, dinamik olarak birleştirilmiş prompt'ları kullanarak değerlendirir.
        """
        tool_calls_str = str(tool_calls) if tool_calls else "Not used"
        logger.info(f"Tekli konuşma değerlendirmesi başlatıldı. Sorgu: '{user_query[:50]}...'")
        
        prompt = self._assemble_evaluation_prompt(
            main_prompt_name="evaluate_conversation_prompt",
            user_query=user_query,
            agent_response=agent_response,
            agent_goal=agent_goal,
            rag_context=rag_context,
            agent_persona=agent_persona,
            tool_calls_str=tool_calls_str
        )
        
        try:
            evaluation = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=EvaluationMetrics,
                messages=[
                    {"role": "system", "content": "You are a fair and objective AI agent evaluator. Your output must be a valid JSON object matching the requested Pydantic model."},
                    {"role": "user", "content": prompt}
                ],
            )
            logger.info("Tekli konuşma değerlendirmesi başarıyla tamamlandı.")
            return evaluation
        except Exception as e:
            logger.error(f"Değerlendirme sırasında bir hata oluştu: {e}", exc_info=True)
            return None

    async def evaluate_session(
        self,
        full_conversation: List[Dict[str, str]],
        agent_goal: str,
        agent_persona: str,
    ) -> Optional[EvaluationMetrics]:
        """
        Tüm bir konuşma oturumunu, dinamik olarak birleştirilmiş prompt'ları kullanarak bütünsel olarak değerlendirir.
        """
        conversation_str = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in full_conversation])
        logger.info(f"Oturum değerlendirmesi başlatıldı. Oturumda {len(full_conversation)} mesaj var.")

        # Bu metrikler oturum genelinde relevant olmayabilir, default değerler atıyoruz.
        prompt = self._assemble_evaluation_prompt(
            main_prompt_name="evaluate_session_prompt",
            agent_goal=agent_goal,
            agent_persona=agent_persona,
            conversation_str=conversation_str,
            # Session prompt'unda bulunmayan metrikler için boş değerler
            rag_context="N/A for session evaluation",
            user_query="N/A for session evaluation",
            tool_calls_str="N/A for session evaluation",
            agent_response="N/A for session evaluation"
        )

        try:
            evaluation = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=EvaluationMetrics,
                messages=[
                    {"role": "system", "content": "You are a fair and objective AI agent session evaluator. Your output must be a valid JSON object matching the requested Pydantic model."},
                    {"role": "user", "content": prompt}
                ],
            )
            logger.info("Oturum değerlendirmesi başarıyla tamamlandı.")
            return evaluation
        except Exception as e:
            logger.error(f"Oturum değerlendirme sırasında bir hata oluştu: {e}", exc_info=True)
            return None

    async def summarize_session(self, full_conversation: List[Dict[str, str]]) -> str:
        """
        Tüm bir konuşma oturumunu asenkron olarak özetler.
        """
        conversation_str = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in full_conversation])
        logger.info(f"Oturum özeti oluşturma başlatıldı. Oturumda {len(full_conversation)} mesaj var.")

        prompt_template = self._load_prompt_template(self.base_prompt_path / "summarization" / "summarize_session_prompt.md")
        prompt = prompt_template.format(conversation_str=conversation_str)
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations concisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )
            summary = response.choices[0].message.content or "Özet oluşturulamadı."
            logger.info("Oturum özeti başarıyla oluşturuldu.")
            return summary.strip()
        except Exception as e:
            logger.error(f"Oturum özeti oluşturulurken bir hata oluştu: {e}", exc_info=True)
            return "Özet oluşturulurken bir hata meydana geldi."

# Örnek kullanım (test için)
async def main_async():
    # Bu bölüm artık eski prompt yapısını yansıtıyor. Yeni yapı test edilmeli.
    logger.warning("main_async test fonksiyonu güncel prompt mimarisiyle test edilmelidir.")

if __name__ == "__main__":
    asyncio.run(main_async()) 