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

    async def run_all_evaluations() -> List[Dict]:
        tasks = []
        for _, row in batch_data.iterrows():
            tasks.append(_run_single_evaluation(row.to_dict(), evaluator))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Streamlit'e ilerleme bildirmek için toplu güncelleme
        total_rows = len(batch_data)
        self.update_state(state='PROGRESS', meta={'current': total_rows, 'total': total_rows})
        
        # Başarılı sonuçları filtrele
        successful_results = [res for res in results if isinstance(res, dict)]
        return successful_results

    # asenkron fonksiyonu senkron bir celery task'ı içinden çalıştır
    results = asyncio.run(run_all_evaluations())
    
    return results

@celery_app.task(
    bind=True,
    autoretry_for=(openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60
)
def evaluate_and_summarize_session_task(self: Task, session_data_json: str) -> Dict:
    """
    Celery arka plan görevi. Tek bir oturumu değerlendirir ve özetler.
    """
    evaluator = AgentEvaluator()
    try:
        session_df = pd.read_json(session_data_json, orient='split')
        if session_df.empty:
            return {"error": "Oturum verisi boş."}
    except Exception as e:
        logger.error("Gelen JSON veri (session_data_json) okunamadı.", exc_info=True)
        return {"error": f"JSON parse hatası: {e}"}

    async def run_evaluation_and_summary():
        # Konuşma geçmişini oluştur
        full_conversation = []
        for _, row in session_df.sort_values('created_at').iterrows():
            full_conversation.append({"role": str(row['type']).lower(), "content": str(row['content'])})

        # Agent hedefini ve personasını çıkar
        agent_persona = str(session_df['persona'].iloc[0]) if 'persona' in session_df.columns else "Tanımlanmamış"
        try:
            tasks_str = str(session_df['tasks'].iloc[0])
            tasks = json.loads(tasks_str.replace("'", "\""))
            task_descriptions = [t.get('value', {}).get('about', '') for t in tasks if t.get('type') == 'talk-about']
            agent_goal = ". ".join(filter(None, task_descriptions)) or "Kullanıcıya yardımcı olmak."
        except (json.JSONDecodeError, TypeError, IndexError):
            agent_goal = "Kullanıcıya yardımcı olmak."

        # Değerlendirme ve özeti paralel olarak çalıştır
        self.update_state(state='PROGRESS', meta={'status': 'Değerlendirme ve özetleme çalışıyor...'})
        eval_task = evaluator.evaluate_session(full_conversation, agent_goal, agent_persona)
        summary_task = evaluator.summarize_session(full_conversation)
        
        results = await asyncio.gather(eval_task, summary_task, return_exceptions=True)
        
        evaluation_result, summary_result = results

        final_result = {}
        if isinstance(evaluation_result, Exception):
            final_result['evaluation'] = None
            logger.error(f"Oturum değerlendirme hatası: {evaluation_result}")
        elif evaluation_result:
            final_result['evaluation'] = evaluation_result.model_dump() # type: ignore
        else:
            final_result['evaluation'] = None
            
        if isinstance(summary_result, Exception):
            final_result['summary'] = "Özet oluşturulurken bir hata oluştu."
            logger.error(f"Oturum özetleme hatası: {summary_result}")
        else:
            final_result['summary'] = summary_result
            
        return final_result

    # asenkron fonksiyonu senkron bir celery task'ı içinden çalıştır
    return asyncio.run(run_evaluation_and_summary()) 