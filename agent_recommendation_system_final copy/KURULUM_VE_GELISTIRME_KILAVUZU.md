# AI Agent Tavsiye Sistemi (OpenAI Mimarisi): Kurulum ve Geliştirme Kılavuzu

Bu doküman, RAG tabanlı AI Agent tavsiye sisteminin **tamamen OpenAI API'leri üzerine kurulu** versiyonunun nasıl kurulacağını, çalıştırılacağını ve geliştirme sürecindeki önemli noktaları açıklamaktadır.

---

## 🚀 Projeye Genel Bakış

**Amaç:** Kullanıcı sorgularını analiz ederek, bu sorgulara en uygun AI agent'ını önermek.
**Teknoloji:** Proje, hem **vektör oluşturma (embedding)** hem de **akıl yürütme (generation)** aşamaları için OpenAI API'lerini kullanır. Veritabanı olarak ChromaDB kullanılmaktadır.

---

## 📂 Dosya Yapısı

```
agent_recommendation_system_final/
├── api/                    # FastAPI sunucusu
├── etl/                    # Veri işleme (ETL)
├── rag/                    # RAG mantığı (OpenAI LLM)
├── vector_db/              # Vektör servisi (OpenAI Embedding)
├── ai_agent_data_june_18_25_/ # Ham veri
├── rebuild_database.py     # Veritabanını OpenAI ile inşa etme script'i
├── requirements.txt        # Gerekli kütüphaneler
└── .env                    # API anahtarını içeren dosya (önceden oluşturulmalı)
```

---

## 🔑 OpenAI API Anahtarının Önemi

Bu sistemin çalışması için **geçerli bir OpenAI API anahtarı ZORUNLUDUR**.
- `.env` dosyanızın `OPENAI_API_KEY=sk-xxxxxxxx...` şeklinde doğru anahtarı içerdiğinden emin olun.
- **DİKKAT:** `rebuild_database.py` script'ini çalıştırmak, tüm verilerinizi vektöre çevirmek için OpenAI'nin embedding API'sini kullanır. Bu işlem, veri boyutunuza bağlı olarak **API kredinizi tüketir ve maliyet oluşturabilir.**

---

## ⚙️ Kurulum ve Çalıştırma

### Adım 1: Kurulum
1.  **Sanal Ortam Oluşturun:** `python3 -m venv venv && source venv/bin/activate`
2.  **Kütüphaneleri Yükleyin:** `pip install -r requirements.txt`
3.  **`.env` Dosyasını Oluşturun:** `env_example.txt` dosyasını kopyalayıp adını `.env` yapın ve içine geçerli OpenAI API anahtarınızı girin.

### Adım 2: Veritabanını OpenAI ile İnşa Etme
Bu komut, ham verileri işler ve `chroma_db_openai` adında, OpenAI vektörleriyle dolu tutarlı bir veritabanı oluşturur.

```bash
python rebuild_database.py
```
İşlem tamamlandığında "VERİTABANI YENİDEN İNŞA ETME İŞLEMİ TAMAMLANDI!" mesajını göreceksiniz.

### Adım 3: API Sunucusunu Başlatma
```bash
python api/main.py
```
Sunucu `http://127.0.0.1:8000` adresinde çalışmaya başlayacaktır.

### Adım 4: Sistemi Test Etme
Aşağıdaki `curl` komutuyla sistemi test edebilirsiniz:

```bash
curl -X POST "http://127.0.0.1:8000/recommend" \
     -H "Content-Type: application/json" \
     -d '{"query": "I need help with a customer service issue regarding my account billing."}'
```
Artık sistem, hem anlama hem de yanıtlama için tamamen OpenAI'nin gücünü kullanıyor! 