import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DB = Path(__file__).resolve().parent.parent / "cache.db"
VERSION = 2  
TRACKING = ("utm_", "fbclid", "gclid", "ref", "ocid", "cmpid")

con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE IF NOT EXISTS articles (
    url TEXT PRIMARY KEY, original_url TEXT, title TEXT, text TEXT, source TEXT,
    verdict TEXT, score REAL, kind TEXT, kind_reason TEXT, checked_at TEXT, version INTEGER);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY, article_url TEXT REFERENCES articles(url), claim TEXT,
    verdict TEXT, confidence REAL, decided_by TEXT, reason TEXT);
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
    row = con.execute("SELECT title, text, source, verdict, score, kind, kind_reason FROM articles WHERE url = ?",
                      (url,)).fetchone()
    if not row:
        return None
    title, text, source, verdict, score, kind, kind_reason = row
    domain, label = source.split(" / ")

    results = []
    for claim_id, claim, c_verdict, confidence, decided_by, reason in con.execute(
            "SELECT id, claim, verdict, confidence, decided_by, reason FROM claims WHERE article_url = ? ORDER BY id",
            (url,)):
        evidence = [{"url": e_url, "source": e_label, "text": snippet} for e_url, e_label, snippet in con.execute(
            "SELECT url, source_label, snippet FROM evidence WHERE claim_id = ?", (claim_id,))]
        results.append({"text": claim, "verdict": c_verdict, "confidence": confidence,
                        "decided_by": decided_by, "reason": reason, "evidence": evidence})

    return {"url": url, "title": title, "text": text, "source": {"domain": domain, "label": label},
            "results": results, "verdict": verdict, "score": score, "kind": kind, "kind_reason": kind_reason}


def put_article(original_url, out):
    url = norm_url(original_url)
    source = f"{out['source']['domain']} / {out['source']['label']}"
    with con:
        con.execute("INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (url, original_url, out["title"], out["text"], source, out["verdict"], out["score"],
                     out["kind"], out["kind_reason"], datetime.now().isoformat(timespec="seconds"), VERSION))
        for r in out.get("results", []):
            claim_id = con.execute(
                "INSERT INTO claims (article_url, claim, verdict, confidence, decided_by, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (url, r["text"], r["verdict"], r["confidence"], r["decided_by"], r["reason"])).lastrowid
            for e in r["evidence"]:
                con.execute("INSERT INTO evidence VALUES (?, ?, ?, ?)", (claim_id, e["url"], e["source"], e["text"]))
