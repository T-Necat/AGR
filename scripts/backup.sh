#!/bin/bash
# Bu script, ChromaDB veritabanı klasörünü yedeklemek için kullanılır.

# Ayarlar
# Config dosyasından alınması daha iyi olur, ama basitlik için burada tanımlandı.
DB_DIRECTORY="src/chroma_db" 
BACKUP_DIRECTORY="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIRECTORY/chroma_db_backup_$TIMESTAMP.tar.gz"

# Yedekleme dizininin var olup olmadığını kontrol et, yoksa oluştur
if [ ! -d "$BACKUP_DIRECTORY" ]; then
    echo "Yedekleme dizini '$BACKUP_DIRECTORY' oluşturuluyor..."
    mkdir -p "$BACKUP_DIRECTORY"
fi

# Veritabanı dizininin var olup olmadığını kontrol et
if [ ! -d "$DB_DIRECTORY" ]; then
    echo "Hata: Veritabanı dizini '$DB_DIRECTORY' bulunamadı."
    exit 1
fi

echo "Veritabanı yedekleniyor..."
echo "Kaynak: $DB_DIRECTORY"
echo "Hedef: $BACKUP_FILE"

# Dizini tar.gz olarak sıkıştır
tar -czf "$BACKUP_FILE" -C "$(dirname "$DB_DIRECTORY")" "$(basename "$DB_DIRECTORY")"

# İşlemin sonucunu kontrol et
if [ $? -eq 0 ]; then
    echo "Yedekleme başarıyla tamamlandı: $BACKUP_FILE"
else
    echo "Hata: Yedekleme işlemi başarısız oldu."
    exit 1
fi

# Eski yedekleri temizleme (opsiyonel, son 7 yedeği tutar)
echo "Eski yedekler temizleniyor (son 7 yedek tutulacak)..."
ls -t "$BACKUP_DIRECTORY"/chroma_db_backup_*.tar.gz | tail -n +8 | xargs -I {} rm -- {}
echo "Temizleme tamamlandı."

exit 0 