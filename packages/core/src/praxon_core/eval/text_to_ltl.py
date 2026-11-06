"""Do F1 trich mau Declare tu van ban tren bo 104 cau (task 6.5; spec dong 166).

Bo 104 cau (Grohs et al. 2023, arXiv:2307.09923) la 104 cau mo ta quy trinh
(tieng Anh), moi cau kem nhan la cac rang buoc Declare thuoc 5 mau
(precedence, response, succession, init, end). Muc dich cua bai do: F1 theo
tung mau cho mo hinh 8B cua du an, de biet no kem GPT-4 (0,79 trong bai bao)
bao xa.

Cach do (ghi ro de tai lap duoc):
- Dap an dung (gold) cua mot cau la DANH SACH cac mau trong cac cot nhan
  (Label 1/2/3) cua hang do trong tep `text_to_ltl.xlsx`, GIU NGUYEN THU TU
  VA SO LAN XUAT HIEN (mot cau co the co cung mau o nhieu cot). Tong 128
  nhan tren 104 cau. Ly do giu so lan xuat hien: bang Summary cua bai bao
  tinh Recall theo tong so nhan (vi du precedence 27/51, response 55/57)
  — neu rut gon thanh tap (chi 40/47...) thi mau so khac bai bao va F1
  khong so duoc voi moc 0,79. Moi nhan la mot rang buoc can trich dung.
- Mo hinh tra ve tap cac mau (qua JSON schema ep dinh dang, xem
  `TEXT_TO_LTL_SCHEMA`); `parse_model_output` trich tap do tu text tra ve.
- F1 theo tung mau: dem tren tung cap (cau, nhan). Voi mot mau t va mot cau:
  goi n la so lan t xuat hien trong danh sach nhan cua cau. Neu mo hinh du
  doan co t: TP += n (moi nhan duoc bao phu), neu n = 0 thi FP += 1. Neu mo
  hinh khong du doan t ma n > 0: FN += n. Precision = TP/(TP+FP), Recall =
  TP/(TP+FN), F1 = 2PR/(P+R); mau so rong thi chi so la 0 (theo quy uoc cua
  `eval/metrics.py`). Cach dem nay tai tao dung cac so P/R/F1 theo mau trong
  bang Summary cua bai bao (kiem bang test doi chieu).
- F1 tong (Overall): micro-F1 — gop TP/FP/FN cua ca 5 mau roi tinh P/R/F1
  tren tong gop. (Luu y: so Overall 0,7946 trong bang Summary cua bai bao
  la trung binh dieu hoa cua Overall Precision/Recall cua ho (0,8386 /
  0,7550), khong phai micro-F1 tren 128 nhan theo cong thuc tren — micro-F1
  tinh tu chinh cac so P/R theo mau cua ho ra 0,76. Nen so sanh chinh la
  F1 theo tung mau; Overall cua bai do nay la micro-F1 theo dinh nghia o
  day, ghi ro de khong nham.)
- Khac biet voi bai bao (ghi ro): Grohs et al. yeu cau mo hinh viet cong
  thuc LTL day du roi suy mau tu cong thuc; bai do nay yeu cau mo hinh tra
  thang ten mau (qua JSON schema), nen F1 do phan loai mau truc tiep, khong
  cong them loi cu phap LTL. Vi vay F1 o day co the cao hon neu cung mo hinh
  viet LTL; moc 0,79 chi la diem tham chieu, khong phai muc tieu phai vuot.

Moi ham trong module nay la ham thuan: khong goi mo hinh, khong doc tep,
khong cham co so du lieu. Doc tep XLSX va goi mo hinh nam o lenh do
(`tools/measure_f1_text_to_ltl.py`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "TEMPLATES",
    "TEXT_TO_LTL_SCHEMA",
    "F1Score",
    "LabeledSentence",
    "build_prompt",
    "f1_for_template",
    "f1_per_template",
    "overall_f1",
    "parse_model_output",
]

TEMPLATES: tuple[str, ...] = ("precedence", "response", "succession", "init", "end")
"""Nam mau Declare co trong bo 104 cau (theo bai bao Grohs et al. 2023)."""

TEXT_TO_LTL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "templates": {
            "type": "array",
            "items": {"type": "string", "enum": list(TEMPLATES)},
        }
    },
    "required": ["templates"],
    "additionalProperties": False,
}
"""JSON schema ep dinh dang dau ra cua mo hinh: mot object chi co truong
`templates`, la mang cac ten mau trong `TEMPLATES`. Adapter 6.1 gui schema
nay qua `response_format` va kiem lai o phia host."""

# Vi du 1-shot cho prompt: cau tu viet, KHONG lay tu bo 104 cau (tranh ro ri
# dap an vao tap do). Cau ro rang thuoc mau precedence.
_EXAMPLE_SENTENCE = "A payment must be made before the order is shipped."
_EXAMPLE_TEMPLATES = ("precedence",)

_PROMPT_TEMPLATE = """You are given a sentence describing a business process step.
Identify which Declare constraint template(s) best describe the rule in the sentence.

