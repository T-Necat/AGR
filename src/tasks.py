import pandas as pd
import json
import time
from celery import Task
from .celery_app import celery_app
from .evaluation.evaluator import AgentEvaluator
from typing import Optional, List, Dict

def _run_single_evaluation(eval_data: dict, evaluator: AgentEvaluator) -> Optional[dict]:
    """
    Tek bir satır veri için değerlendirmeyi çalıştıran yardımcı fonksiyon.
    Hata durumunda None döner.
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

        result = evaluator.evaluate_conversation(
            user_query=user_query, agent_response=agent_response,
            agent_goal=agent_goal, rag_context=rag_context,
            agent_persona=agent_persona, tool_calls=None
        )
        # Celery'ye gönderilebilmesi için Pydantic modelini dict'e çeviriyoruz.
        return result.model_dump() if result else None
    except Exception:
        # Hata durumunda görevin çökmemesi için None dönüyoruz.
        return None

@celery_app.task(bind=True)
def batch_evaluate_task(self: Task, batch_data_json: str) -> List[Dict]:
    """
    Celery arka plan görevi. Bir grup konuşmayı değerlendirir.
    Veriyi JSON formatında alır çünkü Celery görevlerine karmaşık nesneler (DataFrame) doğrudan gönderilemez.
    """
    evaluator = AgentEvaluator()
    try:
        batch_data = pd.read_json(batch_data_json, orient='split')
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return []

    total_rows = len(batch_data)
    results = []

    for i, (_, row) in enumerate(batch_data.iterrows()):
        result = _run_single_evaluation(row.to_dict(), evaluator)
        if result:
            results.append(result)
        
        # Streamlit arayüzüne ilerleme durumunu bildirmek için görevin durumunu güncelle.
        self.update_state(state='PROGRESS', meta={'current': i + 1, 'total': total_rows})
        # API'yi aşırı yüklememek için küçük bir bekleme ekleyebiliriz.
        time.sleep(0.1)

    return results 