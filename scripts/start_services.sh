#!/bin/bash
# Bu script, AI Agent Değerlendirme Sistemi için gerekli tüm servisleri başlatır.
# Hem backend (FastAPI, Celery) hem de frontend (Vite) sunucularını başlatır.
# Tüm loglar bu terminalde gösterilecektir.
# Çıkmak ve tüm servisleri durdurmak için Ctrl+C tuşuna basın.

# Proje kök dizinini PYTHONPATH'e ekle. Bu, 'src' modülünün bulunmasını sağlar.
export PYTHONPATH=$(pwd)

echo ">>> AI Agent Sistemi Başlatılıyor..."
echo ">>> Çıkmak için Ctrl+C'ye basın."
echo ""

# Redis'in çalıştığından emin olmak için bir uyarı
if ! redis-cli ping > /dev/null 2>&1; then
    echo "UYARI: Redis sunucusuna bağlanılamıyor. Lütfen Redis'in çalıştığından emin olun."
    echo "         'brew services start redis' veya benzeri bir komutla başlatabilirsiniz."
    echo ""
fi

# Ctrl+C'ye basıldığında çalışacak temizlik fonksiyonu
cleanup() {
    echo ""
    echo ">>> Servisler kapatılıyor... Lütfen bekleyin."
    # Bu script tarafından başlatılan tüm alt işlemleri (Celery, Vite vb.) sonlandırır.
    kill 0
    exit
}

# Ctrl+C sinyalini yakala ve cleanup fonksiyonunu çağır
trap cleanup SIGINT

# 1. Celery Worker'ı Başlat
echo "[1/3] Celery worker başlatılıyor..."
celery -A src.celery_app worker --loglevel=INFO &

# 2. FastAPI API'sini Başlat
echo "[2/3] FastAPI API'si http://localhost:8000 adresinde başlatılıyor..."
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload &

# 3. Frontend Geliştirme Sunucusunu Başlat
echo "[3/3] Frontend geliştirme sunucusu http://localhost:5173 adresinde başlatılıyor..."
(cd frontend && npm run dev) &

# Tüm arka plan işlemleri bitene kadar bekle (Ctrl+C ile kesilene kadar)
wait 