Templates (choose only from this list):
- precedence: B can only happen after A has happened (A must come first).
- response: whenever A happens, B must happen afterwards.
- succession: A and B always happen together, A first then B (precedence plus response).
- init: the process must start with A.
- end: the process must end with A.

Reply with a JSON object with a single field "templates":
an array of the applicable template name(s). If several apply, list all of them.

Example:
Sentence: "{example_sentence}"
Answer: {{"templates": {example_templates}}}

Sentence: "{sentence}"
Answer:"""


@dataclass(frozen=True)
class LabeledSentence:
    """Mot cau trong bo 104 cau kem dap an dung: danh sach cac mau Declare.

    `labels` giu nguyen thu tu va so lan xuat hien trong cac cot Label 1/2/3
    (mot mau co the xuat hien nhieu lan) — xem ghi chu ve cach dem o dau file.
    """

    sentence: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class F1Score:
    """Precision/Recall/F1 cua mot mau (hoac cua tong gop), kem so dem."""

    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def build_prompt(sentence: str) -> str:
    """Prompt 1-shot cho mot cau: dinh nghia 5 mau + 1 vi du + cau can do."""
    return _PROMPT_TEMPLATE.format(
        example_sentence=_EXAMPLE_SENTENCE,
        example_templates=json.dumps(list(_EXAMPLE_TEMPLATES)),
        sentence=sentence,
    )


def parse_model_output(text: str) -> frozenset[str]:
    """Trich tap cac mau Declare tu text mo hinh tra ve.

    Thu JSON truoc: neu text parse duoc thanh object co truong `templates`
    la mang chuoi thi lay cac phan tu thuoc `TEMPLATES` trong do. Neu khong
    phai JSON (mo hinh tra text thuong) thi roi ve khop ten mau theo ranh
    gioi tu, khong phan biet hoa/thuong. Khong bao gio nem loi: text khong
    chua mau nao thi tra tap rong.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        raw = parsed.get("templates")
        if isinstance(raw, list):
            return frozenset(
                item for item in raw if isinstance(item, str) and item in TEMPLATES
            )
    found: set[str] = set()
    lowered = text.lower()
    for template in TEMPLATES:
        if re.search(rf"\b{re.escape(template)}\b", lowered):
            found.add(template)
    return frozenset(found)


def _f1_from_counts(tp: int, fp: int, fn: int) -> F1Score:
    """F1 tu so dem TP/FP/FN; mau so rong thi chi so la 0."""
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return F1Score(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn)


def f1_for_template(
    predicted: Sequence[frozenset[str]],
    gold: Sequence[tuple[str, ...]],
    template: str,
) -> F1Score:
    """F1 cua mot mau: dem TP/FP/FN tren tung cap (cau, nhan).

    Voi mot cau, goi n la so lan mau xuat hien trong danh sach nhan cua cau.
    Neu mo hinh du doan co mau: TP += n (moi nhan duoc bao phu), neu n = 0
    thi FP += 1. Neu mo hinh khong du doan mau ma n > 0: FN += n.
    """
    tp = fp = fn = 0
    for pred_set, gold_list in zip(predicted, gold, strict=True):
        count = gold_list.count(template)
        if template in pred_set:
            if count > 0:
                tp += count
            else:
                fp += 1
        elif count > 0:
            fn += count
    return _f1_from_counts(tp, fp, fn)


def f1_per_template(
    predicted: Sequence[frozenset[str]],
    gold: Sequence[tuple[str, ...]],
) -> dict[str, F1Score]:
    """F1 theo tung mau trong `TEMPLATES`, theo thu tu cua `TEMPLATES`."""
    return {template: f1_for_template(predicted, gold, template) for template in TEMPLATES}


def overall_f1(
    predicted: Sequence[frozenset[str]],
    gold: Sequence[tuple[str, ...]],
) -> F1Score:
    """F1 tong (micro): gop TP/FP/FN cua ca 5 mau roi tinh P/R/F1 tren tong."""
    tp = fp = fn = 0
    for template in TEMPLATES:
        score = f1_for_template(predicted, gold, template)
        tp += score.tp
        fp += score.fp
        fn += score.fn
    return _f1_from_counts(tp, fp, fn)
