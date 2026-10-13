# Gereksinim Analizi Raporu

**Ekip 16** · Haber Metinlerinde Yanlış Bilgi İçeren İçeriklerin Sınıflandırılması

## 1. Amaç ve kapsam
Sistemimiz kullanıcının verdiği İngilizce bir haber linkini inceliyor: haberden kontrol edilebilir iddiaları çıkarıyor, her birini internette araştırıyor ve haber için bir skor, bir sınıf ve sorunluysa bir yalan türü veriyor. Ana fikir kaskad yapı: ücretsiz yerel bir model önce karar vermeyi deniyor, ücretli dil modeli (LLM) yalnız model emin olamadığında devreye giriyor. Türkçe haberler, görsel/video içerik ve sosyal medya paylaşımları kapsam dışında.

## 2. Fonksiyonel gereksinimler

| No | Bileşen | Gereksinim | Nasıl karşılanıyor |
|---|---|---|---|
| F1 | Haber çekme | Linkten haberin başlığı ve metni alınmalı | `requests` ile indirme, `trafilatura` ile menü/reklamdan arındırma; çekilemeyen sayfa 10 sn içinde hata verir |
| F2 | Kaynak kontrolü | Haberin sitesinin güvenilirliği belirlenmeli | Sırayla hiciv listesi (5 site), Wikipedia güvenilir kaynaklar listesi (497 kaynak), Lin 2023 puanları (11.520 site); hiciv sitesiyse araştırma yapılmadan "Hiciv" |
| F3 | İddia çıkarma | Haberden kontrol edilebilir iddialar çıkarılmalı | Gemini ile en fazla 5 iddia; her iddiada kişi, yer ve tarih zorunlu; görüş ve tahminler alınmaz |
| F4 | Kanıt arama | Her iddia için kanıt bulunmalı | İddia başına 2 Tavily araması: 10 fact-check sitesinde (5 sonuç) ve genel web'de (10 sonuç); iddialar paralel işlenir |
| F5 | Kanıt süzme | Güvenilmez ve ilgisiz kanıtlar elenmeli | Haberin kendi sitesi, yasaklı siteler ve sosyal medya atılır; LLM'e "aynı kişi ve olay mı?" diye sorularak ilgisiz sonuçlar elenir |
| F6 | Fact-check etiketi | Daha önce incelenmiş iddiada hazır karar kullanılmalı | Fact-check sayfasındaki ClaimReview etiketi okunur (ör. Snopes "False"); yalnız incelenen iddia bizimkiyle aynıysa kullanılır |
| F7 | Yerel doğrulama | İddia kanıtlarla karşılaştırılıp etiketlenmeli | DeBERTa-v3-large doğrulama modeli 4 sınıf verir: Doğru, Yanlış, Çelişkili, Kanıt yetersiz; güven ≥ 0,9 ise karar kabul edilir |
| F8 | LLM hakim | Modelin emin olmadığı iddialar karara bağlanmalı | İddia, kanıtlar ve kaynak etiketleri Gemini'ye verilir; karar ve tek cümlelik gerekçe döner |
| F9 | Haber kararı | İddia sonuçlarından tek bir sonuç çıkmalı | Her iddia puanı (Doğru +1, Yanlış −1, Çelişkili −0,5, Kanıt yetersiz 0) × güven, fact-check kararı 2 kat; ortalama ≤ −0,2 Yanlış, ≥ 0,2 Güvenilir, arası Yanıltıcı/Şüpheli/Doğrulanamadı |
| F10 | Yalan türü | Sorunlu haberin türü belirlenmeli | Uydurma, çarpıtma, yanıltıcı, sahte alıntı, bilim dışı, hiciv; önce fact-check etiketinden, yoksa LLM'den |
| F11 | Sonuç ekranı | Kullanıcı kararın gerekçesini görebilmeli | Her iddianın kararı, gerekçesi ve kaynak linkleri; sorunlu cümleler metinde işaretli (web arayüzü geliştiriliyor) |

## 3. Fonksiyonel olmayan gereksinimler

| No | Gereksinim | Hedef / mevcut durum |
|---|---|---|
| N1 | Maliyet | LLM yalnız gerektiğinde çağrılmalı. 5 iddialı bir haberde 6–12 çağrı (hiciv sitesinde 0); yaklaşık 0,15–0,3 sent |
| N2 | Doğruluk | Yerel model AVeriTeC geliştirme setinde (500 iddia) %80,2 doğruluk aldı (her şeye "Yanlış" diyen tahmin %61). 0,9 eşiğinde iddiaların %82'si modelde kalıyor ve bunlarda doğruluk %90 |
| N3 | Süre | Bir haber 60 saniyenin altında analiz edilmeli; şu an 35–55 sn. Model program açıkken bir kez yükleniyor (~20 sn) |
| N4 | Açıklanabilirlik | Her iddiada kararı kimin verdiği (fact-check, yerel model, LLM) ve dayandığı kanıt linkleri tutuluyor |
| N5 | Kanıtın güvenilirliği | Haber kendisiyle doğrulanmamalı. Fact-check özetleri yalanı alıntıladığı için kanıt sayılmıyor. Kanıt yoksa model çalıştırılmadan "Kanıt yetersiz" deniyor |
| N6 | Donanım | Yerel model (~1,7 GB) en az 4 GB belleği olan bir NVIDIA ekran kartında çalışmalı (geliştirmede GTX 1650, ~2 GB bellek kullanımı) |
| N7 | Kota | Tavily ücretsiz planı ayda 1.000 arama veriyor; haber başına 10 arama ile ayda yaklaşık 100 haber |
| N8 | Dil | Yalnız İngilizce haberler (uygun Türkçe veri seti yok) |

## 4. Kısıtlar
- Sistem yalnız olgulara bakıyor; doğru bilgileri manipülatif bir dille sunan propaganda haberlerini yakalayamıyor.
- Hiç yaşanmamış olaylar için web'de çürütücü kanıt bulunmayabiliyor; bu haberler "Şüpheli" kalabiliyor.
- LLM kararları aynı haberde çalıştırmadan çalıştırmaya değişebiliyor.
