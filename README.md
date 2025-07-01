# Jotform Agent Insight & Recommendation System (MVP)

Bu proje, yapay zeka ajanlarının performansını ölçmek, analiz etmek ve kullanıcı sorgularına göre en uygun ajanı tavsiye etmek için geliştirilmiş kapsamlı bir sistemdir.

---

## ✨ Ana Özellikler

- **LLM-as-a-Judge Değerlendirmesi:** Agent konuşmalarını; hedefe uygunluk, doğruluk, üslup ve güvenlik gibi çok boyutlu kriterlere göre değerlendirir.
- **Asenkron Görev Yönetimi:** `Celery` ve `Redis` kullanarak, uzun süren toplu değerlendirme ve oturum analizi işlemlerini arayüzü kilitlemeden arka planda çalıştırır.
- **Etkileşimli Arayüz:** `Streamlit` ile geliştirilmiş kullanıcı dostu bir panel üzerinden:
    - **Sandbox:** Manuel senaryoları anında test etme.
    - **Toplu Değerlendirme:** Yüzlerce konuşmayı tek seferde, CSV dosyası yükleyerek değerlendirme.
    - **Oturum Analizi:** Tekil sohbet oturumlarını derinlemesine analiz etme ve otomatik özet çıkarma.
- **RAG Tabanlı Agent Tavsiyesi:** `FastAPI` ile sunulan bir endpoint, kullanıcı sorgusunu analiz ederek vektör veritabanından en uygun agent'ı bulur ve tavsiye eder.
- **Test ve Otomasyon:** Kapsamlı `pytest` testleri ve tüm sistemi tek komutla başlatan bir otomasyon script'i içerir.

---

## 🛠️ Mimaride Kullanılan Teknolojiler

- **Backend & API:** FastAPI, Uvicorn
- **Frontend Arayüzü:** Streamlit
- **Arka Plan Görevleri:** Celery, Redis
- **Dil Modelleri & RAG:** OpenAI API, LangChain, `instructor`
- **Vektör Veritabanı:** ChromaDB
- **Veri İşleme:** Pandas
- **Test:** Pytest

---

## ⚙️ Kurulum

### 1. Projeyi Klonlama
```bash
git clone <projenizin_repo_url'si>
cd jotform-agent-insight-mvp
```

### 2. Sanal Ortam ve Bağımlılıklar
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt
```

### 3. Redis Kurulumu ve Başlatma
Celery'nin çalışması için Redis gereklidir. Eğer kurulu değilse, sisteminize uygun şekilde kurun.

**macOS (Homebrew ile):**
```bash
brew install redis
brew services start redis
```

### 4. API Anahtarlarını Ayarlama
`src/env_example.txt` dosyasını `src/.env` olarak kopyalayın ve kendi API anahtarlarınızı girin.
```sh
cp src/env_example.txt src/.env
```
Ardından `src/.env` dosyasını düzenleyin:
```
# src/.env dosyası
OPENAI_API_KEY="sk-..."
API_KEY="your_secret_api_key_for_the_service"
```

### 5. Veritabanını Oluşturma (İlk Kurulum)
Sistemin ihtiyaç duyduğu vektör veritabanını oluşturmak için aşağıdaki betiği çalıştırın.
**Not:** Bu işlem OpenAI API kredinizi tüketerek maliyet oluşturabilir.
```bash
python src/rebuild_database.py
```

---

## 🚀 Sistemi Çalıştırma

Sistemin tüm bileşenlerini (Celery, FastAPI, Streamlit) tek bir komutla başlatmak için hazırlanan script'i kullanın.

**1. Script'i Çalıştırılabilir Yapma (Sadece bir kez):**
```bash
chmod +x scripts/start_services.sh
```

**2. Sistemi Başlatma:**
```bash
./scripts/start_services.sh
```
Bu komut tüm servisleri başlatacak ve loglarını mevcut terminalde gösterecektir. Streamlit arayüzüne `http://localhost:8501` adresinden erişebilirsiniz.

Sistemi durdurmak için terminalde `Ctrl+C` tuşuna basın.

---

## ✅ Testleri Çalıştırma

Projenin kararlılığını kontrol etmek için testleri çalıştırabilirsiniz:
```bash
pytest
```