import { useRef, useState } from "react";
import { articleTone, claimVerdict, domainOf, explainVerdict, formatDate, sourceLabel } from "./labels.js";
import { scrollToElement } from "./smoothScroll.js";

// Paragrafı, içinde geçen iddia cümlelerine göre parçalara böler.
// Dönen her parça: { text, claimIndex } (claimIndex null ise düz metin).
// Gemini cümleyi metinden kopyalıyor ama birebir eşleşmezse o iddia işaretlenmez.
function splitByClaims(paragraph, results) {
  // 1) paragrafta geçen iddia cümlelerini bul
  const matches = [];
  results.forEach((claim, index) => {
    const sentence = (claim.sentence || "").trim();
    if (!sentence) {
      return;
    }
    const start = paragraph.indexOf(sentence);
    if (start >= 0) {
      matches.push({ start: start, end: start + sentence.length, claimIndex: index });
    }
  });
  matches.sort((a, b) => a.start - b.start);

  // 2) eşleşmelerin arasını düz metin olarak doldur
  const parts = [];
  let position = 0;
  for (const match of matches) {
    if (match.start < position) {
      continue; // önceki işaretle çakışıyor, atla
    }
    if (match.start > position) {
      parts.push({ text: paragraph.slice(position, match.start), claimIndex: null });
    }
    parts.push({ text: paragraph.slice(match.start, match.end), claimIndex: match.claimIndex });
    position = match.end;
  }
  if (position < paragraph.length) {
    parts.push({ text: paragraph.slice(position), claimIndex: null });
  }
  return parts;
}

function VerdictIcon({ tone }) {
  let mark = <path d="M7 12.5l3.2 3.2L17 9" />; // tik
  if (tone === "false") {
    mark = <path d="M8.5 8.5l7 7M15.5 8.5l-7 7" />; // çarpı
  } else if (tone === "mixed" || tone === "unknown") {
    mark = <path d="M12 7v6M12 16.5v.5" />; // ünlem
  }
  return (
    <svg className={"verdict-icon tone-bg-" + tone} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="11" />
      <g fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        {mark}
      </g>
    </svg>
  );
}

export default function Result({ article }) {
  const [selected, setSelected] = useState(0); // açık olan iddia
  const [imageFailed, setImageFailed] = useState(false);
  const markRefs = useRef({}); // iddia numarası -> metindeki işaretli cümle

  // sağdaki listeden bir iddia seçilince aç ve metindeki cümlesine yumuşakça kaydır
  function selectFromList(index) {
    setSelected(index);
    const mark = markRefs.current[index];
    if (mark) {
      scrollToElement(mark);
    }
  }

  const results = article.results || [];
  const tone = articleTone(article.verdict);

  // Kararın altındaki açıklama: haber yanlışsa türü (Uydurma, Çarpıtma...) ve sistemin gerekçesi;
  // türü olmayan kararlarda (Güvenilir, Doğrulanamadı...) kararın ne demek olduğu.
  // Tür kararla aynıysa (ör. Hiciv) tekrar yazmıyoruz.
  const showKind = article.kind !== "" && article.kind !== article.verdict;
  let reason = explainVerdict(article.verdict);
  if (article.kind && article.kind_reason) {
    reason = article.kind_reason;
  }

  // haber metni: boş satırları ve başlığın tekrarını at
  const paragraphs = [];
  for (const line of article.text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed && trimmed !== article.title) {
      paragraphs.push(trimmed);
    }
  }

  return (
    <main className="result">
      <section className="result-head">
        <h1 className="verdict-title">
          {article.verdict}
          <VerdictIcon tone={tone} />
        </h1>
        <div className="verdict-detail">
          {showKind && <p className={"verdict-kind tone-" + tone}>{article.kind}</p>}
          {reason && <p className="verdict-reason">{reason}</p>}
        </div>
        <p className="result-news-title">{article.title}</p>
        <div className="result-meta">
          <span>{article.source.domain}</span>
          {formatDate(article.date) && <span>{formatDate(article.date)}</span>}
        </div>
        {article.image && !imageFailed && (
          <img
            className="cover"
            src={article.image}
            alt="Haberin kapak resmi"
            onError={() => setImageFailed(true)}
          />
        )}
      </section>

      <div className="result-body">
        <article className="news">
          <span className="section-label">Haber</span>
          {paragraphs.map((paragraph, p) => (
            <p key={p}>
              {splitByClaims(paragraph, results).map((part, i) => {
                if (part.claimIndex === null) {
                  return <span key={i}>{part.text}</span>;
                }
                const claimTone = claimVerdict(results[part.claimIndex].verdict).tone;
                const isSelected = part.claimIndex === selected;
                // <mark> satır satır akar; <button> ise kutu gibi durur. Klavyeyle de seçilebilsin diye
                // tabIndex ve Enter/Boşluk desteği ekliyoruz.
                return (
                  <mark
                    key={i}
                    ref={(element) => {
                      if (element) {
                        markRefs.current[part.claimIndex] = element;
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    className={"claim-mark mark-" + claimTone + (isSelected ? " selected" : "")}
                    onClick={() => setSelected(part.claimIndex)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelected(part.claimIndex);
                      }
                    }}
                  >
                    {part.text}
                  </mark>
                );
              })}
            </p>
          ))}
        </article>

        <aside className="claims" aria-label="İddialar">
          <span className="section-label">İddialar</span>

          {results.length === 0 && (
            <p className="muted">Bu haber için iddia kontrol edilmedi.</p>
          )}

          {results.map((claim, index) => {
            const verdict = claimVerdict(claim.verdict);

            // kapalı iddia: tek satır
            if (index !== selected) {
              return (
                <button key={index} type="button" className="claim-row" onClick={() => selectFromList(index)}>
                  <span>{claim.text}</span>
                  <span className={"claim-verdict tone-" + verdict.tone}>{verdict.label}</span>
                </button>
              );
            }

            // açık iddia: kart ve kanıt linkleri
            return (
              <div key={index} className="claim-card">
                {/* kartın üst kısmına tıklayınca da metindeki cümleye kaydır */}
                <button type="button" className="claim-card-main" onClick={() => selectFromList(index)}>
                  <span className="claim-card-head">
                    <span className="muted small">İddia {index + 1}</span>
                    <span className={"claim-verdict strong tone-" + verdict.tone}>{verdict.label}</span>
                  </span>
                  <span className="claim-card-text">{claim.text}</span>
                </button>
                {claim.evidence.length > 0 && (
                  <ul className="evidence">
                    {claim.evidence.map((e) => (
                      <li key={e.url}>
                        <a href={e.url} target="_blank" rel="noreferrer">
                          {domainOf(e.url)}
                          <span className="muted small">{sourceLabel(e.source)}</span>
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </aside>
      </div>
    </main>
  );
}
