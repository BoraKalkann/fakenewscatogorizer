import json
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from backend import database
from backend.schemas import Article, ArticleSummary, CheckRequest
from engine.pipeline import analyze, analyze_stream  # NLI modeli burada, sunucu açılırken bir kez yükleniyor

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


# --- Canlı ilerleme (Server-Sent Events) ---

def sse(event, data):
    """Bir SSE olayı: tarayıcıdaki EventSource bunu `event` adıyla alır."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_events(url):
    # haber daha önce kontrol edildiyse sonucu hemen gönder
    saved = database.get_article(url)
    if saved:
        yield sse("done", saved)
        return

    try:
        for step, values in analyze_stream(url):
            if step == "done":
                # bütün adımlar bitti: kaydet ve tam sonucu veritabanından okuyup gönder
                database.put_article(url, values)
                yield sse("done", database.get_article(url))
            elif step == "fetch_article":
                # haber metnini burada göndermeye gerek yok, sonuçta zaten geliyor
                yield sse(step, {"title": values["title"], "date": values["date"], "image": values["image"]})
            else:
                yield sse(step, values)
    except RuntimeError as e:  # sayfa çekilemedi
        yield sse("failed", {"detail": str(e)})
    except Exception:
        traceback.print_exc()  # hatanın ayrıntısı backend terminalinde görünsün
        yield sse("failed", {"detail": "Analiz sırasında bir hata oluştu. Lütfen tekrar deneyin."})


@app.get("/api/check/stream")
def check_stream(url: str):
    """Haberi kontrol ederken her adımı anında gönderir (Server-Sent Events). Arayüz bunu kullanır.
    Olaylar: fetch_article, source_check, extract_claims, check_claim (iddia başına bir kez),
    report, classify, done (tam sonuç) ve hata olursa failed."""
    return StreamingResponse(stream_events(url), media_type="text/event-stream")
