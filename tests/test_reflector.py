"""Test Reflector theo lô (task 6.4).

Cổng ra: (a) vượt trần thì cắt, không tràn; (b) lỗi gọi mô hình thì thử
lại có giãn cách rồi đánh dấu cả lô thất bại, không nuốt lỗi. Không gọi
model thật: server giả tương thích OpenAI (httpx2.MockTransport) như test
hợp đồng 6.1/6.2 — riêng ca đầu ra sai lược đồ dùng model giả trả text
ghi sẵn (không qua adapter) để tới được đường parse của Reflector.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx2
import openai
import pytest

from praxon_core.adapters.language_model import (
    CompletionResult,
    ModelCallError,
    OpenAICompatibleModel,
)
from praxon_core.learning.applier import build_fact_row
from praxon_core.learning.candidate import FactStatus
from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    run_learning_round,
)
from praxon_core.learning.curator import (
    DeltaKind,
    FactRead,
    InsightSource,
    curate,
    to_candidate,
)
from praxon_core.learning.declare_schema import (
    DECLARE_OUTPUT_SCHEMA,
    DeclareRule,
    ReflectorOutputError,
)
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.reflector import (
    DOCUMENT_PROMPT_VERSION,
    DOCUMENT_VOCAB_BLOCK,
    Reflector,
    ReflectorBatchError,
    _document_prompt,
    _filter_rules_by_source_quote,
    _trace_batch_prompt,
    reflector_from_settings,
)
from praxon_core.learning.rules import default_rule_table
from praxon_core.settings import Settings, load_settings

CPU_BASE_URL = "http://localhost:8080/v1"
MODEL_ID = "Qwen/Qwen3-8B-GGUF"


def _rule(
    template: str = "response",
    activation: str = "A",
    target: str = "B",
    condition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Một luật Declare dạng dict (đúng schema 6.2)."""
    rule: dict[str, Any] = {
        "template": template,
        "activation": activation,
        "target": target,
        "source": "De aanvraag wordt ingediend.",
    }
    if condition is not None:
        rule["condition"] = condition
    return rule


def _rules_text(*rules: dict[str, Any]) -> str:
    """Text JSON đầu ra của mô hình: `{"rules": [...]}`."""
    return json.dumps({"rules": list(rules)})


def _trajectory(
    case_id: str,
    activities: Sequence[str],
    tenant_id: str = "acme",
    attributes: dict[str, Any] | None = None,
    episode_ids: Sequence[UUID] | None = None,
) -> Trajectory:
    """Một trajectory: case_id + dãy hoạt động theo thứ tự.

    `episode_ids` không truyền thì sinh ngẫu nhiên (mỗi hoạt động một id
    riêng) — chỉ test nào khẳng định bằng chứng mới cần id cố định.
    """
    return Trajectory(
        tenant_id=tenant_id,
        case_id=case_id,
        activities=tuple(activities),
        attributes=attributes or {},
        episode_ids=(
            tuple(episode_ids)
            if episode_ids is not None
            else tuple(uuid4() for _ in activities)
        ),
    )


def _fact(canonical_key: str, scope: str = "tenant") -> FactRead:
    """Một fact hiện hành tối thiểu (chỉ để đưa vào prompt)."""
    return FactRead(
        id="33333333-3333-3333-3333-333333333333",
        scope=scope,
        canonical_key=canonical_key,
        template="response",
        activation="A",
        target="B",
        condition=None,
        status=FactStatus.ACTIVE,
    )


