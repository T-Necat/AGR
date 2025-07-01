# Yeni Veri/Oturum Ekleme ve GitHub Yükleme Yönergesi

Bu proje, büyük veri dosyalarını (CSV, veritabanı dosyaları vb.) ve hassas bilgileri (API Anahtarları) doğrudan GitHub repositorisinde saklamayacak şekilde yapılandırılmıştır. Reponun boyutunu küçük ve yönetilebilir tutmak, projenin performansını ve güvenliğini korumak için bu kritik öneme sahiptir.

## Veri ve Konfigürasyon Yönetimi

### 1. Veri Dosyaları (`src/data/`)
- **TÜM VERİ DOSYALARI `src/data/` klasörüne yerleştirilmelidir.**
- Bu klasör ve içindeki `.csv` uzantılı dosyalar (`feedback.csv` dahil) `.gitignore` tarafından **tamamen göz ardı edilmektedir.**
- **KESİNLİKLE `git add -f` gibi komutlarla bu dosyaları repoya eklemeye çalışmayın.**

### 2. API Anahtarları (`.env`)
- API anahtarınız `src/.env` dosyasında saklanmalıdır.
- Bu dosya da `.gitignore` tarafından göz ardı edilir ve **asla** GitHub'a gönderilmez.

Bu basit kurallara uymak, reponun temiz, hızlı ve herkes için güvenli kalmasını sağlayacaktır.

---

## 🚀 GitHub'a Değişiklik Gönderme

Bu projeye yapılan tüm katkılar, belirli bir GitHub profili ve repositorisine gönderilmelidir.

- **GitHub Repository:** `T-Necat/AGR`
- **Profil ve Kimlik Doğrulama:** Bu repoya erişim, özel bir yapılandırma dosyası ile yönetilmektedir. Katkıda bulunmadan önce, aşağıdaki komutla doğru profilin etkinleştirildiğinden emin olun:
  ```bash
  # Özel yapılandırma dosyasını kopyalayarak kısıtlı profili etkinleştirir.
  cp ~/.config/gh/hosts-kisitli.yaml ~/.config/gh/hosts.yml
  ```

Bu adımlar, projenin tutarlılığını ve güvenliğini korumak için zorunludur. 