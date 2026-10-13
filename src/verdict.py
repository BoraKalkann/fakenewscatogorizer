import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = "ctu-aic/deberta-v3-large-AVeriTeC-nli"
LABELS = ["Refuted", "Supported", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]
device = "cuda" if torch.cuda.is_available() else "cpu"

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL).to(device).eval()

@torch.no_grad()
def judge(claim, evidence):
    enc = tok(claim, evidence, truncation="longest_first", max_length=512, return_tensors="pt").to(device)
    p = torch.softmax(model(**enc).logits[0].float(), dim=-1)
    return LABELS[p.argmax().item()], p.max().item()
