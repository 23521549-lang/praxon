"""Ground truth (task 8.1, plan con 8).

Cổng ra: không điều kiện nào được chấm bằng đáp án sinh từ chính nó;
đổi điều kiện không đổi đáp án.

Thí nghiệm then chốt dùng hai tập trace viết tay có luật rời nhau: phần
học chỉ có luật a→b, phần đo chỉ có luật c→d. Nếu đáp án lấy nhầm từ
phần học thì dự đoán từ phần học được chấm hoàn hảo (precision 1,0) —
đúng lỗi phép thử ngày 3/10 trong spec đã bắt được. Đáp án đúng (từ
phần đo) chấm dự đoán đó bằng 0, chứng tỏ không tự chấm.
"""

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import discover
from praxon_core.eval.ground_truth import (
    BPIC_TEST_SPLIT_SOURCE,
    GENERATOR_SOURCE,
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    GroundTruth,
    facts_from_rules,
    ground_truth_from_generator,
    ground_truth_from_test_traces,
)
from praxon_core.eval.metrics import FactScope, precision, recall
from praxon_core.learning.candidate import FactStatus
from praxon_core.synthetic.generator import GeneratorParams, generate

TENANT = "acme"


def _train_traces() -> tuple[Trace, ...]:
    """Phần học viết tay: chỉ luật a→b (a luôn đi trước b)."""
    return tuple(Trace(("a", "b")) for _ in range(4))


def _test_traces() -> tuple[Trace, ...]:
    """Phần đo viết tay: chỉ luật c→d (c luôn đi trước d)."""
    return tuple(Trace(("c", "d")) for _ in range(4))


def test_ground_truth_tu_bo_sinh_lay_dap_an_cua_bo_sinh():
    log = generate(tenant_id=TENANT, params=GeneratorParams(seed=42, n_cases=10))
    truth = ground_truth_from_generator(log)
    assert truth.tenant_id == TENANT
    assert truth.reference == log.ground_truth
    assert truth.source == GENERATOR_SOURCE
    assert len(truth.reference) == 56


def test_ground_truth_bpic_lay_tu_phan_do_khong_phai_phan_hoc():
    truth = ground_truth_from_test_traces(_test_traces(), tenant_id=TENANT)
    assert truth.tenant_id == TENANT
    assert truth.source == BPIC_TEST_SPLIT_SOURCE
    assert truth.support == GROUND_TRUTH_SUPPORT
    assert truth.confidence == GROUND_TRUTH_CONFIDENCE
    assert truth.reference == {"response(c, d)", "precedence(c, d)"}
    # Đúng ngưỡng cố định của module, không phải ngưỡng khác.
    assert truth.reference == {
        rule.canonical_key
        for rule in discover(
            _test_traces(),
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        )
    }


def test_khong_dieu_kien_nao_duoc_cham_bang_dap_an_sinh_tu_chinh_no():
    truth = ground_truth_from_test_traces(_test_traces(), tenant_id=TENANT)
    train_rules = discover(
        _train_traces(),
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    train_facts = facts_from_rules(train_rules, TENANT)
    # Dự đoán từ phần học chấm bằng đáp án phần đo: không luật nào trùng.
    assert precision(train_facts, truth.reference) == 0.0
    assert recall(train_facts, truth.reference) == 0.0
    # Đối chứng: nếu đáp án lấy nhầm từ phần học thì cùng dự đoán đó
    # được chấm hoàn hảo — test này bắt được lỗi đó.
    wrong_truth = ground_truth_from_test_traces(_train_traces(), tenant_id=TENANT)
    assert precision(train_facts, wrong_truth.reference) == 1.0


def test_doi_dieu_kien_khong_doi_dap_an():
    traces = _test_traces()
    truth = ground_truth_from_test_traces(traces, tenant_id=TENANT)
    # Hai điều kiện chấm bằng hai tập dự đoán khác nhau (chỉ-Declare lấy
    # luật từ phần học; cách ly lấy luật từ một phần học khác) — đáp án
    # dùng cho cả hai vẫn là một đối tượng, không đổi.
    other_facts = facts_from_rules(
        discover(
            tuple(Trace(("c", "d")) for _ in range(2)),
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        ),
        TENANT,
    )
    train_facts = facts_from_rules(
        discover(
            _train_traces(),
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        ),
        TENANT,
    )
    assert precision(train_facts, truth.reference) == 0.0
    assert precision(other_facts, truth.reference) == 1.0
    assert ground_truth_from_test_traces(traces, tenant_id=TENANT) == truth


def test_facts_from_rules_doi_luat_thanh_fact_active():
    rules = discover(
        _test_traces(),
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    facts = facts_from_rules(rules, TENANT)
    assert {fact.canonical_key for fact in facts} == {
        "response(c, d)",
        "precedence(c, d)",
    }
    for fact in facts:
        assert fact.status is FactStatus.ACTIVE
        assert fact.scope is FactScope.TENANT
        assert fact.tenant_id == TENANT
        assert fact.activation == "c"
        assert fact.target == "d"
        assert fact.template in ("response", "precedence")


def test_ground_truth_rong_khi_khong_co_trace_do():
    truth = ground_truth_from_test_traces((), tenant_id=TENANT)
    assert truth.reference == frozenset()
    assert truth.source == BPIC_TEST_SPLIT_SOURCE


def test_ground_truth_bat_bien():
    truth = GroundTruth(
        tenant_id=TENANT,
        reference=frozenset({"response(a, b)"}),
        source=GENERATOR_SOURCE,
    )
    assert truth.reference == frozenset({"response(a, b)"})
