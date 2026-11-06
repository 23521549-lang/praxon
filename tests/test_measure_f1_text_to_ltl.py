"""Test cho lenh do F1 text-to-LTL (task 6.5).

Test `load_rows` (doc XLSX) va `measure` (goi mo hinh) cua
`tools/measure_f1_text_to_ltl.py`. Tep XLSX test duoc tao trong test bang
openpyxl + tmp_path (khong commit du lieu that vao kho). Khong annotation
o ham test (quy uoc repo); ham tro giup thi co annotation day du.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import openpyxl  # type: ignore[import-untyped]
import pytest
from tools.measure_f1_text_to_ltl import (
    EXPECTED_ROWS,
    download_dataset,
    load_rows,
    measure,
)

from praxon_core.adapters.language_model import CompletionResult, ModelCallError
from praxon_core.eval.text_to_ltl import LabeledSentence

HEADER = ("task", "Label 1", "Label 2", "Label 3", "manual_labels")


def _viet_xlsx(
    path: Path, rows: list[tuple[Any, ...]], header: tuple[Any, ...] = HEADER
) -> Path:
    """Tao tep XLSX voi sheet `Sheet1` tu cac hang cho truoc."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)
    return path


def _hang_mau(i: int) -> tuple[Any, ...]:
    """Mot hang hop le: cau + nhan precedence (xen ke response)."""
    template = "precedence" if i % 2 == 0 else "response"
    return (f"Cau mo ta so {i}.", template, None, None, f"{template} ,, , ")


def _tep_104_hang(path: Path) -> Path:
    """Tep XLSX hop le dung 104 hang (nhu bo that, nhung cau tu viet)."""
    return _viet_xlsx(path, [_hang_mau(i) for i in range(EXPECTED_ROWS)])


class _MoHinhGia:
    """Mo hinh gia tra JSON co dinh (hoac nem ModelCallError)."""

    def __init__(self, text: str, hong_o_cau: set[int] | None = None) -> None:
        self._text = text
        self._hong_o_cau = hong_o_cau or set()
        self.so_lan_goi = 0

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        self.so_lan_goi += 1
        if self.so_lan_goi in self._hong_o_cau:
            raise ModelCallError("mo hinh gia hong co chu y")
        return CompletionResult(text=self._text)


def test_load_rows_doc_104_hang_hop_le(tmp_path: Path) -> None:
    """Tep dung 104 hang, nhan hop le thi doc du, dap an dung tap nhan."""
    path = _tep_104_hang(tmp_path / "hop_le.xlsx")
    rows = load_rows(path)
    assert len(rows) == EXPECTED_ROWS
    assert rows[0].sentence == "Cau mo ta so 0."
    assert rows[0].labels == ("precedence",)
    assert rows[1].labels == ("response",)
    assert all(isinstance(row, LabeledSentence) for row in rows)


def test_load_rows_sai_so_hang_bao_loi(tmp_path: Path) -> None:
    """Tep khong dung 104 hang thi bao loi (du lieu da doi)."""
    path = _viet_xlsx(tmp_path / "thieu.xlsx", [_hang_mau(0), _hang_mau(1)])
    with pytest.raises(ValueError, match="so hang"):
        load_rows(path)


def test_load_rows_nhan_la_bao_loi(tmp_path: Path) -> None:
    """Nhan khong thuoc 5 mau thi bao loi."""
    hang = [_hang_mau(i) for i in range(EXPECTED_ROWS)]
    hang[0] = ("Cau mo ta so 0.", "khong_co_mau", None, None, "khong_co_mau ,, , ")
    path = _viet_xlsx(tmp_path / "nhan_la.xlsx", hang)
    with pytest.raises(ValueError, match="nhan la"):
        load_rows(path)


def test_load_rows_thieu_sheet_bao_loi(tmp_path: Path) -> None:
    """Tep khong co sheet Sheet1 thi bao loi."""
    path = tmp_path / "khong_sheet.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Khac"
    workbook.save(path)
    with pytest.raises(ValueError, match="Sheet1"):
        load_rows(path)


def test_load_rows_sai_header_bao_loi(tmp_path: Path) -> None:
    """Header khac thi bao loi."""
    path = _viet_xlsx(
        tmp_path / "sai_header.xlsx",
        [_hang_mau(i) for i in range(EXPECTED_ROWS)],
        header=("cau", "nhan1", "nhan2", "nhan3", "nhan_tay"),
    )
    with pytest.raises(ValueError, match="header"):
        load_rows(path)


def test_measure_mo_hinh_tra_dung_thi_f1_tinh_dung() -> None:
    """Mo hinh gia tra precedence cho moi cau: F1 precedence tinh dung."""
    rows = [
        LabeledSentence(sentence="Cau 1.", labels=("precedence",)),
        LabeledSentence(sentence="Cau 2.", labels=("response",)),
        LabeledSentence(sentence="Cau 3.", labels=("precedence",)),
    ]
    model = _MoHinhGia('{"templates": ["precedence"]}')
    result = measure(model, rows, seed=42)
    assert result.measured == 3
    assert result.failures == 0
    assert model.so_lan_goi == 3
    precedence = result.per_template["precedence"]
    # 2 TP (cau 1, 3), 1 FP (cau 2 du doan precedence, dap an response).
    assert precedence.tp == 2
    assert precedence.fp == 1
    assert precedence.fn == 0
    assert precedence.f1 == pytest.approx(0.8)


def test_measure_goi_hong_tinh_la_du_doan_rong() -> None:
    """Cau goi hong (ModelCallError) thi tinh la du doan rong + dem failures."""
    rows = [
        LabeledSentence(sentence="Cau 1.", labels=("precedence",)),
        LabeledSentence(sentence="Cau 2.", labels=("precedence",)),
    ]
    model = _MoHinhGia('{"templates": ["precedence"]}', hong_o_cau={2})
    result = measure(model, rows, seed=42)
    assert result.failures == 1
    assert result.measured == 2
    precedence = result.per_template["precedence"]
    assert precedence.tp == 1
    assert precedence.fn == 1
    assert precedence.f1 == pytest.approx(2 / 3)


def test_download_dataset_tep_da_co_dung_bam_thi_khong_tai() -> None:
    """Tep da co san va khop SHA-256 thi dung lai, khong tai nua."""
    # Dung chinh tep that da tai ve cache (da kiem SHA-256 khop).
    cache = Path.home() / ".cache" / "praxon" / "text_to_ltl" / "text_to_ltl.xlsx"
    if not cache.exists():
        pytest.skip("chua tai bo 104 cau ve cache")
    assert download_dataset("https://khong-ton-tai.invalid/x.xlsx", cache) == cache


def test_download_dataset_url_hong_bao_loi(tmp_path: Path) -> None:
    """Tai tu URL hong thi bao loi ro rang (khong im lang)."""
    dest = tmp_path / "x.xlsx"
    with pytest.raises(RuntimeError, match="khong tai duoc"):
        download_dataset("https://khong-ton-tai.invalid/x.xlsx", dest)
