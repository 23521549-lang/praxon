"""Bảng gắn khái niệm tiếng Hà Lan (Wabo) với hoạt động log BPIC 2015 (task 9.2).

Cổng ra (plan file): bảng gắn nạp được; gắn sai thì luật bị cổng Beta loại
chứ không áp sai.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule
from praxon_core.learning.beta import Prior, posterior_prob_ge
from praxon_core.learning.calibration import count_rule_evidence
from praxon_core.learning.dutch_mapping import (
    default_dutch_mapping,
    load_dutch_mapping,
)
from praxon_core.learning.rules import default_rule_table

AANVRAAG = "01_HOOFD_015"
ONTWERP = "01_HOOFD_440_1"
BEZWAAR = "01_BB_540"


def test_bang_gan_nap_duoc():
    """Bảng gắn nạp được: 13 khái niệm, 123 hoạt động, 8 khái niệm chưa gắn."""
    table = default_dutch_mapping()
    assert len(table.concept) == 13
    assert sum(len(entry.activities) for entry in table.concept) == 123
    assert len(table.unmapped) == 8
    assert table.wabo.source_url == ("https://wetten.overheid.nl/BWBR0024779/2015-01-01")
    assert table.wabo.version == "2015-01-01"


def test_moi_muc_co_du_hai_dau():
    """Mỗi khái niệm có term + ít nhất một hoạt động.

    Mỗi hoạt động có mã, tên NL, tần suất dương; canonical nằm trong danh
    sách hoạt động.
    """
    table = default_dutch_mapping()
    for entry in table.concept:
        assert entry.term
        assert entry.wabo_count >= 0
        assert entry.activities
        for activity in entry.activities:
            assert activity.code
            assert activity.dutch_name
            assert activity.events > 0
        assert entry.canonical in [a.code for a in entry.activities]


def test_canonical_khac_nhau_giua_cac_khai_niem():
    """Mỗi khái niệm có một hoạt động đại diện riêng (không trùng nhau)."""
    table = default_dutch_mapping()
    canonicals = [entry.canonical for entry in table.concept]
    assert len(set(canonicals)) == len(canonicals)


def test_khai_niem_chua_gan_co_ly_do():
    """Khái niệm chưa gắn đều có lý do.

    Các khái niệm Wabo không có hoạt động log tương ứng
    (bouwen/slopen/weigeren/verlenen) nằm trong đó.
    """
    table = default_dutch_mapping()
    assert table.unmapped_terms() == (
        "bouwen",
        "slopen",
        "weigeren",
        "verlenen",
        "vergunningvrij",
        "ontvangstbevestiging",
        "inspraak",
        "kappen",
    )
    for entry in table.unmapped:
        assert entry.reason
    assert not table.is_mapped("bouwen")
    assert not table.is_mapped("weigeren")


def test_canonical_activity_va_activities_for():
    """Tra cứu theo khái niệm: canonical là mã log; tập hoạt động đầy đủ."""
    table = default_dutch_mapping()
    assert table.canonical_activity("ontwerpbesluit") == ONTWERP
    assert table.canonical_activity("aanvraag") == AANVRAAG
    assert table.canonical_activity("bezwaar") == BEZWAAR
    assert table.is_mapped("zienswijze")
    codes = [a.code for a in table.activities_for("voorlopige voorziening")]
    assert codes == [
        "01_BB_590",
        "01_BB_640",
        "01_BB_600",
        "01_BB_610",
        "01_BB_650_1",
        "01_BB_650_2",
    ]


def test_khai_niem_la_bao_loi():
    """Tra cứu khái niệm không có trong bảng thì báo lỗi rõ ràng."""
    table = default_dutch_mapping()
    with pytest.raises(KeyError):
        table.canonical_activity("khong-co-khai-niem-nay")
    with pytest.raises(KeyError):
        table.activities_for("khong-co-khai-niem-nay")
    assert not table.is_mapped("khong-co-khai-niem-nay")


def test_bang_gan_tu_choi_tep_hong(tmp_path):
    """Tệp TOML hỏng bị từ chối lúc nạp thay vì lọt vào dùng.

    Canonical ngoài danh sách hoạt động là một lỗi như vậy.
    """
    good = default_dutch_mapping()
    bad = tmp_path / "hong.toml"
    bad.write_text(
        '[wabo]\nsource_url = "https://example.invalid/x"\nversion = "2015-01-01"\n'
        'valid_during = "2015-01-01/2015-03-31"\nsha256_html = "00"\n'
        '[[concept]]\nterm = "aanvraag"\nwabo_count = 1\n'
        'canonical = "01_XXX_999"\nnote = ""\n'
        "activities = [\n"
        '  { code = "01_HOOFD_015", dutch_name = "fase aanvraag ontvangen",'
        " events = 1 },\n"
        "]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_dutch_mapping(bad)
    assert good.canonical_activity("aanvraag") == AANVRAAG


def _traces_aanvraag_roi_ontwerp(n: int) -> tuple[Trace, ...]:
    """Tạo n trace: đơn (aanvraag) rồi quyết định dự thảo (ontwerpbesluit)."""
    return tuple(Trace(events=(AANVRAAG, ONTWERP)) for _ in range(n))


def test_luat_gan_dung_duoc_cong_beta_duyet():
    """Luật dùng hoạt động gắn ĐÚNG được cổng Beta duyệt.

    Ontwerpbesluit -> 01_HOOFD_440_1: bằng chứng 30/30 trên trace, hậu
    nghiệm Beta vượt ngưỡng lên 0,95.
    """
    policy = default_rule_table().policy
    traces = _traces_aanvraag_roi_ontwerp(30)
    rule = Rule(
        template="response", first=AANVRAAG, second=ONTWERP, support=1.0, confidence=1.0
    )
    evidence = count_rule_evidence(rule, traces)
    assert (evidence.successes, evidence.trials) == (30, 30)
    probability = posterior_prob_ge(
        Prior(canonical_key=rule.canonical_key, confidence=0.5, strength=None),
        evidence.successes,
        evidence.trials,
        policy.confidence_threshold,
        strength_default=policy.prior_strength_default,
    )
    assert probability >= policy.promote_probability


def test_luat_gan_sai_bi_cong_beta_loai():
    """Luật dùng hoạt động gắn SAI bị cổng Beta loại.

    Ontwerpbesluit -> mã của 'bezwaar' (01_BB_540): bằng chứng 0/30 trên
    cùng trace, hậu nghiệm Beta rớt dưới ngưỡng gỡ 0,05 — cổng loại luật,
    không áp sai.
    """
    policy = default_rule_table().policy
    table = default_dutch_mapping()
    wrong = table.canonical_activity("bezwaar")
    assert wrong == BEZWAAR
    traces = _traces_aanvraag_roi_ontwerp(30)
    rule = Rule(template="response", first=AANVRAAG, second=wrong, support=1.0, confidence=1.0)
    evidence = count_rule_evidence(rule, traces)
    assert (evidence.successes, evidence.trials) == (0, 30)
    probability = posterior_prob_ge(
        Prior(canonical_key=rule.canonical_key, confidence=0.5, strength=None),
        evidence.successes,
        evidence.trials,
        policy.confidence_threshold,
        strength_default=policy.prior_strength_default,
    )
    assert probability < policy.retire_probability
