import pandas as pd
import json
import asyncio
from celery import Task
from .celery_app import celery_app
from .evaluation.evaluator import AgentEvaluator
from typing import Optional, List, Dict
import logging
import openai

logger = logging.getLogger(__name__)

async def _run_single_evaluation(eval_data: dict, evaluator: AgentEvaluator) -> Optional[dict]:
    """
    Tek bir satır veri için değerlendirmeyi asenkron olarak çalıştıran yardımcı fonksiyon.
    Hata durumunda loglar ve None döner.
    """
    try:
        user_query = str(eval_data.get('user_query', ''))
        agent_response = str(eval_data.get('agent_response', ''))
        agent_persona = str(eval_data.get('persona', ''))
        
        tasks_str = str(eval_data.get('tasks', '[]'))
        tasks = json.loads(tasks_str.replace("'", "\""))
        task_descriptions = [t.get('value', {}).get('about', '') for t in tasks if t.get('type') == 'talk-about']
        agent_goal = ". ".join(filter(None, task_descriptions)) or "Kullanıcıya yardımcı olmak."
        
        rag_context = f"Agent'ın bilgi tabanından getirdiği varsayılan kanıt: '{agent_response}'"

        result = await evaluator.evaluate_conversation(
            user_query=user_query, agent_response=agent_response,
            agent_goal=agent_goal, rag_context=rag_context,
            agent_persona=agent_persona, tool_calls=None
        )
        return result.model_dump() if result else None
    except Exception as e:
        logger.error(
            f"Tekli değerlendirme sırasında hata oluştu. Veri: {eval_data.get('chat_id', 'N/A')}. Hata: {e}",
            exc_info=True
        )
        return None

@celery_app.task(
    bind=True,
    autoretry_for=(openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60
)
def batch_evaluate_task(self: Task, batch_data_json: str) -> List[Dict]:
    """
    Celery arka plan görevi. Bir grup konuşmayı asenkron ve paralel olarak değerlendirir.
    Geçici API hatalarında otomatik olarak yeniden dener.
    """
    evaluator = AgentEvaluator()
    try:
        batch_data = pd.read_json(batch_data_json, orient='split')
    except Exception as e:
        logger.error("Gelen JSON veri (batch_data_json) okunamadı.", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return []

    async def run_all_evaluations():
        tasks = []
        for _, row in batch_data.iterrows():
            tasks.append(_run_single_evaluation(row.to_dict(), evaluator))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Streamlit'e ilerleme bildirmek için toplu güncelleme
        total_rows = len(batch_data)
        self.update_state(state='PROGRESS', meta={'current': total_rows, 'total': total_rows})
        
        # Başarılı sonuçları filtrele
        successful_results = [res for res in results if res and not isinstance(res, Exception)]
        return successful_results

    # asenkron fonksiyonu senkron bir celery task'ı içinden çalıştır
    results = asyncio.run(run_all_evaluations())
    
    return results 