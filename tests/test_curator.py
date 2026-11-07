"""Curator (task 7.2): sinh Delta bốn loại, bảng cặp mẫu đối nghịch."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from praxon_core.learning.candidate import FactStatus
from praxon_core.learning.curator import (
    DeltaKind,
    FactRead,
    Insight,
    InsightSource,
    canonical_key_for,
    curate,
    opposite_template,
    to_candidate,
)

#: Thời điểm hiệu lực cố định cho test (xác định — không dùng giờ thật).
VALID_START = datetime(2030, 1, 1, tzinfo=UTC)


def _insight(
    template: str = "response",
    activation: str = "A",
    target: str = "B",
    condition: str | None = None,
    scope: str = "acme",
) -> Insight:
    return Insight(
        template=template,
        activation=activation,
        target=target,
        condition=condition,
        evidence_episode_ids=["e1", "e2"],
        source=InsightSource.TRACE,
        scope=scope,
    )


def _fact(
    key: str,
    status: FactStatus = FactStatus.ACTIVE,
    scope: str = "acme",
    fact_id: str = "f1",
    template: str = "response",
    activation: str = "A",
    target: str = "B",
) -> FactRead:
    return FactRead(
        id=fact_id,
        scope=scope,
        canonical_key=key,
        template=template,
        activation=activation,
        target=target,
        condition=None,
        status=status,
    )


def test_canonical_key_ghep_dung_dang_spec():
    assert (
        canonical_key_for("precedence", "Record Goods Receipt", "Record Invoice Receipt", None)
        == "precedence(Record Goods Receipt, Record Invoice Receipt)"
    )


def test_canonical_key_co_dieu_kien_them_doi_so_thu_ba():
    assert canonical_key_for("response", "A", "B", "loai = 'x'") == "response(A, B, loai = 'x')"


def test_bang_doi_nghich_chi_co_response_va_precedence():
    assert opposite_template("response") == "not_response"
    assert opposite_template("not_response") == "response"
    assert opposite_template("precedence") == "not_precedence"
    assert opposite_template("not_precedence") == "precedence"
    assert opposite_template("succession") is None


def test_insight_moi_thi_add():
    deltas = curate(_insight(), [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    assert deltas[0].canonical_key == "response(A, B)"
    assert deltas[0].fact is None


def test_trung_khoa_fact_active_thi_confirm():
    fact = _fact("response(A, B)", FactStatus.ACTIVE)
    deltas = curate(_insight(), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONFIRM]
    assert deltas[0].fact is fact
    assert deltas[0].canonical_key == "response(A, B)"


def test_trung_khoa_fact_trial_thi_confirm():
    fact = _fact("response(A, B)", FactStatus.TRIAL)
    deltas = curate(_insight(), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONFIRM]


def test_doi_nghich_fact_active_thi_contradict():
    fact = _fact("response(A, B)", FactStatus.ACTIVE)
    deltas = curate(_insight(template="not_response"), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONTRADICT]
    assert deltas[0].fact is fact
    assert deltas[0].canonical_key == "response(A, B)"


def test_doi_nghich_fact_trial_thi_retire():
    fact = _fact("response(A, B)", FactStatus.TRIAL)
    deltas = curate(_insight(template="not_response"), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.RETIRE]
    assert deltas[0].fact is fact


def test_doi_nghich_precedence_fact_active_thi_contradict():
    fact = _fact(
        "precedence(A, B)",
        FactStatus.ACTIVE,
        template="precedence",
    )
    deltas = curate(_insight(template="not_precedence"), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONTRADICT]


def test_template_khong_co_doi_nghich_thi_bo_qua_bang_doi_nghich():
    deltas = curate(_insight(template="succession"), [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    assert deltas[0].canonical_key == "succession(A, B)"


def test_fact_da_retired_khong_chan_insight_moi():
    fact = _fact("response(A, B)", FactStatus.RETIRED)
    deltas = curate(_insight(), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]


def test_fact_doi_nghich_da_retired_khong_chan_insight_moi():
    fact = _fact("response(A, B)", FactStatus.RETIRED)
    deltas = curate(_insight(template="not_response"), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]


def test_fact_khac_pham_vi_thi_bo_qua():
    fact = _fact("response(A, B)", FactStatus.ACTIVE, scope="globex")
    deltas = curate(_insight(), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]


def test_tap_fact_chua_ca_khoa_lan_doi_nghich_thi_tra_ca_hai_delta():
    same = _fact("response(A, B)", FactStatus.ACTIVE, fact_id="f1")
    opposite = _fact(
        "not_response(A, B)",
        FactStatus.ACTIVE,
        fact_id="f2",
        template="not_response",
    )
    deltas = curate(_insight(), [same, opposite])
    assert [d.kind for d in deltas] == [DeltaKind.CONFIRM, DeltaKind.CONTRADICT]


def test_dieu_kien_khac_nhau_la_khoa_khac_nhau():
    fact = _fact("response(A, B, loai = 'x')", FactStatus.ACTIVE)
    deltas = curate(_insight(condition="loai = 'y'"), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]


def test_to_candidate_add_mang_du_thong_tin():
    candidate = to_candidate(curate(_insight(), [])[0], valid_start=VALID_START)
    # Insight mang tên tenant "acme" — to_candidate ánh xạ về 'tenant'
    # (DB chỉ nhận 'tenant'/'global'); danh tính tenant ở tenant_id.
    assert candidate.target_scope == "tenant"
    assert candidate.status == "pending"
    assert candidate.payload["kind"] == "add"
    assert candidate.payload["canonical_key"] == "response(A, B)"
    assert candidate.payload["template"] == "response"
    assert candidate.payload["statement"] == "A response B"
    assert candidate.payload["valid_start"] == "2030-01-01T00:00:00Z"
    assert candidate.payload["fact_id"] is None
    assert "fact_canonical_key" not in candidate.payload
    assert "fact_status" not in candidate.payload
    assert candidate.evidence_episode_ids == ["e1", "e2"]
    assert candidate.rule_id is None
    assert candidate.decided_by is None


def test_to_candidate_anh_xa_target_scope_ve_tenant_hoac_global():
    """to_candidate ánh xạ scope Insight về 'tenant'/'global' (DB chỉ nhận hai giá trị)."""
    for scope, expected in (("global", "global"), ("acme", "tenant"), ("tenant", "tenant")):
        candidate = to_candidate(curate(_insight(scope=scope), [])[0], valid_start=VALID_START)
        assert candidate.target_scope == expected


def test_to_candidate_contradict_mang_fact_bi_tac_dong():
    fact = _fact("response(A, B)", FactStatus.ACTIVE)
    candidate = to_candidate(
        curate(_insight(template="not_response"), [fact])[0], valid_start=VALID_START
    )
    assert candidate.payload["kind"] == "contradict"
    assert candidate.payload["fact_id"] == "f1"
    # Khóa là khóa của ràng buộc MỚI (đối nghịch), không phải khóa fact cũ —
    # sửa lỗi §2 (khóa/mẫu lệch ở CONTRADICT/RETIRE).
    assert candidate.payload["canonical_key"] == "not_response(A, B)"
    assert candidate.payload["template"] == "not_response"
    assert candidate.payload["statement"] == "A not_response B"
    assert "fact_canonical_key" not in candidate.payload
    assert "fact_status" not in candidate.payload


def test_khong_import_bat_cu_module_mo_hinh_nao():
    source = (
        Path(__file__).parent.parent
        / "packages"
        / "core"
        / "src"
        / "praxon_core"
        / "learning"
        / "curator.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {
        name
        for name in imported
        if name.startswith("praxon_core.adapters") or name in {"openai", "anthropic"}
    }


def test_curator_la_ham_thuan_khong_doi_dau_vao():
    insight = _insight()
    fact = _fact("response(A, B)", FactStatus.ACTIVE)
    facts = [fact]
    first = curate(insight, facts)
    second = curate(insight, facts)
    assert first == second
    assert facts == [fact]
