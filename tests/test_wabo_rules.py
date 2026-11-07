"""Test trích luật thứ tự từ Wabo vào `global` (task 9.1).

Dữ liệu test tự viết (HTML giả, trace giả, mô hình giả) — không gọi
mô hình thật, không phụ thuộc cache Wabo/BPIC, trừ một test nạp văn
bản thật (skip khi cache trống, như test tải bộ 104 câu của 6.5).
"""

import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from praxon_core.declare.index import Trace
from praxon_core.learning.coordinator import ReflectorResult
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.dutch_mapping import DutchMappingTable, default_dutch_mapping
from praxon_core.learning.rules import default_rule_table
from praxon_core.learning.wabo_rules import (
    WaboDocument,
    extract_wabo_rules,
    extract_wabo_text,
    format_wabo_report,
    load_bpic_traces,
    load_wabo_document,
    main,
    parse_valid_during,
    resolve_activity,
    split_wabo_text,
)

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
) -> Callable[[str, Sequence[FactRead]], ReflectorResult]:
    """Hàm giả cho đường `reflect_document`: trả insight đã định sẵn."""

    def reflect_document(text: str, facts: Sequence[FactRead]) -> ReflectorResult:
        return ReflectorResult(insights=tuple(insights), tokens_in=10, tokens_out=20)

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
        lambda settings, seed: FakeReflector(),
    )
    code = main(["--html", str(html_path), "--cache-dir", str(tmp_path)])
    assert code == 0
