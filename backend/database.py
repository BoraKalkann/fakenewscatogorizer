import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DB = Path(__file__).resolve().parents[1] / "db" / "fakenews.db"
VERSION = 3
TRACKING = ("utm_", "fbclid", "gclid", "ref", "ocid", "cmpid")

DB.parent.mkdir(exist_ok=True)
con = sqlite3.connect(DB, check_same_thread=False)  # FastAPI istekleri farklı thread'lerden gelir
con.executescript("""
CREATE TABLE IF NOT EXISTS articles (
    url TEXT PRIMARY KEY, original_url TEXT, title TEXT, date TEXT, text TEXT,
    source_domain TEXT, source_label TEXT, source_score REAL,
    verdict TEXT, score REAL, kind TEXT, kind_reason TEXT, checked_at TEXT, version INTEGER);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY, article_url TEXT REFERENCES articles(url), claim TEXT, sentence TEXT,
    verdict TEXT, confidence REAL, decided_by TEXT, reason TEXT, rating TEXT);
CREATE TABLE IF NOT EXISTS evidence (
    claim_id INTEGER REFERENCES claims(id), url TEXT, source_label TEXT, snippet TEXT);
""")


def norm_url(url):
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(TRACKING)]
    return urlunsplit(("https", host, parts.path.rstrip("/"), urlencode(query), ""))


def get_article(url):
    url = norm_url(url)
    row = con.execute("SELECT title, date, text, source_domain, source_label, source_score, "
                      "verdict, score, kind, kind_reason FROM articles WHERE url = ?", (url,)).fetchone()
    if not row:
        return None
    title, date, text, s_domain, s_label, s_score, verdict, score, kind, kind_reason = row

    # iddialar ve her iddianın kanıtları
    results = []
    claim_rows = con.execute("SELECT id, claim, sentence, verdict, confidence, decided_by, reason, rating "
                             "FROM claims WHERE article_url = ? ORDER BY id", (url,)).fetchall()
    for claim_id, claim, sentence, c_verdict, confidence, decided_by, reason, rating in claim_rows:
        evidence = []
        for e_url, e_label, snippet in con.execute(
                "SELECT url, source_label, snippet FROM evidence WHERE claim_id = ?", (claim_id,)):
            evidence.append({"url": e_url, "source": e_label, "text": snippet})
        results.append({"text": claim, "sentence": sentence, "verdict": c_verdict, "confidence": confidence,
                        "decided_by": decided_by, "reason": reason, "rating": rating, "evidence": evidence})

    return {"url": url, "title": title, "date": date, "text": text,
            "source": {"domain": s_domain, "label": s_label, "score": s_score},
            "results": results, "verdict": verdict, "score": score, "kind": kind, "kind_reason": kind_reason}


def list_articles():
    rows = con.execute("SELECT url, title, source_domain, verdict, kind, checked_at "
                       "FROM articles ORDER BY checked_at DESC").fetchall()
    articles = []
    for url, title, s_domain, verdict, kind, checked_at in rows:
        articles.append({"url": url, "title": title, "domain": s_domain, "verdict": verdict,
                         "kind": kind, "checked_at": checked_at})
    return articles


def check_url(url, analyze):
    """Önce veritabanına bakar; haber yoksa analyze ile kontrol edip kaydeder.
    Sonuç her durumda veritabanından okunur, böylece çıktı hep aynı biçimdedir."""
    hit = get_article(url)
    if hit:
        return hit
    out = analyze(url)
    put_article(url, out)
    return get_article(url)


def put_article(original_url, out):
    url = norm_url(original_url)
    source = out["source"]
    with con:
        con.execute("INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (url, original_url, out["title"], out["date"], out["text"],
                     source["domain"], source["label"], source["score"],
                     out["verdict"], out["score"], out["kind"], out["kind_reason"],
                     datetime.now().isoformat(timespec="seconds"), VERSION))
        for r in out.get("results", []):
            claim_id = con.execute(
                "INSERT INTO claims (article_url, claim, sentence, verdict, confidence, decided_by, reason, rating) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (url, r["text"], r["sentence"], r["verdict"], r["confidence"], r["decided_by"], r["reason"],
                 r["rating"])).lastrowid
            for e in r["evidence"]:
                con.execute("INSERT INTO evidence VALUES (?, ?, ?, ?)", (claim_id, e["url"], e["source"], e["text"]))
