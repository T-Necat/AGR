import streamlit as st
import pandas as pd
import os
import sys
import json
import time
from typing import Dict, List, Optional
from streamlit_option_menu import option_menu
import datetime
from celery.result import AsyncResult
import asyncio

# Proje kök dizinini sisteme tanıtarak diğer modülleri import et
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.celery_app import celery_app
from src.vector_db.embedding_service import AgentEmbeddingService
from src.rag.rag_pipeline import RAGPipeline
from src.evaluation.evaluator import AgentEvaluator, EvaluationMetrics
from src.tasks import batch_evaluate_task, evaluate_and_summarize_session_task

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="AI Agent Değerlendirme Paneli",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Agent Değerlendirme Paneli")
st.markdown("""
Bu panel, kaydedilmiş ajan konuşmalarını analiz etmek ve ajanların performansını `Agent Goal'ına Uygun Davranmış mı?` belgesindeki kriterlere göre değerlendirmek için tasarlanmıştır.
""")

# --- Servisleri Başlatma ---
@st.cache_resource
def initialize_services() -> Optional[AgentEvaluator]:
    """Gerekli servisleri başlatır ve önbelleğe alır."""
    try:
        # Servisler artık ayarları config dosyasından otomatik olarak alıyor.
        embedding_service = AgentEmbeddingService()
        evaluator = AgentEvaluator()
        return evaluator
    except Exception as e:
        st.error(f"Servisler başlatılırken bir hata oluştu: {e}")
        return None

evaluator = initialize_services()
FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "feedback.csv")

# --- Geri Bildirim Fonksiyonları ---
def save_feedback(evaluation_data: dict, feedback: str):
    """Kullanıcı geri bildirimini bir CSV dosyasına kaydeder."""
    try:
        feedback_df = pd.DataFrame([{"timestamp": datetime.datetime.now(), "feedback": feedback, **evaluation_data}])
        
        # Dosya zaten varsa, başlık olmadan ekle, yoksa dosyayı oluştur
        header = not os.path.exists(FEEDBACK_FILE)
        feedback_df.to_csv(FEEDBACK_FILE, mode='a', header=header, index=False)
        st.toast(f"Geri bildiriminiz kaydedildi: {feedback}", icon="👍" if feedback == "olumlu" else "👎")
    except Exception as e:
        st.error(f"Geri bildirim kaydedilirken hata oluştu: {e}")

