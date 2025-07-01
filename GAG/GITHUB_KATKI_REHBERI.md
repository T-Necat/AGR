# Projeye Katkıda Bulunma ve Değişiklikleri Yükleme Rehberi

Bu rehber, projeye yapılan katkıların tutarlı, güvenli ve standart bir şekilde nasıl yapılacağını açıklamaktadır. Lütfen değişikliklerinizi GitHub'a göndermeden önce bu adımları dikkatlice takip edin.

---

## 🔒 Temel Güvenlik ve Veri Kuralları (Önce Oku!)

Bu proje, büyük veri dosyalarını ve hassas bilgileri (API Anahtarları) doğrudan GitHub repositorisinde **saklamaz**. Bu kural, reponun boyutunu küçük tutmak, performansı korumak ve güvenliği sağlamak için kritik öneme sahiptir.

-   **Veri Dosyaları (`src/data/`):**
    - Tüm ham veri dosyaları (`.csv`, `.json` vb.) `src/data/` klasörüne yerleştirilmelidir.
    - Bu klasör ve içindekiler `.gitignore` tarafından **tamamen göz ardı edilmektedir.**
    - **KESİNLİKLE `git add -f` gibi zorlama komutlarıyla bu dosyaları repoya eklemeye çalışmayın.**

-   **API Anahtarları (`.env`):**
    - API anahtarlarınız **sadece** `src/.env` dosyasında saklanmalıdır.
    - Bu dosya da `.gitignore` tarafından göz ardı edilir ve **asla** GitHub'a gönderilmemelidir.

---

## 🚀 Katkı ve Yükleme İş Akışı (Adım Adım)

### Adım 0: Profil ve Kimlik Doğrulama (Gerekliyse)
Eğer bu repoya erişim için özel bir GitHub profili kullanıyorsanız, çalışmaya başlamadan önce doğru profilin etkinleştirildiğinden emin olun:
```bash
# Örnek: Özel yapılandırma dosyasını kopyalayarak kısıtlı profili etkinleştirir.
cp ~/.config/gh/hosts-kisitli.yaml ~/.config/gh/hosts.yml
```

### Adım 1: Mevcut Değişiklikleri Al
Çalışmaya başlamadan önce, her zaman branch'inizdeki en son değişiklikleri bilgisayarınıza çekin.
```bash
git pull origin test
```

### Adım 2: Kodlama ve Geliştirme
Yeni özellikleri ekleyin veya mevcut hataları düzeltin.

### Adım 3: Testleri Çalıştır (ZORUNLU)
Yaptığınız değişikliklerin mevcut sistemi bozmadığından emin olmak için tüm testleri çalıştırın.
```bash
pytest
```
**Tüm testler başarıyla geçmeden bir sonraki adıma geçmeyin!**

### Adım 4: Değişiklikleri Ekleme
Yaptığınız tüm değişiklikleri hazırlık alanına (`staging area`) ekleyin.
```bash
git add .
```

### Adım 5: Değişiklikleri Commit'leme
Değişikliklerinizi, ne yaptığınızı açıklayan standart bir formatta commit'leyin.

**Commit Mesaj Formatı:** `<tip>: <mesaj>`
- **`feat:`** Yeni bir özellik eklendiğinde.
- **`fix:`** Bir hata düzeltildiğinde.
- **`refactor:`** Kodun işlevini değiştirmeyen yapısal düzenlemelerde.
- **`docs:`** Sadece dokümantasyon güncellendiğinde.

**Örnek Commit Komutu:**
```bash
git commit -m "feat: Oturumlar için otomatik özetleme özelliği eklendi"
```

### Adım 6: Değişiklikleri GitHub'a Yükleme (Push)
Commit'lediğiniz değişiklikleri uzak sunucuya (GitHub) gönderin.
```bash
git push origin test
```

Bu adımları takip etmek, projenin sağlıklı ve güvenli kalmasını sağlayacaktır. Teşekkürler! 