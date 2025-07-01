# Proje Teknik Dokümantasyonu

Bu belge, AI Agent Değerlendirme & Tavsiye Sistemi'nin teknik yapısını, bileşenlerini ve veri akışını açıklamaktadır.

## 1. Genel Bakış

Proje, iki ana işlevsellik üzerine kurulmuştur:
1.  **AI Agent Tavsiye API'si:** Kullanıcı sorgularını analiz ederek en uygun AI agent'ını öneren bir FastAPI sunucusu.
2.  **AI Agent Değerlendirme Paneli:** Ajanların konuşma performansını, belirlenen metrikler çerçevesinde (Amaca Uygunluk, Persona Tutarlılığı, Üslup vb.) analiz eden interaktif bir Streamlit web arayüzü.

Sistem üç ana bölümden oluşur:
- **Veri İşleme (ETL):** Ham veriyi (CSV) temizler ve RAG için vektör veritabanına hazırlar.
- **Çekirdek Modüller (Core Modules):** Değerlendirme motoru, RAG pipeline'ı ve API mantığını içerir.
- **Arayüzler (Interfaces):** Değerlendirme sürecini yönetmek ve sonuçları görselleştirmek için bir Streamlit uygulaması ve tavsiye sunmak için bir FastAPI uygulaması.

## 2. Proje Yapısı

```
jotform-agent-insight-mvp/
└── src/
    ├── api/                  # Agent tavsiye servislerini dışarıya açan API (FastAPI).
    │   └── main.py
    │
    ├── data/                 # Ham veri dosyaları (CSV) ve kullanıcı geri bildirimleri.
    │   ├── agent_knowledge_base.csv
    │   └── feedback.csv
    │
    ├── etl/                  # Ham veriyi işleyen script'ler.
    │   └── data_processor.py
    │
    ├── evaluation/           # Değerlendirme mantığını içeren çekirdek modül.
    │   └── evaluator.py
    │
    ├── rag/                  # Retrieval-Augmented Generation (RAG) mantığı.
    │   └── rag_pipeline.py
    │
    ├── vector_db/            # Vektör veritabanı ve gömme servisleri.
    │   └── embedding_service.py
    │
    ├── evaluation_app.py     # Streamlit ile oluşturulmuş ana web uygulaması.
    │
    ├── rebuild_database.py   # Veritabanını yeniden oluşturan ana script.
    │
    └── requirements.txt      # Gerekli Python kütüphaneleri.
```
*Not: `chroma_db_*` gibi veritabanı klasörleri ve `.env` gibi ortam değişkeni dosyaları `.gitignore` ile versiyon kontrolü dışında tutulmaktadır.*

## 3. Ana Bileşenlerin Detayları

### a. `evaluation_app.py`
- **Teknoloji:** Streamlit
- **Amaç:** Projenin görsel arayüzünü oluşturur. Kullanıcıların değerlendirme süreçlerini yönetmesini, sonuçları görmesini ve geri bildirimde bulunmasını sağlar.
- **İşlevler:**
    - **Sandbox (Manuel Değerlendirme):** Kullanıcıların manuel olarak senaryolar girmesine ve anında değerlendirme sonuçları almasına olanak tanır.
    - **Toplu Değerlendirme:** Kullanıcıların bir CSV dosyası yükleyerek çok sayıda konuşmayı tek seferde değerlendirmesini sağlar.
    - **Oturum Değerlendirme:** Belirli bir konuşma oturumunu seçerek bütünsel olarak değerlendirme imkanı sunar.
    - **Kullanıcı Geri Bildirim Döngüsü:** Her LLM değerlendirmesinin altında, bir insanın (analistin) bu değerlendirmeyi onaylaması (👍) veya reddetmesi (👎) için bir mekanizma bulunur. Bu geri bildirimler, ileride modeli eğitmek amacıyla `src/data/feedback.csv` dosyasına kaydedilir.
- **Performans Optimizasyonları:**
    - `@st.cache_data` ve `@st.cache_resource` dekoratörleri, büyük veri setlerinin ve servislerin tekrar tekrar yüklenmesini önleyerek uygulamada yüksek performans sağlar.

