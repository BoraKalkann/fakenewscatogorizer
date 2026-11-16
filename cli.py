from backend import database
from engine.pipeline import analyze


def show(out):
    print(out["title"], "|", out["source"]["domain"], out["source"]["label"])
    for r in out.get("results", []):
        print(f"{r['verdict']:36} {r['confidence']:.2f} {r['decided_by']:9} | {r['text']}")
        for e in r["evidence"][:2]:
            print(f"{'':49}- [{e['source']}] {e['url']}")
    print(f"HABER: {out['verdict']} (skor {out['score']:+.2f})")
    if out["kind"]:
        print("TÜR:", out["kind"], "-", out["kind_reason"])

while url := input("\nHaber linki (çıkmak için Enter): ").strip():
    try:
        show(database.check_url(url, analyze))
    except Exception as e:
        print("Hata:", e)
