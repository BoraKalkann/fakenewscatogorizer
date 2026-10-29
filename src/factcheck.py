import html
import json
import re

import requests

from sources import domain

SITES = ["snopes.com", "politifact.com", "factcheck.org", "fullfact.org", "factcheck.afp.com",
         "leadstories.com", "africacheck.org", "checkyourfact.com", "boomlive.in", "altnews.in"]
RATING_KINDS = {"misattributed": "Sahte alıntı", "satire": "Hiciv", "fabricated": "Uydurma", "fake": "Uydurma",
                "miscaptioned": "Yanıltıcı", "missing context": "Yanıltıcı", "outdated": "Yanıltıcı"}


def get(url):
    # web.archive.org tarayıcı user-agent'ını 429 ile reddediyor
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "fakenewscatogorizer/0.1"})
        return r.text if r.ok else None
    except requests.RequestException:
        return None


def is_factcheck(url):
    return any(site in domain(url) for site in SITES)


def review(url):
    """(incelenen iddia, karar) – fact-check siteleri bunu ClaimReview (JSON-LD) olarak sayfaya gömüyor."""
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', get(url) or "", re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "ClaimReview":
                # Snopes metni HTML kodlu bırakıyor: "Clinton&#039;s" → "Clinton's"
                reviewed_claim = html.unescape(item.get("claimReviewed", ""))
                rating = html.unescape(item.get("reviewRating", {}).get("alternateName", ""))
                return reviewed_claim, rating
    return None


def to_verdict(rating):
    r = rating.lower()
    if any(w in r for w in ("mixture", "half", "mixed", "missing context", "misleading", "partly")):
        return "Conflicting Evidence/Cherrypicking"
    if any(w in r for w in ("false", "fake", "pants on fire", "incorrect", "no such", "not true", "fabricated")):
        return "Refuted"  # "not true", "true"dan önce bakılmalı
    if any(w in r for w in ("true", "correct", "accurate")):
        return "Supported"
    return None


def kind(rating):
    """Snopes "Misattributed" gibi etiketler yalan türünü zaten söylüyor."""
    return next((k for word, k in RATING_KINDS.items() if word in rating.lower()), None)
