from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import get_settings
from src.database.models import Base

settings = get_settings()

# Veritabanı motorunu oluştur
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} # SQLite için gerekli
)

# Veritabanı oturumları için bir SessionLocal sınıfı oluştur
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Veritabanı tablolarını (yeniden) oluşturur.
    Bu fonksiyon, modellerde yapılan değişikliklerin veritabanına yansıtılması
    için çağrılabilir. Mevcut tabloları silmez, sadece olmayanları ekler.
    Ancak, bir modelde sütun değişikliği gibi durumlarda, veritabanını
    manuel olarak silip yeniden oluşturmak gerekebilir.
    """
    try:
        Base.metadata.create_all(bind=engine)
        print("Veritabanı tabloları başarıyla oluşturuldu veya güncellendi.")
    except Exception as e:
        print(f"Veritabanı tabloları oluşturulurken bir hata oluştu: {e}") 