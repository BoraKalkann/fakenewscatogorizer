# fakenewscatogorizer

Haber linki alır, haberdeki iddiaları web'de araştırır ve haberin doğru mu, yanlış mı, yanıltıcı mı olduğunu gerekçesiyle söyler. Haberin yanlış çıktığı durumda yanlışlığın türünü de belirtir. Sistem yalnızca İngilizce haberlerde çalışır.

## Nasıl çalışıyor

1. **Çekme:** Haber sayfası indirilir, başlık, tarih ve metin çıkarılır (`trafilatura`).
2. **Kaynak:** Sitenin güvenilirliğine bakılır (Wikipedia RSP listesi ve Lin 2023 puanları, `data/`). Site bir hiciv sitesiyse kontrol burada biter.
3. **İddialar:** Gemini, haberden en fazla 5 kontrol edilebilir iddia çıkarır.
4. **Her iddia için:** Fact-check sitelerinde ve web'de arama yapılır (Tavily), işe yarayan kanıtlar seçilir. Karar şu sırayla verilir:
   - Aynı iddiayı inceleyen bir fact-check bulunursa onun kararı kullanılır (`factcheck`).
   - Bulunamazsa DeBERTa NLI modeli karar verir (`nli`), ama yalnızca güveni 0.97 ve üstündeyse.
   - Güven düşükse kararı Gemini verir (`llm`).
5. **Rapor:** İddia kararlarından haber puanı ve sonucu hesaplanır, yanlış haberde tür belirlenir.

Sonuçlar `db/fakenews.db`'ye (SQLite) yazılır. Aynı link tekrar sorulduğunda cevap anında veritabanından gelir.

| Dosya | Görevi |
|---|---|
| `engine/pipeline.py` | Hattın kendisi (LangGraph), giriş noktası `analyze(url)` |
| `engine/llm.py` | Gemini çağrıları |
| `engine/nli.py` | DeBERTa NLI modeli |
| `engine/factcheck.py` | Fact-check sayfalarından karar okuma |
| `engine/sources.py` | Kaynak güvenilirliği |
| `backend/main.py` | FastAPI endpoint'leri |
| `backend/schemas.py` | API'nin istek/cevap şemaları |
| `backend/database.py` | SQLite veritabanı (`db/fakenews.db`) |
| `cli.py` | Terminalden deneme |

`engine/` sadece analiz yapar, veritabanını bilmez. Veritabanına bakmak ve sonucu kaydetmek `backend/`'in işidir.

## Kurulum

Python 3.11+ gerekir.

```
pip install -r requirements.txt
```

`.env.example` dosyasını `.env` adıyla kopyalayıp iki anahtarı doldurun: `GOOGLE_API_KEY` (Gemini) ve `TAVILY_API_KEY` (web araması). İlk çalıştırmada DeBERTa modeli (~1.7 GB) Hugging Face'ten iner. GPU varsa onu kullanır, yoksa CPU'da da çalışır.

Bütün komutlar proje klasöründen çalıştırılır. Terminalden denemek için:

```
python cli.py
```

## API (FastAPI)

```
uvicorn backend.main:app
```

Swagger arayüzü: http://127.0.0.1:8000/docs

| Endpoint | Ne yapar |
|---|---|
| `POST /api/check` | Gövde `{"url": "..."}`. Haberi kontrol eder ve aşağıdaki çıktıyı döndürür. Sayfa çekilemezse 400 döner. |
| `GET /api/articles` | Daha önce kontrol edilen haberlerin listesi (en yeni en üstte) |
| `GET /api/article?url=...` | Önbellekteki tek bir haberin sonucu. Yeni kontrol başlatmaz, haber yoksa 404 döner. |

## Motoru doğrudan kullanmak

```python
from backend import database
from engine.pipeline import analyze

out = database.check_url("https://...", analyze)   # önce veritabanına bakar, yoksa analiz edip kaydeder
```

- `engine.pipeline` import edilirken model belleğe yüklenir. Bu yüzden sunucu açılırken bir kez import edin, her istekte yeniden yüklemeyin.
- Yeni bir haberin kontrolü yaklaşık bir dakika sürebilir ve çağrı bu sırada bekletir. Arayüzde bir yükleniyor durumu gösterin.
- Sayfa çekilemezse `RuntimeError` fırlatılır. Bu hatayı kullanıcıya mesaj olarak gösterin.
- Her yeni kontrol Gemini ve Tavily kotası harcar, önbellekteki haberler ise harcamaz.

## Çıktı

`check_url` her durumda aynı biçimde sözlük (JSON) döndürür:

```json
{
  "url": "https://example.com/news/...",
  "title": "Haber başlığı",
  "date": "2024-05-01",
  "text": "Haberin tam metni...",
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

- **`verdict`** (haberin sonucu): `Güvenilir`, `Yanlış`, `Yanıltıcı`, `Şüpheli`, `Doğrulanamadı`, `Olgular doğru, kaynak güvenilmez`, `Hiciv`
- **`score`**: Kabaca -2 ile +2 arasında bir değer. Eksi değerler yanlış, artı değerler doğru yönü gösterir.
- **`kind`**: `Uydurma`, `Çarpıtma`, `Yanıltıcı`, `Sahte alıntı`, `Bilim dışı`, `Hiciv`. Haber yanlış değilse boş gelir.
- **`source.label`**: `generally_reliable`, `no_consensus`, `generally_unreliable`, `deprecated`, `blacklisted`, `multiple`, `satire`, `unknown`. `source.score` 0 ile 1 arasında bir sayıdır ya da `null` gelir.
- **`results[].verdict`** (iddianın sonucu): `Supported`, `Refuted`, `Not Enough Evidence`, `Conflicting Evidence/Cherrypicking`
- **`results[].decided_by`**: `factcheck`, `nli`, `llm`, `none` (kanıt bulunamadı). `factcheck` olduğunda `reason` fact-check sayfasının linkini, `rating` ise o sitenin verdiği etiketi içerir.
- **`results[].sentence`**: Haber metninde vurgulamak için kullanılabilir. Gemini bu cümleyi metinden kopyalar, ama birebir eşleşmediği durumlar olabilir.
- Hiciv sitelerinde `results` boş gelir.

## Veri

`data/wp_rsp.csv`: [Wikipedia: Reliable sources/Perennial sources](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources) (CC BY-SA 4.0). `data/lin2023_domain_pc1.csv`: [Lin et al. 2023](https://github.com/hauselin/domain-quality-ratings).

## Ekip

- Bora Kalkan (kaptan): sistem mimarisi
- Tuğba Karaca: veri hazırlama, değerlendirme
- İkbal Çanak: web frontend ve backend, test
