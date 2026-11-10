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
- Tách một đoạn tại ranh giới Artikel (`--split-chunk N --split-at
  "Artikel X"`): đoạn N thành hai đoạn con, các đoạn khác không đổi
  từng byte nên file JSONL cũ vẫn nối lại được. Dùng cho đoạn 50
  của Wabo (tách tại Artikel 8.3, lần đo 9.1 lần 4): model sinh
  không dừng trên đoạn nguyên vì schema `rules` không có `maxItems`.
- Chế độ một luật (lần thử 6 chống liệt kê, 9.1, `--one-rule`): mỗi đoạn
  hỏi đúng 1 luật một lần gọi (schema `maxItems = 1` + prompt một luật),
  lặp tối đa 8 lần với danh sách loại trừ mọi luật mô hình đã trả cho
  đoạn đó — kể cả luật bị lọc bỏ — nên prompt mỗi lần đều khác và tính
  xác định giữ nguyên ở temperature 0 + seed cố định; dừng khi danh
  sách loại trừ không dài thêm (mô hình trả rỗng hoặc lặp luật đã có).
  Luật vòng tự thân (activation == target sau khi khớp khái niệm) bị bỏ
  và đếm riêng: hai khái niệm khác nhau luôn khớp về hai mã khác nhau
  (bảng gắn: 13 khái niệm -> 13 mã canonical distinct, đã kiểm thật
  2026-11-09, có test giữ) nên so sánh theo mã đã khớp là chính xác.
- Luật trùng (cùng luật từ nhiều đoạn) chỉ đếm một lần; `extracted`
  đếm insight DUY NHẤT, nên `extracted == chấp nhận + không gắn được
  + có điều kiện + cổng Beta loại`.
- Insight có điều kiện bị bỏ qua (đếm riêng): đếm bằng chứng
  (`count_rule_evidence`) không hỗ trợ điều kiện, nên chấp nhận luật
  có điều kiện bằng bằng chứng của luật không điều kiện là sai — luật
  có điều kiện thuộc về 9.5 (BPIC 2019), không thuộc task này.
- Khái niệm không gắn được bị bỏ qua (đếm riêng): không bịa gắn
  (quy tắc của 9.2).
- Lưu từng đoạn ra JSONL (`--chunks-out`): mỗi đoạn xong ghi ngay một
  dòng (chỉ số đoạn, độ dài + SHA-256 văn bản đoạn, insights,
  token) rồi flush + fsync; chạy lại với `--resume-from` thì nạp
  tiền tố liên tục hợp lệ rồi chỉ gọi model cho các đoạn còn thiếu —
  báo cáo cuối giống hệt chạy liền mạch. Dòng hỏng (chết đúng lúc
  ghi) hoặc dòng không khớp đoạn vừa tách thì bị bỏ cùng toàn bộ
  dòng sau, đoạn đó chạy lại; không bao giờ tin dữ liệu hỏng.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TextIO

from praxon_core.adapters.language_model import ModelCallError, model_from_settings
from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS
from praxon_core.datasets.xes import iter_traces
from praxon_core.declare.index import Trace as DeclareTrace
from praxon_core.declare.miner import Rule
from praxon_core.learning.beta import Prior, posterior_prob_ge
from praxon_core.learning.calibration import count_rule_evidence
from praxon_core.learning.coordinator import ReflectorResult
from praxon_core.learning.curator import FactRead, Insight
from praxon_core.learning.declare_schema import DeclareRule, GroundedCombo
from praxon_core.learning.dutch_mapping import DutchMappingTable, default_dutch_mapping
from praxon_core.learning.payload import statement_for
from praxon_core.learning.reflector import (
    GroundedCallResult,
    Reflector,
    ReflectorBatchError,
)
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
    "assert_grounded_census",
    "build_reflector",
    "extract_wabo_rules",
    "extract_wabo_text",
    "format_wabo_report",
    "grounded_combo_indices",
    "grounded_combos",
    "grounded_pairs_for_chunk",
    "is_grounded",
    "load_bpic_traces",
    "load_wabo_document",
    "main",
    "matched_terms",
    "pair_key",
    "parse_valid_during",
    "resolve_activity",
    "split_chunk_at_article",
    "split_sentences",
    "split_wabo_text",
    "write_doc_law_file",
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
    source_quote_dropped: int
    outcomes: tuple[WaboRuleOutcome, ...]
    facts: tuple[FactRow, ...]
    tokens_in: int
    tokens_out: int
    self_loop_dropped: int = 0
    zero_grounded_chunks: int | None = None

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


