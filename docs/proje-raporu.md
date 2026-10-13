# fakenewscatogorizer – Proje Durum Raporu

Tarih: 2026-10-11 · Durum: çalışan ilk sürüm (v1), henüz commit edilmedi.

## 1. Ne yapıyor?

Kullanıcı bir haber linki veriyor. Sistem:

1. Haberin metnini çekiyor.
2. Haberin geldiği sitenin güvenilirliğine bakıyor.
3. Haberden kontrol edilebilir iddiaları çıkarıyor (en fazla 5).
4. Her iddia için web'de kanıt arıyor.
5. Her iddiaya bir karar veriyor: **Supported** (doğru), **Refuted** (yanlış), **Not Enough Evidence** (kanıt yetersiz), **Conflicting/Cherrypicking** (çelişkili/seçici).
6. Bu kararlardan haber düzeyinde tek bir sonuç çıkarıyor.

Temel fikir **kaskad**: ucuz ve yerel bir model önce karar vermeyi deniyor; yalnız emin olamadığı iddialar ücretli LLM'e gidiyor. Böylece LLM maliyeti düşük tutuluyor.

## 2. Mimari

LangGraph ile kurulmuş bir graf. Her kutu bir node:

```
START → fetch_article → source_check ─(hiciv)───────────────────────────→ report → END
                              │
                              └→ extract_claims ─(her iddia için paralel)→ check_claim ─→ report
```

`check_claim` her iddia için ayrı ve paralel çalışıyor (LangGraph `Send`). Hepsi bitince `report` bir kez çalışıyor.

### Node'lar

| Node | LLM? | Ne yapıyor |
|---|---|---|
| `fetch_article` | Hayır | Sayfayı `requests` ile tek denemede indiriyor (10 sn zaman aşımı, `fakenewscatogorizer/0.1` User-Agent; tarayıcı kimliğini web.archive.org reddediyor), `trafilatura` ile menü/reklamdan arındırılmış başlık ve metni çıkarıyor. Sayfa çekilemezse (bot engeli, ödeme duvarı) 10 sn içinde açık bir hata veriyor. |
| `source_check` | Hayır | Linkin sitesini kaynak tablolarında arıyor (bkz. §4). Hiciv sitesiyse doğrudan `report`'a gidiyor; hiçbir arama ya da LLM çağrısı yapılmıyor. |
| `extract_claims` | **Evet, 1 çağrı** | Gemini'ye haberi verip en fazla 5 kontrol edilebilir iddia çıkarıyor. İddialar tek başına anlaşılır yazılıyor (kim, nerede, ne zaman) ve hangi cümleden geldikleri saklanıyor. Görüş ve tahminler alınmıyor. Çıktı Pydantic şemasıyla zorlanıyor. |
| `check_claim` | Gerekirse | (a) Tavily ile iddiayı arıyor, ilk 10 sonucu alıyor. (b) Haberin kendi sitesinden ve "yasaklanmış / kara listede" sitelerden gelen sonuçları atıyor, en fazla 5 kanıt tutuyor. (c) Karar modeline iddia + kanıtları veriyor. (d) Modelin güveni **< 0.9** ise iddiayı, kanıtları ve kaynak etiketlerini Gemini'ye gönderiyor; kararı ve tek cümlelik gerekçeyi LLM veriyor. |
| `report` | Hayır | İddia kararlarını kurallarla haber kararına çeviriyor (bkz. aşağıda). |

### Haber düzeyinde karar kuralları (`report`)

Kurallar sırayla uygulanıyor, ilk eşleşen kazanıyor:

| Koşul | Haber kararı |
|---|---|
| Site hiciv listesinde | Hiciv |
| En az 1 iddia Refuted | Yanlış |
| En az 1 iddia Conflicting | Yanıltıcı |
| İddiaların yarısından fazlası NEE, site "genel olarak güvenilir" | Doğrulanamadı |
| İddiaların yarısından fazlası NEE, site güvenilir değil/bilinmiyor | Şüpheli |
| Olgular doğru ama site yasaklanmış/kara listede | Olgular doğru, kaynak güvenilmez |
| Diğer | Güvenilir |

## 3. Kullanılan modeller ve servisler

| Parça | Ne | Nerede çalışıyor | Ücret |
|---|---|---|---|
| Karar modeli | `ctu-aic/deberta-v3-large-AVeriTeC-nli` (DeBERTa-v3-large, AVeriTeC ile eğitilmiş, 4 sınıf) | Yerel, GPU (GTX 1650, fp32, ~2 GB VRAM) | Ücretsiz (MIT lisansı) |
| LLM | `gemini-3.1-flash-lite` (Google `google-genai` SDK) | Google API | $0.25 / $1.50 per 1M token (girdi/çıktı) |
| Arama | Tavily API | Bulut | Ücretsiz plan: ayda 1.000 kredi |
| Sayfa çekme | `trafilatura` | Yerel | Ücretsiz |
| Orkestrasyon | LangGraph | Yerel | Ücretsiz |

### Karar modeliyle ilgili önemli ayrıntılar

