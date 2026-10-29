import truststore

truststore.inject_into_ssl()  # antivirüs HTTPS taraması Python'un sertifika doğrulamasını bozuyor

from dotenv import load_dotenv

load_dotenv(override=True)

import time
from typing import Literal

from google import genai
from pydantic import BaseModel

MODEL = "gemini-3.1-flash-lite"
client = genai.Client()


class Claim(BaseModel):
    text: str
    sentence: str


class Claims(BaseModel):
    claims: list[Claim]


class Questions(BaseModel):
    questions: list[str]


class Relevant(BaseModel):
    ids: list[int]


class SameClaim(BaseModel):
    same: bool


class Judgement(BaseModel):
    verdict: Literal["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
    reason: str


class Kind(BaseModel):
    kind: Literal["Uydurma", "Çarpıtma", "Yanıltıcı", "Sahte alıntı", "Bilim dışı"]
    reason: str


def ask(prompt, schema):
    config = {"response_mime_type": "application/json", "response_schema": schema}
    for attempt in range(3):  # Gemini bazen bağlantıyı koparıyor ya da boş cevap dönüyor
        try:
            if (out := client.models.generate_content(model=MODEL, contents=prompt, config=config).parsed):
                return out
        except Exception:
            if attempt == 2:
                raise
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("Gemini 3 denemede geçerli cevap vermedi.")
