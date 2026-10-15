"""AVeriTeC json → csv (opens in Excel; utf-8 with BOM).

<split>.csv           one row per claim; lists joined with "; ", evidence as readable Q/A text
<split>_evidence.csv  one row per answer: claim_id, question, answer, answer_type, source_url

Usage: python dataset/averitec/to_csv.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ["claim_id", "claim", "label", "justification", "claim_date", "speaker", "reporting_source",
          "location_ISO_code", "claim_types", "fact_checking_strategies", "original_claim_url",
          "fact_checking_article", "required_reannotation", "n_questions", "evidence"]
EVIDENCE = ["claim_id", "question", "answer", "answer_type", "boolean_explanation", "source_url", "source_medium"]


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


for split in ("train", "dev"):
    claims, answers = [], []
    for i, c in enumerate(json.load(open(HERE / f"{split}.json", encoding="utf-8"))):
        qa = []
        for q in c.get("questions") or []:
            for a in q.get("answers") or []:
                answers.append({"claim_id": i, "question": q["question"], **a})
            qa.append(f"Q: {q['question']}\nA: " + " | ".join(a.get("answer", "") for a in q.get("answers") or []))
        claims.append({**c, "claim_id": i, "n_questions": len(c.get("questions") or []), "evidence": "\n".join(qa),
                       "claim_types": "; ".join(c.get("claim_types") or []),
                       "fact_checking_strategies": "; ".join(c.get("fact_checking_strategies") or [])})
    write(HERE / f"{split}.csv", FIELDS, claims)
    write(HERE / f"{split}_evidence.csv", EVIDENCE, answers)
    print(f"{split}: {len(claims)} claims, {len(answers)} answers")
