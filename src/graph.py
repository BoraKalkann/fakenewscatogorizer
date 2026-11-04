from llm import Claims, Judgement, Kind, Questions, Relevant, SameClaim, ask  # önce: .env ve sertifika ayarı burada yükleniyor

import json
import operator
import time
from typing import Annotated, TypedDict

import trafilatura
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from tavily import TavilyClient

import cache
import factcheck
from sources import domain, lookup
from verdict import judge

tavily = TavilyClient()
THRESHOLD = 0.97
SUP, REF, NEE, CON = "Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"
POINTS = {SUP: 1, REF: -1, CON: -0.5, NEE: 0}
BAD_SOURCES = {"deprecated", "blacklisted"}
SOCIAL = ("facebook.com", "youtube.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "reddit.com")


class State(TypedDict):
    url: str
    title: str
    date: str
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
    date = page.get("date")
    if not date:  
        date = "unknown"
    return {"title": page["title"], "date": date, "text": page["text"]}


def source_check(state):
    return {"source": lookup(state["url"])}


def after_source(state):
    return "report" if state["source"]["label"] == "satire" else "extract_claims"


def extract_claims(state):
    out = ask("Extract up to 5 checkable factual claims (numbers, events, quotes, causes) from this news article. "
              "Write each claim so it makes sense on its own and copy the sentence it comes from. "
              "Every claim must name the article's main person or organisation, the place and the date; "
              "never write a bare surname or 'the house', 'the company'. "
              "Take the date from the article text or from its publication date below; never guess a date, "
              "if neither gives one, leave the date out. "
              f"Skip opinions and predictions.\n\nTitle: {state['title']}\nPublished: {state['date']}\n\n"
              f"{state['text'][:8000]}", Claims)
    return {"claims": [c.model_dump() for c in out.claims[:5]]}


def fan_out(state):
    return [Send("check_claim", {"claim": c, "own_domain": state["source"]["domain"]}) for c in state["claims"]]


def search(text, **kw):
    for attempt in range(3): 
        try:
            return tavily.search(text, **kw)["results"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def as_qa(evidence):
    groups = {}
    for e in evidence:
        question = e["question"]
        if question is None:  
            question = ""
        if question not in groups:
            groups[question] = []
        groups[question].append(e["text"])

    parts = []
    for question, texts in groups.items():
        part = question + " " + " ".join(texts)
        parts.append(part.strip())
    return " ".join(parts)


def useful_evidence(claim, evidence):
    if not evidence:
        return []
    lines = "\n".join(f"[{i}] {e['text']}" for i, e in enumerate(evidence))
    out = ask(f"Claim: {claim}\n\nSnippets:\n{lines}\n\n"
              "Which snippets help decide whether the claim is true or false? Keep snippets that confirm it, "
              "contradict it, or give the real facts it is about (for example who actually holds a role the claim "
              "names, or the real numbers). Drop snippets that only share a name or a keyword.", Relevant)
    return [evidence[i] for i in out.ids if i < len(evidence)]


def same_claim(claim, reviewed_claim, verdict):
    if verdict == REF:
        question = ("A fact-checker rated B as false. Is A making the same false assertion? Answer true if A's central "
                    "assertion is B's central assertion, even if A adds details such as names, places or dates. "
                    "Answer false if A is about a different event or statement, if A and B give different numbers, "
                    "or if what makes B false is a part A does not claim (for example B adds a cause or purpose).")
    else:
        question = ("A fact-checker rated B as true or partly true. Does that rating apply to A as well? Answer true "
                    "only if everything A asserts is also asserted by B; extra names, places or dates are fine, "
                    "but an extra cause, purpose, number or event is not.")
    out = ask(f"Claim A: {claim}\nClaim B (checked by a fact-checker): {reviewed_claim}\n\n{question}", SameClaim)
    return out.same


def questions(claim):
    out = ask(f"Claim: {claim}\n\n"
              "Write up to 3 short web search questions that would show whether this claim is true. "
              "Ask about the underlying facts (did the event happen, who said what, what the real numbers are); "
              "do not ask 'is it true that'. Each question must stand on its own: name the person or "
              "organisation, never 'he' or 'the company'.", Questions)
    return out.questions[:3]


def check_claim(state):
    claim = state["claim"]
    text = claim["text"]
    hits = []
    for h in search(text, max_results=5, include_domains=factcheck.SITES):
        hits.append((None, h))
    for q in questions(text):
        for h in search(q, max_results=5):
            hits.append((q, h))
    seen_urls = set()
    unique_hits = []
    for q, h in hits:
        if h["url"] in seen_urls:
            continue
        seen_urls.add(h["url"])
        unique_hits.append((q, h))
    evidence = []
    for q, h in unique_hits:
        site = domain(h["url"])
        label = lookup(h["url"])["label"]
        if state["own_domain"] in site:
            continue
        if label in BAD_SOURCES:
            continue
        if site.endswith(SOCIAL):
            continue
        evidence.append({"url": h["url"], "source": label, "question": q,
                         "text": h["title"] + ". " + h["content"]})
    evidence = useful_evidence(text, evidence)
    for e in evidence:
        if not factcheck.is_factcheck(e["url"]):
            continue
        review = factcheck.review(e["url"])
        if not review:
            continue
        reviewed_claim, rating = review
        verdict = factcheck.to_verdict(rating)
        if not verdict:  
            continue
        if same_claim(text, reviewed_claim, verdict):
            return result(claim, verdict, 1.0, "factcheck", e["url"], [e], rating)

    kept = []
    factchecks = []
    for e in evidence:
        if factcheck.is_factcheck(e["url"]):
            factchecks.append(e)
        else:
            kept.append(e)
    evidence = kept[:5]
    if not evidence and factchecks:
        return llm_judge(claim, factchecks[:5], 0.0)
    if not evidence:
        return result(claim, NEE, 1.0, "none", "Kanıt bulunamadı.")

    verdict, conf = judge(text, as_qa(evidence))
    if conf >= THRESHOLD:
        return result(claim, verdict, conf, "nli", evidence=evidence)
    return llm_judge(claim, evidence, conf)


def llm_judge(claim, evidence, conf):
    lines = "\n".join(f"- [{e['source']}] {e['url']}: {e['text']}" for e in evidence)
    out = ask(f"Claim: {claim['text']}\n\nEvidence (source reliability in brackets):\n{lines}\n\n"
              "Based only on this evidence, is the claim supported, refuted, not enough evidence, "
              "or conflicting/cherry-picked? One-sentence reason.", Judgement)
    return result(claim, out.verdict, conf, "llm", out.reason, evidence)


def report(state):
    source = state["source"]["label"]
    results = state.get("results", [])
    if source == "satire":
        return {"verdict": "Hiciv", "score": 0.0}

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


def check_url(url):
    if hit := cache.get_article(url):
        return hit
    out = app.invoke({"url": url})
    cache.put_article(url, out)
    return out
