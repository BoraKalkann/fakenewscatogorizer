import truststore

truststore.inject_into_ssl()  # antivirüs HTTPS taraması Python'un sertifika doğrulamasını bozuyor

from dotenv import load_dotenv

load_dotenv(override=True)

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


class Relevant(BaseModel):
    ids: list[int]


class Judgement(BaseModel):
    verdict: Literal["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
    reason: str


class Kind(BaseModel):
    kind: Literal["Uydurma", "Çarpıtma", "Yanıltıcı", "Sahte alıntı", "Bilim dışı"]
    reason: str


def ask(prompt, schema):
    config = {"response_mime_type": "application/json", "response_schema": schema}
    return client.models.generate_content(model=MODEL, contents=prompt, config=config).parsed
