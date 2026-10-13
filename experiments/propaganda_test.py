"""Try QCRI/PropagandaTechniquesAnalysis-en-BERT on a few articles.

The model ships its own class (model.py) written for an old transformers version;
the class is copied here with the import fixed. Weights are unchanged.

Usage: python experiments/propaganda_test.py URL [URL ...]
"""
import re
import sys
from dataclasses import dataclass
from typing import Optional

import truststore

truststore.inject_into_ssl()

import requests
import torch
import trafilatura
from torch import nn
from transformers import BertModel, BertPreTrainedModel, BertTokenizerFast
from transformers.utils import ModelOutput

TOKEN_TAGS = (
    "<PAD>", "O",
    "Name_Calling,Labeling", "Repetition", "Slogans", "Appeal_to_fear-prejudice", "Doubt",
    "Exaggeration,Minimisation", "Flag-Waving", "Loaded_Language",
    "Reductio_ad_hitlerum", "Bandwagon",
    "Causal_Oversimplification", "Obfuscation,Intentional_Vagueness,Confusion", "Appeal_to_Authority",
    "Black-and-White_Fallacy", "Thought-terminating_Cliches", "Red_Herring", "Straw_Men", "Whataboutism",
)


@dataclass
class Output(ModelOutput):
    token_logits: Optional[torch.FloatTensor] = None
    sequence_logits: Optional[torch.FloatTensor] = None


class BertForTokenAndSequenceJointClassification(BertPreTrainedModel):  # from the model repo's model.py
    def __init__(self, config):
        super().__init__(config)
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.classifier = nn.ModuleList([nn.Linear(config.hidden_size, 20), nn.Linear(config.hidden_size, 2)])
        self.masking_gate = nn.Linear(2, 1)
        self.merge_classifier_1 = nn.Linear(22, 20)
        self.post_init()

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None):
        out = self.bert(input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids)
        token_logits = self.classifier[0](self.dropout(out[0]))
        sequence_logits = self.classifier[1](self.dropout(out[1]))
        gate = torch.sigmoid(self.masking_gate(sequence_logits)).unsqueeze(1)
        return Output(token_logits=gate * token_logits, sequence_logits=sequence_logits)


device = "cuda" if torch.cuda.is_available() else "cpu"
tok = BertTokenizerFast.from_pretrained("bert-base-cased")
model = BertForTokenAndSequenceJointClassification.from_pretrained(
    "QCRI/PropagandaTechniquesAnalysis-en-BERT", revision="v0.1.0").to(device).eval()


@torch.no_grad()
def analyse(sentence):
    enc = tok(sentence, truncation=True, max_length=256, return_tensors="pt", return_offsets_mapping=True)
    offsets = enc.pop("offset_mapping")[0].tolist()
    out = model(**enc.to(device))
    is_prop = out.sequence_logits[0].argmax().item() == 1
    tags = out.token_logits[0].argmax(-1).tolist()
    spans, cur = [], None  # merge consecutive tokens with the same technique into one span
    for (s, e), t in zip(offsets, tags):
        name = TOKEN_TAGS[t]
        if s == e or name in ("<PAD>", "O"):
            cur = None
            continue
        if cur and cur["technique"] == name:
            cur["end"] = e
        else:
            cur = {"technique": name, "start": s, "end": e}
            spans.append(cur)
    return is_prop, [(sentence[x["start"]:x["end"]], x["technique"]) for x in spans]


for url in sys.argv[1:]:
    html = requests.get(url, timeout=10, headers={"User-Agent": "fakenewscatogorizer/0.1"}).text
    text = trafilatura.extract(html)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 3]
    n_prop, n_spans = 0, 0
    print(f"\n=== {url}\n")
    for s in sentences:
        is_prop, spans = analyse(s)
        n_prop += is_prop
        n_spans += len(spans)
        if spans:
            print(f"  {s[:110]}")
            for frag, tech in spans:
                print(f"      -> {tech}: \"{frag}\"")
    print(f"\n  sentences: {len(sentences)} | prop sentences: {n_prop} ({n_prop / len(sentences):.0%}) | "
          f"spans: {n_spans} | spans per 100 sentences: {100 * n_spans / len(sentences):.0f}")
