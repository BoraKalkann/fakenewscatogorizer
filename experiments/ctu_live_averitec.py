"""ctu-aic verdict model on AVeriTeC dev with LIVE web evidence (DuckDuckGo).

Evidence = top search snippets for the claim text. Fact-check sites are removed
so the model cannot read the answer directly. No date filter: results published
after the claim may still leak.

Usage: python experiments/ctu_live_averitec.py
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import truststore

truststore.inject_into_ssl()  # see nli_baseline_averitec.py

import torch
from ddgs import DDGS
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "dataset" / "averitec" / "dev.json"
OUT = ROOT / "experiments" / "results"
CACHE = OUT / "live_search_cache.json"
MODEL = "ctu-aic/deberta-v3-large-AVeriTeC-nli"
LABELS = ["Refuted", "Supported", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]  # see ctu_report.txt
FACTCHECK = ["politifact.com", "snopes.com", "factcheck.org", "fullfact.org", "africacheck.org",
             "factcheck.afp.com", "reuters.com/fact-check", "apnews.com/hub/ap-fact-check",
             "boomlive.in", "altnews.in", "leadstories.com", "checkyourfact.com", "factly.in",
             "newsmeter.in", "vishvasnews.com", "thequint.com/news/webqoof", "usatoday.com/story/news/factcheck",
             "washingtonpost.com/politics/fact-checker", "logically.ai", "misbar.com", "dubawa.org",
             "pesacheck.org", "healthfeedback.org", "sciencefeedback.co", "teyit.org"]


def host(url):
    return (urlparse(url).hostname or "").removeprefix("www.")


def blocked(url, claim):
    u = url.lower()
    own = host(claim.get("fact_checking_article") or "")
    return any(f in u for f in FACTCHECK) or (own and own in host(url)) or "fact" in host(url)


def search_one(text):
    for attempt in range(3):
        try:
            return DDGS().text(text, max_results=10)
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None  # failed: not cached, retried in the next round


def search(claims):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    while todo := [i for i in range(len(claims)) if str(i) not in cache]:
        print(f"  searching {len(todo)} claims", flush=True)
        with ThreadPoolExecutor(3) as pool:
            for i, hits in zip(todo, pool.map(lambda i: search_one(claims[i]["claim"]), todo)):
                if hits is not None:
                    cache[str(i)] = hits
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        time.sleep(30)
    return cache


def main():
    dev = json.load(open(DEV, encoding="utf-8"))
    results = search(dev)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()

    rows, removed = [], 0
    with torch.no_grad():
        for i, c in enumerate(dev):
            hits = [r for r in results[str(i)] if not blocked(r["href"], c)]
            removed += len(results[str(i)]) - len(hits)
            evidence = " ".join(f"{r['title']}. {r['body']}" for r in hits[:5])
            enc = tok(c["claim"], evidence, truncation="longest_first", max_length=512, return_tensors="pt")
            p = torch.softmax(model(**enc).logits[0], dim=-1)
            rows.append({"gold": c["label"], "pred": LABELS[p.argmax().item()], "conf": round(p.max().item(), 4),
                         "n_evidence": len(hits[:5])})
            if (i + 1) % 100 == 0:
                print(f"  scored {i + 1}/{len(dev)}", flush=True)

    n = len(rows)
    acc = sum(r["pred"] == r["gold"] for r in rows) / n
    f1s = []
    for lab in LABELS:
        tp = sum(r["pred"] == lab == r["gold"] for r in rows)
        p = tp / max(1, sum(r["pred"] == lab for r in rows))
        rec = tp / max(1, sum(r["gold"] == lab for r in rows))
        f1s.append(2 * p * rec / (p + rec) if p + rec else 0)
    kept = [r for r in rows if r["conf"] >= 0.9]
    acc90 = sum(r["pred"] == r["gold"] for r in kept) / len(kept) if kept else 0
    report = (f"model: {MODEL}\nevidence: DuckDuckGo top-5 snippets, fact-check sites removed ({removed} results)\n"
              f"claims without evidence: {sum(r['n_evidence'] == 0 for r in rows)}\n"
              f"accuracy: {acc:.1%}\nmacro F1: {sum(f1s) / 4:.3f}\n"
              f"threshold 0.9: kept {len(kept)} ({len(kept) / n:.0%}), accuracy {acc90:.1%}")
    (OUT / "ctu_live_predictions.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (OUT / "ctu_live_report.txt").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
