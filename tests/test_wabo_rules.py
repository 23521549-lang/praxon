"""Test trích luật thứ tự từ Wabo vào `global` (task 9.1).

Dữ liệu test tự viết (HTML giả, trace giả, mô hình giả) — không gọi
mô hình thật, không phụ thuộc cache Wabo/BPIC, trừ một test nạp văn
bản thật (skip khi cache trống, như test tải bộ 104 câu của 6.5).
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from praxon_core.adapters.language_model import ModelCallError
from praxon_core.declare.index import Trace
from praxon_core.learning.coordinator import ReflectorResult
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.dutch_mapping import DutchMappingTable, default_dutch_mapping
from praxon_core.learning.rules import default_rule_table
from praxon_core.learning.wabo_rules import (
    WaboDocument,
    WaboExtraction,
    extract_wabo_rules,
    extract_wabo_text,
    format_wabo_report,
    load_bpic_traces,
    load_wabo_document,
    main,
    parse_valid_during,
    resolve_activity,
    split_chunk_at_article,
    split_wabo_text,
)
from praxon_core.settings import Settings

AANVRAAG = "01_HOOFD_015"
ONTWERP = "01_HOOFD_440_1"
BEZWAAR = "01_BB_540"

FAKE_HTML = """<html><head><title>Wabo</title><style>.x{color:red}</style>
<script>var x = 1;</script></head><body>
<h1>Wet algemene bepalingen omgevingsrecht</h1>
<p>Artikel 1.1 De aanvraag wordt ingediend.</p>
<p>Artikel 3.1 Het ontwerpbesluit wordt ter inzage gelegd.</p>
</body></html>"""

FAKE_TEXT = (
    "Wet algemene bepalingen omgevingsrecht\n"
    "Artikel 1.1 De aanvraag wordt ingediend.\n"
    "Artikel 3.1 Het ontwerpbesluit wordt ter inzage gelegd."
)


def _fake_mapping(sha: str) -> DutchMappingTable:
    """Bảng gắn nhỏ tự viết cho test SHA (một khái niệm duy nhất)."""
    return DutchMappingTable.model_validate(
        {
            "wabo": {
                "source_url": "https://example.invalid/wabo",
                "version": "2015-01-01",
                "valid_during": "2015-01-01/2015-03-31",
                "sha256_html": sha,
            },
            "concept": [
                {
                    "term": "aanvraag",
                    "wabo_count": 1,
                    "canonical": AANVRAAG,
                    "activities": [
                        {
                            "code": AANVRAAG,
                            "dutch_name": "fase aanvraag ontvangen",
                            "events": 1,
                        }
                    ],
                }
            ],
            "unmapped": [],
        }
    )


def _fake_document(text: str) -> WaboDocument:
    """Văn bản Wabo giả (khoảng hiệu lực đúng bản 2015-01-01)."""
    return WaboDocument(
        source_url="https://example.invalid/wabo",
        version="2015-01-01",
        valid_start=datetime(2015, 1, 1, tzinfo=UTC),
        valid_end=datetime(2015, 4, 1, tzinfo=UTC),
        text=text,
        sha256="giả",
    )


def _fake_reflect(
    insights: Sequence[Insight],
    *,
    dropped: int = 0,
) -> Callable[[str, Sequence[FactRead]], ReflectorResult]:
    """Hàm giả cho đường `reflect_document`: trả insight đã định sẵn."""

    def reflect_document(text: str, facts: Sequence[FactRead]) -> ReflectorResult:
        return ReflectorResult(
            insights=tuple(insights),
            tokens_in=10,
            tokens_out=20,
            source_quote_dropped=dropped,
        )

    return reflect_document


def _insight(
    template: str, activation: str, target: str, condition: str | None = None
) -> Insight:
    return Insight(
        template=template,
        activation=activation,
        target=target,
        condition=condition,
        evidence_episode_ids=[],
        source=InsightSource.DOCUMENT,
        scope="global",
    )


def _traces_aanvraag_roi_ontwerp(n: int) -> tuple[Trace, ...]:
    """N trace: đơn (aanvraag) rồi quyết định dự thảo (ontwerpbesluit)."""
    return tuple(Trace((AANVRAAG, ONTWERP)) for _ in range(n))


def _traces_day_du(n: int) -> tuple[Trace, ...]:
    """N trace: aanvraag -> ontwerpbesluit -> bezwaar (cả ba luật đều đủ bằng chứng)."""
    return tuple(Trace((AANVRAAG, ONTWERP, BEZWAAR)) for _ in range(n))


def _fake_document_nhieu_doan() -> WaboDocument:
    """Văn bản giả 3 điều dài: tách thành 6 đoạn (mỗi điều cắt làm đôi)."""
    text = "\n\n".join(
        [
            "Artikel 1.1 " + "a" * 4500,
            "Artikel 1.2 " + "b" * 4500,
            "Artikel 1.3 " + "c" * 4500,
        ]
    )
    return _fake_document(text)


class _ChunkStub:
    """Mô hình giả: trả luật theo chữ lấp đầy đoạn; ghi lại đoạn đã gọi.

    `fail_after=k` thì chết (ModelCallError) ở lần gọi thứ k+1, mô
    phỏng lần chạy hỏng giữa chừng.
    """

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_after: int | None = fail_after

    def reflect_document(self, text: str, facts: Sequence[FactRead]) -> ReflectorResult:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise ModelCallError("mô hình giả chết sau k đoạn")
        self.calls.append(text)
        if "b" * 10 in text:
            insight = _insight("response", "aanvraag", "bezwaar")
        elif "c" * 10 in text:
            insight = _insight("response", "ontwerpbesluit", "bezwaar")
        else:
            insight = _insight("response", "aanvraag", "ontwerpbesluit")
        return ReflectorResult(insights=(insight,), tokens_in=10, tokens_out=20)


def _tom_tat(
    extraction: WaboExtraction,
) -> tuple[int, int, int, int, int, int, int, tuple[str, ...]]:
    """Tóm tắt để so tương đương: số đếm theo cổng + luật đã chấp nhận."""
    return (
        extraction.extracted,
        extraction.unmapped,
        extraction.conditional,
        extraction.beta_filtered,
        extraction.accepted,
        extraction.tokens_in,
        extraction.tokens_out,
        tuple(fact.canonical_key for fact in extraction.facts),
    )


def test_boc_text_html_loai_the_giu_noi_dung():
    text = extract_wabo_text(FAKE_HTML)
    assert "Wet algemene bepalingen omgevingsrecht" in text
    assert "Artikel 1.1 De aanvraag wordt ingediend." in text
    assert "var x = 1;" not in text
    assert ".x{color:red}" not in text
    assert "<p>" not in text


def test_parse_valid_during_doi_sang_nua_mo():
    start, end = parse_valid_during("2015-01-01/2015-03-31")
    assert start == datetime(2015, 1, 1, tzinfo=UTC)
    assert end == datetime(2015, 4, 1, tzinfo=UTC)


def test_parse_valid_during_sai_bao_loi():
    with pytest.raises(ValueError):
        parse_valid_during("2015-01-01")
    with pytest.raises(ValueError):
        parse_valid_during("31-03-2015/01-01-2015")
    with pytest.raises(ValueError):
        parse_valid_during("2015-03-31/2015-01-01")


def test_load_wabo_document_sai_sha_bao_loi(tmp_path):
    html_path = tmp_path / "wabo.html"
    html_path.write_text(FAKE_HTML, encoding="utf-8")
    mapping = _fake_mapping("0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        load_wabo_document(html_path, mapping=mapping)


def test_load_wabo_document_thieu_tep_bao_loi(tmp_path):
    mapping = _fake_mapping("0" * 64)
    with pytest.raises(FileNotFoundError):
        load_wabo_document(tmp_path / "khong-co.html", mapping=mapping)


def test_load_wabo_document_that_dung_sha():
    """Văn bản thật trong cache: SHA khớp bảng gắn, text có điều luật."""
    cache = Path.home() / ".cache" / "praxon" / "wabo" / "wabo-2015-01-01.html"
    if not cache.is_file():
        pytest.skip("chưa tải văn bản Wabo về cache")
    document = load_wabo_document(cache, mapping=default_dutch_mapping())
    assert document.version == "2015-01-01"
    assert document.valid_start == datetime(2015, 1, 1, tzinfo=UTC)
    assert document.valid_end == datetime(2015, 4, 1, tzinfo=UTC)
    assert "Artikel 1.1" in document.text
    assert document.sha256 == hashlib.sha256(cache.read_bytes()).hexdigest()


def test_split_wabo_text_khong_cat_dieu():
    text = "\n\n".join(
        [
            "Mở đầu văn bản.",
            "Artikel 1.1 " + "x" * 30,
            "Artikel 1.2 " + "y" * 30,
            "Artikel 1.3 " + "z" * 30,
        ]
    )
    chunks = split_wabo_text(text, max_chars=60)
    assert chunks
    assert all(0 < len(chunk) <= 60 for chunk in chunks)
    joined = "\n\n".join(chunks)
    assert [line for line in joined.split("\n") if line.startswith("Artikel")] == [
        "Artikel 1.1 " + "x" * 30,
        "Artikel 1.2 " + "y" * 30,
        "Artikel 1.3 " + "z" * 30,
    ]


def test_split_wabo_text_van_ban_rong():
    assert split_wabo_text("") == ()
    assert split_wabo_text("   \n  ") == ()


def test_split_chunk_at_article_chia_dung_ranh_gioi():
    chunk = (
        "Artikel 8.1 Toon relaties in het eerste lid.\n\n"
        "Artikel 8.2 Het tweede lid volgt.\n\n"
        "Artikel 8.3 Toon relaties in het derde lid.\n\n"
        "Artikel 8.4 Het vierde lid sluit af."
    )
    first, second = split_chunk_at_article(chunk, marker="Artikel 8.3")
    assert first.startswith("Artikel 8.1")
    assert "Artikel 8.2" in first
    assert "Artikel 8.3" not in first
    assert second.startswith("Artikel 8.3")
    assert "Artikel 8.4" in second
    assert f"{first}\n\n{second}" == chunk
    with pytest.raises(ValueError):
        split_chunk_at_article(chunk, marker="Artikel 8.5")
    with pytest.raises(ValueError):
        split_chunk_at_article(chunk, marker="Artikel 8.1")
    with pytest.raises(ValueError):
        split_chunk_at_article(chunk, marker="")
    # "Artikel 8.3" không được khớp "Artikel 8.30" (số điều dài hơn).
    with pytest.raises(ValueError):
        split_chunk_at_article(
            "Artikel 8.30 " + "x" * 10 + "\n\nArtikel 8.31 " + "y" * 10,
            marker="Artikel 8.3",
        )


def test_tach_doan_50_thanh_53_doan():
    """Đoạn 50 thật tách tại Artikel 8.3: 53 đoạn, 0-49 không đổi từng byte."""
    cache = Path.home() / ".cache" / "praxon" / "wabo" / "wabo-2015-01-01.html"
    if not cache.is_file():
        pytest.skip("chưa tải văn bản Wabo về cache")
    document = load_wabo_document(cache, mapping=default_dutch_mapping())
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 52
    first, second = split_chunk_at_article(chunks[50], marker="Artikel 8.3")
    assert first.startswith("Artikel 8.1")
    assert "Artikel 8.2" in first
    assert "Artikel 8.3" not in first
    assert second.startswith("Artikel 8.3")
    assert "Artikel 8.4" in second
    assert len(first) == 1830
    assert len(second) == 1976
    assert f"{first}\n\n{second}" == chunks[50]
    split = (*chunks[:50], first, second, chunks[51])
    assert len(split) == 53
    assert split[:50] == chunks[:50]
    assert split[52] == chunks[51]


def test_tach_doan_thieu_co_bao_loi():
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    with pytest.raises(ValueError):
        extract_wabo_rules(
            reflect_document=_fake_reflect([]),
            document=document,
            mapping=mapping,
            traces=(),
            policy=policy,
            split_chunk=0,
        )
    with pytest.raises(ValueError):
        extract_wabo_rules(
            reflect_document=_fake_reflect([]),
            document=document,
            mapping=mapping,
            traces=(),
            policy=policy,
            split_chunk_at="Artikel 1.1",
        )
    with pytest.raises(ValueError):
        extract_wabo_rules(
            reflect_document=_fake_reflect([]),
            document=document,
            mapping=mapping,
            traces=(),
            policy=policy,
            split_chunk=5,
            split_chunk_at="Artikel 1.1",
        )
    with pytest.raises(ValueError):
        extract_wabo_rules(
            reflect_document=_fake_reflect([]),
            document=document,
            mapping=mapping,
            traces=(),
            policy=policy,
            split_chunk=0,
            split_chunk_at="Artikel 9.9",
        )


def test_resolve_activity_khai_niem_va_ten_nl():
    mapping = default_dutch_mapping()
    assert resolve_activity("aanvraag", mapping) == AANVRAAG
    assert resolve_activity("  Aanvraag ", mapping) == AANVRAAG
    assert resolve_activity("fase aanvraag ontvangen", mapping) == AANVRAAG
    assert resolve_activity("ontwerpbesluit", mapping) == ONTWERP
    assert resolve_activity("khái niệm không có", mapping) is None
    assert resolve_activity("", mapping) is None


def test_trich_luat_dung_duoc_cong_beta_duyet():
    """Luật gắn đúng + bằng chứng 30/30 -> vào global, mang valid_during Wabo."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    insights = [_insight("response", "aanvraag", "ontwerpbesluit")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.extracted == 1
    assert extraction.accepted == 1
    assert extraction.beta_filtered == 0
    assert extraction.unmapped == 0
    assert extraction.conditional == 0
    fact = extraction.facts[0]
    assert fact.tenant_id == "global"
    assert fact.scope == "global"
    assert fact.status == "active"
    assert fact.canonical_key == f"response({AANVRAAG}, {ONTWERP})"
    assert fact.statement == f"{AANVRAAG} response {ONTWERP}"
    assert fact.valid_start == datetime(2015, 1, 1, tzinfo=UTC)
    assert fact.valid_end == datetime(2015, 4, 1, tzinfo=UTC)
    assert fact.support == 30
    assert fact.confidence == 1.0
    assert fact.activation == AANVRAAG
    assert fact.target == ONTWERP
    assert fact.candidate_id is None


