from celery import Celery
import os

# Redis'in çalıştığı adresi tanımla.
# Varsayılan olarak localhost:6379 kullanılır.
REDIS_URL = "redis://localhost:6379/0"

# Celery uygulamasını oluştur.
celery_app = Celery(
    'tasks',                      # Uygulamanın adı
    broker=REDIS_URL,             # Görevleri göndereceğimiz yer (Mesajlaşma Aracısı)
    backend=REDIS_URL,            # Görev sonuçlarını saklayacağımız yer (Sonuç Deposu)
    include=['src.tasks']         # Worker başladığında yüklenecek görev modülleri
)

# İsteğe bağlı Celery yapılandırması
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Europe/Istanbul',
    enable_utc=True,
)

if __name__ == '__main__':
    celery_app.start() 