# Gereksinim Analizi Raporu

**Ekip 16** · Haber Metinlerinde Yanlış Bilgi İçeren İçeriklerin Sınıflandırılması

## 1. Sistemin amacı ve kapsamı
Geliştirdiğimiz sistem, kullanıcının verdiği İngilizce bir haber linkini inceleyip haberin ne kadar güvenilir olduğunu gerekçeleriyle söyleyen bir web uygulaması. Sistem haberdeki kontrol edilebilir iddiaları çıkarıyor, her birini internette araştırıyor ve sonunda haber için bir skor, bir sınıf ve haber sorunluysa bir yalan türü veriyor. Türkçe haberler, görsel ve video içerikler ile sosyal medya paylaşımları kapsam dışında.

## 2. Kullanıcılar
Bir haberin doğruluğundan şüphelenen ama bunu kendisi araştırmaya vakti olmayan sıradan okur. Kullanıcının teknik bilgisi olması gerekmiyor; linki yapıştırması yeterli.

## 3. Fonksiyonel gereksinimler
1. Kullanıcı arayüze bir haber linki girebilmeli.
2. Sistem sayfadan haberin başlığını ve metnini çekmeli. Sayfa çekilemezse (ödeme duvarı, bot engeli) 10 saniye içinde anlaşılır bir hata vermeli.
3. Haberin yayımlandığı site güvenilirlik listelerinde aranmalı. Site hiciv sitesiyse haber araştırma yapılmadan "Hiciv" olarak işaretlenmeli.
4. Haberden en fazla 5 kontrol edilebilir iddia çıkarılmalı; görüş ve tahminler alınmamalı.
5. Her iddia için fact-check sitelerinde ve genel web'de kanıt aranmalı. Haberin kendi sitesi, güvenilmez siteler ve sosyal medya kanıt sayılmamalı.
6. Her iddia doğru, yanlış, çelişkili ya da kanıt yetersiz olarak etiketlenmeli.
7. İddia sonuçlarından haber için bir skor ve sınıf (Güvenilir, Yanlış, Yanıltıcı, Şüpheli, Doğrulanamadı, Hiciv) üretilmeli.
8. Haber sorunlu çıkarsa yalan türü (uydurma, çarpıtma, yanıltıcı, sahte alıntı, bilim dışı) belirlenmeli.
9. Sonuç sayfasında her iddianın kararı, gerekçesi ve dayandığı kaynak linkleri gösterilmeli; sorunlu cümleler haber metninde işaretlenmeli.

## 4. Fonksiyonel olmayan gereksinimler
- **Süre:** Bir haberin analizi 60 saniyeyi geçmemeli (şu anki sürümde 35–55 sn).
- **Maliyet:** Ücretli dil modeli yalnız yerel modelin emin olmadığı iddialarda çağrılmalı; haber başına maliyet 1 sentin altında kalmalı (şu an yaklaşık 0,15–0,3 sent).
- **Doğruluk:** Yerel modelin kendi verdiği kararlarda doğruluk en az %90 olmalı. Sistemin tamamı ayrıca doğruluğu bilinen gerçek haberlerle test edilmeli.
- **Açıklanabilirlik:** Sistem hiçbir kararı kaynak göstermeden vermemeli.
- **Güvenlik:** API anahtarları kodun içinde değil, git'e girmeyen ayrı bir dosyada tutulmalı.

## 5. Donanım ve yazılım gereksinimleri
- Python, PyTorch, Transformers, LangGraph ve trafilatura kütüphaneleri; Gemini API ve Tavily arama API'si.
- Yerel doğrulama modeli (DeBERTa-v3-large, ~1,7 GB) için en az 4 GB belleği olan bir NVIDIA ekran kartı (geliştirmede GTX 1650 kullanıyoruz).
- İnternet bağlantısı.

## 6. Kısıtlar ve riskler
- Tavily'nin ücretsiz planı ayda 1.000 arama veriyor. Haber başına 10 arama yapıldığı için ayda yaklaşık 100 haber analiz edilebiliyor.
- Sistem yalnız olgulara bakıyor. Doğru bilgileri manipülatif bir dille sunan propaganda haberlerini şu an yakalayamıyor.
- Hiç yaşanmamış olaylar için web'de çürütücü kanıt bulunmayabiliyor; bu haberler "Şüpheli" olarak kalabiliyor.
- Dil modelinin kararları aynı haberde çalıştırmadan çalıştırmaya değişebiliyor.
