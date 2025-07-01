# AI Agent Değerlendirme Sistemi

Bu proje, yapay zeka ajanlarının konuşma performansını analiz etmek ve değerlendirmek için geliştirilmiş bir Streamlit uygulamasıdır. LLM-as-a-judge (Yargıç olarak LLM) yaklaşımını kullanarak, ajan yanıtlarını çeşitli metriklere göre objektif bir şekilde puanlar.

![Uygulama Arayüzü](agent_recommendation_system_final copy/assets/Jotform-New-Logo.png) 
*Not: Bu görsel yerine uygulamanın ekran görüntüsünü koymak daha açıklayıcı olabilir.*

---

## 🚀 Temel Özellikler

- **🧪 Sandbox (Manuel Değerlendirme):** Ajanın potansiyel performansını test etmek için manuel olarak kullanıcı sorusu, ajan cevabı, persona ve hedef girerek anında değerlendirme alın.
- **📚 Toplu Değerlendirme:** Sohbet geçmişini içeren bir `.csv` dosyası yükleyerek tüm konuşmaları tek seferde değerlendirin ve genel istatistikleri görüntüleyin.
- **💬 Oturum Analizi:** Kayıtlı bir konuşma oturumunu baştan sona inceleyin ve tüm diyalog için bütünsel bir değerlendirme alın.
- **📊 Detaylı Metrikler:** Ajan performansını aşağıdaki gibi çok yönlü metriklerle ölçün:
  - Amaca Uygunluk (Goal Adherence)
  - Temellendirme (Groundedness)
  - Cevap Alaka Düzeyi (Answer Relevance)
  - Persona Uyumu (Persona Compliance)
  - Üslup ve Nezaket (Style & Courtesy)
  - Özlük (Conciseness)
  - Bilgi Sınırı ve Güvenlik İhlalleri

## 🛠️ Kullanılan Teknolojiler

- **Arayüz:** Streamlit, Streamlit Option Menu
- **Dil Modelleri:** OpenAI API (GPT-4, o4-mini vb.)
- **Yapılandırılmış Çıktı:** `instructor` kütüphanesi
- **Vektör Veritabanı:** ChromaDB
- **Veri İşleme:** Pandas

---

## ⚙️ Kurulum ve Çalıştırma

### 1. Projeyi Klonlama

```bash
git clone https://github.com/T-Necat/AGR.git
cd AGR
```

### 2. Bağımlılıkları Yükleme

Projeyi çalıştırmak için gerekli olan tüm kütüphaneleri yükleyin. Bir sanal ortam (virtual environment) kullanmanız şiddetle tavsiye edilir.

```bash
pip install -r agent_recommendation_system_final copy/requirements.txt
```

### 3. API Anahtarlarını Ayarlama

Projenin OpenAI API'sine erişmesi gerekmektedir. `agent_recommendation_system_final copy/` klasörü içindeki `env_example.txt` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun ve kendi OpenAI API anahtarınızı girin.

```
# agent_recommendation_system_final copy/.env dosyası

OPENAI_API_KEY="sk-..."
```
**Not:** `.env` dosyası `.gitignore` tarafından korunmaktadır ve asla GitHub'a gönderilmez.

### 4. Uygulamayı Çalıştırma

Tüm kurulum adımları tamamlandıktan sonra, aşağıdaki komutla Streamlit uygulamasını başlatabilirsiniz:

```bash
streamlit run "agent_recommendation_system_final copy/evaluation_app.py"
```

Uygulama yerel ağınızda başlayacak ve tarayıcınızda otomatik olarak bir sekme açılacaktır. 