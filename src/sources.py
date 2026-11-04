import csv
from pathlib import Path
from urllib.parse import urlparse

DATA = Path(__file__).resolve().parents[1] / "dataset"
SATIRE = {"theonion.com", "babylonbee.com", "clickhole.com", "thebeaverton.com", "newsthump.com"}

wp = {}
for r in csv.DictReader(open(DATA / "wp_rsp.csv", encoding="utf-8")):
    for d in r["domains"].split(";"):
        if d:
            wp.setdefault(d, r["status"])
lin = {r["domain"]: float(r["pc1"]) for r in csv.DictReader(open(DATA / "lin2023_domain_pc1.csv", encoding="utf-8"))}


def domain(url):
    if "web.archive.org/web/" in url:  
        url = url.split("/", 5)[5]
    return (urlparse(url).hostname or "").removeprefix("www.")


def lin_label(score):
    if score >= 0.75:
        return "generally_reliable"
    if score < 0.35:
        return "deprecated"
    return "no_consensus"


def lookup(url):
    parts = domain(url).split(".")
    candidates = [".".join(parts[i:]) for i in range(len(parts) - 1)] 
    for table, label in ((SATIRE, "satire"), (wp, None), (lin, "lin")):
        for d in candidates:
            if d in table:
                if label == "lin":
                    label = lin_label(lin[d])
                return {"domain": d, "label": label or wp[d], "score": lin.get(d)}
    return {"domain": domain(url), "label": "unknown", "score": None}