# --- Veri İşleme Fonksiyonları ---
@st.cache_data
def process_chat_data(chats_df: pd.DataFrame, personas_df: pd.DataFrame, tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Sohbet verilerini işleyip soru-cevap çiftleri haline getirir."""
    # Çakışmayı önlemek için 'created_at' sütunlarını birleştirmeden önce yeniden adlandır
    personas_df.rename(columns={'created_at': 'persona_created_at'}, inplace=True)
    tasks_df.rename(columns={'created_at': 'task_created_at'}, inplace=True)
    
    personas_df = personas_df.sort_values('persona_created_at').drop_duplicates('agent_id', keep='last')
    tasks_df = tasks_df.sort_values('task_created_at').drop_duplicates('agent_id', keep='last')
    
    merged_df = pd.merge(chats_df, personas_df, on='agent_id', how='left')
    merged_df = pd.merge(merged_df, tasks_df, on='agent_id', how='left')
    
    user_chats = merged_df[merged_df['type'] == 'USER'].rename({'content': 'user_query', 'created_at': 'user_time'}, axis='columns')
    assistant_chats = merged_df[merged_df['type'] == 'ASSISTANT'].rename({'content': 'agent_response', 'created_at': 'assistant_time'}, axis='columns')
    
    user_chats['chat_rank'] = user_chats.groupby('chat_id').cumcount()
    assistant_chats['chat_rank'] = assistant_chats.groupby('chat_id').cumcount()
    
    qa_df = pd.DataFrame(pd.merge(
        user_chats[user_chats['chat_rank'] == 0], # type: ignore
        assistant_chats[assistant_chats['chat_rank'] > 0], # type: ignore
        on=['chat_id', 'agent_id'],
        suffixes=('_user', '_assistant')
    ))
    
    # HATA DÜZELTMESİ: Birleştirme sonrası _user ve _assistant olarak ayrılan sütunları düzelt
    if 'persona_user' in qa_df.columns:
        qa_df['persona'] = qa_df['persona_user']
    if 'tasks_user' in qa_df.columns:
        qa_df['tasks'] = qa_df['tasks_user']

    qa_df = qa_df.sort_values('assistant_time').drop_duplicates('chat_id', keep='first')
    return qa_df.dropna(subset=['user_query', 'agent_response', 'persona', 'tasks'])

@st.cache_data
def load_default_data(data_path: str) -> pd.DataFrame:
    """Varsayılan veri dosyalarını yükler ve işler."""
    try:
        chats_df = pd.read_csv(os.path.join(data_path, "ai_agent_chat_messages_june_18_25.csv"))
        personas_df = pd.read_csv(os.path.join(data_path, "ai_agent_persona_june_18_25.csv"))
        tasks_df = pd.read_csv(os.path.join(data_path, "ai_agent_tasks_june_18_25.csv"))
        return process_chat_data(chats_df, personas_df, tasks_df)
    except FileNotFoundError as e:
        st.error(f"Veri dosyası bulunamadı: {e.filename}")
        return pd.DataFrame()

@st.cache_data
def load_and_merge_raw_data(data_path: str) -> pd.DataFrame:
    """Varsayılan veri dosyalarını yükler ve birleştirir, ancak QA formatına dönüştürmez."""
    try:
        chats_df = pd.read_csv(os.path.join(data_path, "ai_agent_chat_messages_june_18_25.csv"))
        personas_df = pd.read_csv(os.path.join(data_path, "ai_agent_persona_june_18_25.csv"))
        tasks_df = pd.read_csv(os.path.join(data_path, "ai_agent_tasks_june_18_25.csv"))
        
        personas_df.rename(columns={'created_at': 'persona_created_at'}, inplace=True)
        tasks_df.rename(columns={'created_at': 'task_created_at'}, inplace=True)
    
        personas_df = personas_df.sort_values('persona_created_at').drop_duplicates('agent_id', keep='last')
        tasks_df = tasks_df.sort_values('task_created_at').drop_duplicates('agent_id', keep='last')
        
        merged_df = pd.merge(chats_df, personas_df, on='agent_id', how='left')
        merged_df = pd.merge(merged_df, tasks_df, on='agent_id', how='left')
        
        return merged_df.dropna(subset=['content', 'persona', 'tasks'])
    except FileNotFoundError as e:
        st.error(f"Veri dosyası bulunamadı: {e.filename}")
        return pd.DataFrame()

# --- Değerlendirme Fonksiyonu ---
async def run_evaluation(eval_data: pd.Series, _evaluator: AgentEvaluator) -> Optional[EvaluationMetrics]:
    """Tek bir konuşma verisi için değerlendirmeyi çalıştırır."""
    try:
        user_query = str(eval_data['user_query'])
        agent_response = str(eval_data['agent_response'])
        agent_persona = str(eval_data['persona'])
        
        try:
            tasks_str = str(eval_data.get('tasks', '[]'))
            tasks = json.loads(tasks_str.replace("'", "\""))
            task_descriptions = [t.get('value', {}).get('about', '') for t in tasks if t.get('type') == 'talk-about']
            agent_goal = ". ".join(filter(None, task_descriptions)) or "Kullanıcıya yardımcı olmak."
        except (json.JSONDecodeError, TypeError):
            agent_goal = "Kullanıcıya yardımcı olmak."
        
        rag_context = f"Agent'ın bilgi tabanından getirdiği varsayılan kanıt: '{agent_response}'"

        return await _evaluator.evaluate_conversation(
            user_query=user_query, agent_response=agent_response,
            agent_goal=agent_goal, rag_context=rag_context,
            agent_persona=agent_persona, tool_calls=None
        )
    except Exception as e:
        st.error(f"Değerlendirme hatası: {e}")
        return None

def display_evaluation_results(evaluation_result: Optional[EvaluationMetrics]):
    """Değerlendirme sonuçlarını görselleştirir."""
    if not evaluation_result:
        st.error("Değerlendirme sonucu alınamadı.")
        return
        
    st.header("📊 Değerlendirme Sonuçları")
    # Değerlendirmenin benzersiz bir anahtarını oluşturmak için session state kullan
    if 'current_eval_result' not in st.session_state or st.session_state.current_eval_result != evaluation_result:
        st.session_state.current_eval_result = evaluation_result
        st.session_state.feedback_given = False # Yeni sonuç için geri bildirimi sıfırla

    cols = st.columns(4)
    metrics_to_show = {
        "Goal Adherence": evaluation_result.goal_adherence,
        "Answer Relevance": evaluation_result.answer_relevance,
        "Groundedness": evaluation_result.groundedness,
        "Persona Compliance": getattr(evaluation_result, 'persona_compliance', None),
        "Style & Courtesy": getattr(evaluation_result, 'style_and_courtesy', None),
        "Conciseness": getattr(evaluation_result, 'conciseness', None),
        "Knowledge Boundary": evaluation_result.knowledge_boundary_violation,
        "Security/Policy": evaluation_result.security_policy_violation,
    }
    
    col_idx = 0
    for name, metric in metrics_to_show.items():
        if metric is None: continue
        with cols[col_idx % 4]:
            delta_color = "inverse" if name in ["Knowledge Boundary", "Security/Policy"] and metric.score > 0 else "normal"
            st.metric(label=name, value=f"{metric.score:.2f}", delta_color=delta_color)
            with st.expander("Gerekçeyi Gör"):
                st.write(metric.reasoning)
        col_idx += 1
    
    # --- Geri Bildirim Bölümü ---
    if not st.session_state.get('feedback_given', False):
        st.markdown("---")
        st.subheader("Bu Değerlendirme Faydalı Oldu mu?")
        feedback_cols = st.columns(8)
        
        if feedback_cols[0].button("👍 Olumlu", key=f"positive_feedback_{id(evaluation_result)}"):
            save_feedback(evaluation_result.model_dump(), "olumlu")
            st.session_state.feedback_given = True
            st.rerun()

        if feedback_cols[1].button("👎 Olumsuz", key=f"negative_feedback_{id(evaluation_result)}"):
            save_feedback(evaluation_result.model_dump(), "olumsuz")
            st.session_state.feedback_given = True
            st.rerun()
    else:
        st.success("Bu değerlendirme için geri bildiriminiz alınmıştır. Teşekkürler!")

def display_session_results(result_data: dict):
    """Oturum değerlendirme ve özet sonuçlarını görselleştirir."""
    if not result_data:
        st.error("Değerlendirme sonucu alınamadı.")
        return

    summary = result_data.get("summary")
    evaluation_result_data = result_data.get("evaluation")

    if summary:
        st.subheader("Oturum Özeti")
        st.markdown(summary)
    
    if evaluation_result_data:
        # Pydantic modelini yeniden oluşturarak eski fonksiyonu kullanabiliriz
        evaluation_metrics = EvaluationMetrics.model_validate(evaluation_result_data)
        display_evaluation_results(evaluation_metrics)
    else:
        st.error("Değerlendirme metrikleri alınamadı.")

# --- NAVİGASYON ---
with st.sidebar:
    # Projeyi taşınabilir hale getirmek için yerel ve göreceli bir yol kullanın.
    # 'use_column_width' genellikle daha iyi kalite için genişliği optimize eder.
    st.image("src/assets/Jotform-New-Logo.png", use_container_width=True) # type: ignore
    st.title("AI Agent Değerlendirme")
    
    page = option_menu(
        menu_title=None,
        options=["Sandbox", "Toplu Değerlendirme", "Oturum Analizi"],
        icons=["beaker", "collection-fill", "chat-left-text-fill"],
        menu_icon="cast",
        default_index=0,
    )

# --- Sayfa 1: Manuel Değerlendirme (Sandbox) ---
if page == "Sandbox":
    st.header("🧪 Manuel Değerlendirme (Sandbox)")
    st.markdown("""
    Bu bölümde, belirlediğiniz bir senaryoya göre ajanın potansiyel performansını değerlendirebilirsiniz. 
    Aşağıdaki alanları doldurarak varsayımsal bir durumu test edin veya hızlı test butonuyla önceden tanımlanmış bir senaryoyu çalıştırın.
    """)

    if st.button("⚡ Hızlı Test Çalıştır (Geçici)", use_container_width=True, type="secondary"):
        if evaluator:
            with st.spinner("Hızlı test senaryosu değerlendiriliyor..."):
                test_user_query = "Jotform'un ücretsiz planında kaç form oluşturabilirim ve bu formlara kaç yanıt alabilirim?"
                test_agent_response = "Jotform'un ücretsiz planıyla 5 adede kadar form oluşturabilirsiniz. Bu formlar üzerinden aylık toplam 100 yanıt alabilirsiniz. Ayrıca 100 MB depolama alanınız olur."
                test_agent_persona = "Yardımsever, profesyonel ve çözüm odaklı bir asistansınız. Kullanıcının sorununu net bir şekilde anlayıp etkili bir çözüm sunmaya odaklanmalısınız."
                test_agent_goal = "Kullanıcının Jotform hakkındaki sorularını yanıtlamak ve onlara platformu en verimli şekilde nasıl kullanacakları konusunda rehberlik etmek."
                rag_context = f"Agent'ın bilgi tabanından getirdiği varsayılan kanıt: '{test_agent_response}'"
                
                result = asyncio.run(evaluator.evaluate_conversation(
                    user_query=test_user_query,
                    agent_response=test_agent_response,
                    agent_goal=test_agent_goal,
                    rag_context=rag_context,
                    agent_persona=test_agent_persona,
                    tool_calls=None
                ))
                st.session_state.eval_result = result
                
                with st.expander("Çalıştırılan Test Verisi", expanded=True):
                    st.text_area("Kullanıcı Sorusu", value=test_user_query, disabled=True, height=100)
                    st.text_area("Agent'ın Cevabı", value=test_agent_response, disabled=True, height=150)
                    st.text_area("Agent'ın Personası", value=test_agent_persona, disabled=True, height=150)
                    st.text_area("Agent'ın Görevi (Goal)", value=test_agent_goal, disabled=True, height=100)
        else:
            st.error("Değerlendirici servisi (Evaluator) başlatılamadı.")

    with st.form(key="sandbox_form"):
        user_query = st.text_area("👤 Kullanıcı Sorusu", height=100, placeholder="Ör: Jotform'un sunduğu farklı abonelik planları nelerdir?")
        agent_response = st.text_area("🤖 Ajanın Cevabı", height=150, placeholder="Ör: Elbette, Jotform'da Ücretsiz, Bronz, Gümüş ve Altın olmak üzere dört farklı plan bulunmaktadır. Her planın form limiti, gönderi sayısı ve depolama alanı gibi farklı özellikleri vardır. İhtiyaçlarınıza en uygun olanı seçmenize yardımcı olabilirim.")
        agent_persona = st.text_area("🎭 Ajan Personası", height=150, value="Yardımsever, profesyonel ve çözüm odaklı bir asistansınız. Kullanıcının sorununu net bir şekilde anlayıp etkili bir çözüm sunmaya odaklanmalısınız.")
        agent_goal = st.text_area("🎯 Ajanın Görevi (Goal)", height=100, value="Kullanıcının Jotform hakkındaki sorularını yanıtlamak ve onlara platformu en verimli şekilde nasıl kullanacakları konusunda rehberlik etmek.")
        
        submit_button = st.form_submit_button(label="🧪 Senaryoyu Değerlendir", use_container_width=True, type="primary")

    if submit_button:
        if not all([user_query, agent_response, agent_persona, agent_goal]):
            st.warning("Lütfen değerlendirme yapmadan önce tüm alanları doldurun.")
        elif evaluator:
            with st.spinner("Senaryo değerlendiriliyor..."):
                rag_context = f"Agent'ın bilgi tabanından getirdiği varsayılan kanıt: '{agent_response}'"
                
                result = asyncio.run(evaluator.evaluate_conversation(
                    user_query=user_query,
                    agent_response=agent_response,
                    agent_goal=agent_goal,
                    rag_context=rag_context,
                    agent_persona=agent_persona,
                    tool_calls=None
                ))
                # Sonucu session_state'e kaydet ki geri bildirim için kullanılabilsin
                st.session_state.eval_result = result
        else:
            st.error("Değerlendirici servisi (Evaluator) başlatılamadı.")

    # Sandbox formu gönderildikten sonra sonucu göster
    if 'eval_result' in st.session_state:
        display_evaluation_results(st.session_state.eval_result)

# --- Sayfa 2: Toplu Değerlendirme ---
elif page == "Toplu Değerlendirme":
    st.header("📚 Dosya Yükleyerek Toplu Değerlendirme")
    st.markdown("""
    Sohbet geçmişini içeren bir `.csv` dosyası yükleyerek tüm konuşmaları **arka planda** otomatik olarak değerlendirin.
    Bu işlem sırasında uygulamada gezinmeye devam edebilirsiniz.
    """)

    uploaded_file = st.file_uploader("Sohbet (.csv) dosyasını seçin", type="csv")

    if 'results_df' not in st.session_state:
        st.session_state.results_df = pd.DataFrame()

    if uploaded_file is not None:
        if st.button("Veriyi İşle ve Analize Hazırla", key="process_data"):
            try:
                uploaded_chats_df = pd.read_csv(uploaded_file, engine='python', on_bad_lines='warn')
                data_path = "src/data"
                personas_df = pd.read_csv(os.path.join(data_path, "ai_agent_persona_june_18_25.csv"))
                tasks_df = pd.read_csv(os.path.join(data_path, "ai_agent_tasks_june_18_25.csv"))
                
                with st.spinner("Veri işleniyor..."):
                    processed_data = process_chat_data(uploaded_chats_df, personas_df, tasks_df)
                
                st.session_state.processed_data = processed_data
                st.success(f"Yüklenen dosyadan değerlendirilmeye hazır {len(processed_data)} konuşma bulundu.")
                
            except Exception as e:
                st.error(f"Dosya işlenirken bir hata oluştu: {e}")

    if 'processed_data' in st.session_state and not st.session_state.processed_data.empty:
        processed_data = st.session_state.processed_data
        
        if st.button(f"📚 {len(processed_data)} Konuşmayı Arka Planda Değerlendir", key="eval_batch_async", use_container_width=True, type="primary"):
            batch_data_json = processed_data.to_json(orient='split')
            task = batch_evaluate_task.delay(batch_data_json)
            st.session_state['batch_task_id'] = task.id
            st.success(f"Toplu değerlendirme görevi başlatıldı! Görev ID: {task.id}")

    if 'batch_task_id' in st.session_state:
        task_id = st.session_state['batch_task_id']
        task_result = AsyncResult(task_id, app=celery_app)

        st.markdown("---")
        st.subheader("Görev İlerleme Durumu")
        
        if task_result.ready():
            if task_result.successful():
                st.success(f"Görev (ID: {task_id}) başarıyla tamamlandı!")
                results = task_result.get()
                
                if not results:
                    st.warning("Değerlendirme görevi çalıştı ancak hiçbir sonuç üretmedi.")
                else:
                    results_df = pd.DataFrame(results)
                    st.session_state.results_df = results_df # Sonuçları state'e kaydet
                
                if 'batch_task_id' in st.session_state:
                    del st.session_state['batch_task_id']
                if 'processed_data' in st.session_state:
                    del st.session_state['processed_data'] # İşlenmiş veriyi temizle
                st.rerun() # Sayfayı yeniden çalıştırarak sonuçları göster
            else:
                st.error(f"Görev (ID: {task_id}) bir hatayla sonuçlandı: {task_result.info}")
                if 'batch_task_id' in st.session_state:
                    del st.session_state['batch_task_id']
        else:
            progress_meta = task_result.info or {'current': 0, 'total': 1}
            current, total = progress_meta.get('current', 0), progress_meta.get('total', 1)
            progress_percent = (current / total) if total > 0 else 0
            st.progress(progress_percent, text=f"Değerlendiriliyor... ({current}/{total})")
            time.sleep(5)
            st.rerun()

    if not st.session_state.results_df.empty:
        results_df = st.session_state.results_df.copy()
        
        # Sadece bir kere metrik sütunlarını oluştur
        if 'Overall Score' not in results_df.columns:
            metric_names = []
            for col in results_df.columns:
                if isinstance(results_df[col].iloc[0], dict) and 'score' in results_df[col].iloc[0]:
                    metric_name = col.replace('_', ' ').title()
                    if metric_name not in metric_names:
                        metric_names.append(metric_name)
                    results_df[f'{metric_name} Score'] = results_df[col].apply(lambda x: x.get('score') if isinstance(x, dict) else None)
                    results_df[f'{metric_name} Reasoning'] = results_df[col].apply(lambda x: x.get('reasoning') if isinstance(x, dict) else None)
            
            score_cols = [f'{name} Score' for name in metric_names if 'Violation' not in name and 'Boundary' not in name]
            results_df['Overall Score'] = results_df[score_cols].mean(axis=1)
            st.session_state.results_df = results_df # Güncellenmiş df'i kaydet
            st.session_state.metric_names = metric_names
            st.session_state.score_cols = score_cols

        metric_names = st.session_state.metric_names
        score_cols = st.session_state.score_cols

        st.subheader("Filtreleme ve Sıralama")
        filter_cols = st.columns([2, 2, 3, 3])
        
        # Filtreleri uygula
        agent_ids = ['Tümü'] + sorted(list(results_df['agent_id'].unique()))
        selected_agent = filter_cols[0].selectbox("Agent ID'ye Göre Filtrele", agent_ids)
        if selected_agent != 'Tümü':
            results_df = results_df[results_df['agent_id'] == selected_agent]

        sort_by = filter_cols[1].selectbox("Sırala", ["Overall Score"] + sorted(metric_names))
        sort_ascending = filter_cols[1].toggle("Artan", False)
        sort_key = f"{sort_by} Score" if sort_by != "Overall Score" else sort_by
        results_df = results_df.sort_values(by=sort_key, ascending=sort_ascending)

        score_filter_metric = filter_cols[2].selectbox("Skor Filtre Metriği", ["Overall Score"] + sorted(metric_names))
        score_key = f"{score_filter_metric} Score" if score_filter_metric != "Overall Score" else score_filter_metric
        
        # DataFrame boş değilse devam et
        if not results_df.empty:
            min_val, max_val = float(results_df[score_key].min()), float(results_df[score_key].max())
            
            # Eğer min ve max değerleri aynıysa slider'ı devre dışı bırak
            if min_val == max_val:
                filter_cols[3].info(f"Tek skor ({min_val:.2f}) olduğu için aralık filtresi uygulanamıyor.")
            else:
                score_range = filter_cols[3].slider(f"'{score_filter_metric}' Skoruna Göre Filtrele", min_value=min_val, max_value=max_val, value=(min_val, max_val))
                results_df = results_df[results_df[score_key].between(score_range[0], score_range[1])]
        
        st.markdown("---")

        if not results_df.empty:
            st.subheader("Genel Metrikler (Filtrelenmiş)")
            score_df = results_df[score_cols]
            avg_cols = st.columns(len(score_cols))
            for i, col_name in enumerate(score_cols):
                with avg_cols[i]:
                    st.metric(label=f"Ort. {col_name.replace(' Score', '')}", value=f"{score_df[col_name].mean():.2f}")
            
            # AI Analizi
            with st.expander("🤖 AI Analizi ve Öneriler"):
                if st.button("Analiz Oluştur", key="generate_analysis"):
                    if evaluator:
                        with st.spinner("AI Analisti sonuçları inceliyor..."):
                            stats_df = results_df[score_cols]
                            stats = stats_df.agg(['mean', 'std', 'min', 'max']).to_dict()
                            stats['total_conversations'] = len(results_df)
                            
                            # `n` ve `columns` parametrelerini doğru kullan
                            low_df = results_df.nsmallest(n=3, columns='Overall Score')
                            high_df = results_df.nlargest(n=3, columns='Overall Score')

                            def format_examples(df, title):
                                formatted_str = f"--- {title} ---\n"
                                for _, r in df.iterrows():
                                    formatted_str += f"Chat ID: {r.get('chat_id', 'N/A')}\n"
                                    formatted_str += f"Overall Score: {r.get('Overall Score', 0):.2f}\n"
                                    formatted_str += f"Query: {r.get('user_query', 'N/A')}\n"
                                    formatted_str += f"Response: {r.get('agent_response', 'N/A')}\n\n"
                                return formatted_str

                            analysis = asyncio.run(evaluator.analyze_batch_results(
                                stats_json=json.dumps(stats, indent=2),
                                low_score_examples_str=format_examples(low_df, "Low-Scoring Conversations"),
                                high_score_examples_str=format_examples(high_df, "High-Scoring Conversations")
                            ))
                            st.session_state.ai_analysis = analysis
                    else:
                        st.warning("Analiz oluşturmak için Değerlendirici servisi (Evaluator) başlatılamadı.")

                if 'ai_analysis' in st.session_state:
                    st.markdown(st.session_state.ai_analysis)

            st.markdown("---")
            st.subheader(f"Değerlendirme Sonuçları ({len(results_df)} adet)")

            # Paginasyon
            if 'page' not in st.session_state: st.session_state.page = 0
            items_per_page = 10
            start_idx = st.session_state.page * items_per_page
            end_idx = start_idx + items_per_page
            paginated_df = results_df.iloc[start_idx:end_idx]

            for _, row in paginated_df.iterrows():
                st.markdown(f"**Chat ID:** `{row.get('chat_id', 'N/A')}` | **Genel Skor:** `{row.get('Overall Score', 0):.2f}`")
                with st.expander("Detayları ve Gerekçeleri Gör"):
                     st.markdown(f"**Kullanıcı Sorusu:** *{row.get('user_query', 'N/A')}*")
                     st.markdown(f"**Agent Cevabı:** *{row.get('agent_response', 'N/A')}*")
                     st.divider()
                     metric_cols = st.columns(len(metric_names))
                     for i, name in enumerate(metric_names):
                         with metric_cols[i]:
                             score = row.get(f"{name} Score")
                             is_violation = "Violation" in name or "Boundary" in name
                             # Hata düzeltmesi: score'un None olup olmadığını kontrol et
                             delta_color = "inverse" if is_violation and score is not None and score > 0 else "normal"
                             st.metric(label=name, value=f"{score:.2f}" if score is not None else "N/A", delta_color=delta_color)
                     
                     st.divider()
                     st.markdown("**Tüm Metrik Gerekçeleri:**")
                     for name in metric_names:
                         reasoning = row.get(f"{name} Reasoning", "Gerekçe bulunamadı.")
                         st.markdown(f"- **{name}:** {reasoning}")
                
            page_cols = st.columns([1, 1, 1])
            if st.session_state.page > 0:
                if page_cols[0].button("⬅️ Önceki Sayfa", use_container_width=True):
                    st.session_state.page -= 1
                    st.rerun()
            if end_idx < len(results_df):
                if page_cols[2].button("Sonraki Sayfa ➡️", use_container_width=True):
                    st.session_state.page += 1
                    st.rerun()
        else:
            st.info("Filtre kriterlerine uygun sonuç bulunamadı.")

# --- Sayfa 3: Oturum Değerlendirme ---
elif page == "Oturum Analizi":
    st.header("💬 Sohbet Oturumu Seçimi ve Analizi")
    data_path = "src/data"
    session_raw_data = load_and_merge_raw_data(data_path)

    if not session_raw_data.empty:
        chat_ids = session_raw_data['chat_id'].unique()
        
        # Kullanıcı yeni bir oturum seçtiğinde eski sonuçları ve task'ı temizle
        def on_chat_id_change():
            if 'session_task_id' in st.session_state:
                del st.session_state['session_task_id']

        selected_chat_id = st.selectbox(
            "Değerlendirilecek Oturumu Seçin (Chat ID):", 
            chat_ids,
            key="chat_id_selector",
            on_change=on_chat_id_change
        )

        if selected_chat_id:
            session_df = session_raw_data[session_raw_data['chat_id'] == selected_chat_id].copy() # type: ignore
            
            st.subheader(f"Oturum Dökümü: `{selected_chat_id}`")
            with st.container(height=400):
                for _, row in session_df.sort_values(by='created_at').iterrows(): # type: ignore
                    user_type = str(row.get('type', 'assistant')).upper()
                    with st.chat_message(name="user" if user_type == 'USER' else "assistant"):
                        st.markdown(str(row.get('content', '')))
            
            with st.expander("Agent Görev ve Persona Detayları"):
                if not session_df.empty and 'persona' in session_df.columns:
                    st.code(str(session_df['persona'].iloc[0]), language=None) # type: ignore

            if st.button("🚀 Bu Oturumu Arka Planda Değerlendir", key="eval_session_async", use_container_width=True, type="primary"):
                if not session_df.empty:
                    session_data_json = session_df.to_json(orient='split')
                    task = evaluate_and_summarize_session_task.delay(session_data_json)
                    st.session_state['session_task_id'] = task.id
                    st.success(f"Oturum değerlendirme görevi başlatıldı! Görev ID: {task.id}")
                    st.info("İlerleme durumu aşağıda gösterilecektir. Bu sırada başka sayfalara gidebilirsiniz.")
                else:
                    st.warning("Değerlendirilecek oturum verisi bulunamadı.")

            # --- Görev Durumunu Kontrol Etme ve Sonuçları Gösterme ---
            if 'session_task_id' in st.session_state:
                task_id = st.session_state['session_task_id']
                task_result = AsyncResult(task_id, app=celery_app)

                st.markdown("---")
                
                if task_result.ready():
                    if task_result.successful():
                        st.success(f"Oturum değerlendirme görevi (ID: {task_id}) başarıyla tamamlandı!")
                        result_data = task_result.get()
                        
                        if result_data:
                            if result_data.get("error"):
                                st.error(f"Değerlendirme hatası: {result_data.get('error')}")
                            else:
                                display_session_results(result_data)
                        else:
                            st.error("Görevden bir sonuç alınamadı.")

                        # Sonucu gösterdikten sonra task id'yi temizle
                        del st.session_state['session_task_id']
                    else:
                        st.error(f"Görev (ID: {task_id}) bir hatayla sonuçlandı: {task_result.info}")
                        del st.session_state['session_task_id']
                else:
                    # Görev hala çalışıyor, ilerlemeyi göster
                    progress_meta = task_result.info or {'current': 0, 'total': 1}
                    current = progress_meta.get('current', 0)
                    total = progress_meta.get('total', 1)
                    
                    progress_percent = (current / total) if total > 0 else 0
                    st.progress(progress_percent, text=f"Değerlendiriliyor... ({current}/{total})")
                    
                    # Sayfanın periyodik olarak yenilenmesini tetikle
                    time.sleep(5)
                    st.rerun()
                
    else:
        st.error("Varsayılan veri yüklenemedi.") 