def split_chunk_at_article(chunk: str, *, marker: str) -> tuple[str, str]:
    """Tách một đoạn thành hai tại đầu một điều ("Artikel X").

    `marker` là đầu đề của điều bắt đầu đoạn thứ hai (vd "Artikel 8.3").
    Đoạn đầu là toàn bộ văn bản trước điều đó, đoạn sau bắt đầu đúng
    tại điều đó. Lỗi nếu không tìm thấy điều, điều nằm ở đầu đoạn,
    hoặc một phía rỗng — không bao giờ trả đoạn rỗng.
    """
    marker = marker.strip()
    if not marker:
        raise ValueError("marker tách đoạn không được rỗng")
    match = re.search(rf"^{re.escape(marker)}(?=\s|$)", chunk, re.MULTILINE)
    if match is None:
        raise ValueError(f"không tìm thấy {marker!r} trong đoạn")
    if match.start() == 0:
        raise ValueError(f"{marker!r} nằm ở đầu đoạn, không tách được")
    first = chunk[: match.start()].strip()
    second = chunk[match.start() :].strip()
    if not first or not second:
        raise ValueError(f"tách tại {marker!r} cho một phía rỗng")
    return first, second


def _split_named_chunk(chunks: Sequence[str], *, index: int, marker: str) -> tuple[str, ...]:
    """Thay đoạn ở `index` bằng hai đoạn con tách tại `marker`."""
    if not 0 <= index < len(chunks):
        raise ValueError(f"chỉ số đoạn tách {index} ngoài 0..{len(chunks) - 1}")
    first, second = split_chunk_at_article(chunks[index], marker=marker)
    return (*chunks[:index], first, second, *chunks[index + 1 :])


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


#: Thứ tự mẫu khi liệt kê combo có căn cứ: precedence trước, response sau.
#: Phải khớp thứ tự thí nghiệm loop-back v2 (không dùng TIER_1_TEMPLATES,
#: vốn là ("response", "precedence") theo ADR) để tái tạo đúng 12/15/15
#: khi kiểm port (bước 5) — thứ tự enum ảnh hưởng luật mô hình chọn.
_GROUNDED_TEMPLATE_ORDER: tuple[str, ...] = ("precedence", "response")

_TERM_PATTERNS: dict[str, re.Pattern[str]] = {}


def _term_pattern(term: str) -> re.Pattern[str]:
    """Mẫu regex word-boundary cho một khái niệm (như S1/S2/S6)."""
    pattern = _TERM_PATTERNS.get(term)
    if pattern is None:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        _TERM_PATTERNS[term] = pattern
    return pattern


def matched_terms(sentence: str, terms: Sequence[str]) -> list[str]:
    """Khái niệm trong bảng mapping xuất hiện trong câu (khớp chuỗi)."""
    return [term for term in terms if _term_pattern(term).search(sentence)]


def is_grounded(activation: str, target: str, quote: str, terms: Sequence[str]) -> bool:
    """Cổng kiểm căn cứ R1: cả hai khái niệm phải có trong trích dẫn."""
    present = matched_terms(quote, terms)
    return activation in present and target in present


def pair_key(template: str, activation: str, target: str) -> str:
    """Một cặp cho phép dạng chuỗi duy nhất, vd "precedence(aanvraag, besluit)"."""
    return f"{template}({activation}, {target})"


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(\[])")


def split_sentences(text: str) -> list[str]:
    """Tách đoạn thành câu: ranh giới tổng quát, không quy tắc riêng ngôn ngữ."""
    out: list[str] = []
    for para in text.split("\n\n"):
        para = " ".join(para.split())
        if not para:
            continue
        for piece in _SENT_SPLIT_RE.split(para):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def grounded_combo_indices(
    chunk: str, terms: Sequence[str]
) -> list[tuple[tuple[str, str, str], int]]:
    """Tổ hợp (cặp, chỉ số câu) có căn cứ của một đoạn, theo thứ tự cố định.

    Thứ tự: mẫu (precedence trước), activation theo thứ tự bảng mapping,
    target theo thứ tự bảng mapping, rồi chỉ số câu. Dùng chỉ số câu
    (không phải văn bản câu) để đối chiếu với file kiểm toán — văn bản
    câu có thể trùng nhau trong một đoạn.
    """
    sentences = split_sentences(chunk)
    sent_terms = [set(matched_terms(sentence, terms)) for sentence in sentences]
    out: list[tuple[tuple[str, str, str], int]] = []
    for template in _GROUNDED_TEMPLATE_ORDER:
        for activation in terms:
            for target in terms:
                if activation == target:
                    continue
                for index, present in enumerate(sent_terms):
                    if activation in present and target in present:
                        out.append(((template, activation, target), index))
    return out


