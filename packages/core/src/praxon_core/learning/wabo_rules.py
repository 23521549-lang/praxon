"""Trích luật thứ tự từ Wabo vào `global` (task 9.1; spec dòng 27, 56, 164, 174, 176).

Luồng (thuần, không chạm DB — người gọi ghi fact qua vai promoter):
Wabo HTML trong cache -> bóc text -> Reflector trích luật thứ tự theo
đoạn (đường `reflect_document`, scope global) -> gắn khái niệm tiếng Hà
Lan sang mã hoạt động log bằng bảng gắn 9.2 -> đo bằng chứng mỗi luật
trên toàn bộ trace BPIC 2015 (gộp 5 đô thị) -> cổng Beta loại luật
không đủ bằng chứng -> fact cho luật còn lại, mang `valid_during` của
văn bản, vào `global`.

Quyết định thiết kế (ghi rõ để review):
- `valid_during` lấy từ bảng gắn 9.2 (`[wabo] valid_during`, bản
  2015-01-01: "2015-01-01/2015-03-31"), KHÔNG hard-code trong module
  này. Hai đầu bao hàm theo wetten.nl ("Geldend van ... t/m ...");
  cột DB là `tstzrange` nửa mở `[)` nên `valid_end` là 00:00 UTC ngày
  sau ngày cuối (2015-04-01) — ghi rõ trong `parse_valid_during`.
- Bằng chứng gộp cả 5 đô thị BPIC 2015 (không chia train/test): văn bản
  là global (giống nhau cho cả 5 đô thị, spec dòng 174) nên bằng chứng
  cho fact global là toàn bộ quần thể; đây là ÁP DỤNG cổng đã khóa
  (ngưỡng 0,7/0,95/0,05 từ `default_rule_table.toml`), không phải hiệu
  chỉnh — không vi phạm luật "chỉ hiệu chỉnh trên phần hiệu chỉnh"
  (9.6). Người đo điều kiện 7 sau này cần biết: bộ lọc Beta đã dùng
  bằng chứng gộp (ghi rõ ở đây).
- Cổng Beta: chỉ luật có hậu nghiệm Beta >= ngưỡng lên (0,95, theo
  chính sách) mới vào gói; mọi luật khác bị loại — gói nhà cung cấp
  thận trọng, luật chưa đủ bằng chứng vẫn học được theo đường tenant
  sau này. Tiên nghiệm trung lập (độ tin 0,5, như test 9.2): việc trích
  bằng LLM không phải bằng chứng; hậu nghiệm chỉ tính từ số đếm trong
  log.
- Fact đã duyệt vào `global` mang status `active`: luật đã qua đúng
  ngưỡng lên của cổng Beta (ngưỡng lên chính là tiêu chí lên chính
  thức), và gói nhà cung cấp là tri thức đã chứng nhận — tenant vẫn
  nhận nó vào `trial` ngày đầu theo spec dòng 164 (đường coordinator,
  không thuộc task này). `candidate_id` để None (fact seed — V4 cho
  qua, xem `insert_fact`).
- Văn bản chia đoạn ở đầu mỗi "Artikel " (không cắt giữa một điều),
  tối đa `WABO_CHUNK_MAX_CHARS` ký tự mỗi đoạn — giới hạn gắn với
  ctx 2048 token mà phép đo 6.5 dùng (`--ctx-size 2048`): một đoạn
  ~1000 token, cộng prompt + JSON đầu ra vẫn vừa cửa sổ. Server chạy
  ctx lớn hơn thì tăng hằng này.
- Luật trùng (cùng luật từ nhiều đoạn) chỉ đếm một lần; `extracted`
  đếm insight DUY NHẤT, nên `extracted == chấp nhận + không gắn được
  + có điều kiện + cổng Beta loại`.
- Insight có điều kiện bị bỏ qua (đếm riêng): đếm bằng chứng
  (`count_rule_evidence`) không hỗ trợ điều kiện, nên chấp nhận luật
  có điều kiện bằng bằng chứng của luật không điều kiện là sai — luật
  có điều kiện thuộc về 9.5 (BPIC 2019), không thuộc task này.
- Khái niệm không gắn được bị bỏ qua (đếm riêng): không bịa gắn
  (quy tắc của 9.2).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

from praxon_core.adapters.language_model import ModelCallError, model_from_settings
from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS
from praxon_core.datasets.xes import iter_traces
from praxon_core.declare.index import Trace as DeclareTrace
from praxon_core.declare.miner import Rule
from praxon_core.learning.beta import Prior, posterior_prob_ge
from praxon_core.learning.calibration import count_rule_evidence
from praxon_core.learning.coordinator import ReflectorResult
from praxon_core.learning.curator import FactRead, Insight
from praxon_core.learning.dutch_mapping import DutchMappingTable, default_dutch_mapping
from praxon_core.learning.payload import statement_for
from praxon_core.learning.reflector import Reflector, ReflectorBatchError
from praxon_core.learning.rules import Policy, default_rule_table
from praxon_core.repositories.facts import FactRow
from praxon_core.settings import Settings, load_settings

__all__ = [
    "WABO_CHUNK_MAX_CHARS",
    "WABO_DEFAULT_HTML_FILENAME",
    "WABO_PRIOR_CONFIDENCE",
    "WaboDocument",
    "WaboExtraction",
    "WaboRuleOutcome",
    "build_reflector",
    "extract_wabo_rules",
    "extract_wabo_text",
    "format_wabo_report",
    "load_bpic_traces",
    "load_wabo_document",
    "main",
    "parse_valid_during",
    "resolve_activity",
    "split_wabo_text",
]

WABO_DEFAULT_HTML_FILENAME = "wabo-2015-01-01.html"
WABO_CHUNK_MAX_CHARS = 4000
WABO_PRIOR_CONFIDENCE = 0.5


@dataclass(frozen=True)
class WaboDocument:
    """Văn bản Wabo đã tải + kiểm SHA-256, sẵn để trích luật."""

    source_url: str
    version: str
    valid_start: datetime
    valid_end: datetime
    text: str
    sha256: str


@dataclass(frozen=True)
class WaboRuleOutcome:
    """Một luật đã gắn + đo bằng chứng: hậu nghiệm Beta và kết quả cổng."""

    rule: Rule
    successes: int
    trials: int
    posterior: float
    accepted: bool


@dataclass(frozen=True)
class WaboExtraction:
    """Kết quả trích luật từ Wabo: luật + fact global + số đếm theo cổng."""

    document: WaboDocument
    extracted: int
    unmapped: int
    conditional: int
    beta_filtered: int
    outcomes: tuple[WaboRuleOutcome, ...]
    facts: tuple[FactRow, ...]
    tokens_in: int
    tokens_out: int

    @property
    def accepted(self) -> int:
        """Số luật vào `global` (bằng số fact)."""
        return len(self.facts)


class _TextExtractor(HTMLParser):
    """Bóc text khỏi HTML: bỏ thẻ + script/style, giữ ngắt đoạn."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "br"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(data)

    def text(self) -> str:
        """Text đã chuẩn hóa: mỗi dòng gọn, đoạn cách nhau một dòng trống."""
        lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(self._parts).split("\n")]
        out: list[str] = []
        for line in lines:
            if line:
                out.append(line)
            elif out and out[-1] != "":
                out.append("")
        return "\n".join(out).strip()


