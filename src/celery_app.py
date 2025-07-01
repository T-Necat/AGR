from celery import Celery
from src.config import get_settings

settings = get_settings()

# Celery uygulamasını oluştur.
celery_app = Celery(
    'tasks',                                # Uygulamanın adı
    broker=settings.CELERY_BROKER_URL,      # Görevleri göndereceğimiz yer (Mesajlaşma Aracısı)
    backend=settings.CELERY_RESULT_BACKEND, # Görev sonuçlarını saklayacağımız yer (Sonuç Deposu)
    include=['src.tasks']                   # Worker başladığında yüklenecek görev modülleri
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