import logging
import sys
from pythonjsonlogger.json import JsonFormatter

def setup_logging():
    """
    Uygulama genelinde kullanılacak JSON formatlı logger'ı yapılandırır.
    """
    logger = logging.getLogger()
    
    # Mevcut handler'ları temizle
    if logger.hasHandlers():
        logger.handlers.clear()

    # Log level'ı INFO olarak ayarla
    logger.setLevel(logging.INFO)

    # Console'a log basmak için bir handler oluştur
    log_handler = logging.StreamHandler(sys.stdout)
    
    # JSON formatlayıcı oluştur
    formatter = JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(lineno)d %(filename)s'
    )
    
    # Handler'a formatlayıcıyı ekle
    log_handler.setFormatter(formatter)
    
    # Root logger'a handler'ı ekle
    logger.addHandler(log_handler)

    logging.info("JSON formatlı logger başarıyla yapılandırıldı.")

if __name__ == '__main__':
    setup_logging()
    logging.info("Bu bir test log mesajıdır.", extra={'test_key': 'test_value'})
    logging.warning("Bu bir uyarı mesajıdır.")
    try:
        raise ZeroDivisionError("Hata yakalama testi")
    except ZeroDivisionError:
        logging.error("Bir hata oluştu", exc_info=True) 