### b. `evaluation/evaluator.py`
- **Teknoloji:** Pydantic, OpenAI API, Instructor
- **Amaç:** Değerlendirmenin beyin fonksiyonunu görür. Bir konuşmayı veya oturumu alıp, belirlenmiş metriklere göre analiz eder.
- **Metrikler:** LLM, agent yanıtını aşağıdaki ana kriterlere göre puanlar:
    - `goal_adherence`: Göreve sadakat.
    - `groundedness`: Sağlanan bilgiye dayalı olma.
    - `answer_relevance`: Cevabın alaka düzeyi.
    - `persona_compliance`: Tanımlanan personele uyum.
    - `style_and_courtesy`: Üslup ve nezaket.
    - `conciseness`: Cevabın öz ve kısa olması.
    - `security_policy_violation`: Toksik, zararlı veya hassas bilgi içerip içermemesi.
    - `knowledge_boundary_violation`: Tanımlı bilgi sınırlarını aşıp aşmaması.
- **Teknik Detaylar:**
    - `AgentEvaluator` sınıfı, OpenAI'nin dil modellerine özel olarak hazırlanmış bir "prompt" gönderir.
    - `instructor` kütüphanesi sayesinde, LLM'den gelen yanıt, `EvaluationMetrics` Pydantic modeli kullanılarak doğrudan yapılandırılmış bir JSON olarak alınır. Bu, sonuçların tutarlı ve güvenilir olmasını sağlar.

### c. `api/main.py`
- **Teknoloji:** FastAPI
- **Amaç:** Kullanıcı sorgusuna en uygun agent'ı tavsiye eden bir API sunucusu sağlar.
- **İşlevler:**
    - `/recommend` endpoint'i, bir kullanıcı sorgusu (`query`) alır.
    - RAG pipeline'ını kullanarak bilgi tabanında arama yapar ve en uygun agent'ı bularak yanıt döner.

## 4. Veri Akışı

Aşağıdaki şema, Değerlendirme Paneli'ndeki veri akışını özetlemektedir:

```mermaid
graph TD
    subgraph "1. Veri Hazırlama (ETL)"
        A[CSV Dosyaları<br/>src/data/] --> B(ETL Süreçleri<br/>`rebuild_database.py`);
        B --> C{Vektör Veritabanı<br/>(ChromaDB)};
    end

    subgraph "2. Değerlendirme ve Geri Bildirim"
        E[evaluation_app.py] --> F{Değerlendirme Arayüzü};
        A -- Ham Konuşma Verisi --> H(Değerlendirici<br/>`evaluation/evaluator.py`);
        F -- Kullanıcı Girdisi/Seçimi --> H;
        H -- Sonuçları Hesaplar --> I[📊 Değerlendirme Sonuçları];
        I --> F;
        F -- Geri Bildirim --> J(👍/👎 Butonları);
        J --> K[feedback.csv<br/>src/data/];
    end
```

1.  **ETL Aşaması:** `rebuild_database.py` çalıştırıldığında, CSV'lerdeki veriler işlenir ve RAG için ChromaDB'ye yüklenir.
2.  **Değerlendirme Aşaması:** Kullanıcı, Streamlit arayüzü üzerinden bir değerlendirme başlatır. `AgentEvaluator`, LLM'i kullanarak değerlendirmeyi yapar ve sonuçları arayüzde gösterir.
3.  **Geri Bildirim Aşaması:** Kullanıcı, sunulan değerlendirme sonucuna 👍 veya 👎 ile geri bildirimde bulunur. Bu geri bildirim, değerlendirme verileriyle birlikte `feedback.csv` dosyasına kaydedilir.

## 5. Kurulum ve Çalıştırma

1.  **Bağımlılıkları Yükleme:**
    ```bash
    pip install -r src/requirements.txt
    ```

2.  **API Anahtarlarını Ayarlama:**
    `src/env_example.txt` dosyasını `src/.env` olarak kopyalayın ve içine kendi OpenAI API anahtarınızı girin.
    ```
    OPENAI_API_KEY="sk-..."
    ```

3.  **Veritabanını Oluşturma (İsteğe Bağlı):**
    ```bash
    python src/rebuild_database.py
    ```

4.  **Uygulamaları Çalıştırma:**
    - **Değerlendirme Paneli:**
      ```bash
      streamlit run src/evaluation_app.py
      ```
    - **Tavsiye API'si:**
      ```bash
      python src/api/main.py
      ``` 