def extract_wabo_text(html: str) -> str:
    """Bóc text khỏi HTML của wetten.nl (xác định, không gọi mạng)."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


def parse_valid_during(value: str) -> tuple[datetime, datetime]:
    """Khoảng hiệu lực "YYYY-MM-DD/YYYY-MM-DD" (cả hai đầu bao hàm).

    Trả (đầu, cuối) cho `tstzrange` nửa mở `[)`: đầu là 00:00 UTC ngày
    đầu, cuối là 00:00 UTC ngày SAU ngày cuối (vd "2015-01-01/2015-03-31"
    -> 2015-01-01T00:00Z đến 2015-04-01T00:00Z).
    """
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError(f"valid_during phải dạng YYYY-MM-DD/YYYY-MM-DD, nhận {value!r}")
    try:
        start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").replace(tzinfo=UTC)
        last = datetime.strptime(parts[1].strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"valid_during sai định dạng ngày: {value!r}") from exc
    if last < start:
        raise ValueError(f"valid_during ngược: ngày cuối trước ngày đầu: {value!r}")
    return start, last + timedelta(days=1)


def load_wabo_document(html_path: Path, *, mapping: DutchMappingTable) -> WaboDocument:
    """Nạp văn bản Wabo từ cache: kiểm SHA-256 rồi bóc text.

    Nguồn + phiên bản + khoảng hiệu lực + SHA kỳ vọng đều lấy từ bảng
    gắn 9.2 (một nguồn sự thật duy nhất) — không hard-code ở đây.
    """
    if not html_path.is_file():
        raise FileNotFoundError(f"thiếu tệp Wabo HTML: {html_path}")
    data = html_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != mapping.wabo.sha256_html:
        raise ValueError(
            f"SHA-256 tệp Wabo không khớp bảng gắn: tính được {digest}, "
            f"bảng gắn ghi {mapping.wabo.sha256_html}"
        )
    valid_start, valid_end = parse_valid_during(mapping.wabo.valid_during)
    return WaboDocument(
        source_url=mapping.wabo.source_url,
        version=mapping.wabo.version,
        valid_start=valid_start,
        valid_end=valid_end,
        text=extract_wabo_text(data.decode("utf-8")),
        sha256=digest,
    )


_ARTICLE_RE = re.compile(r"^Artikel \S+", re.MULTILINE)


def _split_long_block(block: str, *, max_chars: int) -> list[str]:
    """Chia một khối dài: trước ở ngắt đoạn, đoạn dài thì cắt cứng."""
    if len(block) <= max_chars:
        return [block]
    paras = [para for para in block.split("\n\n") if para.strip()]
    if len(paras) > 1:
        out: list[str] = []
        for para in paras:
            out.extend(_split_long_block(para, max_chars=max_chars))
        return out
    return [block[i : i + max_chars] for i in range(0, len(block), max_chars)]


def split_wabo_text(text: str, *, max_chars: int = WABO_CHUNK_MAX_CHARS) -> tuple[str, ...]:
    """Chia văn bản thành đoạn <= max_chars, không cắt giữa một điều.

    Chia ở đầu mỗi "Artikel "; phần mở đầu (trước điều đầu tiên) là một
    đoạn riêng. Không trả đoạn rỗng. Xác định (cùng đầu vào -> cùng đoạn).
    """
    if max_chars < 1:
        raise ValueError(f"max_chars phải >= 1, nhận {max_chars}")
    text = text.strip()
    if not text:
        return ()
    starts = [match.start() for match in _ARTICLE_RE.finditer(text)]
    pieces: list[str] = []
    prev = 0
    for start in starts:
        if start > prev:
            pieces.append(text[prev:start])
        prev = start
    pieces.append(text[prev:])
    pieces = [piece.strip() for piece in pieces if piece.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        for part in _split_long_block(piece, max_chars=max_chars):
            if current and len(current) + 2 + len(part) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        chunks.append(current)
    return tuple(chunks)


def resolve_activity(text: str, mapping: DutchMappingTable) -> str | None:
    """Mã hoạt động log cho một chuỗi mô hình viết.

    Khái niệm Wabo -> mã canonical của nó; tên hoạt động NL -> mã đó;
    không khớp -> None (không bịa gắn).
    """
    key = text.strip().lower()
    if not key:
        return None
    if mapping.is_mapped(key):
        return mapping.canonical_activity(key)
    for entry in mapping.concept:
        for activity in entry.activities:
            if activity.dutch_name.strip().lower() == key:
                return activity.code
    return None


def extract_wabo_rules(
    *,
    reflect_document: Callable[[str, Sequence[FactRead]], ReflectorResult],
    document: WaboDocument,
    mapping: DutchMappingTable,
    traces: Sequence[DeclareTrace],
    policy: Policy,
    limit_chunks: int | None = None,
) -> WaboExtraction:
    """Trích luật thứ tự từ Wabo: Reflector -> gắn khái niệm -> cổng Beta.

    `reflect_document` là đường vào tài liệu của Reflector (6.4) hoặc
    hàm giả trong test — module này không gọi mô hình trực tiếp.
    `limit_chunks` chỉ chạy N đoạn đầu (chạy thử nhanh); None là toàn bộ.
    """
    if limit_chunks is not None and limit_chunks < 1:
        raise ValueError(f"limit_chunks phải >= 1, nhận {limit_chunks}")
    chunks = split_wabo_text(document.text)
    if limit_chunks is not None:
        chunks = chunks[:limit_chunks]
    insights: list[Insight] = []
    tokens_in = 0
    tokens_out = 0
    for chunk in chunks:
        result = reflect_document(chunk, ())
        insights.extend(result.insights)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
    seen: set[tuple[str, str, str, str | None]] = set()
    unique: list[Insight] = []
    for insight in insights:
        key = (
            insight.template,
            insight.activation.strip().lower(),
            insight.target.strip().lower(),
            insight.condition,
        )
        if key not in seen:
            seen.add(key)
            unique.append(insight)
    unmapped = 0
    conditional = 0
    outcomes: list[WaboRuleOutcome] = []
    facts: list[FactRow] = []
    for insight in unique:
        if insight.condition is not None:
            conditional += 1
            continue
        first = resolve_activity(insight.activation, mapping)
        second = resolve_activity(insight.target, mapping)
        if first is None or second is None:
            unmapped += 1
            continue
        skeleton = Rule(insight.template, first, second, 0.0, 0.0)
        evidence = count_rule_evidence(skeleton, traces)
        confidence = evidence.successes / evidence.trials if evidence.trials else 0.0
        support = evidence.successes / len(traces) if traces else 0.0
        rule = Rule(insight.template, first, second, support, confidence)
        posterior = posterior_prob_ge(
            Prior(
                canonical_key=rule.canonical_key,
                confidence=WABO_PRIOR_CONFIDENCE,
                strength=None,
            ),
            evidence.successes,
            evidence.trials,
            policy.confidence_threshold,
            strength_default=policy.prior_strength_default,
        )
        accepted = posterior >= policy.promote_probability
        outcomes.append(
            WaboRuleOutcome(
                rule=rule,
                successes=evidence.successes,
                trials=evidence.trials,
                posterior=posterior,
                accepted=accepted,
            )
        )
        if accepted:
            facts.append(
                FactRow(
                    tenant_id="global",
                    scope="global",
                    canonical_key=rule.canonical_key,
                    template=rule.template,
                    statement=statement_for(rule.template, rule.first, rule.second, None),
                    status="active",
                    support=evidence.successes,
                    confidence=confidence,
                    valid_start=document.valid_start,
                    valid_end=document.valid_end,
                    activation=rule.first,
                    target=rule.second,
                    condition=None,
                    source_episode_ids=(),
                    candidate_id=None,
                )
            )
    return WaboExtraction(
        document=document,
        extracted=len(unique),
        unmapped=unmapped,
        conditional=conditional,
        beta_filtered=sum(1 for outcome in outcomes if not outcome.accepted),
        outcomes=tuple(outcomes),
        facts=tuple(facts),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def load_bpic_traces(cache_dir: Path) -> tuple[DeclareTrace, ...]:
    """Toàn bộ trace BPIC 2015 (5 đô thị gộp) để đo bằng chứng luật global."""
    traces: list[DeclareTrace] = []
    for dataset in BPIC2015_DATASETS:
        path = cache_dir / dataset.xes_filename
        if not path.is_file():
            raise FileNotFoundError(f"thiếu tệp log BPIC 2015: {path}")
        for trace in iter_traces(path):
            traces.append(DeclareTrace(tuple(event.activity for event in trace.events)))
    return tuple(traces)


def format_wabo_report(extraction: WaboExtraction) -> str:
    """Báo cáo trích luật: số luật theo từng cổng + luật đã chấp nhận."""
    document = extraction.document
    lines = [
        f"Wabo {document.version} "
        f"({document.valid_start.date()}-{document.valid_end.date()}, "
        f"{document.sha256[:12]}…)",
        f"Trích được: {extraction.extracted} luật",
        f"Không gắn được khái niệm: {extraction.unmapped} luật",
        f"Có điều kiện (bỏ qua): {extraction.conditional} luật",
        f"Cổng Beta loại: {extraction.beta_filtered} luật",
        f"Chấp nhận vào global: {extraction.accepted} luật",
        f"Token: vào {extraction.tokens_in}, ra {extraction.tokens_out}",
    ]
    for outcome in extraction.outcomes:
        if outcome.accepted:
            lines.append(
                f"- {outcome.rule.canonical_key}: {outcome.successes}/"
                f"{outcome.trials}, P={outcome.posterior:.4f}"
            )
    return "\n".join(lines)


def build_reflector(settings: Settings, *, seed: int) -> Reflector:
    """Dựng Reflector thật từ Settings (backend CPU, llama-server)."""
    model = model_from_settings(settings, backend="cpu")
    return Reflector(
        model,
        batch_size=settings.reflector_batch_size,
        max_insights_per_batch=settings.reflector_max_insights_per_batch,
        seed=seed,
    )


def main(argv: list[str] | None = None) -> int:
    """Lệnh trích luật Wabo: tải văn bản -> trích -> cổng Beta -> in số liệu.

    Mã thoát: 0 = xong (kể cả khi 0 luật được chấp nhận — đó là kết quả
    đo, không phải lỗi); 1 = lỗi dữ liệu (thiếu tệp / SHA không khớp);
    2 = không gọi được mô hình.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="đường dẫn tệp Wabo HTML (mặc định: cache/wabo/wabo-2015-01-01.html)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "praxon",
        help="thư mục cache chứa wabo/ và bpic2015/",
    )
    parser.add_argument("--seed", type=int, default=42, help="seed mô hình (mặc định 42)")
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=None,
        help="chỉ chạy N đoạn đầu (chạy thử nhanh)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="tệp TOML cấu hình (mặc định: giá trị mặc định + biến PRAXON_*)",
    )
    args = parser.parse_args(argv)
    # Lệnh trích không dùng cơ sở dữ liệu; database_url chỉ để đủ trường
    # bắt buộc của Settings — cùng cách tool đo 6.5 làm (chuỗi rỗng khi
    # không có tệp cấu hình). Đọc biến môi trường chỉ được phép trong
    # module settings (cổng check_env_access), nên ở đây không đọc env.
    settings = (
        load_settings(args.config) if args.config is not None else Settings(database_url="")
    )
    try:
        mapping = default_dutch_mapping()
        html_path = args.html or (args.cache_dir / "wabo" / WABO_DEFAULT_HTML_FILENAME)
        document = load_wabo_document(html_path, mapping=mapping)
        traces = load_bpic_traces(args.cache_dir / "bpic2015")
    except (FileNotFoundError, ValueError) as exc:
        print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
        return 1
    policy = default_rule_table().policy
    try:
        reflector = build_reflector(settings, seed=args.seed)
        extraction = extract_wabo_rules(
            reflect_document=reflector.reflect_document,
            document=document,
            mapping=mapping,
            traces=traces,
            policy=policy,
            limit_chunks=args.limit_chunks,
        )
    except (ModelCallError, ReflectorBatchError) as exc:
        print(f"lỗi mô hình: {exc}", file=sys.stderr)
        return 2
    print(format_wabo_report(extraction))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