def grounded_combos(chunk: str, terms: Sequence[str]) -> list[GroundedCombo]:
    """Mọi tổ hợp (cặp, câu) có căn cứ của một đoạn, theo thứ tự cố định.

    Một tổ hợp có căn cứ khi câu đó chứa cả hai khái niệm của cặp
    (khớp word-boundary, không phân biệt hoa/thường) — đúng định nghĩa
    cổng vòng 1. Kết quả phải khớp file kiểm toán
    `loopback-r2-grounded-pairs.json` (assert ở `assert_grounded_census`).
    """
    sentences = split_sentences(chunk)
    return [(pair, sentences[index]) for pair, index in grounded_combo_indices(chunk, terms)]


def grounded_pairs_for_chunk(chunk: str, terms: Sequence[str]) -> list[tuple[str, str, str]]:
    """Cặp có căn cứ của một đoạn (không trùng), cùng thứ tự như `grounded_combos`."""
    seen: list[tuple[str, str, str]] = []
    for pair, _sentence in grounded_combos(chunk, terms):
        if pair not in seen:
            seen.append(pair)
    return seen


def assert_grounded_census(
    chunks: Sequence[str], terms: Sequence[str], census_path: Path
) -> None:
    """Kiểm tập combo/cặp có căn cứ khớp CHÍNH XÁC file kiểm toán.

    Chạy trước bất kỳ lần gọi mô hình nào (như thí nghiệm loop-back v2):
    nếu code port tính khác thí nghiệm thì dừng ngay, không chạy. File
    kiểm toán là `loopback-r2-grounded-pairs.json` (52 đoạn).
    """
    census = json.loads(census_path.read_text(encoding="utf-8"))
    for index, chunk in enumerate(chunks):
        combos = grounded_combo_indices(chunk, terms)
        by_pair: dict[str, list[int]] = {}
        for pair, sent_index in combos:
            by_pair.setdefault(pair_key(*pair), []).append(sent_index)
        try:
            entry = census[str(index)]
            entry_pairs = entry["grounded_pairs"]
            entry_combos = entry["n_pair_sentence_combos"]
            entry_n_pairs = entry["n_grounded_pairs"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"file kiểm toán thiếu/sai dạng ở đoạn {index}: {exc}") from exc
        if (
            by_pair != entry_pairs
            or len(combos) != entry_combos
            or len(by_pair) != entry_n_pairs
        ):
            raise ValueError(
                f"tập tổ hợp đoạn {index} lệch file kiểm toán: tính "
                f"{len(by_pair)} cặp / {len(combos)} tổ hợp, file ghi "
                f"{entry_n_pairs} cặp / {entry_combos} tổ hợp"
            )


@dataclass(frozen=True)
class _LoadedChunk:
    """Một đoạn đã nạp từ file JSONL: insights + token đã ghi."""

    insights: tuple[Insight, ...]
    tokens_in: int
    tokens_out: int
    source_quote_dropped: int = 0
    self_loop_dropped: int = 0
    grounded_pairs: int | None = None


