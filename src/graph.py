from llm import Claims, Judgement, Kind, Relevant, ask  # önce: .env ve sertifika ayarı burada yükleniyor

import json
import operator
from typing import Annotated, TypedDict

import trafilatura
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from tavily import TavilyClient

import factcheck
from sources import domain, lookup
from verdict import judge

tavily = TavilyClient()
THRESHOLD = 0.9
SUP, REF, NEE, CON = "Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"
POINTS = {SUP: 1, REF: -1, CON: -0.5, NEE: 0}
BAD_SOURCES = {"deprecated", "blacklisted"}
SOCIAL = ("facebook.com", "youtube.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "reddit.com")


class State(TypedDict):
    url: str
    title: str
    text: str
    source: dict
    claims: list[dict]
    results: Annotated[list[dict], operator.add]
    verdict: str
    score: float
    kind: str
    kind_reason: str


def result(claim, verdict, confidence, by, reason="", evidence=(), rating=""):
    return {"results": [{**claim, "verdict": verdict, "confidence": round(confidence, 2), "decided_by": by,
                         "reason": reason, "evidence": list(evidence), "rating": rating}]}


def fetch_article(state):
    html = factcheck.get(state["url"])
    page = html and trafilatura.extract(html, output_format="json", with_metadata=True)
    if not page:
        raise RuntimeError(f"Sayfa çekilemedi: {state['url']}")
    page = json.loads(page)
    return {"title": page["title"], "text": page["text"]}


def source_check(state):
    return {"source": lookup(state["url"])}


def after_source(state):
    return "report" if state["source"]["label"] == "satire" else "extract_claims"


def extract_claims(state):
    out = ask("Extract up to 5 checkable factual claims (numbers, events, quotes, causes) from this news article. "
              "Write each claim so it makes sense on its own and copy the sentence it comes from. "
              "Every claim must name the article's main person or organisation, the place and the date; "
              "never write a bare surname or 'the house', 'the company'. "
              f"Skip opinions and predictions.\n\nTitle: {state['title']}\n\n{state['text'][:8000]}", Claims)
    return {"claims": [c.model_dump() for c in out.claims[:5]]}


def fan_out(state):
    return [Send("check_claim", {"claim": c, "own_domain": state["source"]["domain"]}) for c in state["claims"]]


def same_event(claim, evidence):
    if not evidence:
        return []
    lines = "\n".join(f"[{i}] {e['text']}" for i, e in enumerate(evidence))
    out = ask(f"Claim: {claim}\n\nSnippets:\n{lines}\n\n"
              "Which snippets are about the same person and the same event as the claim? "
              "Sharing only a name is not enough. A snippet that contradicts the claim still counts.", Relevant)
    return [evidence[i] for i in out.ids if i < len(evidence)]


def check_claim(state):
    claim, text = state["claim"], state["claim"]["text"]
    hits = (tavily.search(text, max_results=5, include_domains=factcheck.SITES)["results"]
            + tavily.search(text, max_results=10)["results"])
    evidence = []
    for h in hits:
        site, label = domain(h["url"]), lookup(h["url"])["label"]
        if state["own_domain"] not in site and label not in BAD_SOURCES and not site.endswith(SOCIAL):
            evidence.append({"url": h["url"], "source": label, "text": f"{h['title']}. {h['content']}"})
    evidence = same_event(text, evidence)[:5]

    # aynı iddiayı inceleyen bir fact-check varsa onun kararını kullan
    for e in filter(lambda e: factcheck.is_factcheck(e["url"]), evidence):
        review = factcheck.review(e["url"])
        if not review:
            continue
        verdict = factcheck.to_verdict(review[1])
        same, conf = judge(text, review[0])
        if verdict and same == SUP and conf >= THRESHOLD:
            return result(claim, verdict, 1.0, "factcheck", e["url"], [e], review[1])

    # fact-check özetleri yalanı alıntıladığı için kanıt olarak kullanılmıyor
    evidence = [e for e in evidence if not factcheck.is_factcheck(e["url"])]
    if not evidence:  # boş kanıtta model Refuted'a kayıyor
        return result(claim, NEE, 1.0, "none", "Kanıt bulunamadı.")

    verdict, conf = judge(text, " ".join(e["text"] for e in evidence))
    if conf >= THRESHOLD:
        return result(claim, verdict, conf, "nli", evidence=evidence)

    lines = "\n".join(f"- [{e['source']}] {e['url']}: {e['text']}" for e in evidence)
    out = ask(f"Claim: {text}\n\nEvidence (source reliability in brackets):\n{lines}\n\n"
              "Based only on this evidence, is the claim supported, refuted, not enough evidence, "
              "or conflicting/cherry-picked? One-sentence reason.", Judgement)
    return result(claim, out.verdict, conf, "llm", out.reason, evidence)


def report(state):
    source = state["source"]["label"]
    results = state.get("results", [])
    if source == "satire":
        return {"verdict": "Hiciv", "score": 0.0}

    # puan × ağırlık × güven ortalaması; fact-check 2 kat, LLM kararında güven 1
    score = sum(POINTS[r["verdict"]] * (2 if r["decided_by"] == "factcheck" else 1)
                * (1 if r["decided_by"] == "llm" else r["confidence"]) for r in results) / max(len(results), 1)

    if score <= -0.2:
        verdict = "Yanlış"
    elif score < 0.2 and any(r["verdict"] == CON for r in results):
        verdict = "Yanıltıcı"
    elif score < 0.2:
        verdict = "Doğrulanamadı" if source == "generally_reliable" else "Şüpheli"
    elif source in BAD_SOURCES:
        verdict = "Olgular doğru, kaynak güvenilmez"
    else:
        verdict = "Güvenilir"
    return {"verdict": verdict, "score": round(score, 2)}


def classify(state):
    if state["verdict"] == "Hiciv":
        return {"kind": "Hiciv", "kind_reason": "Kaynak hiciv sitesi."}
    if state["verdict"] not in ("Yanlış", "Yanıltıcı", "Şüpheli"):
        return {"kind": "", "kind_reason": ""}

    bad = [r for r in state["results"] if r["verdict"] != SUP]
    for r in bad:
        if kind := factcheck.kind(r["rating"]):
            return {"kind": kind, "kind_reason": f"{r['reason']}: {r['rating']}"}

    lines = "\n".join(f"- [{r['verdict']}] {r['text']} | {r['reason']} | "
                      + " | ".join(e["text"][:300] for e in r["evidence"][:2]) for r in bad)
    out = ask(f"This article (source: {state['source']['label']}) was judged '{state['verdict']}'.\n"
              f"Problem claims:\n{lines}\n\n"
              "Pick the misinformation type: Uydurma (never happened), Çarpıtma (real event, details changed), "
              "Yanıltıcı (true but missing context), Sahte alıntı (fake or misattributed quote), "
              "Bilim dışı (unfounded health/science claim). Reason in one Turkish sentence.", Kind)
    return {"kind": out.kind, "kind_reason": out.reason}


g = StateGraph(State)
for node in (fetch_article, source_check, extract_claims, check_claim, report, classify):
    g.add_node(node)
g.add_edge(START, "fetch_article")
g.add_edge("fetch_article", "source_check")
g.add_conditional_edges("source_check", after_source, ["extract_claims", "report"])
g.add_conditional_edges("extract_claims", fan_out, ["check_claim"])
g.add_edge("check_claim", "report")
g.add_edge("report", "classify")
g.add_edge("classify", END)
app = g.compile()
