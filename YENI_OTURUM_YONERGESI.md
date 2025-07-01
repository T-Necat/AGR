# Yeni Veri/Oturum Ekleme Yönergesi

Bu proje, büyük veri dosyalarını (CSV, veritabanı dosyaları vb.) doğrudan GitHub repositorisinde saklamayacak şekilde yapılandırılmıştır. Reponun boyutunu küçük ve yönetilebilir tutmak, projenin performansını ve taşınabilirliğini korumak için bu kritik öneme sahiptir.

## Yeni Bir Veri Seti Eklerken İzlenecek Adımlar

1.  **Verileri Doğru Klasöre Koyun:**
    Yeni sohbet, persona veya görev verilerinizi içeren `.csv` dosyalarını `agent_recommendation_system_final copy/ai_agent_data_june_18_25_` gibi mevcut veri klasörlerinin içine yerleştirin veya yeni bir veri klasörü oluşturun.

2.  **`.gitignore` Kontrolü:**
    Projenin kök dizinindeki `.gitignore` dosyası, `*.csv`, `*.sqlite3` gibi yaygın veri dosyası uzantılarını zaten hariç tutacak şekilde yapılandırılmıştır. Bu sayede, bu klasörlere eklediğiniz veri dosyaları otomatik olarak `git` tarafından göz ardı edilecektir.

3.  **ASLA `git add` ile Büyük Dosya Eklemeyin:**
    `git add .` komutunu çalıştırmadan önce, yeni eklediğiniz büyük veri dosyalarının `.gitignore` kuralları tarafından kapsandığından emin olun. `git status` komutu, hangi dosyaların ekleneceğini size gösterecektir. Listede büyük bir veri dosyası görüyorsanız, `.gitignore` dosyasını kontrol edip güncellemeniz gerekir.

4.  **Veritabanlarını Hariç Tutun:**
    Uygulama çalıştırıldığında oluşturulan ChromaDB veritabanları (`chroma_db_...` klasörleri) da `.gitignore` tarafından otomatik olarak hariç tutulur. Bu klasörleri de asla repoya eklemeyin.

Bu basit kurallara uymak, reponun temiz, hızlı ve herkes için kolayca kullanılabilir kalmasını sağlayacaktır. 