def _write_chunk_line(
    handle: TextIO,
    *,
    chunk_index: int,
    chunk: str,
    result: ReflectorResult,
    grounded_pairs: int | None = None,
    n_combos: int | None = None,
    grounded_rules: Sequence[DeclareRule] | None = None,
    n_calls: int | None = None,
    grounding_dropped: int | None = None,
    calls: Sequence[dict[str, Any]] | None = None,
) -> None:
    """Ghi một dòng JSONL cho đoạn vừa xong, rồi flush + fsync ngay.

    Ở chế độ grounded, ghi thêm số cặp có căn cứ, số combo và luật
    giữ kèm trích dẫn nguồn (để kiểm bước 5 đọc từ file, không cần
    trạng thái trong bộ nhớ) + diễn biến từng lần gọi (`calls`, theo
    thứ tự gọi: `{"kept": luật}` / `{"dropped": "quote"|"grounding"}` /
    `{"empty": true}`) để kiểm bước 5 cắt đúng 15 lần gọi đầu khi tái
    lập 12/15/15 từ lần chạy không giới hạn.
    """
    line = {
        "chunk_index": chunk_index,
        "chunk_chars": len(chunk),
        "chunk_sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
        "insights": [insight.model_dump(mode="json") for insight in result.insights],
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "source_quote_dropped": result.source_quote_dropped,
        "self_loop_dropped": result.self_loop_dropped,
    }
    if grounded_pairs is not None:
        line["grounded_pairs"] = grounded_pairs
    if n_combos is not None:
        line["n_combos"] = n_combos
    if grounded_rules is not None:
        line["grounded_rules"] = [
            {
                "template": rule.template,
                "activation": rule.activation,
                "target": rule.target,
                "source": rule.source,
            }
            for rule in grounded_rules
        ]
    if n_calls is not None:
        line["n_calls"] = n_calls
    if grounding_dropped is not None:
        line["grounding_dropped"] = grounding_dropped
    if calls is not None:
        line["calls"] = list(calls)
    handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _load_chunk_lines(path: Path, chunks: Sequence[str]) -> dict[int, _LoadedChunk]:
    """Nạp tiền tố liên tục hợp lệ của file JSONL, theo chỉ số đoạn.

    Mỗi dòng phải parse JSON được, đúng kiểu từng trường, `Insight`
    validate được, và `chunk_chars`/`chunk_sha256` khớp đoạn vừa tách
    ở đúng chỉ số đó. Gặp dòng đầu tiên không hợp lệ thì bỏ dòng đó
    và toàn bộ dòng sau, cảnh báo ra stderr, chạy lại từ đoạn đó.
    File không có hoặc không đọc được thì coi như chưa có đoạn nào.
    """
    loaded: dict[int, _LoadedChunk] = {}
    if not path.is_file():
        print(f"cảnh báo: không có file JSONL để nối lại: {path}", file=sys.stderr)
        return loaded
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"cảnh báo: không đọc được file JSONL {path}: {exc}", file=sys.stderr)
        return loaded
    for raw in lines:
        if not raw.strip():
            continue
        expected = len(loaded)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("dòng JSONL không phải object")
            index = data["chunk_index"]
            chars = data["chunk_chars"]
            digest = data["chunk_sha256"]
            raw_insights = data["insights"]
            tokens_in = data["tokens_in"]
            tokens_out = data["tokens_out"]
            dropped = data.get("source_quote_dropped", 0)
            self_loop_dropped = data.get("self_loop_dropped", 0)
            grounded_pairs = data.get("grounded_pairs")
            if grounded_pairs is not None and (
                type(grounded_pairs) is not int or grounded_pairs < 0
            ):
                raise ValueError("grounded_pairs không phải số nguyên không âm")
            if type(index) is not int or index != expected:
                raise ValueError(f"chunk_index {index!r} khác đoạn chờ {expected}")
            if index >= len(chunks):
                raise ValueError(f"chunk_index {index} vượt số đoạn {len(chunks)}")
            if type(chars) is not int or chars != len(chunks[index]):
                raise ValueError(f"chunk_chars {chars!r} không khớp đoạn {index}")
            if digest != hashlib.sha256(chunks[index].encode("utf-8")).hexdigest():
                raise ValueError(f"chunk_sha256 không khớp đoạn {index}")
            if not isinstance(raw_insights, list):
                raise ValueError("insights không phải danh sách")
            if type(tokens_in) is not int or type(tokens_out) is not int:
                raise ValueError("tokens_in/tokens_out không phải số nguyên")
            if tokens_in < 0 or tokens_out < 0:
                raise ValueError("tokens_in/tokens_out âm")
            if type(dropped) is not int or dropped < 0:
                raise ValueError("source_quote_dropped không phải số nguyên không âm")
            if type(self_loop_dropped) is not int or self_loop_dropped < 0:
                raise ValueError("self_loop_dropped không phải số nguyên không âm")
            insights = tuple(Insight.model_validate(item) for item in raw_insights)
        except (KeyError, TypeError, ValueError) as exc:
            print(
                f"cảnh báo: bỏ dòng JSONL hỏng ở đoạn {expected} và toàn bộ sau: {exc}",
                file=sys.stderr,
            )
            break
        loaded[index] = _LoadedChunk(
            insights=insights,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            source_quote_dropped=dropped,
            self_loop_dropped=self_loop_dropped,
            grounded_pairs=grounded_pairs,
        )
    return loaded


def _is_self_loop_rule(insight: Insight, mapping: DutchMappingTable) -> bool:
    """Luật vòng tự thân: activation và target khớp về cùng một mã.

    Hai khái niệm khác nhau luôn khớp về hai mã khác nhau (bảng gắn:
    13 khái niệm -> 13 mã canonical distinct, đã kiểm thật 2026-11-09,
    có test giữ) nên so sánh theo mã đã khớp là chính xác; khái niệm
    không gắn được thì không tính là vòng tự thân (nó bị đếm riêng ở
    `unmapped`). Luật vòng tự thân là luật rỗng — mô hình sinh nó khi
    cạn luật thật (lần thử 5, 9.1: `response(verlengen, verlengen)` x14).
    """
    first = resolve_activity(insight.activation, mapping)
    second = resolve_activity(insight.target, mapping)
    return first is not None and first == second


