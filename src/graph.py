import truststore

truststore.inject_into_ssl()  

from dotenv import load_dotenv

load_dotenv(override=True)  

import json
import operator
import re
import sys
from typing import Annotated, Literal, TypedDict

import requests
import trafilatura
from google import genai
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel
from tavily import TavilyClient

from sources import domain, lookup
from verdict import judge

client = genai.Client()
tavily = TavilyClient()
MODEL = "gemini-3.1-flash-lite"
THRESHOLD = 0.9
BAD_SOURCES = {"deprecated", "blacklisted"}
FACTCHECK_SITES = ["snopes.com", "politifact.com", "factcheck.org", "fullfact.org", "factcheck.afp.com",
                   "leadstories.com", "africacheck.org", "checkyourfact.com", "boomlive.in", "altnews.in"]
USER_AGENT = "fakenewscatogorizer/0.1"  # tarayıcı kimliğini web.archive.org 429 ile reddediyor
POINTS = {"Supported": 1, "Refuted": -1, "Conflicting Evidence/Cherrypicking": -0.5, "Not Enough Evidence": 0}
RATING_KINDS = {"misattributed": "Sahte alıntı", "satire": "Hiciv", "fabricated": "Uydurma", "fake": "Uydurma",
                "miscaptioned": "Yanıltıcı", "missing context": "Yanıltıcı", "outdated": "Yanıltıcı"}


class Claim(BaseModel):
    text: str
    sentence: str


class Claims(BaseModel):
    claims: list[Claim]


class LLMVerdict(BaseModel):
    verdict: Literal["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
    reason: str


class Relevant(BaseModel):
    ids: list[int]


class Kind(BaseModel):
    kind: Literal["Uydurma", "Çarpıtma", "Yanıltıcı", "Sahte alıntı", "Bilim dışı"]
    reason: str


def ask(prompt, schema):
    config = {"response_mime_type": "application/json", "response_schema": schema}
    return client.models.generate_content(model=MODEL, contents=prompt, config=config).parsed


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


def fetch_article(state):
    try:
        r = requests.get(state["url"], timeout=10, headers={"User-Agent": USER_AGENT})  # tek deneme, yeniden deneme yok
    except requests.RequestException:
        r = None
    page = r is not None and r.ok and trafilatura.extract(r.text, output_format="json", with_metadata=True)
    if not page:
        raise RuntimeError(f"Sayfa çekilemedi (bot engeli ya da ödeme duvarı olabilir): {state['url']}")
    page = json.loads(page)
    return {"title": page["title"], "text": page["text"]}


def source_check(state):
    return {"source": lookup(state["url"])}


def after_source(state):
    return "report" if state["source"]["label"] == "satire" else "extract_claims"


def extract_claims(state):
    prompt = (
        "Extract up to 5 check-worthy factual claims from this news article. "
        "Each claim must be self-contained (name who, where, when) and checkable: numbers, events, quotes, causes. "
        "Skip opinions and predictions. For each claim, copy the article sentence it comes from.\n\n"
        f"Title: {state['title']}\n\n{state['text'][:8000]}")
    out = ask(prompt, Claims)
    return {"claims": [c.model_dump() for c in out.claims[:5]]}


def fan_out(state):
    return [Send("check_claim", {"claim": c, "own_domain": state["source"]["domain"]}) for c in state["claims"]]


def same_event(claim, evidence):
    if not evidence:  # arama boş döndüyse LLM'e sormaya gerek yok
        return []
    lines = "\n".join(f"[{i}] {e['text']}" for i, e in enumerate(evidence))
    out = ask(
        f"Claim: {claim}\n\nEvidence snippets:\n{lines}\n\n"
        "Return the ids of the snippets that are about the same person and the same event as the claim. "
        "A snippet that only shares a name but describes a different person or event is not relevant. "
        "Relevance is not agreement: a snippet that contradicts the claim about the same event IS relevant.",
        Relevant)
    return [evidence[i] for i in out.ids if i < len(evidence)]


def is_factcheck(url):
    return any(site in domain(url) for site in FACTCHECK_SITES)


def factcheck_rating(url):
    """Fact-check sayfasındaki ClaimReview etiketi → (incelenen iddia, karar), ör. Snopes: (..., "False")."""
    try:
        html = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT}).text
    except requests.RequestException:
        return None
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "ClaimReview":
                return item.get("claimReviewed", ""), item.get("reviewRating", {}).get("alternateName", "")
    return None


def rating_to_verdict(rating):
    r = rating.lower()
    if any(w in r for w in ("mixture", "half", "mixed", "missing context", "misleading", "partly", "cherry")):
        return "Conflicting Evidence/Cherrypicking"
    if any(w in r for w in ("false", "fake", "pants on fire", "incorrect", "no such", "not true", "fabricated", "hoax")):
        return "Refuted"  # "not true" "true"dan önce kontrol edilmeli
    if any(w in r for w in ("true", "correct", "accurate")):
        return "Supported"
    return None  # "unproven" vb. → karar modeline bırak


