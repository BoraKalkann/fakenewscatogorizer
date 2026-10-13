import truststore

truststore.inject_into_ssl()  

from dotenv import load_dotenv

load_dotenv(override=True)  

import json
import operator
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
USER_AGENT = "fakenewscatogorizer/0.1"  # tarayıcı kimliğini web.archive.org 429 ile reddediyor


class Claim(BaseModel):
    text: str
    sentence: str


class Claims(BaseModel):
    claims: list[Claim]


class LLMVerdict(BaseModel):
    verdict: Literal["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
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


def check_claim(state):
    claim = state["claim"]["text"]
    evidence = []
    for hit in tavily.search(claim, max_results=10)["results"]:
        src = lookup(hit["url"])
        if state["own_domain"] not in domain(hit["url"]) and src["label"] not in BAD_SOURCES:
            evidence.append({"url": hit["url"], "source": src["label"], "text": f"{hit['title']}. {hit['content']}"})
    evidence = evidence[:5]

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
    verdicts = [r["verdict"] for r in state.get("results", [])]
    if source == "satire":
        verdict = "Hiciv"
    elif "Refuted" in verdicts:
        verdict = "Yanlış"
    elif "Conflicting Evidence/Cherrypicking" in verdicts:
        verdict = "Yanıltıcı"
    elif verdicts.count("Not Enough Evidence") > len(verdicts) / 2:
        verdict = "Doğrulanamadı" if source == "generally_reliable" else "Şüpheli"
    elif source in BAD_SOURCES:
        verdict = "Olgular doğru, kaynak güvenilmez"
    else:
        verdict = "Güvenilir"
    return {"verdict": verdict}


g = StateGraph(State)
g.add_node(fetch_article)
g.add_node(source_check)
g.add_node(extract_claims)
g.add_node(check_claim)
g.add_node(report)
g.add_edge(START, "fetch_article")
g.add_edge("fetch_article", "source_check")
g.add_conditional_edges("source_check", after_source, ["extract_claims", "report"])
g.add_conditional_edges("extract_claims", fan_out, ["check_claim"])
g.add_edge("check_claim", "report")
g.add_edge("report", END)
app = g.compile()

if __name__ == "__main__":
    out = app.invoke({"url": sys.argv[1]})
    print(out["title"], "|", out["source"])
    for r in out.get("results", []):
        print(f"{r['verdict']:36} {r['confidence']:.2f} {r['decided_by']:3} | {r['text']}")
    print("HABER:", out["verdict"])
