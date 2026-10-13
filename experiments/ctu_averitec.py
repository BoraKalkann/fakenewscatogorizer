"""Test ctu-aic/deberta-v3-large-AVeriTeC-nli as the verdict step, on AVeriTeC dev.

The model card names its 4 outputs LABEL_0..LABEL_3 only. The label mapping and
the input order (evidence/claim) are chosen on 150 TRAIN claims, never on dev.
Evidence = gold question/answer pairs, so this is an upper bound.

Usage: python experiments/ctu_averitec.py
"""
import itertools
import json
import random
from collections import Counter
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # see nli_baseline_averitec.py

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset" / "averitec"
OUT = ROOT / "experiments" / "results"
MODEL = "ctu-aic/deberta-v3-large-AVeriTeC-nli"
LABELS = ["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
THRESHOLDS = [0.0, 0.5, 0.7, 0.8, 0.9, 0.95]
torch.set_num_threads(torch.get_num_threads())


def evidence_text(claim):
    return " ".join(
        f"{q['question']} " + " ".join(a["answer"] for a in q["answers"] if a.get("answer"))
        for q in claim["questions"])


def predict(tok, model, claims, order):
    out = []
    with torch.no_grad():
        for i, c in enumerate(claims):
            a, b = (evidence_text(c), c["claim"]) if order == "evidence_first" else (c["claim"], evidence_text(c))
            enc = tok(a, b, truncation="longest_first", max_length=512, return_tensors="pt")
            out.append(torch.softmax(model(**enc).logits[0], dim=-1).tolist())
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(claims)}", flush=True)
    return out


def best_mapping(probs, gold):
    """Label permutation that maximises accuracy on the calibration set."""
    best = None
    for perm in itertools.permutations(LABELS):
        acc = sum(perm[max(range(4), key=p.__getitem__)] == g for p, g in zip(probs, gold)) / len(gold)
        if best is None or acc > best[0]:
            best = (acc, perm)
    return best


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()

    train = json.load(open(DATA / "train.json", encoding="utf-8"))
    random.seed(0)
    calib = random.sample(train, 150)
    gold_c = [c["label"] for c in calib]
    choice = None
    for order in ["evidence_first", "claim_first"]:
        print(f"calibration, {order}")
        acc, perm = best_mapping(predict(tok, model, calib, order), gold_c)
        print(f"  best accuracy {acc:.1%} with {perm}")
        if choice is None or acc > choice[0]:
            choice = (acc, order, perm)
    _, order, perm = choice

    dev = json.load(open(DATA / "dev.json", encoding="utf-8"))
    print(f"dev, {order}")
    probs = predict(tok, model, dev, order)
    rows = [{"i": i, "gold": c["label"], "pred": perm[max(range(4), key=p.__getitem__)],
             "conf": round(max(p), 4)} for i, (c, p) in enumerate(zip(dev, probs))]
    (OUT / "ctu_predictions.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    n = len(rows)
    majority = Counter(r["gold"] for r in rows).most_common(1)[0]
    lines = [f"model: {MODEL}", f"input order: {order}", f"label mapping (from 150 train claims): {perm}",
             f"dev claims: {n}, majority class '{majority[0]}' = {majority[1] / n:.1%}", "",
             "threshold | kept by model | accuracy on kept | sent to LLM"]
    for t in THRESHOLDS:
        kept = [r for r in rows if r["conf"] >= t]
        acc = sum(r["pred"] == r["gold"] for r in kept) / len(kept) if kept else 0
        lines.append(f"{t:>9} | {len(kept):>4} ({len(kept) / n:.0%}) | {acc:.1%} | {n - len(kept)}")
    f1s = []
    for lab in LABELS:
        tp = sum(r["pred"] == lab and r["gold"] == lab for r in rows)
        p = tp / max(1, sum(r["pred"] == lab for r in rows))
        rec = tp / max(1, sum(r["gold"] == lab for r in rows))
        f1s.append(2 * p * rec / (p + rec) if p + rec else 0)
    lines.append(f"\nmacro F1 (all dev): {sum(f1s) / 4:.3f}")
    lines.append("\nconfusion (gold -> pred):")
    for (g, p), k in sorted(Counter((r["gold"], r["pred"]) for r in rows).items()):
        lines.append(f"  {g:36} -> {p:36} {k}")
    report = "\n".join(lines)
    (OUT / "ctu_report.txt").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