def _extract_chunk_one_rule(
    reflect_document_once: Callable[
        [str, Sequence[FactRead], Sequence[str]],
        tuple[ReflectorResult, tuple[str, ...]],
    ],
    chunk: str,
    *,
    max_calls: int,
    mapping: DutchMappingTable,
) -> ReflectorResult:
    """Một đoạn bằng chế độ một luật: lặp tối đa `max_calls` lần gọi.

    Mỗi lần gọi hỏi đúng 1 luật, danh sách loại trừ gồm mọi luật mô
    hình đã trả cho đoạn này (kể cả luật bị lọc bỏ) nên prompt mỗi lần
    đều khác — tính xác định giữ nguyên ở temperature 0 + seed cố định.
    Dừng khi danh sách loại trừ không dài thêm (mô hình trả rỗng hoặc
    lặp luật đã có) hoặc hết `max_calls` lần gọi. Luật vòng tự thân bị
    bỏ và đếm riêng (`self_loop_dropped`); luật còn lại gộp lại (đã
    khử trùng vì danh sách loại trừ chặn lặp).
    """
    excluded: tuple[str, ...] = ()
    insights: list[Insight] = []
    tokens_in = 0
    tokens_out = 0
    quote_dropped = 0
    self_loop_dropped = 0
    for _ in range(max_calls):
        result, updated = reflect_document_once(chunk, (), excluded)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        quote_dropped += result.source_quote_dropped
        if updated == excluded:
            break
        excluded = updated
        for insight in result.insights:
            if _is_self_loop_rule(insight, mapping):
                self_loop_dropped += 1
            else:
                insights.append(insight)
    return ReflectorResult(
        insights=tuple(insights),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        source_quote_dropped=quote_dropped,
        self_loop_dropped=self_loop_dropped,
    )


@dataclass(frozen=True)
class _GroundedChunkResult:
    """Kết quả một đoạn ở chế độ grounded: gộp ReflectorResult + luật giữ + số đếm.

    `calls` là diễn biến từng lần gọi theo thứ tự (để kiểm bước 5 cắt
    đúng 15 lần gọi đầu): mỗi phần tử là `{"kept": luật}` /
    `{"dropped": "quote"|"grounding"}` / `{"empty": true}`.
    """

    result: ReflectorResult
    pairs: tuple[tuple[str, str, str], ...]
    n_combos: int
    kept_rules: tuple[DeclareRule, ...]
    grounding_dropped: int
    calls: tuple[dict[str, Any], ...]


def _extract_chunk_grounded(
    grounded_reflect: Callable[
        [str, Sequence[FactRead], Sequence[GroundedCombo]],
        GroundedCallResult,
    ],
    chunk: str,
    terms: Sequence[str],
    *,
    max_grounded_calls: int | None = None,
) -> _GroundedChunkResult:
    """Một đoạn ở chế độ grounded (A2-full): lặp gọi mô hình trên tập cho phép.

    Mỗi lần gọi tối đa một luật; cặp vừa trả bị xóa khỏi tập cho phép
    kể cả khi luật bị lọc bỏ; mô hình trả rỗng thì thử lại đúng một
    lần rồi dừng; tập cho phép cạn thì dừng. `max_grounded_calls` chỉ
    để kiểm chứng (tái lập 12/15/15 với cap 15) — mặc định None là
    không giới hạn. Luật vòng tự thân không xảy ra ở chế độ này theo
    cấu trúc (cặp luôn có activation khác target), nên không cần cổng
    riêng như chế độ một luật.
    """
    pairs = grounded_pairs_for_chunk(chunk, terms)
    combos = grounded_combos(chunk, terms)
    remaining = tuple(combos)
    insights: list[Insight] = []
    kept_rules: list[DeclareRule] = []
    calls: list[dict[str, Any]] = []
    tokens_in = 0
    tokens_out = 0
    quote_dropped = 0
    grounding_dropped = 0
    empty_streak = 0
    calls_made = 0
    while remaining:
        if max_grounded_calls is not None and calls_made >= max_grounded_calls:
            break
        outcome = grounded_reflect(chunk, (), remaining)
        calls_made += 1
        tokens_in += outcome.result.tokens_in
        tokens_out += outcome.result.tokens_out
        quote_dropped += outcome.result.source_quote_dropped
        grounding_dropped += outcome.grounding_dropped
        remaining = outcome.remaining
        if outcome.empty:
            calls.append({"empty": True})
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0
        if outcome.kept_rules:
            rule = outcome.kept_rules[0]
            calls.append(
                {
                    "kept": {
                        "template": rule.template,
                        "activation": rule.activation,
                        "target": rule.target,
                        "source": rule.source,
                    }
                }
            )
            insights.extend(outcome.result.insights)
            kept_rules.extend(outcome.kept_rules)
        elif outcome.result.source_quote_dropped:
            calls.append({"dropped": "quote"})
        elif outcome.grounding_dropped:
            calls.append({"dropped": "grounding"})
        else:
            raise RuntimeError(
                "luật grounded trả về nhưng không giữ cũng không bị loại (bất biến nội bộ vỡ)"
            )
    return _GroundedChunkResult(
        result=ReflectorResult(
            insights=tuple(insights),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            source_quote_dropped=quote_dropped,
        ),
        pairs=tuple(pairs),
        n_combos=len(combos),
        kept_rules=tuple(kept_rules),
        grounding_dropped=grounding_dropped,
        calls=tuple(calls),
    )