class _FakeServer:
    """Server giả tương thích OpenAI: trả phản hồi ghi sẵn, ghi lại yêu cầu.

    `texts` là text trả cho từng lần gọi (hết danh sách thì lặp lại text
    cuối — dùng khi nhiều lô cùng một canned output). `fail_times` lần
    đầu trả 500 rồi mới thành công; `fail_always` luôn trả 500 (lỗi tạm
    thời, adapter thử lại). `usage=None` nghĩa là phản hồi không có
    `usage` (server thật có thể không trả).
    """

    def __init__(
        self,
        texts: Sequence[str],
        *,
        prompt_tokens: int = 1,
        completion_tokens: int = 1,
        usage: bool = True,
        fail_times: int = 0,
        fail_always: bool = False,
    ) -> None:
        self._texts = list(texts)
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._usage = usage
        self._fail_times = fail_times
        self._fail_always = fail_always
        self.calls: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        """Trả phản hồi ghi sẵn (hoặc lỗi 500) cho một yêu cầu."""
        self.calls.append(request)
        if self._fail_always or len(self.calls) <= self._fail_times:
            return httpx2.Response(
                500,
                json={"error": {"message": "lỗi server giả", "type": "error"}},
            )
        index = min(len(self.calls) - 1, len(self._texts) - 1)
        payload: dict[str, Any] = {
            "id": "chatcmpl-gia",
            "object": "chat.completion",
            "created": 1700000000,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self._texts[index]},
                    "finish_reason": "stop",
                }
            ],
        }
        if self._usage:
            payload["usage"] = {
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_tokens": self._prompt_tokens + self._completion_tokens,
            }
        return httpx2.Response(200, json=payload)


