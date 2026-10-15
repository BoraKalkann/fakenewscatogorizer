"""Our full claim checker (src/graph.py check_claim) on a stratified AVeriTeC dev sample.

Every AVeriTeC claim was already fact-checked, so search can find the answer. Two modes:
  real : fact-check shortcut on, only the claim's own fact-check article is removed
  own  : every fact-check site is removed, the system must decide from other evidence
Tavily results and generated search questions are cached, so both modes share the same searches
(~4 credits per claim: 1 fact-check search + up to 3 question searches).
Not removed: pages published after the claim date. Tavily's end_date was tried (2026-10-15) and dropped:
11/30 searches came back empty, the rest lost relevance, accuracy fell from 60% to 20%.

Usage: python experiments/system_averitec.py [n_claims] [mode ...]
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import graph  # noqa: E402  (loads .env, Tavily client and the verdict model)
import factcheck  # noqa: E402
from sources import domain  # noqa: E402

DEV = ROOT / "dataset" / "averitec" / "dev.json"
OUT = ROOT / "experiments" / "results"
CACHE = OUT / "system_search_cache.json"
QCACHE = OUT / "system_questions_cache.json"
LABELS = [graph.REF, graph.SUP, graph.NEE, graph.CON]
FACT_WORDS = ("fact", "snopes", "politifact", "teyit", "leadstories", "boomlive", "altnews")


def sample(dev, n, seed=0):
    """Stratified: each label keeps its share of dev (largest remainder)."""
    by_label = {lab: [i for i, c in enumerate(dev) if c["label"] == lab] for lab in LABELS}
    share = {lab: n * len(ids) / len(dev) for lab, ids in by_label.items()}
    counts = {lab: int(s) for lab, s in share.items()}
    for lab in sorted(share, key=lambda l: share[l] - counts[l], reverse=True)[:n - sum(counts.values())]:
        counts[lab] += 1
    rng = random.Random(seed)
    return sorted(i for lab, ids in by_label.items() for i in rng.sample(ids, counts[lab]))


def norm(url):
    """https://web.archive.org/web/<date>/https://www.x.com/a/ → x.com/a"""
    if "web.archive.org/web/" in url:
        url = url.split("/", 5)[5]
    return url.split("://")[-1].removeprefix("www.").split("?")[0].rstrip("/").lower()


class FilteredTavily:
    """Stands in for graph.tavily: cached search, then drops what the mode forbids."""

    def __init__(self, client):
        self.client, self.cache = client, json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
        self.mode, self.claim = "real", None

    def search(self, query, **kw):
        key = json.dumps([query, kw], sort_keys=True)
        if key not in self.cache:
            self.cache[key] = self.client.search(query, **kw)["results"]
            CACHE.write_text(json.dumps(self.cache), encoding="utf-8")
        own = norm(self.claim.get("fact_checking_article") or "")
        keep = [h for h in self.cache[key] if not self.forbidden(h["url"], own)]
        return {"results": keep}

    def forbidden(self, url, own):
        if self.mode == "real":
            return bool(own) and norm(url) == own
        return factcheck.is_factcheck(url) or any(w in domain(url) for w in FACT_WORDS)


def cached_questions(make):
    """Same questions in both modes; otherwise Gemini's new wording means new searches and noise."""
    cache = json.loads(QCACHE.read_text("utf-8")) if QCACHE.exists() else {}

    def wrapped(claim):
        if claim not in cache:
            cache[claim] = make(claim)
            QCACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        return cache[claim]
    return wrapped


def run(dev, ids, mode, search):
    search.mode, rows = mode, []
    for k, i in enumerate(ids, 1):
        c = dev[i]
        search.claim = c
        own_site = domain(c.get("original_claim_url") or "") or "-no-site-"  # "" would match every site
        try:
            r = graph.check_claim({"claim": {"text": c["claim"], "sentence": c["claim"]}, "own_domain": own_site})
            r = r["results"][0]
            row = {"id": i, "gold": c["label"], "pred": r["verdict"], "by": r["decided_by"],
                   "conf": r["confidence"], "n_evidence": len(r["evidence"]), "reason": r["reason"]}
        except Exception as e:  # one failed claim should not stop the run
            row = {"id": i, "gold": c["label"], "pred": "ERROR", "by": "error", "conf": 0, "n_evidence": 0,
                   "reason": repr(e)[:300]}
        rows.append(row)
        print(f"  [{mode} {k}/{len(ids)}] gold={row['gold'][:10]:10} pred={row['pred'][:10]:10} by={row['by']}",
              flush=True)
    return rows


def report(rows, mode):
    n = len(rows)
    acc = sum(r["pred"] == r["gold"] for r in rows) / n
    f1s = []
    for lab in LABELS:
        tp = sum(r["pred"] == lab == r["gold"] for r in rows)
        p = tp / max(1, sum(r["pred"] == lab for r in rows))
        rec = tp / max(1, sum(r["gold"] == lab for r in rows))
        f1s.append(2 * p * rec / (p + rec) if p + rec else 0)
    majority = Counter(r["gold"] for r in rows).most_common(1)[0]
    lines = [f"mode: {mode}  claims: {n}",
             f"accuracy: {acc:.1%}   macro F1: {sum(f1s) / 4:.3f}",
             f"majority baseline ({majority[0]}): {majority[1] / n:.1%}",
             "per label F1: " + ", ".join(f"{lab[:12]} {f:.2f}" for lab, f in zip(LABELS, f1s)),
             "decided by:"]
    for by, group in sorted(Counter(r["by"] for r in rows).items()):
        hit = sum(r["pred"] == r["gold"] for r in rows if r["by"] == by)
        lines.append(f"  {by:9} {group:3}  correct {hit}/{group}")
    lines.append("confusion (gold -> pred):")
    for lab in LABELS:
        preds = Counter(r["pred"] for r in rows if r["gold"] == lab)
        lines.append(f"  {lab[:12]:12} " + ", ".join(f"{p[:12]} {k}" for p, k in preds.most_common()))
    return "\n".join(lines)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    modes = sys.argv[2:] or ["real", "own"]
    dev = json.load(open(DEV, encoding="utf-8"))
    ids = sample(dev, n)
    search = FilteredTavily(graph.tavily)
    graph.tavily = search
    graph.questions = cached_questions(graph.questions)
    OUT.mkdir(exist_ok=True)
    for mode in modes:
        rows = run(dev, ids, mode, search)
        text = report(rows, mode)
        (OUT / f"system_{mode}_predictions.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                                             encoding="utf-8")
        (OUT / f"system_{mode}_report.txt").write_text(text + "\n", encoding="utf-8")
        print(text + "\n")


if __name__ == "__main__":
    main()