def extract_wabo_rules(
    *,
    reflect_document: Callable[[str, Sequence[FactRead]], ReflectorResult],
    document: WaboDocument,
    mapping: DutchMappingTable,
    traces: Sequence[DeclareTrace],
    policy: Policy,
    limit_chunks: int | None = None,
    chunks_out: Path | None = None,
    resume_from: Path | None = None,
    split_chunk: int | None = None,
    split_chunk_at: str | None = None,
    one_rule: bool = False,
    max_one_rule_calls: int = 8,
    reflect_document_one_rule: Callable[
        [str, Sequence[FactRead], Sequence[str]],
        tuple[ReflectorResult, tuple[str, ...]],
    ]
    | None = None,
    grounded: bool = False,
    max_grounded_calls: int | None = None,
    reflect_document_grounded: Callable[
        [str, Sequence[FactRead], Sequence[GroundedCombo]],
        GroundedCallResult,
    ]
    | None = None,
) -> WaboExtraction:
    """Trích luật thứ tự từ Wabo: Reflector -> gắn khái niệm -> cổng Beta.

    `reflect_document` là đường vào tài liệu của Reflector (6.4) hoặc
    hàm giả trong test — module này không gọi mô hình trực tiếp.
    `limit_chunks` chỉ chạy N đoạn đầu (chạy thử nhanh); None là toàn bộ.
    `chunks_out` ghi mỗi đoạn vừa xong ra file JSONL (append + flush +
    fsync); `resume_from` nạp các đoạn đã xong từ file đó rồi chỉ gọi
    model cho các đoạn còn thiếu — báo cáo cuối giống hệt chạy liền
    mạch. Khi nối lại vào một file khác, file mới chỉ chứa các đoạn
    chạy mới; muốn một file đầy đủ thì dùng cùng đường dẫn cho cả hai.
    `split_chunk` + `split_chunk_at` tách đoạn đó thành hai tại ranh
    giới Artikel TRƯỚC khi áp `limit_chunks`: các đoạn khác không đổi
    nên file JSONL cũ vẫn nối lại được; hai cờ phải đi cùng nhau.
    `one_rule` thì mỗi đoạn trích bằng chế độ một luật (lần thử 6, 9.1):
    lặp tối đa `max_one_rule_calls` lần gọi qua `reflect_document_one_rule`
    (bắt buộc phải truyền khi bật); luật vòng tự thân bị bỏ và đếm riêng.
    `grounded` thì mỗi đoạn trích bằng chế độ có căn cứ (A2-full, 9.1):
    chỉ hỏi các cặp có căn cứ của đoạn qua `reflect_document_grounded`
    (bắt buộc phải truyền khi bật); `max_grounded_calls` giới hạn số
    lần gọi mỗi đoạn (mặc định không giới hạn; 15 để tái lập 12/15/15).
    """
    if limit_chunks is not None and limit_chunks < 1:
        raise ValueError(f"limit_chunks phải >= 1, nhận {limit_chunks}")
    if (split_chunk is None) != (split_chunk_at is None):
        raise ValueError("--split-chunk và --split-at phải đi cùng nhau")
    one_rule_fn = reflect_document_one_rule
    if one_rule and one_rule_fn is None:
        raise ValueError("one_rule cần reflect_document_one_rule")
    if max_one_rule_calls < 1:
        raise ValueError(f"max_one_rule_calls phải >= 1, nhận {max_one_rule_calls}")
    grounded_fn = reflect_document_grounded
    if grounded and grounded_fn is None:
        raise ValueError("grounded cần reflect_document_grounded")
    if max_grounded_calls is not None and max_grounded_calls < 1:
        raise ValueError(f"max_grounded_calls phải >= 1, nhận {max_grounded_calls}")
    terms = [entry.term for entry in mapping.concept]
    chunks = split_wabo_text(document.text)
    if split_chunk is not None and split_chunk_at is not None:
        chunks = _split_named_chunk(chunks, index=split_chunk, marker=split_chunk_at)
    if limit_chunks is not None:
        chunks = chunks[:limit_chunks]
    resumed = _load_chunk_lines(resume_from, chunks) if resume_from is not None else {}
    insights: list[Insight] = []
    tokens_in = 0
    tokens_out = 0
    source_quote_dropped = 0
    self_loop_dropped = 0
    zero_grounded = 0
    with ExitStack() as stack:
        handle = (
            stack.enter_context(open(chunks_out, "a", encoding="utf-8"))
            if chunks_out is not None
            else None
        )
        for index, chunk in enumerate(chunks):
            if index in resumed:
                loaded = resumed[index]
                insights.extend(loaded.insights)
                tokens_in += loaded.tokens_in
                tokens_out += loaded.tokens_out
                source_quote_dropped += loaded.source_quote_dropped
                self_loop_dropped += loaded.self_loop_dropped
                if grounded and loaded.grounded_pairs == 0:
                    zero_grounded += 1
                continue
            grounded_info: _GroundedChunkResult | None = None
            if grounded and grounded_fn is not None:
                grounded_info = _extract_chunk_grounded(
                    grounded_fn,
                    chunk,
                    terms,
                    max_grounded_calls=max_grounded_calls,
                )
                result = grounded_info.result
                if not grounded_info.pairs:
                    zero_grounded += 1
            elif one_rule and one_rule_fn is not None:
                result = _extract_chunk_one_rule(
                    one_rule_fn,
                    chunk,
                    max_calls=max_one_rule_calls,
                    mapping=mapping,
                )
            else:
                result = reflect_document(chunk, ())
            insights.extend(result.insights)
            tokens_in += result.tokens_in
            tokens_out += result.tokens_out
            source_quote_dropped += result.source_quote_dropped
            self_loop_dropped += result.self_loop_dropped
            if handle is not None:
                _write_chunk_line(
                    handle,
                    chunk_index=index,
                    chunk=chunk,
                    result=result,
                    grounded_pairs=(
                        len(grounded_info.pairs) if grounded_info is not None else None
                    ),
                    n_combos=grounded_info.n_combos if grounded_info is not None else None,
                    grounded_rules=(
                        grounded_info.kept_rules if grounded_info is not None else None
                    ),
                    n_calls=len(grounded_info.calls) if grounded_info is not None else None,
                    grounding_dropped=(
                        grounded_info.grounding_dropped if grounded_info is not None else None
                    ),
                    calls=grounded_info.calls if grounded_info is not None else None,
                )
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
        source_quote_dropped=source_quote_dropped,
        outcomes=tuple(outcomes),
        facts=tuple(facts),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        self_loop_dropped=self_loop_dropped,
        zero_grounded_chunks=zero_grounded if grounded else None,
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
        f"Trích dẫn nguồn không khớp (bỏ): {extraction.source_quote_dropped} luật",
        f"Luật vòng tự thân (bỏ): {extraction.self_loop_dropped} luật",
        f"Không gắn được khái niệm: {extraction.unmapped} luật",
        f"Có điều kiện (bỏ qua): {extraction.conditional} luật",
        f"Cổng Beta loại: {extraction.beta_filtered} luật",
        f"Chấp nhận vào global: {extraction.accepted} luật",
        f"Token: vào {extraction.tokens_in}, ra {extraction.tokens_out}",
    ]
    if extraction.zero_grounded_chunks is not None:
        lines.append(f"Đoạn có 0 cặp có căn cứ: {extraction.zero_grounded_chunks} đoạn")
    for outcome in extraction.outcomes:
        if outcome.accepted:
            lines.append(
                f"- {outcome.rule.canonical_key}: {outcome.successes}/"
                f"{outcome.trials}, P={outcome.posterior:.4f}"
            )
    return "\n".join(lines)


