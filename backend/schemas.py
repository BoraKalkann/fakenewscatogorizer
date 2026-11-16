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
    source: Source
    verdict: str
    score: float
    kind: str
    kind_reason: str
    results: list[ClaimResult]


class ArticleSummary(BaseModel):
    url: str
    title: str
    domain: str
    verdict: str
    kind: str
    checked_at: str
