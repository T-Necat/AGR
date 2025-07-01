import streamlit as st
import pandas as pd
import os
import sys
import json
from typing import Dict, List, Optional
from streamlit_option_menu import option_menu

# Proje kök dizinini sisteme tanıtarak diğer modülleri import et
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.vector_db.embedding_service import AgentEmbeddingService
from src.rag.rag_pipeline import RAGPipeline
from src.evaluation.evaluator import AgentEvaluator, EvaluationMetrics

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
        project_root = "src"
        db_path = os.path.join(project_root, "chroma_db_openai")
        
        embedding_service = AgentEmbeddingService(persist_directory=db_path)
        # Not: RAG Pipeline'ı tam olarak kullanmıyoruz, çünkü bağlam sohbet geçmişinden geliyor.
        # Ancak değerlendirici için bir RAG context'i simüle etmemiz gerekebilir.
        # rag_pipeline = RAGPipeline(embedding_service=embedding_service) 
        evaluator = AgentEvaluator()
        return evaluator
    except Exception as e:
        st.error(f"Servisler başlatılırken bir hata oluştu: {e}")
        return None

evaluator = initialize_services()

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
    
    user_chats = merged_df[merged_df['type'] == 'USER'].rename(columns={'content': 'user_query', 'created_at': 'user_time'})
    assistant_chats = merged_df[merged_df['type'] == 'ASSISTANT'].rename(columns={'content': 'agent_response', 'created_at': 'assistant_time'})
    
    user_chats['chat_rank'] = user_chats.groupby('chat_id').cumcount()
    assistant_chats['chat_rank'] = assistant_chats.groupby('chat_id').cumcount()
    
    qa_df = pd.merge(
        user_chats[user_chats['chat_rank'] == 0], 
        assistant_chats[assistant_chats['chat_rank'] > 0],
        on=['chat_id', 'agent_id'],
        suffixes=('_user', '_assistant')
    )
    
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

