// Backend'in döndürdüğü değerlerin arayüzdeki Türkçe karşılıkları ve renk tonları.
// Ton adları styles.css'teki .tone-* sınıflarıyla eşleşir.

// İddia kararı (AVeriTeC etiketleri)
export const CLAIM_VERDICTS = {
  "Supported": { label: "Doğru", tone: "true" },
  "Refuted": { label: "Yanlış", tone: "false" },
  "Conflicting Evidence/Cherrypicking": { label: "Çelişkili", tone: "mixed" },
  "Not Enough Evidence": { label: "Kanıt yetersiz", tone: "unknown" },
};

// Haberin kararı (engine/pipeline.py report adımı)
export const ARTICLE_TONES = {
  "Güvenilir": "true",
  "Yanlış": "false",
  "Yanıltıcı": "mixed",
  "Şüpheli": "mixed",
  "Olgular doğru, kaynak güvenilmez": "mixed",
  "Doğrulanamadı": "unknown",
  "Hiciv": "unknown",
};

// Haber kararının ne demek olduğu; tür (kind) ya da gerekçe yoksa sonuç ekranında bu gösterilir.
// Kurallar engine/pipeline.py içindeki report adımından.
export const VERDICT_EXPLANATIONS = {
  "Güvenilir": "Haberdeki iddialar kanıtlarla doğrulandı.",
  "Yanlış": "Haberdeki iddiaların önemli bir kısmı kanıtlarla çürütüldü.",
  "Yanıltıcı": "Bazı iddialar için kanıtlar çelişkili; haber eksik ya da seçici bilgi veriyor olabilir.",
  "Şüpheli": "Kanıtlar haberi doğrulamaya yetmedi ve kaynağın güvenilirliği belirsiz.",
  "Doğrulanamadı": "Kanıtlar haberi doğrulamaya ya da çürütmeye yetmedi; kaynak genel olarak güvenilir.",
  "Olgular doğru, kaynak güvenilmez": "İddialar doğrulandı, ama haberin yayımlandığı site güvenilmez kaynaklar arasında.",
  "Hiciv": "Bu bir hiciv sitesi; içerik gerçek haber değil, mizah amaçlı.",
};

export function explainVerdict(verdict) {
  if (VERDICT_EXPLANATIONS[verdict]) {
    return VERDICT_EXPLANATIONS[verdict];
  }
  return "";
}

// Site güvenilirlik etiketi (engine/sources.py)
export const SOURCE_LABELS = {
  generally_reliable: "Güvenilir",
  no_consensus: "Tartışmalı",
  generally_unreliable: "Güvenilmez",
  deprecated: "Güvenilmez",
  blacklisted: "Kara listede",
  multiple: "Konuya göre değişir",
  satire: "Hiciv sitesi",
  unknown: "Bilinmiyor",
};

export function claimVerdict(verdict) {
  if (CLAIM_VERDICTS[verdict]) {
    return CLAIM_VERDICTS[verdict];
  }
  return { label: verdict, tone: "unknown" };
}

export function articleTone(verdict) {
  if (ARTICLE_TONES[verdict]) {
    return ARTICLE_TONES[verdict];
  }
  return "unknown";
}

export function sourceLabel(label) {
  if (SOURCE_LABELS[label]) {
    return SOURCE_LABELS[label];
  }
  return label;
}

// "https://www.bbc.com/news/..." -> "bbc.com"
export function domainOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// "2026-11-15" -> "15 Kasım 2026"; tarih yoksa boş metin
export function formatDate(value, withYear = true) {
  if (!value || value === "unknown") {
    return "";
  }
  const date = new Date(value);
  if (isNaN(date)) {
    return "";
  }
  const options = { day: "numeric", month: "long" };
  if (withYear) {
    options.year = "numeric";
  }
  return date.toLocaleDateString("tr-TR", options);
}
