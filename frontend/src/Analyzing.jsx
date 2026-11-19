import { useEffect, useState } from "react";
import { claimVerdict, domainOf, formatDate, sourceLabel } from "./labels.js";

// Adımın durumuna göre soldaki işaret: bitti (dolu tik), sürüyor (halka), bekliyor (gri halka)
function StepIcon({ status }) {
  if (status === "done") {
    return (
      <svg className="step-icon" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="11" fill="#0066CC" />
        <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === "active") {
    return (
      <svg className="step-icon pulse" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="none" stroke="#0066CC" strokeWidth="2" />
        <circle cx="12" cy="12" r="4" fill="#0066CC" />
      </svg>
    );
  }
  return (
    <svg className="step-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="none" stroke="#D2D2D7" strokeWidth="2" />
    </svg>
  );
}

export default function Analyzing({ url, progress }) {
  const [seconds, setSeconds] = useState(0);

  // geçen süreyi saniye saniye say
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  // --- gelen adımlardan ekranın durumunu çıkar ---
  const fetched = progress.title !== "";
  const sourceDone = progress.source !== null;
  const isSatire = sourceDone && progress.source.label === "satire";
  const claimsDone = progress.claims !== null;
  const claimCount = claimsDone ? progress.claims.length : 0;
  const checkedCount = progress.results.length;
  const allChecked = isSatire || (claimsDone && checkedCount >= claimCount);
  const verdictDone = progress.verdict !== "";

  // her iddianın sonucu geldiyse bul (sonuçlar bitiş sırasıyla geliyor, iddia metniyle eşleştiriyoruz)
  function resultOf(claim) {
    for (const r of progress.results) {
      if (r.text === claim.text) {
        return r;
      }
    }
    return null;
  }

  // adımların sırası; ilk bitmemiş olan "sürüyor", sonrakiler "bekliyor"
  const steps = [
    { key: "fetch", done: fetched, doneText: "Haber okundu", activeText: "Haber okunuyor" },
    {
      key: "source",
      done: sourceDone,
      doneText: "Kaynak kontrol edildi",
      activeText: "Kaynağın güvenilirliğine bakılıyor",
      detail: sourceDone ? sourceLabel(progress.source.label) : "",
    },
    {
      key: "claims",
      done: claimsDone || isSatire,
      doneText: isSatire ? "Hiciv sitesi, iddia çıkarılmadı" : "İddialar çıkarıldı",
      activeText: "İddialar çıkarılıyor",
      detail: claimsDone ? claimCount + " iddia" : "",
    },
    {
      key: "check",
      done: allChecked,
      doneText: isSatire ? "İddia kontrolü atlandı" : "İddialar kontrol edildi",
      activeText: "İddialar kontrol ediliyor",
      detail: claimsDone ? checkedCount + " / " + claimCount : "",
    },
    { key: "verdict", done: verdictDone, doneText: "Haber kararı: " + progress.verdict, activeText: "Haber kararı veriliyor" },
  ];
  let activeFound = false;
  for (const step of steps) {
    if (step.done) {
      step.status = "done";
    } else if (!activeFound) {
      step.status = "active";
      activeFound = true;
    } else {
      step.status = "waiting";
    }
  }

  // ilerleme çubuğu: 4 sabit adım + iddia başına bir adım
  const totalUnits = 4 + claimCount;
  let doneUnits = checkedCount;
  for (const step of steps) {
    if (step.key !== "check" && step.done) {
      doneUnits += 1;
    }
  }
  const percent = Math.round((doneUnits / totalUnits) * 100);

  const meta = [domainOf(url)];
  if (formatDate(progress.date)) {
    meta.push(formatDate(progress.date));
  }

  return (
    <main className="analyzing">
      <section className="analyzing-head">
        <span className="eyebrow">Analiz ediliyor</span>
        <h1>{fetched ? progress.title : domainOf(url)}</h1>
        <span className="muted">
          {meta.join(" · ")} · {seconds} sn
        </span>
      </section>

      <div
        className="progress"
        role="progressbar"
        aria-label="Analiz ilerlemesi"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={percent}
      >
        <div className="progress-fill" style={{ width: Math.max(percent, 4) + "%" }} />
      </div>

      <ol className="steps">
        {steps.map((step) => (
          <li key={step.key} className={"step step-" + step.status}>
            <div className="step-row">
              <StepIcon status={step.status} />
              <span className="step-text">{step.status === "done" ? step.doneText : step.activeText}</span>
              {step.detail && <span className="step-detail">{step.detail}</span>}
            </div>

            {/* iddia adımının altında iddiaları ve gelen kararları göster */}
            {step.key === "check" && claimsDone && claimCount > 0 && (
              <ul className="step-claims">
                {progress.claims.map((claim, index) => {
                  const result = resultOf(claim);
                  let label = "Kanıt aranıyor…";
                  let tone = "unknown";
                  if (result) {
                    const verdict = claimVerdict(result.verdict);
                    label = verdict.label;
                    tone = verdict.tone;
                  }
                  return (
                    <li key={index}>
                      <span className={result ? "" : "muted"}>{claim.text}</span>
                      <span className={"step-claim-verdict tone-" + tone}>{label}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </main>
  );
}
