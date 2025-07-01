# Proje Teknik Dokümantasyonu

Bu belge, AI Agent Değerlendirme Sistemi'nin teknik yapısını, bileşenlerini ve veri akışını açıklamaktadır.

## 1. Genel Bakış

Projenin temel amacı, yapay zeka ajanlarının kullanıcılarla olan konuşmalarını analiz ederek performanslarını belirli metrikler (Amaca Uygunluk, Persona Tutarlılığı, Bilgi Sınırları vb.) çerçevesinde değerlendirmektir. Sistem, kaydedilmiş konuşma verilerini işler, bir değerlendirme modelinden geçirir ve sonuçları interaktif bir web arayüzü üzerinden sunar.

Sistem üç ana bölümden oluşur:
- **Veri İşleme (ETL):** Ham veriyi (CSV) temizler ve vektör veritabanına hazırlar.
- **Değerlendirme Motoru (Evaluation Engine):** LLM kullanarak konuşmaları analiz eder ve puanlar.
- **Web Arayüzü (Streamlit App):** Değerlendirme sürecini yönetmek ve sonuçları görselleştirmek için kullanılır.

## 2. Proje Yapısı

```
agent_recommendation_system_final/
│
├── api/                  # Değerlendirme servislerini dışarıya açan API (FastAPI).
│   └── main.py
│
├── chroma_db_openai/     # Gömme (embedding) vektörlerinin saklandığı veritabanı.
│
├── etl/                  # Ham veriyi işleyen, temizleyen ve dönüştüren script'ler.
│   ├── data_processor.py
│   └── clean_data_processor.py
│
├── evaluation/           # Değerlendirme mantığını içeren çekirdek modül.
│   └── evaluator.py
│
├── rag/                  # Retrieval-Augmented Generation (RAG) mantığını barındırır.
│   └── rag_pipeline.py
│
├── vector_db/            # Vektör veritabanı ve gömme servisleri ile ilgili kodlar.
│   └── embedding_service.py
│
├── evaluation_app.py     # Streamlit ile oluşturulmuş ana web uygulaması.
│
├── rebuild_database.py   # Veritabanını yeniden oluşturan ana script.
│
└── requirements.txt      # Gerekli Python kütüphaneleri.
```

## 3. Ana Bileşenlerin Detayları

### a. `evaluation_app.py`
- **Teknoloji:** Streamlit
- **Amaç:** Projenin kullanıcı arayüzünü oluşturur. Kullanıcıların değerlendirme süreçlerini yönetmesini ve sonuçları görmesini sağlar.
- **İşlevler:**
    - **Sandbox (Manuel Değerlendirme):** Kullanıcıların manuel olarak senaryo (kullanıcı sorusu, ajan cevabı, persona, hedef) girmesine ve anında değerlendirme sonuçları almasına olanak tanır. Bu, hipotetik durumları test etmek için idealdir.
    - **Toplu Değerlendirme:** Kullanıcıların bir CSV dosyası yükleyerek çok sayıda konuşmayı tek seferde değerlendirmesini sağlar. Sonuçlar, genel istatistikler ve detaylı bir tablo olarak sunulur.
    - **Oturum Değerlendirme:** Veri setinden belirli bir konuşma oturumunu seçerek, baştan sona tüm diyaloğu görüntüleme ve bütünsel olarak değerlendirme imkanı sunar.
- **Performans Optimizasyonları:**
    - **Kullanıcı Bekleme Yönetimi:** LLM API çağrıları gibi zaman alan işlemler sırasında arayüzün donmasını engellemek ve kullanıcıya sürecin devam ettiğini bildirmek için `st.spinner` ve `st.progress` gibi görsel bileşenler kullanılır.
    - **Önbellekleme (Caching):** `@st.cache_data` ve `@st.cache_resource` dekoratörleri, büyük veri setlerinin (örn: CSV dosyaları) ve servislerin (örn: `AgentEvaluator`) tekrar tekrar yüklenmesini önler. Veri ve servisler hafızada tutularak uygulama genelinde yüksek performans sağlanır.

### b. `evaluation/evaluator.py`
- **Teknoloji:** Pydantic, OpenAI API
- **Amaç:** Değerlendirmenin beyin fonksiyonunu görür. Bir konuşmayı veya oturumu alıp, belirlenmiş metriklere göre analiz eder.
- **Teknik Detaylar:**
    - `AgentEvaluator` sınıfı, `evaluate_conversation` ve `evaluate_session` metodlarını içerir.
    - Bu metodlar, OpenAI'nin `gpt-4` veya benzeri bir modeline özel olarak hazırlanmış bir "prompt" gönderir. Bu prompt, konuşma metnini, ajan hedefini, personasını ve değerlendirme kriterlerini içerir.
    - LLM'den gelen yanıt, yapılandırılmış bir formatta (JSON) istenir ve `EvaluationMetrics` gibi Pydantic modelleri kullanılarak parse edilir. Bu, sonuçların tutarlı ve güvenilir olmasını sağlar.

