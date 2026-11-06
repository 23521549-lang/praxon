"""Do F1 trich mau Declare tu van ban tren bo 104 cau (task 6.5; spec dong 166).

Chay tu goc worktree (venv cua worktree len dau PATH):

    python -m tools.measure_f1_text_to_ltl

Bo 104 cau (Grohs et al. 2023) chi tai ve LUC DO, khong dong goi vao kho
(spec dong 166 — kho goc khong co tep giay phep). Tep nam o cache ngoai kho
(`~/.cache/praxon/text_to_ltl/text_to_ltl.xlsx`); lenh kiem SHA-256 + dung
104 hang truoc khi do. Khong bao gio commit tep nay (cong chan du lieu van
phai xanh sau khi do).

Mo hinh: adapter 6.1 (`OpenAICompatibleModel`) qua llama-server tren CPU
(Qwen3-8B-GGUF Q4_K_M) — server phai dang chay o `cpu_model_base_url`
(mac dinh `http://localhost:8080/v1`, xem
`docs/guides/chay-mo-hinh-cpu-llama-server.md`). Moi cau goi mot lan, non-
thinking, `temperature=0`, `seed` co dinh (mac dinh 42), dau ra ep theo
JSON schema `TEXT_TO_LTL_SCHEMA` cua `eval/text_to_ltl.py`.

Ket qua in ra: F1 theo tung mau (precedence/response/succession/init/end)
+ F1 tong (micro) + so lan goi mo hinh hong (tinh la du doan rong). Thoat 0
khi do xong (du F1 thap — F1 thap la ket qua do, khong phai loi lenh);
thoat 1 khi tai/du lieu loi, 2 khi khong noi duoc mo hinh.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# openpyxl chi co trong venv dev (requirements-dev.txt), khong co trong venv
# chay mypy neu thieu stub; dung ignore tran nhu tools/cross_check_pm4py.py
# (pandas/pm4py) de dung o ca hai truong hop.
import openpyxl  # type: ignore[import-untyped]

from praxon_core.adapters.language_model import (
    LanguageModel,
    ModelCallError,
    model_from_settings,
)
from praxon_core.eval.text_to_ltl import (
    TEMPLATES,
    TEXT_TO_LTL_SCHEMA,
    F1Score,
    LabeledSentence,
    build_prompt,
    f1_per_template,
    overall_f1,
    parse_model_output,
)
from praxon_core.settings import Settings, load_settings

DATASET_URL = (
    "https://raw.githubusercontent.com/KiriBu10/openLLMinBPM-benchmark/"
    "dev_kiran/data/text_to_ltl.xlsx"
)
"""URL bo 104 cau (da duyet, da kiem chung ngay 7/11/2026)."""

EXPECTED_SHA256 = "61ccc8a12a724a32380360156ea15848e8e65993ff95c9eca3ab62b2c02123c7"
"""SHA-256 cua tep `text_to_ltl.xlsx` (83.446 byte, kiem ngay 7/11/2026)."""

EXPECTED_SIZE = 83446
"""Dung luong tep `text_to_ltl.xlsx` (byte)."""

EXPECTED_ROWS = 104
"""So hang du lieu trong sheet `Sheet1` (khong tinh header)."""

SHEET_NAME = "Sheet1"
"""Sheet chua bo 104 cau chinh."""

DEFAULT_SEED = 42
"""Seed co dinh cho moi lan goi mo hinh (xac dinh, spec dong 191)."""

# Moc GPT-4 trong bai bao Grohs et al. 2023 (sheet Summary, "Examples
# provided, Try 1") — chi de doi chieu, khong phai muc tieu phai vuot.
GPT4_F1_OVERALL = 0.7946
GPT4_F1_PER_TEMPLATE = {
    "precedence": 0.6835,
    "response": 0.7971,
    "succession": 1.00,
    "init": 0.90,
    "end": 0.2857,
}


def default_dataset_path() -> Path:
    """Duong dan cache mac dinh cua bo 104 cau (ngoai kho)."""
    return Path.home() / ".cache" / "praxon" / "text_to_ltl" / "text_to_ltl.xlsx"


def _sha256(path: Path) -> str:
    """SHA-256 cua mot tep."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(url: str, dest: Path) -> Path:
    """Tai bo 104 cau ve `dest` (chi luc do); kiem dung luong + SHA-256.

    Neu tep da co san va khop SHA-256 thi dung lai, khong tai nua. Tep sai
    bam thi tai lai; tai hong hoac bam van sai thi bao loi.
    """
    if dest.exists() and _sha256(dest) == EXPECTED_SHA256:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
    except OSError as exc:
        raise RuntimeError(f"khong tai duoc bo 104 cau tu {url}: {exc}") from exc
    if dest.stat().st_size != EXPECTED_SIZE:
        raise RuntimeError(
            f"tep tai ve sai dung luong: {dest.stat().st_size} byte (cho {EXPECTED_SIZE})"
        )
    if _sha256(dest) != EXPECTED_SHA256:
        raise RuntimeError(
            f"tep tai ve sai SHA-256 (cho {EXPECTED_SHA256[:12]}...); "
            "nguon co the da doi — dung do, kiem lai URL."
        )
    return dest