- **Girdi sırası:** önce iddia, sonra kanıt. Ters sırada doğruluk düşüyor (%72).
- **Etiket sırası:** `LABEL_0`=Refuted, `1`=Supported, `2`=NEE, `3`=Conflicting. Model kartında yazmıyor; 150 eğitim iddiasıyla biz bulduk.
- **fp16 kullanılmıyor:** GTX 1650'de tensor çekirdeği yok. fp16, fp32'den 3 kat yavaş çıktı (5 iddia: 5.3 sn'ye karşı 1.7 sn).
- **Model AVeriTeC eğitim setini ezberlemiş** (eğitim iddialarında %100). Testlerde yalnız geliştirme (dev) seti kullanılmalı.

### Neden bu seçimler?

| Karar | Gerekçe |
|---|---|
| ctu-aic modeli | İlk aday (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`) AVeriTeC'te %52.4 aldı; her şeye "yanlış" diyen basit tahminden (%66) bile kötü, güven değeri de anlamsızdı. ctu-aic %80.2 aldı ve güven değeri anlamlı (bkz. §5). |
| Eşik 0.9 | Bu eşikte iddiaların %82'si %90 doğrulukla modelde kalıyor, yalnız %18'i LLM'e gidiyor. |
| Gemini 3.1 Flash-Lite | Hesapta çalışan en ucuz model. `gemini-2.5-flash` ve `2.5-flash-lite` yeni hesaplara kapalı (API 404 veriyor). |
| Langchain yok | LangGraph yalnız orkestrasyon yapıyor; Gemini doğrudan Google SDK ile çağrılıyor. Fazladan bir katmana gerek yoktu. |
| Tavily | Ücretsiz arama kütüphanesi (`ddgs`: DuckDuckGo/Bing/Yahoo kazıma) paralel aramalarda sürekli engellendi; 5 aramadan 0–4'ü başarılı oluyordu. Tavily'de hepsi başarılı. |

## 4. Veri setleri

Hepsi `dataset/` klasöründe. Ayrıntılı sayılar: `docs/veri-setleri.md`.

| Veri | Ne için | İçerik | Link |
|---|---|---|---|
| Wikipedia Perennial Sources (`wp_rsp.csv`) | Kaynak motoru (öncelikli) | 497 kaynak, 756 alan adı; karar + gerekçe + tartışma linki. Sürüm 1378772250. | https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources |
| Lin ve ark. 2023 (`lin2023_*.csv`) | Kaynak motoru (yedek) | 11.520 site, 0–1 göreli puan; 6 uzman puan setinin birleşimi. 2023'ten beri güncellenmiyor. | https://github.com/hauselin/domain-quality-ratings |
| AVeriTeC (`averitec/`) | Karar modelinin testi | Gerçek fact-check iddiaları; train 3.068, dev 500; soru-cevap kanıtlı. | https://github.com/MichSchli/AVeriTeC |

### Kaynak motoru nasıl çalışıyor? (`src/sources.py`)

Linkten site adı çıkarılıyor (`edition.cnn.com` → önce `edition.cnn.com`, sonra `cnn.com` denenir). Arşiv linkinde (`web.archive.org/web/<tarih>/<link>`) içteki asıl site kullanılıyor. Arama sırası:

1. **Hiciv listesi** (5 site: theonion.com, babylonbee.com, clickhole.com, thebeaverton.com, newsthump.com)
2. **Wikipedia** kararı (generally_reliable, no_consensus, generally_unreliable, deprecated, blacklisted)
3. **Lin** puanı
4. Hiçbiri yoksa **unknown**

Önemli: Wikipedia'nın "generally_unreliable" etiketi "yalan yayıyor" demek değil; "ansiklopedide kaynak gösterilemez" demek (Statista, Wikipedia'nın kendisi de bu etikette). Sistemde güçlü olumsuz sinyal olarak yalnız **deprecated** ve **blacklisted** kullanılıyor.

## 5. Deneyler ve sonuçlar

Kod: `experiments/`, ham sonuçlar: `experiments/results/`, ayrıntı: `docs/model-testleri.md`.

### Karar modeli testi (AVeriTeC dev, 500 iddia, insan yazımı kanıtla)

| Model | Doğruluk | Macro F1 |
|---|---|---|
| Hep "Refuted" de (alt sınır) | %61.0 | – |
| MoritzLaurer DeBERTa-base | %52.4 (3 sınıf, 462 iddia) | – |
| **ctu-aic DeBERTa-large** | **%80.2** | **0.680** |

| ctu-aic güven eşiği | Modelde kalan iddia | Bunlarda doğruluk | LLM'e giden |
|---|---|---|---|
| 0.7 | %93 | %84.1 | 35 |
| 0.8 | %90 | %85.9 | 52 |
| **0.9** | **%82** | **%90.0** | **92** |
| 0.95 | %75 | %92.8 | 126 |

**Uyarı:** Bu test "kolay mod". Kanıt olarak AVeriTeC'teki temiz, insan yazımı soru-cevaplar verildi. Gerçek sistemde kanıt web aramasından geliyor; başarının düşmesi bekleniyor. Web kanıtıyla ölçüm (`experiments/ctu_live_averitec.py`) yazıldı ama arama engelleri yüzünden **tamamlanmadı**; Tavily ile yeniden çalıştırılmalı.

### Uçtan uca testler (gerçek haber linkleri)

| Haber | Gerçekte | Sistemin kararı | LLM | Not |
|---|---|---|---|---|
| BBC – Delhi protestosu (2026-10-10) | Gerçek | 5/5 Supported → Güvenilir | 3.5 Flash | LLM hakim hiç çağrılmadı |
| The Onion – sırtlan haberi | Hiciv | Hiciv | – | Arama/LLM yok, maliyet 0 |
| LA Times – Tupac haberinin geri çekme yazısı | Gerçek | 3 Supported, 2 NEE | 3.5 Flash | Link haberin kendisi değil, düzeltme yazısıydı |
| Denver Guardian – "FBI ajanı ölü bulundu" (2016, arşiv) | Uydurma | 2 Refuted, 3 NEE → Yanlış | 3.5 Flash | |
| Denver Guardian – "Florida seçmeni 7 kez oy verdi" (2016, arşiv) | Uydurma | 2 Refuted, 3 NEE → Yanlış | Flash-Lite | 3.5 Flash ile önceki denemede 5/5 NEE çıkmıştı |
| RT – "Callous Kallas" | Propaganda | 5/5 Supported | 3.5 Flash | Olgular doğru; propaganda çerçevede. Kaynak "deprecated". |
| Washington Post – Giuliani haberi | Düzeltilmiş haber | Sayfa çekilemedi | – | Bot engeli / ödeme duvarı |

Süre: haber başına ~35–55 sn. Bunun bir kısmı her çalıştırmada 1.7 GB'lık modelin yeniden yüklenmesi; sistem sunucu olarak sürekli açık kalırsa bu tekrar etmez.

## 6. Kurulum ve çalıştırma

```
pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu126
pip install transformers sentencepiece protobuf langgraph google-genai tavily-python trafilatura python-dotenv truststore
```

Proje kökünde `.env` dosyası (git'e girmez, herkes kendi anahtarını koyar):

```
GOOGLE_API_KEY=...
TAVILY_API_KEY=...
```

Çalıştırma:

```
python src/graph.py <haber-linki>
```

Not: `truststore` satırı, bilgisayardaki antivirüs HTTPS trafiğini incelediği için Python'un sertifika doğrulaması bozulmasın diye var. İlk çalıştırmada karar modeli (~1.7 GB) Hugging Face'ten iner.

## 7. Dosya yapısı

```
src/
  graph.py      LangGraph hattı: node'lar, graf, çalıştırma
  sources.py    Kaynak motoru (site → etiket)
  verdict.py    Karar modeli (ctu-aic)
dataset/        Kaynak listeleri + AVeriTeC
experiments/    Model testleri ve sonuçları
docs/           Raporlar (veri setleri, model testleri, bu rapor)
```

## 8. Bilinen sınırlar

- **Propaganda yakalanmıyor.** Sistem yalnız olgulara bakıyor; doğru olguları manipülatif çerçeveyle sunan haberleri (RT örneği) "doğru" buluyor. Tek sinyal kaynak etiketi.
- **Uydurma kişi/olaylarda kanıt yokluğu.** Hiç yaşanmamış bir olay için web'de çürüten kanıt olmayabilir; sistem bazen "kanıt yetersiz" diyor. `report` bu durumda kaynak bilinmiyorsa "Şüpheli" veriyor.
- **LLM kararları değişken.** Aynı haber farklı çalıştırmalarda farklı sonuç verebiliyor (Florida örneği).
- **Kaynak verileri temizlenmedi.** Ham CSV'ler kullanılıyor; platform siteleri (blogspot, medium) ve çakışan Wikipedia kararları içinde.
- **Hata yönetimi yok.** Tavily ya da Gemini hata verirse program duruyor (bilinçli; ilk sürümde hatayı görmek tercih edildi).

## 9. Açık işler

1. ~~Sayfa çekilemezse ~85 sn bekleniyordu~~ → Çözüldü (2026-10-11): indirme tek denemeli `requests` (10 sn zaman aşımı) ile yapılıyor; çekilemeyen sayfa 10 sn'de açık hatayla düşüyor.
2. Web kanıtıyla AVeriTeC ölçümü (Tavily ile) – sistemin gerçek başarısı.
3. Flash-Lite ile 3.5 Flash'ın iddia çıkarma kalitesini karşılaştırmak.
4. Propaganda tekniği modeli (aday veri: SemEval-2023 Task 3).
5. Kaynak verisinin temizlenmesi (platform siteleri, çakışan kararlar, hiciv listesinin genişletilmesi).
6. Arayüz (rapor sayfası: kırmızı/sarı işaretli cümleler, kanıt linkleri).
7. `README.md` eski fikri anlatıyor, güncellenmeli.
8. Hiçbir şey commit edilmedi; GitHub girişi düzeltilip ilk commit atılmalı.
