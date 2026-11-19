# Fake News Detector (fakenewscatogorizer)

Haber linki alır, haberdeki iddiaları web'de araştırır ve haberin doğru mu, yanlış mı, yanıltıcı mı olduğunu gerekçesiyle söyler. Haber yanlışsa yanlışlığın türünü de belirtir (uydurma, çarpıtma, sahte alıntı...). Sistem yalnızca İngilizce haberlerde çalışır.

## Kurulum (adım adım)

### 0. Gerekenler

| Ne | Nereden | Not |
|---|---|---|
| Git | https://git-scm.com | |
| Python 3.11 veya üstü | https://www.python.org | Kurarken "Add Python to PATH" kutusunu işaretleyin |
| Node.js (LTS) | https://nodejs.org | Arayüz için |
| Gemini API anahtarı | https://aistudio.google.com/apikey | Ücretsiz plan yeterli |
| Tavily API anahtarı | https://app.tavily.com | Web araması için; ücretsiz planda ayda 1000 kredi var |

Diskte yaklaşık 5 GB boş yer gerekir (Python paketleri ve 1,7 GB'lık doğrulama modeli). Ekran kartı (NVIDIA) şart değil, yoksa model işlemcide çalışır.

### 1. Projeyi indirin

```
git clone https://github.com/BoraKalkann/fakenewscatogorizer.git
cd fakenewscatogorizer
```

Bundan sonraki bütün komutlar bu klasörde çalıştırılır.

### 2. Python paketlerini kurun

Projeye özel bir sanal ortam açmanızı öneririz, böylece paketler bilgisayardaki diğer projelere karışmaz:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Mac/Linux'ta ikinci satır `source .venv/bin/activate` olur. Yeni bir terminal açtığınızda sanal ortamı tekrar etkinleştirmeyi (`.venv\Scripts\activate`) unutmayın.

NVIDIA ekran kartınız varsa ve modeli onda çalıştırmak isterseniz, yukarıdakilerden sonra şunu da çalıştırın:

```
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

### 3. API anahtarlarını girin

`.env.example` dosyasını `.env` adıyla kopyalayın ve iki anahtarı yazın:

```
copy .env.example .env
```

(Mac/Linux: `cp .env.example .env`). Sonra `.env` dosyasını açıp doldurun:

```
GOOGLE_API_KEY=buraya-gemini-anahtari
TAVILY_API_KEY=buraya-tavily-anahtari
```

`.env` GitHub'a gönderilmez; anahtarlarınızı kimseyle paylaşmayın.

### 4. Backend'i başlatın

```
uvicorn backend.main:app
```

İlk açılışta doğrulama modeli (1,7 GB) Hugging Face'ten iner; bu birkaç dakika sürebilir. Terminalde `Application startup complete` yazısını görünce backend hazırdır. Kontrol etmek için tarayıcıda http://127.0.0.1:8000/docs adresini açın (Swagger sayfası).

### 5. Arayüzü başlatın

Backend açık kalsın. **İkinci bir terminal** açın:

```
cd frontend
npm install
npm run dev
```

`npm install` yalnızca ilk seferde gerekir. Tarayıcıda http://localhost:5173 adresini açın, bir haber linki yapıştırıp **Kontrol et**'e basın.

Denemek için bilinen bir sahte haber (2016, İnternet Arşivi kopyası):

```
https://web.archive.org/web/20161111145042/http://wtoe5news.com/us-election/pope-francis-shocks-world-endorses-donald-trump-for-president-releases-statement/
```

## Sık karşılaşılan sorunlar

- **`npm` / `python` / `uvicorn` bulunamadı:** Programı kurduktan sonra terminali (VS Code kullanıyorsanız VS Code'u tamamen) kapatıp açın. `uvicorn` için sanal ortamın etkin olduğundan emin olun.
- **Arayüz "Sunucuyla bağlantı koptu" diyor:** Backend çalışmıyor ya da henüz açılmamış. 4. adımdaki terminale bakın.
- **"Sayfa çekilemedi":** Bazı siteler (New York Times, Wall Street Journal gibi abonelikli siteler) otomatik okumayı engelliyor. Aynı haberi başka bir kaynaktan deneyin.
- **Kodu güncelledikten (`git pull`) sonra kaydetme hatası:** Veritabanının yapısı değişmiş olabilir. Backend'i durdurup `db\fakenews.db` dosyasını silin ve yeniden başlatın; veritabanı kendiliğinden yeniden oluşur (eski analizler gider).
- **Kota:** Her yeni haber analizi yaklaşık 20 Tavily kredisi ve birkaç Gemini çağrısı harcar (Tavily'nin ücretsiz planı ayda yaklaşık 50 habere yeter). Daha önce analiz edilen haberler veritabanından gelir, kota harcamaz. Hiciv sitelerinde de arama yapılmaz.

## Nasıl çalışıyor

1. **Çekme:** Haber sayfası indirilir; başlık, tarih, kapak resmi ve metin çıkarılır (`trafilatura`).
2. **Kaynak:** Sitenin güvenilirliğine bakılır (Wikipedia RSP listesi ve Lin 2023 puanları, `data/`). Site bir hiciv sitesiyse kontrol burada biter.
3. **İddialar:** Gemini haberden en fazla 5 kontrol edilebilir iddia çıkarır.
4. **Her iddia için:** Fact-check sitelerinde ve web'de arama yapılır (Tavily), işe yarayan kanıtlar seçilir. Karar şu sırayla verilir:
   - Aynı iddiayı inceleyen bir fact-check bulunursa onun kararı kullanılır (`factcheck`).
   - Bulunamazsa DeBERTa doğrulama modeli karar verir (`nli`), ama yalnızca güveni 0.97 ve üstündeyse.
   - Güven düşükse kararı Gemini verir (`llm`).
5. **Rapor:** İddia kararlarından haberin kararı hesaplanır; haber yanlışsa yanlışlığın türü belirlenir.

Sonuçlar `db/fakenews.db`'ye (SQLite) yazılır. Aynı link tekrar sorulduğunda cevap anında veritabanından gelir.

| Dosya | Görevi |
|---|---|
| `engine/pipeline.py` | Hattın kendisi (LangGraph); `analyze(url)` ve adım adım çalışan `analyze_stream(url)` |
| `engine/llm.py` | Gemini çağrıları |
| `engine/nli.py` | DeBERTa doğrulama modeli |
| `engine/factcheck.py` | Fact-check sayfalarından karar okuma |
| `engine/sources.py` | Kaynak güvenilirliği ve hiciv siteleri listesi |
| `backend/main.py` | FastAPI endpoint'leri |
| `backend/schemas.py` | API'nin istek/cevap şemaları |
| `backend/database.py` | SQLite veritabanı (`db/fakenews.db`) |
| `frontend/src/App.jsx` | Ekranlar arası geçiş ve backend bağlantısı |
| `frontend/src/Home.jsx`, `Analyzing.jsx`, `Result.jsx` | Giriş, analiz sürüyor ve sonuç ekranları |
| `frontend/src/labels.js` | Türkçe etiketler, renkler ve karar açıklamaları |
| `cli.py` | Arayüz olmadan terminalden deneme (`python cli.py`) |

`engine/` sadece analiz yapar, veritabanını bilmez. Veritabanına bakmak ve sonucu kaydetmek `backend/`'in işidir.

## API (FastAPI)

Swagger arayüzü: http://127.0.0.1:8000/docs

| Endpoint | Ne yapar |
|---|---|
| `POST /api/check` | Gövde `{"url": "..."}`. Haberi kontrol eder ve aşağıdaki çıktıyı döndürür. Sayfa çekilemezse 400 döner. |
| `GET /api/articles` | Daha önce kontrol edilen haberlerin listesi (en yeni en üstte) |
| `GET /api/article?url=...` | Veritabanındaki tek bir haberin sonucu. Yeni kontrol başlatmaz, haber yoksa 404 döner. |
| `GET /api/check/stream?url=...` | Arayüzün kullandığı canlı sürüm (Server-Sent Events). Analiz sürerken her adım bitince bir olay gönderir: `fetch_article` (başlık, tarih, resim), `source_check`, `extract_claims`, `check_claim` (iddia başına bir kez), `report`, `classify`; en sonda `done` ile tam çıktıyı, hata olursa `failed` ile `{"detail": ...}` gönderir. Kayıtlı haberde doğrudan `done` gelir. |

Arayüz geliştirirken `/api` ile başlayan istekler Vite tarafından backend'e (8000 portu) yönlendirilir; kodda yalnız `fetch("/api/...")` yazmak yeterli.

Motoru Python'dan doğrudan kullanmak için:

```python
from backend import database
from engine.pipeline import analyze

out = database.check_url("https://...", analyze)   # önce veritabanına bakar, yoksa analiz edip kaydeder
```

`engine.pipeline` import edilirken model belleğe yüklenir; bir kez import edin. Sayfa çekilemezse `RuntimeError` fırlatılır.

## Çıktı

API her durumda aynı biçimde JSON döndürür:

```json
{
  "url": "https://example.com/news/...",
  "title": "Haber başlığı",
  "date": "2024-05-01",
  "text": "Haberin tam metni...",
  "image": "https://.../kapak.jpg",
  "source": {"domain": "example.com", "label": "generally_reliable", "score": 0.91},
  "verdict": "Yanlış",
  "score": -0.85,
  "kind": "Uydurma",
  "kind_reason": "Türün tek cümlelik gerekçesi.",
  "results": [
    {
      "text": "Kontrol edilen iddia",
      "sentence": "Haberde iddianın geçtiği cümle",
      "verdict": "Refuted",
      "confidence": 1.0,
      "decided_by": "factcheck",
      "reason": "Gerekçe",
      "rating": "False",
      "evidence": [{"url": "https://...", "source": "generally_reliable", "text": "Kanıt parçası"}]
    }
  ]
}
```

Alanların alabileceği değerler:

- **`verdict`** (haberin kararı): `Güvenilir`, `Yanlış`, `Yanıltıcı`, `Şüpheli`, `Doğrulanamadı`, `Olgular doğru, kaynak güvenilmez`, `Hiciv`
- **`kind`** (yanlışlığın türü): `Uydurma`, `Çarpıtma`, `Yanıltıcı`, `Sahte alıntı`, `Bilim dışı`, `Hiciv`. Yalnızca haber `Yanlış`, `Yanıltıcı`, `Şüpheli` ya da `Hiciv` çıkarsa dolu gelir; diğer kararlarda boştur.
- **`score`**: Kabaca -2 ile +2 arasında. Eksi değerler yanlış, artı değerler doğru yönü gösterir.
- **`source.label`**: `generally_reliable`, `no_consensus`, `generally_unreliable`, `deprecated`, `blacklisted`, `multiple`, `satire`, `unknown`. `source.score` 0 ile 1 arasında bir sayıdır ya da `null` gelir.
- **`results[].verdict`** (iddianın kararı): `Supported`, `Refuted`, `Not Enough Evidence`, `Conflicting Evidence/Cherrypicking`
- **`results[].decided_by`**: `factcheck`, `nli`, `llm`, `none` (kanıt bulunamadı). `factcheck` olduğunda `reason` fact-check sayfasının linkini, `rating` o sitenin verdiği etiketi içerir.
- **`results[].sentence`**: Haber metninde vurgulamak için. Gemini bu cümleyi metinden kopyalar, ama birebir eşleşmediği durumlar olabilir.
- **`image`**: Haberin kapak resminin linki; resmi olmayan sayfalarda `null`. `GET /api/articles` listesinde de var.
- Hiciv sitelerinde `results` boş gelir.

## Veri

`data/wp_rsp.csv`: [Wikipedia: Reliable sources/Perennial sources](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources) (CC BY-SA 4.0). `data/lin2023_domain_pc1.csv`: [Lin et al. 2023](https://github.com/hauselin/domain-quality-ratings).

## Ekip

- Bora Kalkan: sistem mimarisi, doğrulama hattı
- Tuğba Karaca: veri hazırlama, değerlendirme
- İkbal Çanak: web arayüzü (ön ve arka uç), test
