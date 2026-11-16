from fastapi import FastAPI, HTTPException

from backend import database
from backend.schemas import Article, ArticleSummary, CheckRequest
from engine.pipeline import analyze  # NLI modeli burada, sunucu açılırken bir kez yükleniyor

app = FastAPI(title="fakenewscatogorizer API",
              description="Haber linkindeki iddiaları web'de araştırıp haberin doğruluğunu ve yanlışlık türünü döndürür.")


@app.post("/api/check", response_model=Article)
def check(req: CheckRequest):
    """Haberi kontrol eder. Daha önce kontrol edildiyse sonuç veritabanından anında gelir, değilse yaklaşık bir dakika sürer."""
    try:
        return database.check_url(req.url, analyze)
    except RuntimeError as e:  # sayfa çekilemedi
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/articles", response_model=list[ArticleSummary])
def articles():
    """Daha önce kontrol edilmiş haberlerin listesi (en yeni önce)."""
    return database.list_articles()


@app.get("/api/article", response_model=Article)
def article(url: str):
    """Veritabanındaki tek bir haberin tam sonucu. Yeni kontrol başlatmaz."""
    out = database.get_article(url)
    if not out:
        raise HTTPException(status_code=404, detail="Bu haber henüz kontrol edilmedi.")
    return out
