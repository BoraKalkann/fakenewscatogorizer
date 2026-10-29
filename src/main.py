from graph import app


def show(out):
    print(out["title"], "|", out["source"])
    for r in out.get("results", []):
        print(f"{r['verdict']:36} {r['confidence']:.2f} {r['decided_by']:9} | {r['text']}")
        # kararın hangi kanıta dayandığını görmek için ilk 2 kanıtın linki
        for e in r["evidence"][:2]:
            print(f"{'':49}- [{e['source']}] {e['url']}")
    print(f"HABER: {out['verdict']} (skor {out['score']:+.2f})")
    if out["kind"]:
        print("TÜR:", out["kind"], "-", out["kind_reason"])


# model bir kez yükleniyor; sonra program kapanmadan link bekliyor
while url := input("\nHaber linki (çıkmak için Enter): ").strip():
    try:
        show(app.invoke({"url": url}))
    except Exception as e:
        print("Hata:", e)
