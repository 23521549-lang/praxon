"""Reflector theo lô: trajectory/tài liệu thành Insight (task 6.4).

Spec (dòng 76): Reflector nhận lô trajectory hoặc tài liệu quy trình của
tenant, cùng fact hiện hành của tenant và của `global`, trả Insight (ràng
buộc Declare đề xuất, kèm case làm bằng chứng); một lần gọi mô hình mỗi lô,
giải mã có ràng buộc theo JSON schema Declare (6.2).

BĐ3 (dòng 88): đầu ra luôn đúng lược đồ — adapter 6.1 kiểm lại ở phía host,
Reflector parse lại bằng `parse_reflector_output` (6.2); sai thì cả lô thất
bại, không dùng luật nửa vời.

BĐ4 (dòng 89): Reflector chạy theo lô, có trần đầu ra. Kích thước lô
(`reflector_batch_size`) và số insight tối đa mỗi lô
(`reflector_max_insights_per_batch`) là tham số cấu hình (xem `Settings`) —
không hard-code số chính sách ở đây.

Lỗi (spec dòng 219): gọi mô hình hỏng thì adapter 6.1 thử lại có giãn cách
(theo `model_max_retries`/`model_retry_base_delay_seconds`); hết lượt thì
adapter báo `ModelCallError`. Reflector KHÔNG thử lại lần nữa (tránh hai
vòng thử lại nhân nhau) mà đổi lỗi thành `ReflectorBatchError` — bên gọi
bắt một loại lỗi duy nhất để đánh dấu cả lô thất bại rồi dừng, không nuốt
lỗi, không trả kết quả rỗng im lặng.

Quyết định thiết kế (ghi rõ để review):
- Trần cắt theo thứ tự mô hình trả về (luật đầu giữ lại): mô hình liệt kê
  luật tin nhất trước là giả thuyết hợp lý nhất khi không có số đo; sắp
  xếp lại theo khóa canonical sẽ mất thứ tự đó.
- Case trong lô là bằng chứng mô hình đã thấy (ghi trong prompt); kiểm
  đúng/sai từng luật là việc của Governor và phép đo (BĐ3), không phải
  của Reflector — nên Reflector không tính support từng luật.
- `evidence_episode_ids` gắn id episode thật cho Insight từ trace: mỗi luật
  mang id của các episode thể hiện mẫu của nó (tính từ `activities` +
  `episode_ids` của trajectory — `response(A, B)` lấy episode của A rồi B
  sau A; `precedence(A, B)` lấy episode của A trước B); luật nào không có
  trajectory nào thể hiện mẫu thì evidence rỗng (mô hình có thể đã đề xuất
  luật không có bằng chứng — Governor và phép đo sẽ loại). Đường tài liệu
  vẫn để rỗng vì tài liệu không có episode làm bằng chứng.
- `reflect` nhận lô rỗng (hoặc tài liệu rỗng) thì trả kết quả rỗng, không
  gọi mô hình — không có dữ liệu thì không có insight.
- `seed` gắn lúc dựng Reflector (chữ ký `ReflectorFn` của coordinator
  không có tham số seed); người gọi truyền seed của vòng học để xác định.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from praxon_core.adapters.language_model import LanguageModel, ModelCallError
from praxon_core.learning.coordinator import ReflectorResult
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.declare_schema import (
    DECLARE_OUTPUT_SCHEMA,
    DeclareRule,
    ReflectorOutputError,
    parse_reflector_output,
)
from praxon_core.learning.generator import Trajectory
from praxon_core.settings import Settings

__all__ = [
    "Reflector",
    "ReflectorBatchError",
    "reflector_from_settings",
]


class ReflectorBatchError(RuntimeError):
    """Một lô Reflector thất bại (gọi mô hình hỏng sau khi thử lại, hoặc đầu ra sai lược đồ).

    Bên gọi bắt lỗi này để đánh dấu cả lô thất bại rồi dừng — không nuốt lỗi,
    không dùng luật nửa vời (spec dòng 219, task 6.4). Nguyên nhân gốc nằm
    trong `__cause__` (`ModelCallError` hoặc `ReflectorOutputError`).
    """


class Reflector:
    """Reflector: trajectory/tài liệu thành Insight, theo lô, có trần đầu ra.

    Một lần gọi mô hình mỗi lô (spec dòng 76). `reflect` khớp chữ ký
    `ReflectorFn` của coordinator nên truyền trực tiếp làm `reflect=` cho
    `run_learning_round`; `reflect_document` là đường vào thứ hai (tài liệu
    quy trình, vd luật Wabo — task 9.1 dùng sau).
    """

    def __init__(
        self,
        model: LanguageModel,
        *,
        batch_size: int = 10,
        max_insights_per_batch: int = 20,
        seed: int | None = None,
        temperature: float = 0.0,
    ) -> None:
        """Giữ model và tham số lô; không gọi mạng lúc dựng."""
        if batch_size < 1:
            raise ValueError(f"batch_size phải >= 1, nhận {batch_size}")
        if max_insights_per_batch < 1:
            raise ValueError(f"max_insights_per_batch phải >= 1, nhận {max_insights_per_batch}")
        self._model = model
        self._batch_size = batch_size
        self._max_insights_per_batch = max_insights_per_batch
        self._seed = seed
        self._temperature = temperature

    def reflect(
        self, trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        """Một lô trajectory thành Insight — khớp `ReflectorFn` của coordinator.

        Chia trajectory thành lô theo `batch_size`, mỗi lô một lần gọi mô
        hình; Insight từ trace có `scope="tenant"`. Mỗi Insight mang
        `evidence_episode_ids` là id episode thể hiện mẫu của luật nó mang
        (tính từ trajectory của lô — xem `_evidence_for_rule`); luật nào
        không có trajectory nào thể hiện mẫu thì evidence rỗng. Lô rỗng thì
        trả kết quả rỗng, không gọi mô hình. Một lô nào thất bại thì cả lần
        gọi này thất bại (`ReflectorBatchError`) — không trả insight nửa vời.
        """
        ordered = tuple(trajectories)
        if not ordered:
            return ReflectorResult(insights=(), tokens_in=0, tokens_out=0)
        insights: list[Insight] = []
        tokens_in = 0
        tokens_out = 0
        for start in range(0, len(ordered), self._batch_size):
            batch = ordered[start : start + self._batch_size]
            rules, batch_in, batch_out = self._call_model(_trace_batch_prompt(batch, facts))
            tokens_in += batch_in
            tokens_out += batch_out
            insights.extend(
                _rules_to_insights(
                    rules,
                    source=InsightSource.TRACE,
                    scope="tenant",
                    trajectories=batch,
                    cap=self._max_insights_per_batch,
                )
            )
        return ReflectorResult(
            insights=tuple(insights), tokens_in=tokens_in, tokens_out=tokens_out
        )

    def reflect_document(
        self,
        document_text: str,
        facts: Sequence[FactRead],
        *,
        scope: str = "global",
    ) -> ReflectorResult:
        """Tài liệu quy trình thành Insight (đường vào thứ hai, spec dòng 76).

        Một lần gọi mô hình cho cả tài liệu; Insight từ tài liệu có
        `scope="global"` mặc định (luật Wabo vào `global`, task 9.1) và
        không có episode làm bằng chứng. Tài liệu rỗng thì trả kết quả
        rỗng, không gọi mô hình.
        """
        if not document_text.strip():
            return ReflectorResult(insights=(), tokens_in=0, tokens_out=0)
        rules, tokens_in, tokens_out = self._call_model(_document_prompt(document_text, facts))
        insights = _rules_to_insights(
            rules,
            source=InsightSource.DOCUMENT,
            scope=scope,
            cap=self._max_insights_per_batch,
        )
        return ReflectorResult(insights=insights, tokens_in=tokens_in, tokens_out=tokens_out)

    def _call_model(self, prompt: str) -> tuple[list[DeclareRule], int, int]:
        """Một lần gọi mô hình cho một lô: thất bại thì cả lô thất bại.

        Adapter 6.1 đã thử lại lỗi tạm thời có giãn cách; hết lượt (hoặc
        phản hồi sai hợp đồng) thì nó báo `ModelCallError` — đổi thành
        `ReflectorBatchError` để bên gọi bắt một loại duy nhất. Đầu ra
        parse sai lược đồ cũng vậy (phòng thủ thêm, vì adapter đã kiểm
        ở phía host).
        """
        try:
            result = self._model.complete(
                prompt,
                json_schema=DECLARE_OUTPUT_SCHEMA,
                temperature=self._temperature,
                seed=self._seed,
            )
        except ModelCallError as exc:
            raise ReflectorBatchError(
                f"lô Reflector thất bại: gọi mô hình hỏng: {exc}"
            ) from exc
        try:
            rules = parse_reflector_output(result.text)
        except ReflectorOutputError as exc:
            raise ReflectorBatchError(
                f"lô Reflector thất bại: đầu ra không khớp lược đồ: {exc}"
            ) from exc
        return (
            rules,
            result.prompt_tokens or 0,
            result.completion_tokens or 0,
        )


def reflector_from_settings(settings: Settings, model: LanguageModel) -> Reflector:
    """Dựng Reflector từ Settings (trần lô theo cấu hình, BĐ4).

    `seed` để `None` ở đây — người gọi muốn xác định thì dựng trực tiếp
    với seed của vòng học (chữ ký `ReflectorFn` không có tham số seed).
    """
    return Reflector(
        model,
        batch_size=settings.reflector_batch_size,
        max_insights_per_batch=settings.reflector_max_insights_per_batch,
    )


def _facts_block(facts: Sequence[FactRead]) -> str:
    """Fact hiện hành, một khóa mỗi dòng (để mô hình khỏi đề xuất lại)."""
    keys = sorted(fact.canonical_key for fact in facts)
    if not keys:
        return "Chưa có fact nào."
    return "\n".join(f"- {key}" for key in keys)


def _attributes_text(attributes: dict[str, Any]) -> str:
    """Thuộc tính case dạng ` [k=v, ...]` (rỗng thì chuỗi rỗng)."""
    if not attributes:
        return ""
    parts = [f"{key}={value}" for key, value in sorted(attributes.items())]
    return " [" + ", ".join(parts) + "]"


def _trace_batch_prompt(batch: Sequence[Trajectory], facts: Sequence[FactRead]) -> str:
    """Prompt cho một lô trajectory: trace + fact hiện hành."""
    lines = [
        "Đề xuất luật thứ tự Declare (response/precedence) từ các trace sau.",
        "Chỉ đề xuất luật có bằng chứng trong trace; trả JSON theo lược đồ.",
        "",
        "Trace (case_id: hoạt động theo thứ tự):",
    ]
    for trajectory in batch:
        lines.append(
            f"- {trajectory.case_id}{_attributes_text(trajectory.attributes)}: "
            + " -> ".join(trajectory.activities)
        )
    lines.append("")
    lines.append("Fact hiện hành (đừng đề xuất lại):")
    lines.append(_facts_block(facts))
    return "\n".join(lines)


def _document_prompt(document_text: str, facts: Sequence[FactRead]) -> str:
    """Prompt cho tài liệu quy trình: chỉ trích luật thứ tự."""
    return "\n".join(
        [
            "Trích luật thứ tự Declare (response/precedence) từ tài liệu sau.",
            "Chỉ trích luật thứ tự (không trích luật thời hạn); trả JSON theo lược đồ.",
            "",
            "Tài liệu:",
            document_text,
            "",
            "Fact hiện hành (đừng đề xuất lại):",
            _facts_block(facts),
        ]
    )


def _evidence_for_rule(rule: DeclareRule, trajectories: Sequence[Trajectory]) -> list[str]:
    """Id episode thể hiện mẫu của một luật, theo thứ tự trajectory trong lô.

    Chỉ episode nào thực sự thể hiện mẫu mới được gắn (tiêu chí (a) của đề
    xuất): `response(A, B)` lấy episode của A đầu tiên rồi B đầu tiên sau
    A đó; `precedence(A, B)` lấy episode của A đầu tiên trước B đầu tiên.
    Mỗi trajectory đóng góp tối đa 2 id (một cặp A/B); trajectory nào
    không thể hiện mẫu thì không đóng góp. Mẫu lạ (ngoài tầng 1) thì không
    có evidence — schema 6.2 chỉ cho `response`/`precedence` nên trường
    hợp này không xảy ra ở đường chính, chỉ phòng thủ.

    `activities` và `episode_ids` của một trajectory phải cùng độ dài
    (`replay` giữ khớp từng vị trí); lệch thì ValueError ngay — bằng
    chứng sai hình dạng phải lộ ra, không im lặng gắn thiếu.
    """
    evidence: list[str] = []
    for trajectory in trajectories:
        activities = trajectory.activities
        episode_ids = trajectory.episode_ids
        if len(activities) != len(episode_ids):
            raise ValueError(
                f"trajectory {trajectory.case_id}: activities ({len(activities)}) "
                f"không khớp episode_ids ({len(episode_ids)})"
            )
        pair: tuple[int, int] | None = None
        if rule.template == "response":
            try:
                first_a = activities.index(rule.activation)
            except ValueError:
                continue
            for j in range(first_a + 1, len(activities)):
                if activities[j] == rule.target:
                    pair = (first_a, j)
                    break
        elif rule.template == "precedence":
            try:
                first_b = activities.index(rule.target)
            except ValueError:
                continue
            for i in range(first_b):
                if activities[i] == rule.activation:
                    pair = (i, first_b)
                    break
        if pair is None:
            continue
        for index in pair:
            episode_id = str(episode_ids[index])
            if episode_id not in evidence:
                evidence.append(episode_id)
    return evidence


def _rules_to_insights(
    rules: Sequence[DeclareRule],
    *,
    source: InsightSource,
    scope: str,
    trajectories: Sequence[Trajectory] = (),
    cap: int,
) -> tuple[Insight, ...]:
    """Luật thành Insight, cắt ở trần — giữ thứ tự mô hình trả về.

    Mỗi Insight mang `evidence_episode_ids` riêng: id episode thể hiện
    mẫu của chính luật đó (tính từ `trajectories` — xem
    `_evidence_for_rule`). Đường tài liệu không truyền trajectory nên
    evidence rỗng (tài liệu không có episode làm bằng chứng).
    """
    kept = rules[:cap]
    return tuple(
        Insight(
            template=rule.template,
            activation=rule.activation,
            target=rule.target,
            condition=rule.condition_string,
            evidence_episode_ids=_evidence_for_rule(rule, trajectories),
            source=source,
            scope=scope,
        )
        for rule in kept
    )
