"""Kiểm điều kiện thuộc tính phân loại trên loại matching của BPIC 2019 (task 9.5).

Nhiệm vụ (plan file dòng 234): "Kiểm điều kiện thuộc tính phân loại trên
loại matching của BPIC 2019" — lệnh in số case trong phần thỏa điều kiện;
dưới 30 case thì loại theo luật 7.

Nguồn (đã duyệt + đã kiểm, xem ``~/workspace/praxon-wabo-bpic2019-sources.md``
§3): 4TU.ResearchData, DOI ``10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1``,
một tệp ``BPI_Challenge_2019.xes`` (728.558.522 byte, md5
``4eb909242351193a61e1c15b9c3cc814``, CC BY 4.0). Log đã có trong cache ngoài
kho (``~/.cache/praxon/bpic2019/``) — tệp kiểm md5 trước khi dùng, KHÔNG
bao giờ commit vào kho. BPIC 2019 không dùng làm tenant (spec dòng 25: log
chỉ có 4 mã công ty, một mã chiếm gần hết); nó chỉ dùng để kiểm điều kiện
dữ liệu trên loại matching.

"Loại matching" là thuộc tính case ``Item Category`` (4 giá trị, đo từ log
thật ngày 7/11/2026 — KHÔNG hard-code giá trị nào: module đếm mọi giá trị
xuất hiện trong log rồi kiểm từng giá trị):
- ``'3-way match, invoice before GR'``: 220.752 case (năm 2018).
- ``'3-way match, invoice after GR'``: 15.131 case (năm 2018).
- ``'Consignment'``: 14.494 case (năm 2018).
- ``'2-way match'``: 891 case (năm 2018).

Cách kiểm (luật 7 của Governor, spec dòng 117 + bảng luật mặc định): một
ràng buộc mới có điều kiện thuộc tính chỉ được đi tiếp (luật 2, lên
``trial``) khi phần dữ liệu thỏa điều kiện có ít nhất ``min_matching_cases``
case; dưới ngưỡng thì luật 7 loại (``reject``). Module này đếm số case
trong từng phần (theo giá trị ``Item Category``), rồi chạy Governor thật
(``decide()`` với bảng luật thật) trên một candidate thăm dò cho mỗi loại
— quyết định in ra là quyết định thật của Governor, không phải so sánh
tay. Candidate thăm dò chỉ mang điều kiện ``Item Category = <giá trị>``,
không bịa hoạt động hay luật cụ thể; ``rationale`` ghi rõ nó là thăm dò.

Lọc lỗi dữ liệu: chỉ case bắt đầu trong năm 2018 mới được đếm (log là dữ
liệu 2018; trace bắt đầu ngoài 2018 là lỗi dữ liệu, loại ra và báo số
lượng riêng). Trace thiếu ``Item Category`` cũng đếm riêng, không gán vào
loại nào. Trace không có thời điểm bắt đầu thì không kết luận được năm —
đếm vào loại của nó (không có bằng chứng là lỗi) và báo số lượng riêng.
Đo ngày 7/11/2026: 251.734 case, 1.595.923 sự kiện; ngoài năm 2018: 466
case (2-way match 153, 3-way before GR 258, 3-way after GR 51,
Consignment 4); thiếu ``Item Category``: 0; thiếu thời điểm bắt đầu: 0.

Hiệu chỉnh ``min_matching_cases`` (9.6 đã ghi: nó được hiệu chỉnh ở đây,
vì bộ chuẩn bán tổng hợp không có luật điều kiện nên 9.6 không đo được):
ngưỡng 30 lấy từ tệp cấu hình chính sách (KHÔNG hard-code — đọc từ
``table.policy.min_matching_cases``). Kết quả đo: cả 4 loại đều vượt xa
ngưỡng (nhỏ nhất 891 case, gấp ~29,7 lần 30) — ngưỡng 30 được giữ nguyên
như đã hiệu chỉnh; không loại nào bị luật 7 loại trên dữ liệu này. Nếu
một loại nào đó dưới ngưỡng, lệnh vẫn in đầy đủ rồi kết luận loại đó
không dùng được cho luật có điều kiện (luật 7 loại), chứ không tự đổi
ngưỡng.

Lệnh: ``python -m praxon_core.learning.bpic2019`` (``--cache-dir``,
``--config``). Mã thoát 0 = xong (kể cả khi có loại bị luật 7 loại — loại
là kết quả, không phải lỗi); 1 = lỗi dữ liệu (thiếu tệp, sai md5/kích cỡ).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from praxon_core.datasets.xes import iter_traces
from praxon_core.learning.candidate import Candidate, DecisionVerdict
from praxon_core.learning.governor import decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import RuleTable, default_rule_table, load_rule_table

BPIC2019_DOI = "10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1"
"""DOI 4TU của BPIC 2019 (đã kiểm qua API figshare, ngày 7/11/2026)."""

BPIC2019_ARTICLE_URL = "https://data.4tu.nl/articles/BPI_Challenge_2019/12715853"
"""Trang landing 4TU của BPIC 2019."""

BPIC2019_FILENAME = "BPI_Challenge_2019.xes"
BPIC2019_EXPECTED_SIZE = 728558522
"""Kích cỡ tệp do 4TU công bố (byte)."""

BPIC2019_EXPECTED_MD5 = "4eb909242351193a61e1c15b9c3cc814"
"""Md5 do 4TU công bố — tệp kiểm khớp giá trị này mới được dùng."""

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "praxon" / "bpic2019"
ITEM_CATEGORY_ATTR = "Item Category"
"""Thuộc tính case định nghĩa loại matching (MP-Declare, spec dòng 144)."""

VALID_YEAR = 2018
"""Năm của log BPIC 2019: trace bắt đầu ngoài năm này là lỗi dữ liệu."""

CHUNK_BYTES = 1024 * 1024


class Bpic2019Error(Exception):
    """Lỗi dữ liệu BPIC 2019: thiếu tệp, sai md5/kích cỡ — dừng, không đo."""


@dataclass(frozen=True)
class MatchingCounts:
    """Số case theo loại matching, đếm bằng streaming (không giữ trace).

    ``counts`` chỉ đếm case bắt đầu trong năm 2018; ``out_of_year`` đếm
    case bắt đầu ngoài năm 2018 theo từng loại (lỗi dữ liệu, đã loại);
    ``missing_item_category`` đếm case thiếu thuộc tính (không gán loại
    nào); ``no_start`` đếm case không có thời điểm bắt đầu (đếm vào loại
    của nó vì không có bằng chứng là lỗi).
    """

    total: int
    counts: dict[str, int]
    out_of_year: dict[str, int]
    missing_item_category: int
    no_start: int


def verify_bpic2019(path: Path) -> None:
    """Kiểm tệp BPIC 2019 tồn tại + đúng kích cỡ + đúng md5 4TU công bố."""
    if not path.is_file():
        raise Bpic2019Error(f"thiếu tệp BPIC 2019: {path}")
    size = path.stat().st_size
    if size != BPIC2019_EXPECTED_SIZE:
        raise Bpic2019Error(
            f"kích cỡ tệp {path} là {size} byte, 4TU công bố {BPIC2019_EXPECTED_SIZE} byte"
        )
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    if digest.hexdigest() != BPIC2019_EXPECTED_MD5:
        raise Bpic2019Error(
            f"md5 của {path} không khớp giá trị 4TU công bố {BPIC2019_EXPECTED_MD5}"
        )


def count_matching_cases(path: Path) -> MatchingCounts:
    """Đếm số case theo giá trị ``Item Category`` (streaming, một lượt đọc).

    Chỉ case bắt đầu trong năm 2018 mới vào ``counts``; case ngoài năm
    vào ``out_of_year``; case thiếu thuộc tính vào
    ``missing_item_category`` (không gán loại nào).
    """
    counts: Counter[str] = Counter()
    out_of_year: Counter[str] = Counter()
    missing_item_category = 0
    no_start = 0
    total = 0
    for trace in iter_traces(path):
        total += 1
        value = trace.attributes.get(ITEM_CATEGORY_ATTR)
        if value is None:
            missing_item_category += 1
            continue
        if trace.start is None:
            no_start += 1
            counts[value] += 1
            continue
        if trace.start.year == VALID_YEAR:
            counts[value] += 1
        else:
            out_of_year[value] += 1
    return MatchingCounts(
        total=total,
        counts=dict(counts),
        out_of_year=dict(out_of_year),
        missing_item_category=missing_item_category,
        no_start=no_start,
    )


def _probe_candidate(value: str) -> Candidate:
    """Candidate thăm dò cho một loại matching: chỉ mang điều kiện.

    Không bịa hoạt động hay luật cụ thể — payload chỉ có mẫu + điều kiện;
    ``rationale`` ghi rõ đây là thăm dò cho luật 7, không phải luật thật.
    Governor chỉ đọc số đo (``Measures``), không đọc payload, nên nội
    dung payload không ảnh hưởng quyết định.
    """
    return Candidate(
        target_scope="global",
        payload={
            "template": "response",
            "condition": f"{ITEM_CATEGORY_ATTR} = {value}",
        },
        rationale=(
            f"Thăm dò luật 7 cho loại matching {value!r} trên BPIC 2019 "
            "(task 9.5): đếm case thỏa điều kiện, không phải luật thật."
        ),
        evidence_episode_ids=[],
        status="pending",
    )


def _probe_measures(matching_cases: int) -> Measures:
    """Số đo cho candidate thăm dò: ràng buộc mới, có điều kiện.

    Các số đo khác đặt ở giá trị trung lập để chỉ luật 2 / luật 7 quyết:
    không xung đột trực tiếp (luật 1 không khớp), schema hợp lệ, từ trace
    (đo trên log thật), không phải nâng phạm vi, không từ global. Luật 3 /
    4 / 8 cần ``is_new`` sai nên không khớp; luật 9 là luật cuối cùng.
    """
    return Measures(
        has_direct_conflict=False,
        schema_valid=True,
        from_trace=True,
        wilson_lower=1.0,
        beta_prob=0.5,
        is_scope_promotion=False,
        from_global=False,
        has_condition=True,
        matching_cases=matching_cases,
        fact_status=None,
        is_new=True,
        human_early_activate=False,
        has_rubric_clause=False,
    )


@dataclass(frozen=True)
class MatchingCheck:
    """Kết quả kiểm một loại matching bằng Governor thật."""

    value: str
    cases: int
    rule_id: int | None
    verdict: DecisionVerdict
    reason: str


def check_matching_conditions(counts: MatchingCounts, table: RuleTable) -> list[MatchingCheck]:
    """Chạy Governor thật cho từng loại matching (theo thứ tự tên loại).

    Luật 2 khớp (lên ``trial``) khi phần thỏa điều kiện đủ
    ``min_matching_cases``; luật 7 khớp (``reject``) khi dưới ngưỡng.
    """
    checks: list[MatchingCheck] = []
    for value in sorted(counts.counts):
        cases = counts.counts[value]
        result = decide(_probe_candidate(value), table, _probe_measures(cases))
        checks.append(
            MatchingCheck(
                value=value,
                cases=cases,
                rule_id=result.decision.rule_id,
                verdict=result.decision.verdict,
                reason=result.decision.reason,
            )
        )
    return checks


@dataclass(frozen=True)
class CalibrationResult:
    """Kết quả hiệu chỉnh ``min_matching_cases`` trên BPIC 2019.

    Ngưỡng lấy từ tệp cấu hình (``table.policy``), không hard-code. ``all_pass``
    đúng khi mọi loại đều đủ ngưỡng — khi đó ngưỡng được giữ nguyên như đã
    hiệu chỉnh. ``below`` liệt kê loại dưới ngưỡng (nếu có): loại đó không
    dùng được cho luật có điều kiện (luật 7 loại).
    """

    threshold: int
    min_cases: int
    min_value: str
    n_types: int
    all_pass: bool
    below: tuple[str, ...]


def calibrate_min_matching_cases(counts: MatchingCounts, table: RuleTable) -> CalibrationResult:
    """Hiệu chỉnh ``min_matching_cases``: kiểm mọi loại có đủ ngưỡng."""
    threshold = table.policy.min_matching_cases
    if not counts.counts:
        return CalibrationResult(
            threshold=threshold,
            min_cases=0,
            min_value="",
            n_types=0,
            all_pass=False,
            below=(),
        )
    min_value = min(counts.counts, key=lambda value: counts.counts[value])
    below = tuple(sorted(value for value, cases in counts.counts.items() if cases < threshold))
    return CalibrationResult(
        threshold=threshold,
        min_cases=counts.counts[min_value],
        min_value=min_value,
        n_types=len(counts.counts),
        all_pass=not below,
        below=below,
    )


def format_report(
    counts: MatchingCounts,
    checks: list[MatchingCheck],
    calibration: CalibrationResult,
    path: Path,
) -> str:
    """In số case trong phần thỏa điều kiện + quyết định + hiệu chỉnh."""
    out_of_year_total = sum(counts.out_of_year.values())
    lines = [
        f"BPIC 2019 ({BPIC2019_DOI}): {path.name}",
        f"tổng case: {counts.total} "
        f"(trong năm {VALID_YEAR}: {sum(counts.counts.values())}; "
        f"ngoài năm: {out_of_year_total}; "
        f"thiếu {ITEM_CATEGORY_ATTR}: {counts.missing_item_category}; "
        f"không có thời điểm bắt đầu: {counts.no_start})",
        f"loại matching ({ITEM_CATEGORY_ATTR}) | case ({VALID_YEAR}) | luật | quyết định",
    ]
    for check in checks:
        lines.append(
            f"{check.value} | {check.cases} | {check.rule_id} | "
            f"{check.verdict.value} ({check.reason})"
        )
    if calibration.all_pass:
        ratio = calibration.min_cases / calibration.threshold
        lines.append(
            f"hiệu chỉnh min_matching_cases={calibration.threshold}: "
            f"cả {calibration.n_types} loại đều đủ ngưỡng "
            f"(nhỏ nhất {calibration.min_value!r}: "
            f"{calibration.min_cases} case, gấp {ratio:.1f} lần) "
            "— ngưỡng được giữ nguyên."
        )
    else:
        lines.append(
            f"hiệu chỉnh min_matching_cases={calibration.threshold}: "
            f"{len(calibration.below)}/{calibration.n_types} loại dưới ngưỡng "
            f"({', '.join(calibration.below)}) — loại đó không dùng được "
            "cho luật có điều kiện (luật 7 loại)."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh kiểm điều kiện thuộc tính trên BPIC 2019.

    ``python -m praxon_core.learning.bpic2019`` — in số case trong phần
    thỏa điều kiện cho từng loại matching + quyết định của Governor + kết
    quả hiệu chỉnh ``min_matching_cases``. Mã thoát 0 = xong (kể cả khi
    có loại bị luật 7 loại — loại là kết quả, không phải lỗi); 1 = lỗi
    dữ liệu (thiếu tệp, sai md5/kích cỡ).
    """
    parser = argparse.ArgumentParser(
        prog="praxon_core.learning.bpic2019",
        description=(
            "Kiểm điều kiện thuộc tính phân loại trên loại matching "
            "của BPIC 2019 (task 9.5): in số case thỏa điều kiện cho "
            "từng loại + quyết định luật 7 của Governor."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache ngoài kho (mặc định: %(default)s)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="tệp bảng luật TOML (mặc định: bảng mặc định của Governor)",
    )
    args = parser.parse_args(argv)
    path = args.cache_dir / BPIC2019_FILENAME
    try:
        verify_bpic2019(path)
    except Bpic2019Error as exc:
        print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
        return 1
    table = load_rule_table(args.config) if args.config is not None else default_rule_table()
    counts = count_matching_cases(path)
    checks = check_matching_conditions(counts, table)
    calibration = calibrate_min_matching_cases(counts, table)
    print(format_report(counts, checks, calibration, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