def load_rows(path: Path) -> list[LabeledSentence]:
    """Doc 104 cau tu sheet `Sheet1` cua tep XLSX.

    Dap an dung cua mot cau la tap cac nhan khong rong trong cac cot
    Label 1/2/3. Kiem chat: dung ten sheet, dung header, dung 104 hang,
    cau nao cung co text, nhan nao cung thuoc 5 mau.
    """
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if SHEET_NAME not in workbook.sheetnames:
        raise ValueError(f"tep thieu sheet {SHEET_NAME!r}: {workbook.sheetnames}")
    sheet = workbook[SHEET_NAME]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("sheet trong, khong co header")
    header = tuple(rows[0][:5])
    if header != ("task", "Label 1", "Label 2", "Label 3", "manual_labels"):
        raise ValueError(f"header la: {header}")
    data = rows[1:]
    if len(data) != EXPECTED_ROWS:
        raise ValueError(f"so hang du lieu la {len(data)} (cho {EXPECTED_ROWS})")
    sentences: list[LabeledSentence] = []
    for index, row in enumerate(data, start=2):
        sentence = row[0]
        if not isinstance(sentence, str) or not sentence.strip():
            raise ValueError(f"hang {index}: thieu cau mo ta")
        labels = tuple(label for label in row[1:4] if isinstance(label, str) and label.strip())
        unknown = set(labels) - set(TEMPLATES)
        if unknown:
            raise ValueError(f"hang {index}: nhan la {sorted(unknown)}")
        if not labels:
            raise ValueError(f"hang {index}: khong co nhan nao")
        sentences.append(LabeledSentence(sentence=sentence.strip(), labels=labels))
    return sentences


@dataclass(frozen=True)
class MeasurementResult:
    """Ket qua mot lan do: F1 theo mau + tong + so lan goi hong."""

    per_template: dict[str, F1Score]
    overall: F1Score
    failures: int
    measured: int


def measure(
    model: LanguageModel,
    rows: list[LabeledSentence],
    *,
    seed: int = DEFAULT_SEED,
) -> MeasurementResult:
    """Do F1 tren cac cau: goi mo hinh tung cau, trich mau, tinh F1.

    `model` la mot `LanguageModel` (adapter 6.1). Cau nao goi hong
    (`ModelCallError`) thi tinh la du doan rong (khong duoc diem) va dem
    vao `failures` — khong nuot loi, khong dung ket qua gia.
    """
    predicted: list[frozenset[str]] = []
    gold: list[tuple[str, ...]] = []
    failures = 0
    for row in rows:
        try:
            result = model.complete(
                build_prompt(row.sentence),
                json_schema=TEXT_TO_LTL_SCHEMA,
                temperature=0.0,
                seed=seed,
            )
            predicted.append(parse_model_output(result.text))
        except ModelCallError:
            failures += 1
            predicted.append(frozenset())
        gold.append(row.labels)
    return MeasurementResult(
        per_template=f1_per_template(predicted, gold),
        overall=overall_f1(predicted, gold),
        failures=failures,
        measured=len(rows),
    )


def _format_report(result: MeasurementResult, settings: Settings) -> str:
    """Bang ket qua F1 theo tung mau + tong, kem moc GPT-4 de doi chieu."""
    lines = [
        "Do F1 trich mau Declare tren bo 104 cau (task 6.5)",
        f"Mo hinh: {settings.model_id} (revision {settings.model_revision})",
        f"So cau do: {result.measured}; goi mo hinh hong: {result.failures}",
        "",
        f"{'Mau':<12}{'P':>8}{'R':>8}{'F1':>8}{'F1 GPT-4':>10}{'TP':>5}{'FP':>5}{'FN':>5}",
    ]
    for template in TEMPLATES:
        score = result.per_template[template]
        lines.append(
            f"{template:<12}{score.precision:>8.4f}{score.recall:>8.4f}"
            f"{score.f1:>8.4f}{GPT4_F1_PER_TEMPLATE[template]:>10.4f}"
            f"{score.tp:>5}{score.fp:>5}{score.fn:>5}"
        )
    overall = result.overall
    lines.append(
        f"{'Overall':<12}{overall.precision:>8.4f}{overall.recall:>8.4f}"
        f"{overall.f1:>8.4f}{GPT4_F1_OVERALL:>10.4f}"
        f"{overall.tp:>5}{overall.fp:>5}{overall.fn:>5}"
    )
    lines.append("")
    lines.append("F1 tong (micro) cua bai do nay; moc GPT-4 0,7946 la Overall")
    lines.append("trong bang Summary cua bai bao (xem ghi chu trong eval/text_to_ltl.py).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lenh do: tai/du lieu -> goi mo hinh -> in F1 theo tung mau."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=None,
        help="duong dan tep text_to_ltl.xlsx (mac dinh: tai ve cache neu chua co)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="chi do N cau dau (kiem nhanh); mac dinh do ca 104 cau",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"seed co dinh cho moi lan goi (mac dinh {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="tep TOML cau hinh (mac dinh: dung gia tri mac dinh + bien PRAXON_*)",
    )
    args = parser.parse_args(argv)
    try:
        path = args.xlsx or download_dataset(DATASET_URL, default_dataset_path())
        rows = load_rows(path)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"loi du lieu: {exc}", file=sys.stderr)
        return 1
    if args.limit is not None:
        rows = rows[: args.limit]
    # Lenh do khong dung co so du lieu; database_url chi de du truong bat
    # buoc cua Settings (lay tu PRAXON_DATABASE_URL neu co, khong thi rong).
    settings = (
        load_settings(args.config)
        if args.config is not None
        else Settings(database_url=os.environ.get("PRAXON_DATABASE_URL", ""))
    )
    try:
        model = model_from_settings(settings, backend="cpu")
        result = measure(model, rows, seed=args.seed)
    except (ModelCallError, ValueError, OSError) as exc:
        print(f"loi goi mo hinh: {exc}", file=sys.stderr)
        return 2
    print(_format_report(result, settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
