"""Test a ready-made NLI model as the verdict step, on AVeriTeC dev.

Evidence = the human-written question/answer pairs (gold evidence), so this is
an upper bound: in the real system evidence comes from web search.

Usage: python experiments/nli_baseline_averitec.py
"""
import json
from collections import Counter
from pathlib import Path

import truststore

# Use the Windows certificate store: antivirus HTTPS scanning (e.g. AVG) signs
# traffic with a root that Python's bundled certificates do not include.
truststore.inject_into_ssl()

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "dataset" / "averitec" / "dev.json"
OUT = ROOT / "experiments" / "results"
MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

# NLI label -> AVeriTeC verdict
NLI_TO_VERDICT = {"entailment": "Supported", "contradiction": "Refuted", "neutral": "Not Enough Evidence"}
THRESHOLDS = [0.0, 0.5, 0.7, 0.8, 0.9, 0.95]


def evidence_text(claim):
    parts = []
    for q in claim["questions"]:
        answers = " ".join(a["answer"] for a in q["answers"] if a.get("answer"))
        parts.append(f"{q['question']} {answers}")
    return " ".join(parts)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.load(open(DEV, encoding="utf-8"))
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    id2label = model.config.id2label

    rows = []
    with torch.no_grad():
        for i, c in enumerate(data):
            enc = tok(evidence_text(c), c["claim"], truncation="only_first",
                      max_length=512, return_tensors="pt")
            probs = torch.softmax(model(**enc).logits[0], dim=-1)
            conf, idx = probs.max(dim=-1)
            rows.append({
                "i": i, "gold": c["label"],
                "pred": NLI_TO_VERDICT[id2label[idx.item()].lower()],
                "conf": round(conf.item(), 4),
            })
            if (i + 1) % 100 == 0:
                print(f"{i + 1}/{len(data)}")

    (OUT / "nli_baseline_predictions.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    # The 4th AVeriTeC class has no NLI equivalent; report it separately.
    main_rows = [r for r in rows if r["gold"] != "Conflicting Evidence/Cherrypicking"]
    lines = [f"model: {MODEL}", f"dev claims: {len(rows)} (scored: {len(main_rows)}, "
             f"conflicting excluded: {len(rows) - len(main_rows)})", ""]
    lines.append("threshold | kept by model | accuracy on kept | sent to LLM")
    for t in THRESHOLDS:
        kept = [r for r in main_rows if r["conf"] >= t]
        acc = sum(r["pred"] == r["gold"] for r in kept) / len(kept) if kept else 0
        lines.append(f"{t:>9} | {len(kept):>4} ({len(kept)/len(main_rows):.0%}) | {acc:.1%} | "
                     f"{len(main_rows) - len(kept)}")
    lines.append("")
    lines.append("confusion (gold -> pred), all scored claims:")
    for (g, p), n in sorted(Counter((r["gold"], r["pred"]) for r in main_rows).items()):
        lines.append(f"  {g:22} -> {p:22} {n}")
    conflicting = Counter(r["pred"] for r in rows if r["gold"] == "Conflicting Evidence/Cherrypicking")
    lines.append(f"\nconflicting/cherrypicking predicted as: {dict(conflicting)}")
    report = "\n".join(lines)
    (OUT / "nli_baseline_report.txt").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
