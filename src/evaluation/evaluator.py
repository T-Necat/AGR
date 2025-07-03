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
    Bu model, bir agent yanıtının ve ilgili kullanıcı sorgusunun belirtilen kriterlere göre 
    değerlendirme sonuçlarını içerir.
    """
    goal_adherence: Optional[MetricEvaluation] = Field(default=None, description="Agent'ın ana görevine sadakati.")
    groundedness: Optional[MetricEvaluation] = Field(default=None, description="Yanıtın sağlanan bilgiye dayanması.")
    answer_relevance: Optional[MetricEvaluation] = Field(default=None, description="Yanıtın kullanıcı sorusuna uygunluğu.")
    persona_compliance: Optional[MetricEvaluation] = Field(default=None, description="Agent'ın tanımlanan personaya uyumu.")
    tool_accuracy: Optional[MetricEvaluation] = Field(default=None, description="Araç kullanımının doğruluğu.")
    knowledge_boundary_violation: Optional[MetricEvaluation] = Field(default=None, description="Bilgi sınırlarının ihlali.")
    security_policy_violation: Optional[MetricEvaluation] = Field(default=None, description="Güvenlik politikası ihlali.")
    style_and_courtesy: Optional[MetricEvaluation] = Field(default=None, description="Üslup ve nezaket.")
    conciseness: Optional[MetricEvaluation] = Field(default=None, description="Yanıtın özlülüğü.")
    user_sentiment: Optional[MetricEvaluation] = Field(default=None, description="Kullanıcı sorgusunun duygu durumu.")

class OutlierAnalysis(BaseModel):
    """Bir metrikteki aykırı (düşük) skorun nedenini analiz eden model."""
    metric_name: str = Field(..., description="Analiz edilen metriğin adı.")
    explanation: str = Field(..., description="Bu düşük skorun kök nedenini açıklayan, yapay zeka tarafından üretilmiş detaylı analiz.")

class EvaluationResult(BaseModel):
    """Tek bir değerlendirmenin tüm sonuçlarını kapsayan model."""
    metrics: EvaluationMetrics
    outlier_analyses: Optional[List[OutlierAnalysis]] = Field(default=None, description="Tespit edilen aykırı değerler için üretilen analizler.")

class SentimentTurn(BaseModel):
    """Her bir kullanıcı dönüşü için duygu durumunu içeren model."""
    turn: int = Field(..., description="Konuşmadaki kullanıcı dönüşünün sırası (1'den başlayarak).")
    sentiment_score: float = Field(..., description="Kullanıcının bu dönüşteki duygu puanı (-1.0 ile 1.0 arasında).")
    reasoning: str = Field(..., description="Bu puanın neden verildiğini açıklayan kısa ve net bir gerekçe.")

class GEvalResult(BaseModel):
    """G-EVAL denetim sonucunu içeren model."""
    is_consistent: bool = Field(..., description="Orijinal puan ve gerekçenin tutarlı olup olmadığını belirtir.")
    re_evaluation_reasoning: str = Field(..., description="Tutarlılık kararının arkasındaki mantığı açıklar.")
    corrected_score: Optional[float] = Field(default=None, description="Tutarsızlık durumunda önerilen düzeltilmiş puan.")


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
        Tüm metrik prompt'larını okur, ilgili bölümlere ayırır ve ana prompt şablonuna enjekte eder.
        """
        main_template_path = self.base_prompt_path / "evaluation" / f"{main_prompt_name}.md"
        main_template = self._load_prompt_template(main_template_path)

        # Agent yanıtını değerlendiren metrikleri topla
        agent_metrics_dir = self.base_prompt_path / "evaluation" / "metrics"
        agent_criteria_parts = []
        # user_sentiment.md hariç tüm metrikleri al
        for metric_file in sorted(agent_metrics_dir.glob("*.md")):
            if "user_sentiment" not in metric_file.name:
                agent_criteria_parts.append(self._load_prompt_template(metric_file))
        
        agent_criteria_section = "\n\n".join(agent_criteria_parts)

        # Kullanıcı sorgusunu değerlendiren metrikleri topla
        user_sentiment_prompt_path = agent_metrics_dir / "user_sentiment.md"
        user_criteria_section = self._load_prompt_template(user_sentiment_prompt_path)
        
        # 1. Adım: Ana şablonu, metrik bölümleriyle birleştir.
        # Bu aşamada formatlama yapılmaz, sadece metin eklenir.
        
        # KEYERROR DÜZELTMESİ: İki adımlı formatlama yerine, tüm argümanları
        # birleştirip tek seferde formatlayarak hatayı önle.
        format_args = {
            "agent_criteria_section": agent_criteria_section,
            "user_criteria_section": user_criteria_section,
            **kwargs
        }

        # 2. Adım: Birleştirilmiş ve tamamlanmış şablonu, gelen tüm argümanlarla tek seferde formatla.
        final_prompt = main_template.format(**format_args)
        
        return final_prompt

    async def evaluate_conversation(
        self,
        user_query: str,
        agent_response: str,
        agent_goal: str,
        rag_context: str,
        agent_persona: str,
        tool_calls: Optional[List[dict]] = None,
        enable_outlier_analysis: bool = False,
        outlier_threshold: float = 0.5,
        enable_g_eval: bool = False
    ) -> Optional[EvaluationResult]:
        """
        Bir konuşma turunu, dinamik olarak birleştirilmiş prompt'ları kullanarak değerlendirir.
        Gerekirse aykırı değer analizi ve G-EVAL tutarlılık denetimi yapar.
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
            evaluation_metrics = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=EvaluationMetrics,
                messages=[
                    {"role": "system", "content": "You are a fair and objective AI agent evaluator. Your output must be a valid JSON object matching the requested Pydantic model."},
                    {"role": "user", "content": prompt}
                ],
            )
            logger.info("Tekli konuşma değerlendirmesi başarıyla tamamlandı.")

            # G-EVAL: Değerlendirme tutarlılığını denetle ve gerekirse düzelt
            if enable_g_eval and evaluation_metrics:
                logger.info("G-EVAL tutarlılık denetimi başlatılıyor...")
                g_eval_tasks = []
                # `evaluation_metrics` bir Pydantic model olduğu için, üzerinde döngü kurmak için field'larını kullanırız
                for metric_name, metric_value in evaluation_metrics:
                    if metric_value and isinstance(metric_value, MetricEvaluation):
                        task = self._g_eval_metric_consistency(
                            metric_name=metric_name,
                            original_score=metric_value.score,
                            original_reasoning=metric_value.reasoning,
                            user_query=user_query,
                            agent_response=agent_response
                        )
                        g_eval_tasks.append((metric_name, task))

                if g_eval_tasks:
                    # Task'leri paralel olarak çalıştır
                    g_eval_results_list = await asyncio.gather(*[task for _, task in g_eval_tasks])
                    
                    # Sonuçları işle
                    for (metric_name, _), g_eval_result in zip(g_eval_tasks, g_eval_results_list):
                        if g_eval_result and not g_eval_result.is_consistent and g_eval_result.corrected_score is not None:
                            # İlgili metrik nesnesini güncelle
                            metric_to_update = getattr(evaluation_metrics, metric_name)
                            if metric_to_update:
                                logger.warning(
                                    f"G-EVAL tutarsızlık buldu: '{metric_name}'. "
                                    f"Orijinal Skor: {metric_to_update.score}, Yeni Skor: {g_eval_result.corrected_score}."
                                )
                                metric_to_update.score = g_eval_result.corrected_score
                                # Gerekçeyi, denetim kaydını içerecek şekilde güncelle
                                metric_to_update.reasoning = (
                                    f"[G-EVAL DENETİMİ]: {g_eval_result.re_evaluation_reasoning}\\n"
                                    f"---------------------\\n"
                                    f"[ORİJİNAL GEREKÇE]: {metric_to_update.reasoning}"
                                )
                logger.info("G-EVAL tutarlılık denetimi tamamlandı.")


            result = EvaluationResult(metrics=evaluation_metrics)

            if enable_outlier_analysis and evaluation_metrics:
                outliers = await self.explain_evaluation_outliers(
                    evaluation_results=evaluation_metrics,
                    user_query=user_query,
                    agent_response=agent_response,
                    rag_context=rag_context, # Varsayılan olarak tüm context'i kullan
                    agent_goal=agent_goal,
                    agent_persona=agent_persona,
                    outlier_threshold=outlier_threshold
                )
                result.outlier_analyses = outliers
            
            return result
            
        except Exception as e:
            logger.error(f"Değerlendirme sırasında bir hata oluştu: {e}", exc_info=True)
            return None

    async def explain_evaluation_outliers(
        self,
        evaluation_results: EvaluationMetrics,
        user_query: str,
        agent_response: str,
        rag_context: str,
        agent_goal: str,
        agent_persona: str,
        outlier_threshold: float = 0.5
    ) -> List[OutlierAnalysis]:
        """
        Verilen değerlendirme sonuçlarındaki düşük puanlı metrikleri (aykırı değerleri)
        belirler ve her biri için kök neden analizi yapar.
        """
        outlier_tasks = []
        for metric_name, metric_value in evaluation_results:
            if metric_value and isinstance(metric_value, MetricEvaluation) and metric_value.score < outlier_threshold:
                logger.info(f"'{metric_name}' metriği için aykırı değer bulundu (Skor: {metric_value.score}). Analiz başlatılıyor.")
                task = self._analyze_single_outlier(
                    user_query=user_query,
                    agent_response=agent_response,
                    rag_context=rag_context,
                    agent_goal=agent_goal,
                    agent_persona=agent_persona,
                    metric_name=metric_name,
                    metric_score=metric_value.score,
                    metric_reasoning=metric_value.reasoning
                )
                outlier_tasks.append(task)
        
        if not outlier_tasks:
            return []

        analyses = await asyncio.gather(*outlier_tasks)
        return [analysis for analysis in analyses if analysis]

    async def _analyze_single_outlier(
        self,
        user_query: str,
        agent_response: str,
        rag_context: str,
        agent_goal: str,
        agent_persona: str,
        metric_name: str,
        metric_score: float,
        metric_reasoning: str
    ) -> Optional[OutlierAnalysis]:
        """Bir metrikteki tek bir aykırı değer için yapay zeka analizi yapar."""
        logger.debug(f"'{metric_name}' için tekil aykırı değer analizi yapılıyor.")
        prompt_template = self._load_prompt_template(self.base_prompt_path / "evaluation" / "analyze_outlier_prompt.md")
        prompt = prompt_template.format(
            user_query=user_query,
            agent_response=agent_response,
            rag_context=rag_context,
            agent_goal=agent_goal,
            agent_persona=agent_persona,
            metric_name=metric_name,
            metric_score=metric_score,
            metric_reasoning=metric_reasoning
        )
        
        try:
            analysis_response = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=OutlierAnalysis,
                messages=[
                    {"role": "system", "content": "You are an expert AI performance analyst. Your task is to find the root cause of a low score. Your output must be a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
            )
            return analysis_response
        except Exception as e:
            logger.error(f"'{metric_name}' metriği için aykırı değer analizi sırasında hata: {e}", exc_info=True)
            return None

    async def _g_eval_metric_consistency(
        self,
        metric_name: str,
        original_score: float,
        original_reasoning: str,
        user_query: str,
        agent_response: str
    ) -> Optional[GEvalResult]:
        """Tek bir metriğin değerlendirme tutarlılığını G-EVAL ile denetler."""
        logger.debug(f"'{metric_name}' için G-EVAL tutarlılık denetimi yapılıyor.")
        prompt_template = self._load_prompt_template(self.base_prompt_path / "evaluation" / "g_eval_prompt.md")
        
        prompt = prompt_template.format(
            user_query=user_query,
            agent_response=agent_response,
            metric_name=metric_name,
            original_score=original_score,
            original_reasoning=original_reasoning
        )
        
        try:
            g_eval_response = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=GEvalResult,
                messages=[
                    {"role": "system", "content": "You are a meticulous AI Evaluation Auditor. Your task is to check the consistency of an evaluation made by another AI. Your output must be a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
            )
            return g_eval_response
        except Exception as e:
            logger.error(f"'{metric_name}' metriği için G-EVAL denetimi sırasında hata: {e}", exc_info=True)
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

        main_template = self._load_prompt_template(self.base_prompt_path / "evaluation" / "evaluate_session_prompt.md")

        # Oturum değerlendirmesi için relevant olan metrikleri topla
        metrics_dir = self.base_prompt_path / "evaluation" / "metrics"
        criteria_parts = []
        # user_sentiment hariç, oturum genelinde anlamlı olan metrikleri seç
        session_relevant_metrics = [
            "goal_adherence.md", "persona_compliance.md", 
            "style_and_courtesy.md", "conciseness.md",
            "knowledge_boundary_violation.md", "security_policy_violation.md",
            "user_sentiment.md"
        ]
        for metric_name in session_relevant_metrics:
            criteria_parts.append(self._load_prompt_template(metrics_dir / metric_name))
        
        criteria_section = "\n\n".join(criteria_parts)

        prompt = main_template.format(
            conversation_str=conversation_str,
            agent_goal=agent_goal,
            agent_persona=agent_persona,
            criteria_section=criteria_section
        )

        try:
            evaluation = await self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=EvaluationMetrics,
                messages=[
                    {"role": "system", "content": "You are a fair and objective AI agent session evaluator. Your output must be a valid JSON object matching the requested Pydantic model. Fill in any metrics not directly evaluated with a default score of 0.0 and 'N/A' for reasoning."},
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

    async def analyze_batch_results(
        self,
        stats_json: str,
        low_score_examples_str: str,
        high_score_examples_str: str
    ) -> str:
        """
        Değerlendirme sonuçlarını yapay zeka ile analiz edip bir rapor oluşturur.
        """
        logger.info("Toplu değerlendirme sonuçları için AI analizi başlatıldı.")
        prompt_template = self._load_prompt_template(self.base_prompt_path / "summarization" / "summarize_batch_results_prompt.md")
        prompt = prompt_template.format(
            stats_json=stats_json,
            low_score_examples_str=low_score_examples_str,
            high_score_examples_str=high_score_examples_str
        )
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            analysis = response.choices[0].message.content or "Analiz oluşturulamadı."
            logger.info("AI analizi başarıyla tamamlandı.")
            return analysis.strip()
        except Exception as e:
            logger.error(f"Toplu sonuç analizi sırasında bir hata oluştu: {e}", exc_info=True)
            return "Sonuçlar analiz edilirken bir hata meydana geldi."

    async def analyze_sentiment_trend(self, stats_json: str, sentiment_trend_data_str: str) -> str:
        """
        Verilen duygu verileri üzerinden bir trend analizi raporu oluşturur.
        """
        logger.info("Duygu trend analizi başlatıldı.")
        prompt_template = self._load_prompt_template(self.base_prompt_path / "summarization" / "analyze_sentiment_trend_prompt.md")
        prompt = prompt_template.format(
            stats_json=stats_json,
            sentiment_trend_data_str=sentiment_trend_data_str
        )
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            analysis = response.choices[0].message.content or "Trend analizi oluşturulamadı."
            logger.info("Duygu trend analizi başarıyla tamamlandı.")
            return analysis.strip()
        except Exception as e:
            logger.error(f"Duygu trend analizi sırasında bir hata oluştu: {e}", exc_info=True)
            return "Trend analizi oluşturulurken bir hata meydana geldi."

    async def analyze_sentiment_per_turn(self, full_conversation: List[Dict[str, str]]) -> List[Dict]:
        """
        Bir konuşmadaki her bir kullanıcı mesajının duygu durumunu ayrı ayrı analiz eder.
        """
        logger.info(f"Konuşma içi duygu analizi başlatıldı. Toplam {len(full_conversation)} mesaj var.")
        
        prompt_template = self._load_prompt_template(self.base_prompt_path / "summarization" / "analyze_sentiment_per_turn_prompt.md")
        
        user_turns = [(i, msg['content']) for i, msg in enumerate(full_conversation) if msg['role'] == 'user']
        
        tasks = []
        for i, (turn_idx, content) in enumerate(user_turns):
            prompt = prompt_template.format(turn_number=i + 1, user_query=content)
            task = self.async_client.chat.completions.create( # type: ignore
                model=self.model,
                response_model=SentimentTurn,
                messages=[
                    {"role": "system", "content": "You are an expert sentiment analyst. Your output must be a valid JSON object matching the requested Pydantic model."},
                    {"role": "user", "content": prompt}
                ],
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Konuşma içi duygu analizi sırasında bir alt görevde hata: {res}")
            elif isinstance(res, SentimentTurn):
                processed_results.append(res.model_dump())

        logger.info(f"{len(processed_results)} adet kullanıcı dönüşü için duygu analizi tamamlandı.")
        return processed_results


# Örnek kullanım (test için)
async def main_async():
    # Bu bölüm artık eski prompt yapısını yansıtıyor. Yeni yapı test edilmeli.
    logger.warning("main_async test fonksiyonu güncel prompt mimarisiyle test edilmelidir.")

if __name__ == "__main__":
    asyncio.run(main_async()) 