def write_doc_law_file(
    path: Path,
    *,
    rules: Sequence[str],
    model_id: str,
    model_revision: str,
    extracted_at: str,
    seed: int,
    beta_support: float,
    beta_confidence: float,
    beta_promote_probability: float,
    beta_prior_confidence: float,
    n_rules_extracted: int,
    n_rules_gated: int,
) -> None:
    """Viết file luật tài liệu đúng định dạng driver đọc (`_read_doc_law_file`).

    Đầu mục `# key: value` (gồm `model_id`/`model_revision` khớp lock)
    + một khóa luật mỗi dòng, **sắp xếp, duy nhất** — đúng như driver
    yêu cầu (khóa chưa sắp xếp hoặc trùng thì driver từ chối cả file).
    Khóa lấy từ `canonical_key` của luật đã qua cổng Beta.
    """
    keys = sorted(set(rules))
    lines = [
        f"# model_id: {model_id}",
        f"# model_revision: {model_revision}",
        f"# extracted_at: {extracted_at}",
        f"# seed: {seed}",
        f"# beta_support: {beta_support}",
        f"# beta_confidence: {beta_confidence}",
        f"# beta_promote_probability: {beta_promote_probability}",
        f"# beta_prior_confidence: {beta_prior_confidence}",
        f"# n_rules_extracted: {n_rules_extracted}",
        f"# n_rules_gated: {n_rules_gated}",
        *keys,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_reflector(
    settings: Settings, *, seed: int, max_tokens: int | None = None
) -> Reflector:
    """Dựng Reflector thật từ Settings (backend CPU, llama-server)."""
    model = model_from_settings(settings, backend="cpu")
    return Reflector(
        model,
        batch_size=settings.reflector_batch_size,
        max_insights_per_batch=settings.reflector_max_insights_per_batch,
        seed=seed,
        max_tokens=max_tokens,
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
        "--chunks-out",
        type=Path,
        default=None,
        help="ghi mỗi đoạn đã xong ra file JSONL (mặc định: không ghi)",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=None,
        help="nạp các đoạn đã xong từ file JSONL rồi chạy tiếp (mặc định: chạy từ đầu)",
    )
    parser.add_argument(
        "--split-chunk",
        type=int,
        default=None,
        help="tách đoạn này thành hai tại ranh giới Artikel (cùng --split-at)",
    )
    parser.add_argument(
        "--split-at",
        type=str,
        default=None,
        help='đầu điều bắt đầu đoạn sau, vd "Artikel 8.3" (cùng --split-chunk)',
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=(
            "lưới an toàn: cắt sinh ở N token, mặc định không giới hạn; "
            "giá trị 2000 lấy theo mức cao nhất đã thấy 748 token x ~2,7"
        ),
    )
    parser.add_argument(
        "--one-rule",
        action="store_true",
        help="chế độ một luật (lần thử 6, 9.1): mỗi đoạn hỏi đúng 1 luật "
        "một lần gọi, lặp tối đa 8 lần (cùng --max-one-rule-calls)",
    )
    parser.add_argument(
        "--max-one-rule-calls",
        type=int,
        default=8,
        help="số lần gọi tối đa mỗi đoạn ở chế độ một luật (mặc định 8)",
    )
    parser.add_argument(
        "--grounded",
        action="store_true",
        help="chế độ có căn cứ (A2-full, 9.1): mỗi đoạn chỉ hỏi các cặp "
        "có căn cứ, không giới hạn số lần gọi (cùng --max-grounded-calls)",
    )
    parser.add_argument(
        "--max-grounded-calls",
        type=int,
        default=None,
        help="số lần gọi tối đa mỗi đoạn ở chế độ grounded (mặc định: "
        "không giới hạn; 15 để tái lập 12/15/15)",
    )
    parser.add_argument(
        "--write-law-file",
        type=Path,
        default=None,
        help="ghi luật đã qua cổng Beta ra file luật tài liệu (mặc định: không ghi)",
    )
    parser.add_argument(
        "--census",
        type=Path,
        default=None,
        help="kiểm tập combo/cặp có căn cứ khớp file kiểm toán trước khi "
        "gọi mô hình (mặc định: không kiểm)",
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
    if args.census is not None:
        try:
            terms = [entry.term for entry in mapping.concept]
            assert_grounded_census(split_wabo_text(document.text), terms, args.census)
        except (FileNotFoundError, ValueError) as exc:
            print(f"lỗi kiểm toán: {exc}", file=sys.stderr)
            return 1
    policy = default_rule_table().policy
    try:
        reflector = build_reflector(settings, seed=args.seed, max_tokens=args.max_tokens)
        extraction = extract_wabo_rules(
            reflect_document=reflector.reflect_document,
            reflect_document_one_rule=(
                reflector.reflect_document_once if args.one_rule else None
            ),
            reflect_document_grounded=(
                reflector.reflect_document_grounded if args.grounded else None
            ),
            document=document,
            mapping=mapping,
            traces=traces,
            policy=policy,
            limit_chunks=args.limit_chunks,
            chunks_out=args.chunks_out,
            resume_from=args.resume_from,
            split_chunk=args.split_chunk,
            split_chunk_at=args.split_at,
            one_rule=args.one_rule,
            max_one_rule_calls=args.max_one_rule_calls,
            grounded=args.grounded,
            max_grounded_calls=args.max_grounded_calls,
        )
    except (ModelCallError, ReflectorBatchError) as exc:
        print(f"lỗi mô hình: {exc}", file=sys.stderr)
        return 2
    print(format_wabo_report(extraction))
    if args.write_law_file is not None:
        write_doc_law_file(
            args.write_law_file,
            rules=[
                outcome.rule.canonical_key
                for outcome in extraction.outcomes
                if outcome.accepted
            ],
            model_id=settings.model_id,
            model_revision=settings.model_revision,
            extracted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            seed=args.seed,
            # Cổng Beta không có ngưỡng support (chỉ hậu nghiệm >= ngưỡng
            # lên) nên đầu mục ghi 0.0 như file luật hiện tại.
            beta_support=0.0,
            beta_confidence=policy.confidence_threshold,
            beta_promote_probability=policy.promote_probability,
            beta_prior_confidence=WABO_PRIOR_CONFIDENCE,
            n_rules_extracted=extraction.extracted,
            n_rules_gated=extraction.accepted,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
