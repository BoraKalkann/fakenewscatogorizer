from pydantic import BaseModel


# --- İstek ---

class CheckRequest(BaseModel):
    url: str


# --- Cevaplar (Swagger'da görünen biçim) ---

class Evidence(BaseModel):
    url: str
    source: str
    text: str


class ClaimResult(BaseModel):
    text: str
    sentence: str
    verdict: str
    confidence: float
    decided_by: str
    reason: str
    rating: str
    evidence: list[Evidence]


class Source(BaseModel):
    domain: str
    label: str
    score: float | None


class Article(BaseModel):
    url: str
    title: str
    date: str
    text: str
    image: str | None   # haberin kapak resmi linki; yoksa null
    source: Source
    verdict: str
    score: float
    kind: str
    kind_reason: str
    results: list[ClaimResult]


class ArticleSummary(BaseModel):
    url: str
    title: str
    image: str | None
    domain: str
    verdict: str
    kind: str
    checked_at: str