def check_claim(state):
    claim = state["claim"]["text"]
    evidence = []
    hits = (tavily.search(claim, max_results=5, include_domains=FACTCHECK_SITES)["results"]  # önce fact-check siteleri
            + tavily.search(claim, max_results=10)["results"])
    for hit in hits:
        src = lookup(hit["url"])
        if state["own_domain"] not in domain(hit["url"]) and src["label"] not in BAD_SOURCES:
            evidence.append({"url": hit["url"], "source": src["label"], "text": f"{hit['title']}. {hit['content']}"})
    evidence = same_event(claim, evidence)[:5]

    for e in evidence:  # aynı iddiayı inceleyen bir fact-check varsa karar onun etiketinden gelir
        review = is_factcheck(e["url"]) and factcheck_rating(e["url"])
        if not review:
            continue
        reviewed, rating = review
        same_claim, conf = judge(claim, reviewed)  # fact-check'in incelediği iddia bizimkini söylüyor mu?
        verdict = rating_to_verdict(rating)
        if same_claim == "Supported" and conf >= THRESHOLD and verdict:
            return {"results": [{**state["claim"], "verdict": verdict, "confidence": 1.0, "decided_by": "factcheck",
                                 "reason": f"{e['url']}: {rating}", "evidence": [e]}]}
    evidence = [e for e in evidence if not is_factcheck(e["url"])]  # fact-check özetleri yalanı alıntılıyor

    if not evidence:  # boş kanıtta model "Refuted"a kayıyor (eğitimdeki çoğunluk sınıfı)
        return {"results": [{**state["claim"], "verdict": "Not Enough Evidence", "confidence": 1.0,
                             "decided_by": "none", "reason": "Aynı olayla ilgili kanıt bulunamadı.", "evidence": []}]}
    verdict, confidence = judge(claim, " ".join(e["text"] for e in evidence))
    decided_by, reason = "nli", ""
    if confidence < THRESHOLD:
        lines = "\n".join(f"- [{e['source']}] {e['url']}: {e['text']}" for e in evidence)
        out = ask(
            f"Claim: {claim}\n\nEvidence (with source reliability label):\n{lines}\n\n"
            "Using only this evidence, decide whether the claim is supported, refuted, "
            "has not enough evidence, or is conflicting/cherry-picked. Give a one-sentence reason.", LLMVerdict)
        verdict, decided_by, reason = out.verdict, "llm", out.reason

    return {"results": [{**state["claim"], "verdict": verdict, "confidence": round(confidence, 2),
                         "decided_by": decided_by, "reason": reason, "evidence": evidence}]}


def report(state):
    source = state["source"]["label"]
    results = state.get("results", [])
    if source == "satire":
        return {"verdict": "Hiciv", "score": 0.0}

    # Skor = iddia puanlarının ortalaması: puan × ağırlık (fact-check 2 kat) × güven.
    # LLM kararlarında güven 1 alınır; "confidence" alanı LLM'in değil, modelin (düşük) güveni.
    score = sum(POINTS[r["verdict"]] * (2 if r["decided_by"] == "factcheck" else 1)
                * (1.0 if r["decided_by"] == "llm" else r["confidence"]) for r in results) / max(len(results), 1)

    if score <= -0.2:
        verdict = "Yanlış"
    elif score < 0.2:
        if any(r["verdict"] == "Conflicting Evidence/Cherrypicking" for r in results):
            verdict = "Yanıltıcı"
        else:
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
    bad = [r for r in state["results"] if r["verdict"] != "Supported"]

    for r in bad:  # fact-check etiketi türü söylüyorsa (ör. Snopes "Misattributed") LLM'e gerek yok
        if r["decided_by"] == "factcheck":
            rating = r["reason"].rsplit(": ", 1)[-1].lower()
            for word, kind in RATING_KINDS.items():
                if word in rating:
                    return {"kind": kind, "kind_reason": r["reason"]}

    lines = "\n".join(
        f"- [{r['verdict']}] {r['text']}\n  reason: {r['reason']}\n  evidence: "
        + " | ".join(e["text"][:300] for e in r["evidence"][:2]) for r in bad)
    out = ask(
        f"A news article from a source rated '{state['source']['label']}' was judged '{state['verdict']}'. "
        f"Problematic claims with their evidence:\n{lines}\n\n"
        "Classify the type of misinformation: Uydurma (the event never happened), "
        "Çarpıtma (a real event with changed numbers or details), Yanıltıcı (true facts with missing context "
        "or cherry-picked), Sahte alıntı (fabricated or misattributed quote), "
        "Bilim dışı (unfounded health or science claim). Give a one-sentence reason in Turkish.", Kind)
    return {"kind": out.kind, "kind_reason": out.reason}


g = StateGraph(State)
g.add_node(fetch_article)
g.add_node(source_check)
g.add_node(extract_claims)
g.add_node(check_claim)
g.add_node(report)
g.add_node(classify)
g.add_edge(START, "fetch_article")
g.add_edge("fetch_article", "source_check")
g.add_conditional_edges("source_check", after_source, ["extract_claims", "report"])
g.add_conditional_edges("extract_claims", fan_out, ["check_claim"])
g.add_edge("check_claim", "report")
g.add_edge("report", "classify")
g.add_edge("classify", END)
app = g.compile()

if __name__ == "__main__":
    out = app.invoke({"url": sys.argv[1]})
    print(out["title"], "|", out["source"])
    for r in out.get("results", []):
        print(f"{r['verdict']:36} {r['confidence']:.2f} {r['decided_by']:3} | {r['text']}")
    print(f"HABER: {out['verdict']} (skor {out['score']:+.2f})")
    if out["kind"]:
        print("TÜR:", out["kind"], "-", out["kind_reason"])
