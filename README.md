# Jotform Agent Insight & Recommendation API (MVP)

Bu proje, iki ana bileşenden oluşan bir yapay zeka destekli ajan yönetim sistemidir:

1.  **Agent Recommendation API:** Kullanıcı sorgularına göre en uygun yapay zeka ajanını öneren bir FastAPI tabanlı API.
2.  **Agent Insight Dashboard:** Yapay zeka ajanlarının konuşma performansını analiz etmek ve değerlendirmek için geliştirilmiş bir Streamlit tabanlı arayüz.

---

## 🛠️ Kullanılan Teknolojiler

- **API:** FastAPI, Uvicorn
- **Arayüz:** Streamlit, Streamlit Option Menu
- **Dil Modelleri:** OpenAI API (GPT-4, o4-mini vb.)
- **RAG & Yapılandırılmış Çıktı:** LangChain, `instructor`
- **Vektör Veritabanı:** ChromaDB
- **Veri İşleme:** Pandas

---

## ⚙️ Kurulum

### 1. Projeyi Klonlama (Eğer Gerekliyse)
```bash
git clone <projenizin_repo_url'si>
cd jotform-agent-insight-mvp
```

### 2. Bağımlılıkları Yükleme
Projeyi çalıştırmak için gerekli olan tüm kütüphaneleri yükleyin. Bir sanal ortam (virtual environment) kullanmanız şiddetle tavsiye edilir.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt
```

### 3. API Anahtarlarını Ayarlama
Projenin OpenAI API'sine erişmesi gerekmektedir. `src/` klasörü içindeki `env_example.txt` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun ve kendi OpenAI API anahtarınızı girin.

```sh
cp src/env_example.txt src/.env
```
Daha sonra `src/.env` dosyasını düzenleyerek anahtarınızı girin:
```
# src/.env dosyası
OPENAI_API_KEY="sk-..."
```

### 4. Veritabanını Oluşturma
Sistemin ihtiyaç duyduğu vektör veritabanını oluşturmak için aşağıdaki betiği çalıştırın. Bu betik, `agent_knowledge_base.csv` dosyasını işleyerek ChromaDB veritabanını oluşturur.

**Not:** Bu işlem, verilerinizi vektöre çevirmek için OpenAI'nin embedding API'sini kullanır ve API kredinizi tüketerek maliyet oluşturabilir.

```bash
python src/rebuild_database.py
```

---

## 🚀 Uygulamaları Çalıştırma

Kurulum tamamlandıktan sonra, API'yi veya değerlendirme arayüzünü ayrı ayrı çalıştırabilirsiniz.

### 1. Agent Recommendation API (FastAPI)

API sunucusunu başlatmak için:
```bash
python src/api/main.py
```
Sunucu varsayılan olarak `http://127.0.0.1:8000` adresinde çalışmaya başlayacaktır. API'yi test etmek için aşağıdaki `curl` komutunu kullanabilirsiniz:

```bash
curl -X POST "http://127.0.0.1:8000/recommend" \
     -H "Content-Type: application/json" \
     -d '{"query": "I need help with a customer service issue regarding my account billing."}'
```

### 2. Agent Insight Dashboard (Streamlit)

Değerlendirme arayüzünü başlatmak için:
```bash
streamlit run src/evaluation_app.py
```
Uygulama yerel ağınızda başlayacak ve tarayıcınızda otomatik olarak bir sekme açılacaktır.