def _model(
    texts: Sequence[str],
    *,
    max_retries: int = 3,
    retry_base_delay_seconds: float = 0.0,
    usage: bool = True,
    fail_times: int = 0,
    fail_always: bool = False,
    prompt_tokens: int = 1,
    completion_tokens: int = 1,
) -> tuple[OpenAICompatibleModel, _FakeServer]:
    """Adapter trỏ về server giả; tắt vòng thử lại của SDK."""
    server = _FakeServer(
        texts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        usage=usage,
        fail_times=fail_times,
        fail_always=fail_always,
    )
    client = openai.OpenAI(
        base_url=CPU_BASE_URL,
        api_key="local",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    model = OpenAICompatibleModel(
        client,
        model=MODEL_ID,
        max_retries=max_retries,
        retry_base_delay_seconds=retry_base_delay_seconds,
    )
    return model, server


def _prompt(call: httpx2.Request) -> str:
    """Prompt (content của message user) trong một yêu cầu đã ghi."""
    body = json.loads(call.content.decode("utf-8"))
    return str(body["messages"][0]["content"])


class _StubModel:
    """LanguageModel giả trả text ghi sẵn, không gọi mạng.

    Dùng cho ca adapter không chạm tới: đầu ra sai lược đồ phải tới được
    đường parse của Reflector (adapter thật đã chặn ở phía host).
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.prompts: list[str] = []

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        self.prompts.append(prompt)
        return CompletionResult(text=self._text)


def test_reflect_trace_tra_luat_thanh_insight():
    """Trace thành Insight: đúng luật, đúng scope/bằng chứng/token."""
    canned = _rules_text(_rule(), _rule(template="precedence", activation="A", target="C"))
    model, server = _model([canned])
    reflector = Reflector(model)
    result = reflector.reflect(
        [
            _trajectory("c1", ["A", "B"], episode_ids=(UUID(int=11), UUID(int=12))),
            _trajectory("c2", ["A", "C"], episode_ids=(UUID(int=21), UUID(int=22))),
        ],
        [_fact("response(X, Y)")],
    )
    assert len(server.calls) == 1
    assert [insight.canonical_key for insight in result.insights] == [
        "response(A, B)",
        "precedence(A, C)",
    ]
    for insight in result.insights:
        assert insight.source is InsightSource.TRACE
        assert insight.scope == "tenant"
    # Bằng chứng là episode thể hiện mẫu của từng luật: response(A, B)
    # chỉ lấy episode A/B của c1 (c2 không có B); precedence(A, C) chỉ
    # lấy episode A/C của c2 (c1 không có C).
    assert result.insights[0].evidence_episode_ids == [str(UUID(int=11)), str(UUID(int=12))]
    assert result.insights[1].evidence_episode_ids == [str(UUID(int=21)), str(UUID(int=22))]
    assert (result.tokens_in, result.tokens_out) == (1, 1)


def test_reflect_document_khong_truyen_max_tokens():
    # Hồi quy task 9.1: Reflector KHÔNG giới hạn max_tokens — đoạn Wabo
    # dài phải sinh tới hết; cắt giữa chừng làm JSON dở dang, parse hỏng.
    # Chứng minh ở thân yêu cầu thật gửi tới server giả: không có khóa
    # `max_tokens` (adapter chỉ đưa khóa này khi khác None).
    rule = _rule()
    rule["source"] = "De aanvrager dient een aanvraag in"
    canned = _rules_text(rule)
    model, server = _model([canned])
    reflector = Reflector(model)
    result = reflector.reflect_document("Artikel 1. De aanvrager dient een aanvraag in.", [])
    assert len(result.insights) == 1
    body = json.loads(server.calls[0].content.decode("utf-8"))
    assert "max_tokens" not in body


def test_reflect_document_truyen_max_tokens_khi_dat():
    # Lưới an toàn 9.1: Reflector(max_tokens=2000) đưa đúng khóa `max_tokens`
    # vào thân yêu cầu thật gửi tới server giả; adapter chỉ đưa khóa này
    # khi khác None (đường mặc định đã có test hồi quy riêng ở trên).
    rule = _rule()
    rule["source"] = "De aanvrager dient een aanvraag in"
    canned = _rules_text(rule)
    model, server = _model([canned])
    reflector = Reflector(model, max_tokens=2000)
    result = reflector.reflect_document("Artikel 1. De aanvrager dient een aanvraag in.", [])
    assert len(result.insights) == 1
    body = json.loads(server.calls[0].content.decode("utf-8"))
    assert body["max_tokens"] == 2000


def test_reflector_max_tokens_khong_hop_le_thi_loi():
    # Lưới an toàn phải >= 1 khi được đặt; 0 hay âm là lỗi lập trình, lộ ngay
    # lúc dựng thay vì lặng lẽ gửi giá trị vô nghĩa cho server.
    model, _server = _model([_rules_text(_rule())])
    with pytest.raises(ValueError, match="max_tokens phải >= 1"):
        Reflector(model, max_tokens=0)


def _reflect_evidence(
    rules: Sequence[dict[str, Any]],
    trajectories: Sequence[Trajectory],
) -> list[list[str]]:
    """Chạy reflect với luật ghi sẵn, trả evidence từng insight theo thứ tự."""
    model, _server = _model([_rules_text(*rules)])
    reflector = Reflector(model)
    result = reflector.reflect(list(trajectories), [])
    return [insight.evidence_episode_ids for insight in result.insights]


def test_response_gan_episode_cua_a_roi_b_sau_a():
    """response(A, B): lấy episode A đầu tiên + B đầu tiên sau A đó."""
    ids = tuple(UUID(int=i) for i in range(1, 5))
    evidence = _reflect_evidence(
        [_rule()],
        [_trajectory("c1", ["X", "A", "Y", "B"], episode_ids=ids)],
    )
    assert evidence == [[str(UUID(int=2)), str(UUID(int=4))]]


def test_response_khong_b_sau_a_thi_khong_bang_chung():
    """response(A, B): có A nhưng không có B sau A thì không có bằng chứng."""
    evidence = _reflect_evidence(
        [_rule()],
        [_trajectory("c1", ["A", "X"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_response_b_truoc_a_thi_khong_bang_chung():
    """response(A, B): B trước A không tính — cần B sau A."""
    evidence = _reflect_evidence(
        [_rule()],
        [_trajectory("c1", ["B", "A"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_response_khong_co_a_thi_khong_bang_chung():
    """response(A, B): không có A thì không có bằng chứng."""
    evidence = _reflect_evidence(
        [_rule()],
        [_trajectory("c1", ["B", "C"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_precedence_gan_episode_cua_a_truoc_b():
    """precedence(A, B): lấy episode A đầu tiên trước B đầu tiên."""
    ids = tuple(UUID(int=i) for i in range(1, 5))
    evidence = _reflect_evidence(
        [_rule(template="precedence")],
        [_trajectory("c1", ["X", "A", "Y", "B"], episode_ids=ids)],
    )
    assert evidence == [[str(UUID(int=2)), str(UUID(int=4))]]


def test_precedence_a_sau_b_thi_khong_bang_chung():
    """precedence(A, B): A sau B không tính — cần A trước B."""
    evidence = _reflect_evidence(
        [_rule(template="precedence")],
        [_trajectory("c1", ["B", "A"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_precedence_khong_co_b_thi_khong_bang_chung():
    """precedence(A, B): không có B thì không có bằng chứng."""
    evidence = _reflect_evidence(
        [_rule(template="precedence")],
        [_trajectory("c1", ["A", "C"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_bang_chung_gom_tu_nhieu_trajectory_theo_thu_tu_lo():
    """Luật thể hiện ở nhiều trajectory thì gom episode của từng trajectory theo thứ tự lô."""
    evidence = _reflect_evidence(
        [_rule()],
        [
            _trajectory("c1", ["A", "B"], episode_ids=(UUID(int=1), UUID(int=2))),
            _trajectory("c2", ["A", "B"], episode_ids=(UUID(int=3), UUID(int=4))),
        ],
    )
    assert evidence == [[str(UUID(int=i)) for i in range(1, 5)]]


def test_luat_khong_trajectory_nao_the_hien_thi_bang_chung_rong():
    """Luật không trajectory nào thể hiện mẫu: insight vẫn tạo, evidence rỗng."""
    evidence = _reflect_evidence(
        [_rule()],
        [_trajectory("c1", ["X", "Y"], episode_ids=(UUID(int=1), UUID(int=2)))],
    )
    assert evidence == [[]]


def test_trajectory_lech_activities_episode_ids_thi_tu_choi():
    """Trajectory mà activities không khớp episode_ids thì từ chối ngay, không gắn thiếu."""
    model, _server = _model([_rules_text(_rule())])
    reflector = Reflector(model)
    broken = Trajectory(
        tenant_id="acme",
        case_id="c1",
        activities=("A", "B"),
        attributes={},
        episode_ids=(UUID(int=1),),
    )
    with pytest.raises(ValueError, match="không khớp episode_ids"):
        reflector.reflect([broken], [])


def test_round_trip_insight_mang_evidence_toi_fact():
    """Insight mang evidence → Candidate → Fact mang đúng UUID episode."""
    canned = _rules_text(_rule())
    model, _server = _model([canned])
    reflector = Reflector(model)
    id_a, id_b = UUID(int=11), UUID(int=12)
    result = reflector.reflect([_trajectory("c1", ["A", "B"], episode_ids=(id_a, id_b))], [])
    assert len(result.insights) == 1
    insight = result.insights[0]
    assert insight.evidence_episode_ids == [str(id_a), str(id_b)]
    deltas = curate(insight, [])
    assert len(deltas) == 1
    assert deltas[0].kind is DeltaKind.ADD
    candidate = to_candidate(deltas[0], valid_start=datetime(2030, 1, 1, tzinfo=UTC))
    assert candidate.evidence_episode_ids == [str(id_a), str(id_b)]
    approved = candidate.model_copy(update={"status": "approved"})
    row = build_fact_row(approved, candidate_id="cand-1", tenant_id="acme")
    assert row.source_episode_ids == (id_a, id_b)


def test_reflect_chia_lo_theo_batch_size():
    """5 trace, batch 2 → 3 lần gọi, mỗi prompt chỉ chứa case của lô đó."""
    canned = _rules_text(_rule())
    model, server = _model([canned])
    reflector = Reflector(model, batch_size=2)
    trajectories = [_trajectory(f"c{i}", ["A", "B"]) for i in range(1, 6)]
    result = reflector.reflect(trajectories, [])
    assert len(server.calls) == 3
    assert len(result.insights) == 3
    assert "c1" in _prompt(server.calls[0]) and "c2" in _prompt(server.calls[0])
    assert "c3" not in _prompt(server.calls[0])
    assert "c3" in _prompt(server.calls[1]) and "c4" in _prompt(server.calls[1])
    assert "c5" in _prompt(server.calls[2]) and "c1" not in _prompt(server.calls[2])


def test_vuot_tran_thi_cat_khong_tran():
    """Mô hình trả 5 luật, trần 2 → chỉ 2 luật đầu, giữ thứ tự mô hình."""
    rules = [_rule(target=target) for target in ["B", "C", "D", "E", "F"]]
    model, _server = _model([_rules_text(*rules)])
    reflector = Reflector(model, max_insights_per_batch=2)
    result = reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert [insight.canonical_key for insight in result.insights] == [
        "response(A, B)",
        "response(A, C)",
    ]


def test_tran_ap_dung_tung_lo():
    """Trần tính theo từng lô: 2 lô, mỗi lô 3 luật, trần 2 → 4 insight."""
    rules = [_rule(target=target) for target in ["B", "C", "D"]]
    model, _server = _model([_rules_text(*rules)])
    reflector = Reflector(model, batch_size=1, max_insights_per_batch=2)
    trajectories = [_trajectory("c1", ["A", "B"]), _trajectory("c2", ["A", "B"])]
    result = reflector.reflect(trajectories, [])
    assert len(result.insights) == 4


def test_loi_mo_hinh_thu_lai_roi_danh_dau_ca_lo_that_bai():
    """Server luôn 500: adapter thử lại 3 lần (tổng 4 lần gọi) rồi Reflector báo lô thất bại."""
    model, server = _model([_rules_text(_rule())], fail_always=True)
    reflector = Reflector(model)
    with pytest.raises(ReflectorBatchError) as excinfo:
        reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert len(server.calls) == 4
    assert isinstance(excinfo.value.__cause__, ModelCallError)


def test_thu_lai_co_gian_cach(monkeypatch):
    """Giãn cách thử lại: độ trễ ghi được đúng cấp số nhân (0,05 → 0,1 → 0,2)."""
    delays: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: delays.append(seconds))
    model, server = _model(
        [_rules_text(_rule())],
        fail_always=True,
        retry_base_delay_seconds=0.05,
    )
    reflector = Reflector(model)
    with pytest.raises(ReflectorBatchError):
        reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert len(server.calls) == 4
    assert delays == [0.05, 0.1, 0.2]


def test_dau_ra_sai_luoc_do_danh_dau_ca_lo_that_bai():
    """Model trả text không phải JSON: Reflector báo cả lô thất bại, không trả luật nửa vời."""
    model = _StubModel("đây không phải JSON")
    reflector = Reflector(model)
    with pytest.raises(ReflectorBatchError) as excinfo:
        reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert isinstance(excinfo.value.__cause__, ReflectorOutputError)
    assert len(model.prompts) == 1


def test_reflect_document_tra_insight_global():
    """Tài liệu thành Insight: scope global, nguồn document, không episode bằng chứng."""
    rule = _rule(template="precedence", activation="A", target="B")
    rule["source"] = "Công bố dự thảo"
    canned = _rules_text(rule)
    model, server = _model([canned])
    reflector = Reflector(model)
    result = reflector.reflect_document("Công bố dự thảo trước quyết định cuối.", [])
    assert len(server.calls) == 1
    assert len(result.insights) == 1
    insight = result.insights[0]
    assert insight.canonical_key == "precedence(A, B)"
    assert insight.source is InsightSource.DOCUMENT
    assert insight.scope == "global"
    assert insight.evidence_episode_ids == []


def test_tai_lieu_rong_khong_goi_mo_hinh():
    """Tài liệu rỗng thì trả kết quả rỗng, không gọi mô hình."""
    model, server = _model([_rules_text(_rule())])
    reflector = Reflector(model)
    result = reflector.reflect_document("   \n", [])
    assert result == ReflectorResult(insights=(), tokens_in=0, tokens_out=0)
    assert len(server.calls) == 0


def test_lo_rong_khong_goi_mo_hinh():
    """Không có trajectory thì trả kết quả rỗng, không gọi mô hình."""
    model, server = _model([_rules_text(_rule())])
    reflector = Reflector(model)
    result = reflector.reflect([], [])
    assert result == ReflectorResult(insights=(), tokens_in=0, tokens_out=0)
    assert len(server.calls) == 0


def test_prompt_chua_trace_va_fact_hien_hanh():
    """Prompt chứa case của lô và khóa fact hiện hành (để mô hình khỏi đề xuất lại)."""
    model, server = _model([_rules_text(_rule())])
    reflector = Reflector(model)
    reflector.reflect(
        [_trajectory("c1", ["A", "B"], attributes={"case_type": "X"})],
        [_fact("response(X, Y)"), _fact("precedence(P, Q)", scope="global")],
    )
    prompt = _prompt(server.calls[0])
    assert "c1" in prompt and "A -> B" in prompt and "case_type=X" in prompt
    assert "response(X, Y)" in prompt and "precedence(P, Q)" in prompt


def test_reflector_gui_dung_schema_cho_adapter():
    """Reflector truyền đúng DECLARE_OUTPUT_SCHEMA làm response_format."""
    model, server = _model([_rules_text(_rule())])
    reflector = Reflector(model)
    reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    body = json.loads(server.calls[0].content.decode("utf-8"))
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "schema": DECLARE_OUTPUT_SCHEMA},
    }


def _episode(
    case_id: str, activity: str, occurred: str, episode_id: UUID | None = None
) -> EpisodeRow:
    """Một hàng episode tối thiểu cho vòng học qua coordinator."""
    return EpisodeRow(
        id=episode_id if episode_id is not None else uuid4(),
        tenant_id="acme",
        case_id=case_id,
        payload={"activity": activity, "case_attributes": {}},
        occurred_at=datetime.fromisoformat(occurred),
        ingested_at=datetime.fromisoformat("2026-11-06T00:00:00"),
    )


def _measures() -> Measures:
    """Số đo giả: candidate mới từ trace, đủ mạnh để Governor quyết."""
    return Measures(
        has_direct_conflict=False,
        schema_valid=True,
        from_trace=True,
        wilson_lower=0.8,
        beta_prob=0.5,
        is_scope_promotion=False,
        from_global=False,
        has_condition=False,
        matching_cases=0,
        fact_status=None,
        is_new=True,
        human_early_activate=False,
        has_rubric_clause=False,
    )


def test_reflector_khop_reflector_fn_cua_coordinator():
    """Reflector thật chạy được trong vòng học của coordinator (khớp ReflectorFn)."""
    canned = _rules_text(_rule())
    model, _server = _model([canned])
    reflector = Reflector(model, seed=42)
    fn: ReflectorFn = reflector.reflect
    _ids = itertools.count()
    outcome = run_learning_round(
        LearningRound(
            tenant_id="acme",
            episode_rows=(
                _episode("c1", "A", "2026-11-06T10:00:00", episode_id=UUID(int=11)),
                _episode("c1", "B", "2026-11-06T11:00:00", episode_id=UUID(int=12)),
            ),
            facts=(),
            rule_table=default_rule_table(),
            seed=42,
            model_id=MODEL_ID,
            model_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
            code_commit="d" * 40,
            config_hash="c" * 64,
            data_hash="d" * 64,
            valid_start=datetime(2030, 1, 1, tzinfo=UTC),
            retired_at=datetime(2030, 2, 1, tzinfo=UTC),
        ),
        reflect=fn,
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=lambda: f"candidate-{next(_ids)}",
    )
    assert len(outcome.insights) == 1
    assert outcome.insights[0].canonical_key == "response(A, B)"
    assert outcome.insights[0].evidence_episode_ids == [str(UUID(int=11)), str(UUID(int=12))]
    assert outcome.run_row.tokens_in == 1 and outcome.run_row.tokens_out == 1


def test_cau_hinh_mac_dinh_tran_lo(tmp_path):
    """Trần lô mặc định 10/20, ghi đè qua TOML, và factory nối đúng Settings."""
    settings = Settings(database_url="x")
    assert settings.reflector_batch_size == 10
    assert settings.reflector_max_insights_per_batch == 20
    config = tmp_path / "config.toml"
    config.write_text(
        'database_url = "x"\nreflector_batch_size = 3\nreflector_max_insights_per_batch = 7\n',
        encoding="utf-8",
    )
    overridden = load_settings(config)
    assert overridden.reflector_batch_size == 3
    assert overridden.reflector_max_insights_per_batch == 7
    model, server = _model([_rules_text(_rule())])
    reflector = reflector_from_settings(overridden, model)
    trajectories = [_trajectory(f"c{i}", ["A", "B"]) for i in range(1, 8)]
    reflector.reflect(trajectories, [])
    assert len(server.calls) == 3


def test_tham_so_lo_khong_hop_le_bi_tu_choi():
    """batch_size / max_insights_per_batch < 1 thì từ chối ngay lúc dựng."""
    model, _server = _model([_rules_text(_rule())])
    with pytest.raises(ValueError):
        Reflector(model, batch_size=0)
    with pytest.raises(ValueError):
        Reflector(model, max_insights_per_batch=0)


def test_token_khong_co_tinh_bang_0():
    """Server không trả usage thì token tính bằng 0 (không None)."""
    model, _server = _model([_rules_text(_rule())], usage=False)
    reflector = Reflector(model)
    result = reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert (result.tokens_in, result.tokens_out) == (0, 0)


def test_loi_vinh_vien_khong_thu_lai():
    """Lỗi 401 (sai khóa) là vĩnh viễn: chỉ 1 lần gọi, Reflector báo cả lô thất bại."""

    class _Fail401Server(_FakeServer):
        def handler(self, request: httpx2.Request) -> httpx2.Response:
            self.calls.append(request)
            return httpx2.Response(
                401,
                json={"error": {"message": "sai khóa", "type": "error"}},
            )

    server = _Fail401Server([_rules_text(_rule())])
    client = openai.OpenAI(
        base_url=CPU_BASE_URL,
        api_key="local",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    model = OpenAICompatibleModel(
        client, model=MODEL_ID, max_retries=3, retry_base_delay_seconds=0.0
    )
    reflector = Reflector(model)
    with pytest.raises(ReflectorBatchError) as excinfo:
        reflector.reflect([_trajectory("c1", ["A", "B"])], [])
    assert len(server.calls) == 1
    assert isinstance(excinfo.value.__cause__, ModelCallError)


# --- Prompt tài liệu v4 (trích dẫn nguồn, lần thử 2 chống liệt kê 9.1) ---

#: Khối từ vựng v4 nguyên văn: khối v3 + câu trích dẫn nguồn ở cuối.
VOCAB_BLOCK_V4 = (
    "Chỉ dùng các khái niệm sau cho activation và target (dùng đúng từ này, "
    "không thêm mã hay ký tự nào khác): aanvraag, ontwerpbesluit, ter inzage, "
    "zienswijze, besluit, beschikking, bezwaar, beroep, voorlopige voorziening, "
    "verlengen, buiten behandeling, intrekken, bekendmaking. Không dùng số "
    "điều (ví dụ '2.15'), không dùng cả câu hay cả đoạn văn, không dùng tên "
    "tác nhân (ví dụ 'bevoegd gezag'), không dùng từ 'declare' / 'response' "
    "/ 'precedence' làm hoạt động. Nếu một đoạn không chứa luật nào giữa các "
    "khái niệm trên thì trả danh sách rỗng. Tối đa 15 luật. Mỗi luật phải kèm "
    "trường source là một trích dẫn nguyên văn (một câu hoặc một phần câu) "
    "trong đoạn mà luật đó lấy từ đó, không bịa trích dẫn."
)

#: SHA-256 của prompt đoạn 7 thật với khối v4 (tính từ prompt repo sau khi
#: sửa; đoạn 7 lấy qua pipeline thật như test v3 trước đây).
PROMPT_SHA_DOAN_7_V4 = "16881cc018705f2e071672a323b62852987445f26a1595f49eaf620ffe541fc1"


def test_document_prompt_chua_khoi_tu_vung_v4_nguyen_van():
    """Prompt tài liệu chứa đúng khối v4 nguyên văn, đúng một lần, đúng vị trí."""
    assert DOCUMENT_PROMPT_VERSION == "v4"
    assert DOCUMENT_VOCAB_BLOCK == VOCAB_BLOCK_V4
    prompt = _document_prompt("Văn bản mẫu.", ())
    assert prompt.count(VOCAB_BLOCK_V4) == 1
    lines = prompt.split("\n")
    assert lines[0] == ("Trích luật thứ tự Declare (response/precedence) từ tài liệu sau.")
    assert lines[1] == (
        "Chỉ trích luật thứ tự (không trích luật thời hạn); trả JSON theo lược đồ."
    )
    assert lines[2] == VOCAB_BLOCK_V4
    assert lines[3] == ""
    assert lines[4] == "Tài liệu:"
    assert lines[5] == "Văn bản mẫu."
    assert "01_HOOFD" not in prompt
    assert "10_UOV" not in prompt


def test_document_prompt_doan_7_khop_sha_v4():
    """Prompt đoạn 7 thật khớp SHA với khối v4."""
    from praxon_core.learning.wabo_rules import (
        extract_wabo_text,
        split_wabo_text,
    )

    cache = Path.home() / ".cache" / "praxon" / "wabo" / "wabo-2015-01-01.html"
    if not cache.is_file():
        pytest.skip("chưa tải văn bản Wabo về cache")
    chunks = split_wabo_text(extract_wabo_text(cache.read_text(encoding="utf-8")))
    prompt = _document_prompt(chunks[7], ())
    assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == PROMPT_SHA_DOAN_7_V4


def test_loc_trich_dan_nguon_khop_bua_rong():
    """Lọc source-quote: khớp (lệch hoa/thường, khoảng trắng) thì giữ; bừa/rỗng thì bỏ."""
    text = "Artikel 2.5 De aanvraag wordt ingediend bij het bevoegd gezag."
    rules = [
        DeclareRule(
            template="response",
            activation="aanvraag",
            target="besluit",
            source="de  AANVRAAG wordt ingediend",
        ),
        DeclareRule(
            template="precedence",
            activation="aanvraag",
            target="besluit",
            source="Een câu hoàn toàn không có trong đoạn.",
        ),
        DeclareRule(template="response", activation="aanvraag", target="bezwaar", source=""),
        DeclareRule(template="response", activation="aanvraag", target="bezwaar", source="   "),
    ]
    kept, dropped = _filter_rules_by_source_quote(rules, text)
    assert len(kept) == 1
    assert kept[0].template == "response"
    assert dropped == 3


def test_reflect_document_loc_trich_dan_nguon_khong_khop():
    """Đường tài liệu: trích dẫn khớp đoạn thì giữ, trích dẫn bừa thì bỏ và đếm."""
    doc = (
        "Artikel 2.5 De aanvraag wordt ingediend bij het bevoegd gezag. "
        "Het besluit volgt binnen acht weken."
    )
    khop = _rule(template="response", activation="aanvraag", target="besluit")
    khop["source"] = "de aanvraag wordt ingediend bij het bevoegd gezag"
    bua = _rule(template="precedence", activation="aanvraag", target="besluit")
    bua["source"] = "Een câu hoàn toàn không có trong đoạn."
    model = _StubModel(_rules_text(khop, bua))
    reflector = Reflector(model)
    result = reflector.reflect_document(doc, ())
    assert [insight.canonical_key for insight in result.insights] == [
        "response(aanvraag, besluit)"
    ]
    assert result.source_quote_dropped == 1
    assert "trích dẫn nguyên văn" in model.prompts[0]


def test_reflect_document_trich_dan_rong_loi_luoc_do():
    """Trích dẫn rỗng thì cả lô sai lược đồ (schema bắt minLength 1)."""
    rong = _rule()
    rong["source"] = ""
    model = _StubModel(_rules_text(rong))
    reflector = Reflector(model)
    with pytest.raises(ReflectorBatchError):
        reflector.reflect_document("Artikel 2.5 De aanvraag wordt ingediend.", ())


def test_trace_batch_prompt_khong_doi_khi_sua_prompt_tai_lieu():
    """Hồi quy: prompt đường trace không đổi khi sửa prompt tài liệu."""
    prompt = _trace_batch_prompt([_trajectory("case-1", ["A", "B"])], [])
    assert prompt == (
        "Đề xuất luật thứ tự Declare (response/precedence) từ các trace sau.\n"
        "Chỉ đề xuất luật có bằng chứng trong trace; trả JSON theo lược đồ.\n"
        "\n"
        "Trace (case_id: hoạt động theo thứ tự):\n"
        "- case-1: A -> B\n"
        "\n"
        "Fact hiện hành (đừng đề xuất lại):\n"
        "Chưa có fact nào."
    )