### c. `rag/rag_pipeline.py` & `vector_db/embedding_service.py`
- **Teknoloji:** ChromaDB, OpenAI Embeddings (`text-embedding-3-small`)
- **Amaç:** Bu iki modül, RAG sistemini oluşturur.
- **İşlevler:**
    - `embedding_service.py`: Metin verilerini (ajanın bilgi tabanı) alır ve onları sayısal vektörlere (embeddings) dönüştürür. Bu vektörler, metnin anlamsal içeriğini temsil eder.
    - `rag_pipeline.py`: Bir kullanıcı sorusu geldiğinde, bu soruyu vektöre çevirir ve ChromaDB'de en anlamsal olarak en yakın bilgi parçacıklarını (context) bulur. Bu bulunan bağlam, ajanın daha doğru ve temellendirilmiş cevaplar vermesi için kullanılır.
    - **Not:** `evaluation_app` içinde RAG, doğrudan bir bağlam araması yapmak yerine, ajanın verdiği cevabın "groundedness" (temellendirme) metriğini ölçmek için simüle edilir.

### d. `etl/` & `rebuild_database.py`
- **Amaç:** Ham veri kaynaklarını (CSV) işleyerek RAG sisteminin kullanabileceği temiz bir bilgi tabanı oluşturur.
- **İşlevler:**
    - `data_processor.py`: CSV dosyalarını okur, birleştirir ve gerekli ön işlemleri yapar.
    - `rebuild_database.py`: ETL sürecini başlatan ana betiktir. `data_processor`'ı kullanarak veriyi alır, `embedding_service` ile vektörlere dönüştürür ve ChromaDB'ye kaydeder.

## 4. Veri Akışı

Aşağıdaki şema, verinin sistemdeki yolculuğunu özetlemektedir:

```mermaid
graph TD
    subgraph "1. Veri Hazırlama (ETL)"
        A[CSV Dosyaları<br/>(Konuşmalar, Personalar, Görevler)] --> B(ETL Süreçleri<br/>`rebuild_database.py`);
        B --> C{Vektör Veritabanı<br/>(ChromaDB)};
        D(Gömme Servisi<br/>`vector_db/embedding_service.py`) --> C;
    end

    subgraph "2. Değerlendirme Uygulaması (Streamlit)"
        E[evaluation_app.py] --> F{Değerlendirme Arayüzü};
        A -- Ham Konuşma Verisi --> H(Değerlendirici<br/>`evaluation/evaluator.py`);
        F -- Kullanıcı Girdisi/Seçimi --> H;
        H -- Sonuçları Hesaplar --> I[📊 Değerlendirme Sonuçları];
        I --> F;
    end
```

1.  **ETL Aşaması:** `rebuild_database.py` çalıştırıldığında, CSV'lerdeki veriler işlenir, `embedding_service` kullanılarak vektörlere çevrilir ve ChromaDB'ye yüklenir. Bu genellikle tek seferlik veya periyodik bir işlemdir.
2.  **Değerlendirme Aşaması:**
    - Kullanıcı `evaluation_app.py` arayüzünü açar.
    - Bir değerlendirme türü seçer (Sandbox, Toplu, Oturum).
    - Uygulama, ilgili konuşma verilerini (CSV'den veya kullanıcı girdisinden) alır.
    - Bu veriler, `AgentEvaluator`'a gönderilir.
    - `AgentEvaluator`, LLM'i kullanarak değerlendirmeyi yapar ve yapılandırılmış metrikleri (puan ve gerekçe) döndürür.
    - Sonuçlar, arayüzde kullanıcıya gösterilir.

## 5. Kurulum ve Geliştirme

1.  **Bağımlılıkları Yükleme:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **API Anahtarlarını Ayarlama:**
    Proje, OpenAI gibi servisler için API anahtarlarına ihtiyaç duyar. Bu anahtarları içeren bir `.env` dosyası oluşturun (`env_example.txt` dosyasını kopyalayarak).
    ```
    OPENAI_API_KEY="sk-..."
    ```

3.  **Veritabanını Oluşturma (İsteğe Bağlı):**
    Eğer bilgi tabanını yeniden oluşturmak isterseniz:
    ```bash
    python rebuild_database.py
    ```

4.  **Değerlendirme Uygulamasını Çalıştırma:**
    ```bash
    streamlit run "agent_recommendation_system_final copy/evaluation_app.py"
    ``` 