def test_luat_gan_sai_bi_cong_beta_loai():
    """Luật gắn sai (bezwaar thay cho ontwerpbesluit): bằng chứng 0/30 -> loại."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    insights = [_insight("response", "aanvraag", "bezwaar")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.extracted == 1
    assert extraction.accepted == 0
    assert extraction.beta_filtered == 1
    assert extraction.facts == ()
    assert extraction.outcomes[0].posterior < policy.retire_probability


def test_khai_niem_chua_gan_bi_bo():
    """Khái niệm 'bouwen' không có trong bảng gắn -> bỏ qua, không bịa gắn."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 2.1 Het bouwen van een bouwwerk.")
    insights = [_insight("response", "bouwen", "besluit")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.extracted == 1
    assert extraction.unmapped == 1
    assert extraction.accepted == 0
    assert extraction.facts == ()


def test_luat_co_dieu_kien_bi_bo():
    """Luật có điều kiện không đo được bằng chứng -> bỏ qua, đếm riêng."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    insights = [_insight("response", "aanvraag", "ontwerpbesluit", condition="case_type = X")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.extracted == 1
    assert extraction.conditional == 1
    assert extraction.accepted == 0
    assert extraction.facts == ()


def test_luat_trung_chi_dem_mot_lan():
    """Cùng luật từ hai đoạn -> trích được tính một lần (khử trùng)."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    # Một điều dài hơn max_chars -> tách thành 2 đoạn; mô hình giả trả
    # cùng luật cho cả hai đoạn.
    text = "Artikel 1.1 " + "a" * 4500
    document = _fake_document(text)
    insights = [_insight("response", "aanvraag", "ontwerpbesluit")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.extracted == 1
    assert extraction.accepted == 1


def test_load_bpic_traces_thieu_tep_bao_loi(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"BPIC15_1\.xes"):
        load_bpic_traces(tmp_path)


def test_format_wabo_report_in_du_so_lieu():
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    insights = [
        _insight("response", "aanvraag", "ontwerpbesluit"),
        _insight("response", "aanvraag", "bezwaar"),
    ]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    report = format_wabo_report(extraction)
    assert "Trích được: 2 luật" in report
    assert "Cổng Beta loại: 1 luật" in report
    assert "Chấp nhận vào global: 1 luật" in report
    assert f"response({AANVRAAG}, {ONTWERP})" in report


def test_dem_luat_trich_dan_khong_khop_vao_bao_cao():
    """Số luật bị bỏ vì trích dẫn không khớp được cộng dồn và in ra báo cáo."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    insights = [_insight("response", "aanvraag", "ontwerpbesluit")]
    extraction = extract_wabo_rules(
        reflect_document=_fake_reflect(insights, dropped=2),
        document=document,
        mapping=mapping,
        traces=_traces_aanvraag_roi_ontwerp(30),
        policy=policy,
    )
    assert extraction.source_quote_dropped == 2
    assert "Trích dẫn nguồn không khớp (bỏ): 2 luật" in format_wabo_report(extraction)


def test_main_thieu_du_lieu_tra_1(tmp_path):
    code = main(["--html", str(tmp_path / "khong-co.html")])
    assert code == 1


def test_main_chay_duoc_voi_mo_hinh_gia(monkeypatch, tmp_path):
    """Lệnh chạy hết đường dây với mô hình + dữ liệu giả (không gọi mạng)."""
    html_path = tmp_path / "wabo.html"
    html_path.write_text(FAKE_HTML, encoding="utf-8")
    document = WaboDocument(
        source_url="https://example.invalid/wabo",
        version="2015-01-01",
        valid_start=datetime(2015, 1, 1, tzinfo=UTC),
        valid_end=datetime(2015, 4, 1, tzinfo=UTC),
        text=FAKE_TEXT,
        sha256="giả",
    )
    insights = [_insight("response", "aanvraag", "ontwerpbesluit")]
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_wabo_document",
        lambda path, mapping: document,
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_bpic_traces",
        lambda cache_dir: _traces_aanvraag_roi_ontwerp(30),
    )

    class FakeReflector:
        def reflect_document(self, text: str, facts: Sequence[FactRead]) -> ReflectorResult:
            return ReflectorResult(insights=tuple(insights), tokens_in=5, tokens_out=6)

    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.build_reflector",
        lambda settings, seed, max_tokens=None: FakeReflector(),
    )
    code = main(["--html", str(html_path), "--cache-dir", str(tmp_path)])
    assert code == 0


def test_main_tach_doan_voi_co_split_chunk(monkeypatch, tmp_path):
    """Cờ --split-chunk/--split-at tới được extract: 1 đoạn thành 2 lần gọi."""
    html_path = tmp_path / "wabo.html"
    html_path.write_text(FAKE_HTML, encoding="utf-8")
    document = WaboDocument(
        source_url="https://example.invalid/wabo",
        version="2015-01-01",
        valid_start=datetime(2015, 1, 1, tzinfo=UTC),
        valid_end=datetime(2015, 4, 1, tzinfo=UTC),
        text=FAKE_TEXT,
        sha256="giả",
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_wabo_document",
        lambda path, mapping: document,
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_bpic_traces",
        lambda cache_dir: _traces_aanvraag_roi_ontwerp(30),
    )
    calls: list[str] = []

    class FakeReflector:
        def reflect_document(self, text: str, facts: Sequence[FactRead]) -> ReflectorResult:
            calls.append(text)
            return ReflectorResult(insights=(), tokens_in=1, tokens_out=2)

    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.build_reflector",
        lambda settings, seed, max_tokens=None: FakeReflector(),
    )
    code = main(
        [
            "--html",
            str(html_path),
            "--cache-dir",
            str(tmp_path),
            "--split-chunk",
            "0",
            "--split-at",
            "Artikel 3.1",
        ]
    )
    assert code == 0
    assert len(calls) == 2
    assert calls[0].startswith("Wet algemene bepalingen")
    assert calls[1].startswith("Artikel 3.1")


def test_main_co_max_tokens_toi_duoc_build_reflector(monkeypatch, tmp_path):
    """Cờ --max-tokens tới được build_reflector; mặc định là None."""
    html_path = tmp_path / "wabo.html"
    html_path.write_text(FAKE_HTML, encoding="utf-8")
    document = WaboDocument(
        source_url="https://example.invalid/wabo",
        version="2015-01-01",
        valid_start=datetime(2015, 1, 1, tzinfo=UTC),
        valid_end=datetime(2015, 4, 1, tzinfo=UTC),
        text=FAKE_TEXT,
        sha256="giả",
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_wabo_document",
        lambda path, mapping: document,
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_bpic_traces",
        lambda cache_dir: _traces_aanvraag_roi_ontwerp(30),
    )
    seen: list[int | None] = []

    class FakeReflector:
        def reflect_document(self, text: str, facts: Sequence[FactRead]) -> ReflectorResult:
            return ReflectorResult(insights=(), tokens_in=1, tokens_out=2)

    def fake_build(
        settings: Settings, seed: int, max_tokens: int | None = None
    ) -> FakeReflector:
        seen.append(max_tokens)
        return FakeReflector()

    monkeypatch.setattr("praxon_core.learning.wabo_rules.build_reflector", fake_build)
    base = ["--html", str(html_path), "--cache-dir", str(tmp_path)]
    assert main(base) == 0
    assert main([*base, "--max-tokens", "2000"]) == 0
    assert seen == [None, 2000]


def test_jsonl_ghi_dong_hop_le_va_nap_lai_duoc(monkeypatch, tmp_path):
    """Main với --chunks-out: mỗi dòng JSON hợp lệ, Insight validate được."""
    html_path = tmp_path / "wabo.html"
    html_path.write_text(FAKE_HTML, encoding="utf-8")
    document = WaboDocument(
        source_url="https://example.invalid/wabo",
        version="2015-01-01",
        valid_start=datetime(2015, 1, 1, tzinfo=UTC),
        valid_end=datetime(2015, 4, 1, tzinfo=UTC),
        text=FAKE_TEXT,
        sha256="giả",
    )
    insights = [_insight("response", "aanvraag", "ontwerpbesluit")]
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_wabo_document",
        lambda path, mapping: document,
    )
    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.load_bpic_traces",
        lambda cache_dir: _traces_aanvraag_roi_ontwerp(30),
    )

    class FakeReflector:
        def reflect_document(self, text: str, facts: Sequence[FactRead]) -> ReflectorResult:
            return ReflectorResult(insights=tuple(insights), tokens_in=5, tokens_out=6)

    monkeypatch.setattr(
        "praxon_core.learning.wabo_rules.build_reflector",
        lambda settings, seed, max_tokens=None: FakeReflector(),
    )
    chunks_path = tmp_path / "chunks.jsonl"
    code = main(
        [
            "--html",
            str(html_path),
            "--cache-dir",
            str(tmp_path),
            "--chunks-out",
            str(chunks_path),
        ]
    )
    assert code == 0
    chunk = split_wabo_text(FAKE_TEXT)[0]
    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["chunk_index"] == 0
    assert data["chunk_chars"] == len(chunk)
    assert data["chunk_sha256"] == hashlib.sha256(chunk.encode("utf-8")).hexdigest()
    assert data["tokens_in"] == 5
    assert data["tokens_out"] == 6
    loaded = [Insight.model_validate(item) for item in data["insights"]]
    assert len(loaded) == 1
    assert loaded[0].template == "response"
    assert loaded[0].activation == "aanvraag"
    assert loaded[0].target == "ontwerpbesluit"


def test_noi_lai_tuong_duong_chay_lien_mach(tmp_path):
    """Chết sau 3 đoạn rồi nối lại: báo cáo == chạy liền mạch, stub chỉ gọi đoạn thiếu."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document_nhieu_doan()
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 6
    traces = _traces_day_du(30)
    stub_chuan = _ChunkStub()
    chuan = extract_wabo_rules(
        reflect_document=stub_chuan.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
    )
    chunks_path = tmp_path / "chunks.jsonl"
    stub_chet = _ChunkStub(fail_after=3)
    with pytest.raises(ModelCallError):
        extract_wabo_rules(
            reflect_document=stub_chet.reflect_document,
            document=document,
            mapping=mapping,
            traces=traces,
            policy=policy,
            chunks_out=chunks_path,
        )
    assert len(stub_chet.calls) == 3
    assert len(chunks_path.read_text(encoding="utf-8").splitlines()) == 3
    stub_noi = _ChunkStub()
    noi = extract_wabo_rules(
        reflect_document=stub_noi.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
        resume_from=chunks_path,
    )
    assert stub_noi.calls == list(chunks[3:])
    assert _tom_tat(noi) == _tom_tat(chuan)
    assert format_wabo_report(noi) == format_wabo_report(chuan)


def test_noi_lai_jsonl_giu_so_luat_trich_dan_bi_bo(tmp_path):
    """Nối lại JSONL giữ số luật trích dẫn bị bỏ của đoạn đã xong."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document("Artikel 1.1 De aanvraag wordt ingediend.")
    traces = _traces_aanvraag_roi_ontwerp(30)
    chunks_path = tmp_path / "chunks.jsonl"
    extract_wabo_rules(
        reflect_document=_fake_reflect(
            [_insight("response", "aanvraag", "ontwerpbesluit")], dropped=2
        ),
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
    )

    def reflect_chet(text: str, facts: Sequence[FactRead]) -> ReflectorResult:
        raise AssertionError("đoạn đã xong không được gọi lại mô hình")

    noi = extract_wabo_rules(
        reflect_document=reflect_chet,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        resume_from=chunks_path,
    )
    assert noi.source_quote_dropped == 2


def test_duoi_jsonl_hong_bi_bo_het_va_chay_lai(tmp_path, capsys):
    """Dòng cắt dở + dòng hợp lệ sau nó đều bị bỏ; đoạn đó chạy lại, kết quả đúng."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document_nhieu_doan()
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 6
    traces = _traces_day_du(30)
    stub_chuan = _ChunkStub()
    chuan = extract_wabo_rules(
        reflect_document=stub_chuan.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
    )
    chunks_path = tmp_path / "chunks.jsonl"
    extract_wabo_rules(
        reflect_document=_ChunkStub().reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
    )
    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    hong = '{"chunk_index": 3, "chunk_chars": 12'
    chunks_path.write_text(
        "\n".join([*lines[:3], hong, lines[4], lines[5]]) + "\n", encoding="utf-8"
    )
    stub = _ChunkStub()
    noi = extract_wabo_rules(
        reflect_document=stub.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
        resume_from=chunks_path,
    )
    assert stub.calls == list(chunks[3:])
    assert _tom_tat(noi) == _tom_tat(chuan)
    assert "cảnh báo" in capsys.readouterr().err


def test_dong_jsonl_sai_sha_bi_bo_va_chay_lai(tmp_path):
    """Dòng có SHA không khớp đoạn vừa tách thì bị bỏ cùng toàn bộ sau."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document_nhieu_doan()
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 6
    traces = _traces_day_du(30)
    stub_chuan = _ChunkStub()
    chuan = extract_wabo_rules(
        reflect_document=stub_chuan.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
    )
    chunks_path = tmp_path / "chunks.jsonl"
    extract_wabo_rules(
        reflect_document=_ChunkStub().reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
    )
    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    data = json.loads(lines[2])
    data["chunk_sha256"] = "0" * 64
    lines[2] = json.dumps(data, ensure_ascii=False)
    chunks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stub = _ChunkStub()
    noi = extract_wabo_rules(
        reflect_document=stub.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
        resume_from=chunks_path,
    )
    assert stub.calls == list(chunks[2:])
    assert _tom_tat(noi) == _tom_tat(chuan)


def test_noi_lai_ton_trong_limit_chunks(tmp_path):
    """--limit-chunks áp trước: nối lại chỉ chạy các đoạn còn thiếu dưới N."""
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    document = _fake_document_nhieu_doan()
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 6
    traces = _traces_day_du(30)
    stub_chuan = _ChunkStub()
    chuan = extract_wabo_rules(
        reflect_document=stub_chuan.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        limit_chunks=4,
    )
    chunks_path = tmp_path / "chunks.jsonl"
    stub_chet = _ChunkStub(fail_after=2)
    with pytest.raises(ModelCallError):
        extract_wabo_rules(
            reflect_document=stub_chet.reflect_document,
            document=document,
            mapping=mapping,
            traces=traces,
            policy=policy,
            limit_chunks=4,
            chunks_out=chunks_path,
        )
    assert len(chunks_path.read_text(encoding="utf-8").splitlines()) == 2
    stub_noi = _ChunkStub()
    noi = extract_wabo_rules(
        reflect_document=stub_noi.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        limit_chunks=4,
        chunks_out=chunks_path,
        resume_from=chunks_path,
    )
    assert stub_noi.calls == list(chunks[2:4])
    assert _tom_tat(noi) == _tom_tat(chuan)


def test_noi_lai_jsonl_50_dong_vao_danh_sach_53_doan(tmp_path):
    """JSONL 50 dòng cũ nạp đủ vào danh sách 53 đoạn; chỉ 3 đoạn mới gọi model."""
    cache = Path.home() / ".cache" / "praxon" / "wabo" / "wabo-2015-01-01.html"
    if not cache.is_file():
        pytest.skip("chưa tải văn bản Wabo về cache")
    document = load_wabo_document(cache, mapping=default_dutch_mapping())
    mapping = default_dutch_mapping()
    policy = default_rule_table().policy
    traces = _traces_day_du(30)
    chunks = split_wabo_text(document.text)
    assert len(chunks) == 52
    chunks_path = tmp_path / "chunks.jsonl"
    stub_50 = _ChunkStub()
    extract_wabo_rules(
        reflect_document=stub_50.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        limit_chunks=50,
        chunks_out=chunks_path,
    )
    assert len(chunks_path.read_text(encoding="utf-8").splitlines()) == 50
    assert len(stub_50.calls) == 50
    stub_noi = _ChunkStub()
    noi = extract_wabo_rules(
        reflect_document=stub_noi.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        chunks_out=chunks_path,
        resume_from=chunks_path,
        split_chunk=50,
        split_chunk_at="Artikel 8.3",
    )
    assert len(stub_noi.calls) == 3
    assert stub_noi.calls[0].startswith("Artikel 8.1")
    assert stub_noi.calls[1].startswith("Artikel 8.3")
    assert stub_noi.calls[2] == chunks[51]
    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 53
    assert [json.loads(line)["chunk_index"] for line in lines] == list(range(53))
    stub_chuan = _ChunkStub()
    chuan = extract_wabo_rules(
        reflect_document=stub_chuan.reflect_document,
        document=document,
        mapping=mapping,
        traces=traces,
        policy=policy,
        split_chunk=50,
        split_chunk_at="Artikel 8.3",
    )
    assert _tom_tat(noi) == _tom_tat(chuan)
    assert format_wabo_report(noi) == format_wabo_report(chuan)