# --- Değerlendirme Fonksiyonu ---
def run_evaluation(eval_data: pd.Series, _evaluator: AgentEvaluator) -> Optional[EvaluationMetrics]:
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

        return _evaluator.evaluate_conversation(
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

def run_session_evaluation(session_df: pd.DataFrame, _evaluator: AgentEvaluator) -> Optional[EvaluationMetrics]:
    """Tüm bir oturumu değerlendirir."""
    try:
        full_conversation = []
        for _, row in session_df.sort_values('created_at').iterrows():
            full_conversation.append({"role": str(row['type']).lower(), "content": str(row['content'])})
        
        agent_persona = session_df['persona'].iloc[0]
        try:
            tasks_str = str(session_df['tasks'].iloc[0])
            tasks = json.loads(tasks_str.replace("'", "\""))
            task_descriptions = [t.get('value', {}).get('about', '') for t in tasks if t.get('type') == 'talk-about']
            agent_goal = ". ".join(filter(None, task_descriptions)) or "Kullanıcıya yardımcı olmak."
        except (json.JSONDecodeError, TypeError):
            agent_goal = "Kullanıcıya yardımcı olmak."

        return _evaluator.evaluate_session(full_conversation, agent_goal, str(agent_persona))
    except Exception as e:
        st.error(f"Oturum değerlendirme hatası: {e}")
        return None

# --- NAVİGASYON ---
with st.sidebar:
    # Projeyi taşınabilir hale getirmek için yerel ve göreceli bir yol kullanın.
    # 'use_column_width' genellikle daha iyi kalite için genişliği optimize eder.
    st.image("src/assets/Jotform-New-Logo.png", use_container_width='auto')
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
    Aşağıdaki alanları doldurarak varsayımsal bir durumu test edin.
    """)

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
                
                result = evaluator.evaluate_conversation(
                    user_query=user_query,
                    agent_response=agent_response,
                    agent_goal=agent_goal,
                    rag_context=rag_context,
                    agent_persona=agent_persona,
                    tool_calls=None
                )
                display_evaluation_results(result)
        else:
            st.error("Değerlendirici servisi (Evaluator) başlatılamadı.")

# --- Sayfa 2: Toplu Değerlendirme ---
elif page == "Toplu Değerlendirme":
    st.header("📚 Dosya Yükleyerek Toplu Değerlendirme")
    st.markdown("""
    Sohbet geçmişini içeren bir `.csv` dosyası yükleyerek tüm konuşmaları otomatik olarak değerlendirin.
    **Not:** Yükleyeceğiniz dosyanın, `ai_agent_chat_messages_june_18_25.csv` ile aynı formatta olması beklenmektedir.
    """)

    uploaded_file = st.file_uploader("Sohbet (.csv) dosyasını seçin", type="csv")

    if uploaded_file is not None:
        try:
            # Yüklenen dosyadan bir DataFrame oluştur
            uploaded_chats_df = pd.read_csv(uploaded_file)
            st.success(f"`{uploaded_file.name}` dosyası başarıyla yüklendi ve {len(uploaded_chats_df)} satır okundu.")
            
            # Bu ajanların persona ve task verilerini de varsayılan dosyalardan alalım
            data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            personas_df = pd.read_csv(os.path.join(data_path, "ai_agent_persona_june_18_25.csv"))
            tasks_df = pd.read_csv(os.path.join(data_path, "ai_agent_tasks_june_18_25.csv"))

            batch_data = process_chat_data(uploaded_chats_df, personas_df, tasks_df)

            if st.button(f"📚 {len(batch_data)} Konuşmayı Toplu Değerlendir", key="eval_batch", use_container_width=True, type="primary"):
                if evaluator and not batch_data.empty:
                    results = []
                    progress_bar = st.progress(0, text="Değerlendirme başladı...")
                    
                    for i, (_, row) in enumerate(batch_data.iterrows()):
                        result = run_evaluation(row, evaluator)
                        if result:
                            results.append(result.model_dump())
                        progress_bar.progress((i + 1) / len(batch_data), text=f"Konuşma {i+1}/{len(batch_data)} değerlendiriliyor...")
                    
                    progress_bar.empty()
                    st.success("Toplu değerlendirme tamamlandı!")

                    results_df = pd.DataFrame(results)
                    
                    # Sonuçları metrik sütunlarına ayır
                    for metric in ["goal_adherence", "answer_relevance", "groundedness", "persona_compliance", "style_and_courtesy", "conciseness", "knowledge_boundary_violation", "security_policy_violation"]:
                        if metric in results_df.columns:
                            results_df[f'{metric}_score'] = results_df[metric].apply(lambda x: x['score'] if isinstance(x, dict) else None)
                            results_df[f'{metric}_reasoning'] = results_df[metric].apply(lambda x: x['reasoning'] if isinstance(x, dict) else None)

                    # Genel istatistikleri göster
                    st.subheader("Genel Metrikler")
                    avg_cols = st.columns(4)
                    avg_cols[0].metric("Toplam Konuşma", len(results_df))
                    avg_cols[1].metric("Ort. Groundedness", f"{results_df['groundedness_score'].mean():.2f}")
                    avg_cols[2].metric("Ort. Relevance", f"{results_df['answer_relevance_score'].mean():.2f}")
                    avg_cols[3].metric("Ort. Style", f"{results_df['style_and_courtesy_score'].mean():.2f}")


                    # Detaylı sonuçları göster
                    with st.expander("Tüm Değerlendirme Sonuçlarını Gör"):
                        display_cols = ['chat_id', 'user_query', 'agent_response', 'goal_adherence_score', 'groundedness_score', 'answer_relevance_score']
                        # Orijinal veriden sütunları ekle
                        display_df = batch_data[['chat_id', 'user_query', 'agent_response']].reset_index(drop=True)
                        scores_df = results_df[[col for col in results_df.columns if '_score' in col]].reset_index(drop=True)
                        full_display_df = pd.concat([display_df, scores_df], axis=1)
                        
                        st.dataframe(full_display_df)

                elif batch_data.empty:
                    st.warning("Yüklenen dosyadan işlenecek geçerli bir konuşma bulunamadı.")
                else:
                    st.error("Değerlendirici servisi (Evaluator) başlatılamadı.")

        except Exception as e:
            st.error(f"Dosya işlenirken bir hata oluştu: {e}") 

# --- Sayfa 3: Oturum Değerlendirme ---
elif page == "Oturum Analizi":
    st.header("💬 Sohbet Oturumu Seçimi ve Analizi")
    data_path = "src/data"
    session_raw_data = load_and_merge_raw_data(data_path)

    if not session_raw_data.empty:
        chat_ids = session_raw_data['chat_id'].unique()
        
        # Kullanıcı yeni bir oturum seçtiğinde eski sonuçları temizlemek için bir callback
        def on_chat_id_change():
            if 'session_eval_result' in st.session_state:
                del st.session_state['session_eval_result']

        selected_chat_id = st.selectbox(
            "Değerlendirilecek Oturumu Seçin (Chat ID):", 
            chat_ids,
            key="chat_id_selector",
            on_change=on_chat_id_change
        )

        if selected_chat_id:
            session_df = session_raw_data[session_raw_data['chat_id'] == selected_chat_id].copy()
            
            st.subheader(f"Oturum Dökümü: `{selected_chat_id}`")
            with st.container(height=400):
                for _, row in session_df.sort_values('created_at').iterrows():
                    user_type = str(row.get('type', 'assistant')).upper()
                    with st.chat_message(name="user" if user_type == 'USER' else "assistant"):
                        st.markdown(str(row.get('content', '')))
            
            with st.expander("Agent Görev ve Persona Detayları"):
                if not session_df.empty and 'persona' in session_df.columns:
                    st.code(str(session_df['persona'].iloc[0]), language=None)

            if st.button("🚀 Bu Oturumu Değerlendir", key="eval_session", use_container_width=True, type="primary"):
                if evaluator and not session_df.empty:
                    with st.spinner("Oturum değerlendiriliyor..."):
                        result = run_session_evaluation(session_df, evaluator)
                        # Değerlendirme sonucunu session_state'e kaydet
                        st.session_state['session_eval_result'] = result
                elif session_df.empty:
                    st.warning("Değerlendirilecek oturum verisi bulunamadı.")
                else:
                    st.error("Değerlendirici servisi (Evaluator) başlatılamadı.")

            # Eğer session_state'de bir sonuç varsa, onu göster
            if 'session_eval_result' in st.session_state:
                display_evaluation_results(st.session_state['session_eval_result'])
                
    else:
        st.error("Varsayılan veri yüklenemedi.") 