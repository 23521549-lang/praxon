"""Sinh báo cáo kết quả giai đoạn 1 (task 13.2).

Một lệnh duy nhất: đọc đầu ra đã lưu của các lệnh nguồn trong
``docs/reports/inputs/`` rồi lắp thành
``docs/reports/ket-qua-giai-doan-1.md`` theo đúng cấu trúc Phụ lục A
của đề xuất 13.2. Mọi con số trong báo cáo đều có một dòng trong bảng
ánh xạ (Phụ lục B của đề xuất) — số nào không có nguồn thì mục đó ghi
``CHƯA CÓ`` chứ không bao giờ bịa số.

Thoát 0: báo cáo đã sinh (kèm danh sách mục thiếu nếu có).
Thoát 1: một số trong báo cáo không có nguồn trong bảng ánh xạ, hoặc
báo cáo chứa từ verdict cổng 1, hoặc mục caveat rỗng.
Không gọi mô hình, không chạy phép đo đắt, không ghi DB.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from praxon_core.settings import Settings

MISSING = "CHƯA CÓ"
"""Từ đánh dấu mục chưa có đầu vào: trạng thái, không phải lỗi lệnh."""

VERDICT_WORDS: tuple[str, ...] = ("ĐẠT", "KHÔNG ĐẠT", "chặn", "qua cổng")
"""Từ verdict cổng 1 (13.3) — báo cáo kết quả không bao giờ chứa chúng (R4)."""

STRUCTURAL_NUMBERS: frozenset[str] = frozenset(
    {
        "0",  # kích thước đường cong khởi động lạnh (spec 187)
        "1",  # số mục báo cáo (Phụ lục A) + số thứ tự
        "2",  # nhãn loại matching "2-way" (B1.7)
        "3",  # nhãn loại matching "3-way" (B1.7)
        "4",  # bốn chỉ số (spec 178)
        "5",  # năm đô thị (spec) + kích thước đường cong (spec 187)
        "6",  # số mục báo cáo (Phụ lục A)
        "7",  # bảy điều kiện (spec 142)
        "8",  # Qwen3-8B-GGUF (tên mẫu, B1.3)
        "9",  # số mục báo cáo (Phụ lục A)
        "10",  # ngưỡng vi phạm 10% (spec 178) + số mục báo cáo
        "20",  # kích thước đường cong (spec 187)
        "26",  # plan file từng stale 26 task (review đợt 2 §3.3 — trích dẫn)
        "40",  # kích thước đường cong (spec 187)
        "60",  # tỉ lệ phần hiệu chỉnh 60/20/20 (spec 152)
        "65",  # số task lỗi thời ghi trong plan file (trích dẫn, không phải số đo)
        "95",  # khoảng tin cậy 95% (spec 178)
        "104",  # bộ 104 câu (spec 166)
        "2015",  # năm trong tên BPIC 2015
        "2018",  # năm đo trong BPIC 2019 (B1.6)
        "2019",  # năm trong tên BPIC 2019
    }
)
"""Số xuất hiện trong báo cáo mà không phải số đo: số mục, tỉ lệ chia,
kích thước đường cong, năm, và hai số trích dẫn lịch sử (26, 65). Mọi
số đo khác phải có trong registry của lần render (R1)."""

_NUMBER_TOKEN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_HEX_HASH = re.compile(r"[0-9a-f]{7,}")
_DATE_TOKEN = re.compile(r"\d{4}-\d{2}-\d{2}")
_DOT_DECIMAL = re.compile(r"\d+\.\d{1,2}\b")


@dataclass(frozen=True)
class MappingEntry:
    """Một dòng trong bảng ánh xạ (Phụ lục B): số nào, lệnh nào sinh."""

    id: str
    section: str
    label: str
    input_file: str
    command: str
    waiting_task: str | None


MAPPING: tuple[MappingEntry, ...] = (
    MappingEntry(
        id="B1.1",
        section="du-lieu",
        label="Hồ sơ 5 đô thị (case/sự kiện/hoạt động)",
        input_file="profile-bpic2015.txt",
        command="python -m praxon_core.datasets.profile",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.2",
        section="du-lieu",
        label="Phép chia 60/20/20 (số case mỗi phần)",
        input_file="split-bpic2015.txt",
        command="python -m praxon_core.datasets.split",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.3",
        section="f1",
        label="F1 tổng micro (6.5)",
        input_file="f1-text-to-ltl.txt",
        command="python -m tools.measure_f1_text_to_ltl",
        waiting_task="đo lại 6.5 (cần llama-server chạy)",
    ),
    MappingEntry(
        id="B1.4",
        section="f1",
        label="F1 theo mẫu (6.5)",
        input_file="f1-text-to-ltl.txt",
        command="python -m tools.measure_f1_text_to_ltl",
        waiting_task="đo lại 6.5 (cần llama-server chạy)",
    ),
    MappingEntry(
        id="B1.5",
        section="du-lieu",
        label="F1 bộ sinh 5.3 (độ khó)",
        input_file="",
        command="",
        waiting_task="lệnh sinh chưa xác nhận",
    ),
    MappingEntry(
        id="B1.6",
        section="du-lieu",
        label="BPIC 2019: tổng case + sự kiện",
        input_file="bpic2019.txt",
        command="python -m praxon_core.learning.bpic2019",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.7",
        section="du-lieu",
        label="BPIC 2019: 4 loại matching (năm 2018)",
        input_file="bpic2019.txt",
        command="python -m praxon_core.learning.bpic2019",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.8",
        section="du-lieu",
        label="BPIC 2019: ngoài năm / thiếu thuộc tính",
        input_file="bpic2019.txt",
        command="python -m praxon_core.learning.bpic2019",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.9",
        section="du-lieu",
        label="min_matching_cases = 30 giữ nguyên",
        input_file="bpic2019.txt",
        command="python -m praxon_core.learning.bpic2019",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.10",
        section="hieu-chinh",
        label="Hiệu chỉnh 9.6: bảng 2.0/4.0/6.0",
        input_file="calibration-beta.txt",
        command="python -m praxon_core.learning.calibration",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.11",
        section="hieu-chinh",
        label="Độ mạnh đã áp",
        input_file="",
        command="đọc learning/default_rule_table.toml dòng 10",
        waiting_task=None,
    ),
    MappingEntry(
        id="B1.12",
        section="khoi-dong-lanh",
        label="Đường cong khởi động lạnh (8.4)",
        input_file="cold-start.txt",
        command="python -m praxon_core.eval.cold_start",
        waiting_task=None,
    ),
    MappingEntry(
        id="B2.1",
        section="wabo",
        label="Wabo: trích được / không gắn được / cổng Beta loại / token",
        input_file="wabo-rules.txt",
        command="python -m praxon_core.learning.wabo_rules",
        waiting_task="9.1 đo thật",
    ),
    MappingEntry(
        id="B2.2",
        section="bon-chi-so",
        label="Bốn chỉ số theo tenant x điều kiện kèm CI 95%",
        input_file="",
        command="lệnh 13.1 (một lệnh, bảy điều kiện, cả hai nguồn)",
        waiting_task="13.1 (lệnh) + 12.2 (lần chạy đo)",
    ),
    MappingEntry(
        id="B2.3",
        section="tai-lap",
        label="Tái lập: chạy lại lần hai ra đúng kết quả lần đầu hay không",
        input_file="",
        command="chạy của 12.3 (đối chiếu bằng reproducibility_gaps)",
        waiting_task="12.3",
    ),
    MappingEntry(
        id="B2.4",
        section="dut-phien",
        label="Phép thử đứt phiên: verdict 4 lần chạy",
        input_file="",
        command="driver 11.3 + script so sánh compare_11_3.py",
        waiting_task="11.3 (lần chạy Kaggle chờ 11.1 + 11.2)",
    ),
    MappingEntry(
        id="B2.5",
        section="snapshot",
        label="Commit khóa + config_hash của lần chạy đo",
        input_file="",
        command="commit khóa 12.1",
        waiting_task="12.1 (bước khóa)",
    ),
)


@dataclass(frozen=True)
class ProfileRow:
    """Một đô thị trong bảng hồ sơ (B1.1)."""

    municipality: int
    cases: int
    events: int
    activity_types: int


@dataclass(frozen=True)
class SplitRow:
    """Một đô thị trong phép chia (B1.2)."""

    municipality: int
    total: int
    train: int
    calibration: int
    test: int


@dataclass(frozen=True)
class Bpic2019Data:
    """Số đo BPIC 2019 (B1.6-B1.9)."""

    total: int
    in_year: int
    out_of_year: int
    missing_item_category: int
    no_start: int
    matching: tuple[tuple[str, int, str, str], ...]
    threshold: int
    min_type: str
    min_cases: int
    ratio: float
    all_pass: bool


@dataclass(frozen=True)
class ColdStartPoint:
    """Một điểm trên đường cong khởi động lạnh (B1.12)."""

    n_traces: int
    n_rules: int
    precision: float
    recall: float
    violation_rate: float
    negative_transfer: float
    mode: str


@dataclass(frozen=True)
class CalibrationRow:
    """Một hàng trong bảng hiệu chỉnh (B1.10)."""

    strength: float
    median_traces: float | None
    invariant_margin: float
    false_promotes: int
    false_retires: int
    promoted: int


@dataclass(frozen=True)
class F1Data:
    """Kết quả đo F1 (B1.3-B1.4)."""

    model_id: str
    model_revision: str
    measured: int
    failures: int
    per_template: tuple[tuple[str, float, float, float, float, int, int, int], ...]
    overall: tuple[float, float, float, float, int, int, int]


@dataclass(frozen=True)
class Snapshot:
    """Ảnh chụp đầu vào ở đầu báo cáo (Phụ lục A mục 1)."""

    commit: str
    date: str
    lock_commit: str | None
    lock_hash: str | None
    data_hash: str | None
    seed: int | None
    model_id: str
    model_revision: str
    settings_fields: tuple[str, ...]
    plan_task_rows: int | None
    inputs: tuple[tuple[str, str], ...]


@dataclass
class Recorder:
    """Ghi lại mọi số đo đã render — để kiểm R1 ở cuối."""

    values: set[str] = field(default_factory=set)

    def integer(self, value: int) -> str:
        """Số nguyên theo định dạng Việt Nam (dấu chấm ngăn nghìn)."""
        text = f"{value:,}".replace(",", ".")
        self.values.add(text)
        return text

    def decimal(self, value: float, digits: int = 4) -> str:
        """Số thập phân theo định dạng Việt Nam (dấu phẩy thập phân)."""
        text = f"{value:.{digits}f}".replace(".", ",")
        self.values.add(text)
        return text

    def plain(self, value: str) -> str:
        """Ghi lại một số đã có dạng văn bản (vd số đếm từ input)."""
        self.values.add(value)
        return value


def _parse_int(text: str, what: str) -> int:
    try:
        return int(text.replace(".", "").replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"không đọc được số nguyên cho {what}: {text!r}") from exc


def _parse_float(text: str, what: str) -> float:
    try:
        return float(text.replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"không đọc được số thực cho {what}: {text!r}") from exc


_PROFILE_RE = re.compile(r"Đô thị (\d+): (\d+) case, (\d+) sự kiện, (\d+) loại hoạt động")
_SPLIT_RE = re.compile(r"Đô thị (\d+): (\d+) case → học (\d+), hiệu chỉnh (\d+), đo (\d+)")
_COMBINED_HASH_RE = re.compile(r"data_hash chung \(cả năm đô thị\): ([0-9a-f]{64})")
_BPIC2019_TOTAL_RE = re.compile(
    r"tổng case: (\d+) \(trong năm \d+: (\d+); ngoài năm: (\d+); "
    r"thiếu Item Category: (\d+); không có thời điểm bắt đầu: (\d+)\)"
)
_BPIC2019_ROW_RE = re.compile(r"^(.+?) \| (\d+) \| (\S+) \| (\S+) \(.*\)$", re.MULTILINE)
_BPIC2019_CALIB_RE = re.compile(
    r"hiệu chỉnh min_matching_cases=(\d+): cả (\d+) loại đều đủ ngưỡng "
    r"\(nhỏ nhất '(.+?)': (\d+) case, gấp (\d+(?:\.\d+)?) lần\)"
)
_COLD_START_ROW_RE = re.compile(
    r"^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+\.\d+)\s*\|\s*(\d+\.\d+)\s*"
    r"\|\s*(\d+\.\d+)\s*\|\s*(\d+\.\d+)\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
_CALIBRATION_HEADER_RE = re.compile(
    r"Bộ chuẩn: hạt (\d+), (\d+) trace \((\d+) học / (\d+) hiệu chỉnh / (\d+) đo\)"
)
_CALIBRATION_ROW_RE = re.compile(
    r"^(\d+\.\d+) \| (\d+\.\d+|-) \| (\d+\.\d+) \| (\d+) \| (\d+) \| (\d+)$",
    re.MULTILINE,
)
_CALIBRATION_SELECTED_RE = re.compile(r"^Chọn: (\d+\.\d+)$", re.MULTILINE)
_F1_MODEL_RE = re.compile(r"^Mo hinh: (\S+) \(revision ([0-9a-f]+)\)$", re.MULTILINE)
_F1_MEASURED_RE = re.compile(r"^So cau do: (\d+); goi mo hinh hong: (\d+)$", re.MULTILINE)
_F1_ROW_RE = re.compile(
    r"^(\S+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)\s+(\d+)\s+(\d+)$",
    re.MULTILINE,
)


def parse_profile(text: str) -> list[ProfileRow]:
    """Bảng hồ sơ 5 đô thị từ đầu ra `datasets.profile` (B1.1)."""
    rows = [
        ProfileRow(
            municipality=int(match.group(1)),
            cases=_parse_int(match.group(2), "case"),
            events=_parse_int(match.group(3), "sự kiện"),
            activity_types=_parse_int(match.group(4), "loại hoạt động"),
        )
        for match in _PROFILE_RE.finditer(text)
    ]
    if len(rows) != 5:
        raise ValueError(f"bảng hồ sơ phải có đúng 5 đô thị, đọc được {len(rows)}")
    if [row.municipality for row in rows] != [1, 2, 3, 4, 5]:
        raise ValueError("bảng hồ sơ thiếu một đô thị trong 1-5")
    return rows


def parse_split(text: str) -> tuple[list[SplitRow], str]:
    """Phép chia 5 đô thị + data_hash chung từ đầu ra `datasets.split` (B1.2)."""
    rows = [
        SplitRow(
            municipality=int(match.group(1)),
            total=_parse_int(match.group(2), "tổng case"),
            train=_parse_int(match.group(3), "học"),
            calibration=_parse_int(match.group(4), "hiệu chỉnh"),
            test=_parse_int(match.group(5), "đo"),
        )
        for match in _SPLIT_RE.finditer(text)
    ]
    if len(rows) != 5:
        raise ValueError(f"phép chia phải có đúng 5 đô thị, đọc được {len(rows)}")
    combined = _COMBINED_HASH_RE.search(text)
    if combined is None:
        raise ValueError("thiếu dòng data_hash chung trong đầu ra split")
    return rows, combined.group(1)


def parse_bpic2019(text: str) -> Bpic2019Data:
    """Số đo BPIC 2019 từ đầu ra `learning.bpic2019` (B1.6-B1.9)."""
    total_match = _BPIC2019_TOTAL_RE.search(text)
    if total_match is None:
        raise ValueError("thiếu dòng tổng case trong đầu ra bpic2019")
    matching = tuple(
        (
            match.group(1),
            _parse_int(match.group(2), "case matching"),
            match.group(3),
            match.group(4),
        )
        for match in _BPIC2019_ROW_RE.finditer(text)
    )
    if len(matching) != 4:
        raise ValueError(f"phải có đúng 4 loại matching, đọc được {len(matching)}")
    calib = _BPIC2019_CALIB_RE.search(text)
    if calib is None:
        raise ValueError("thiếu dòng hiệu chỉnh min_matching_cases trong đầu ra bpic2019")
    return Bpic2019Data(
        total=_parse_int(total_match.group(1), "tổng case"),
        in_year=_parse_int(total_match.group(2), "trong năm"),
        out_of_year=_parse_int(total_match.group(3), "ngoài năm"),
        missing_item_category=_parse_int(total_match.group(4), "thiếu Item Category"),
        no_start=_parse_int(total_match.group(5), "không có thời điểm bắt đầu"),
        matching=matching,
        threshold=_parse_int(calib.group(1), "ngưỡng"),
        min_type=calib.group(3),
        min_cases=_parse_int(calib.group(4), "nhỏ nhất"),
        ratio=_parse_float(calib.group(5), "tỉ lệ"),
        all_pass=True,
    )


def parse_cold_start(text: str) -> list[ColdStartPoint]:
    """Đường cong khởi động lạnh từ đầu ra `eval.cold_start` (B1.12)."""
    points = [
        ColdStartPoint(
            n_traces=int(match.group(1)),
            n_rules=int(match.group(2)),
            precision=_parse_float(match.group(3), "precision"),
            recall=_parse_float(match.group(4), "recall"),
            violation_rate=_parse_float(match.group(5), "vi phạm"),
            negative_transfer=_parse_float(match.group(6), "neg.transfer"),
            mode=match.group(7),
        )
        for match in _COLD_START_ROW_RE.finditer(text)
    ]
    if [point.n_traces for point in points] != [0, 5, 10, 20, 40]:
        raise ValueError(
            "đường cong phải có đúng 5 điểm 0/5/10/20/40 trace, "
            f"đọc được {[point.n_traces for point in points]}"
        )
    return points


def parse_calibration(text: str) -> tuple[list[CalibrationRow], float, int]:
    """Bảng hiệu chỉnh từ đầu ra `learning.calibration` (B1.10).

    Trả (các hàng, độ mạnh được chọn, hạt của bộ chuẩn).
    """
    header = _CALIBRATION_HEADER_RE.search(text)
    if header is None:
        raise ValueError("thiếu dòng đầu bộ chuẩn trong đầu ra calibration")
    rows = [
        CalibrationRow(
            strength=_parse_float(match.group(1), "độ mạnh"),
            median_traces=(
                _parse_float(match.group(2), "trung vị") if match.group(2) != "-" else None
            ),
            invariant_margin=_parse_float(match.group(3), "biên"),
            false_promotes=int(match.group(4)),
            false_retires=int(match.group(5)),
            promoted=int(match.group(6)),
        )
        for match in _CALIBRATION_ROW_RE.finditer(text)
    ]
    if len(rows) != 3:
        raise ValueError(f"bảng hiệu chỉnh phải có đúng 3 hàng, đọc được {len(rows)}")
    selected = _CALIBRATION_SELECTED_RE.search(text)
    if selected is None:
        raise ValueError("thiếu dòng độ mạnh được chọn trong đầu ra calibration")
    return rows, _parse_float(selected.group(1), "độ mạnh được chọn"), int(header.group(1))


def parse_f1(text: str) -> F1Data:
    """Kết quả đo F1 từ đầu ra `tools.measure_f1_text_to_ltl` (B1.3-B1.4)."""
    model = _F1_MODEL_RE.search(text)
    measured = _F1_MEASURED_RE.search(text)
    if model is None or measured is None:
        raise ValueError("thiếu dòng mô hình hoặc số câu đo trong đầu ra F1")
    rows = [
        (
            match.group(1),
            _parse_float(match.group(2), "precision"),
            _parse_float(match.group(3), "recall"),
            _parse_float(match.group(4), "F1"),
            _parse_float(match.group(5), "F1 GPT-4"),
            int(match.group(6)),
            int(match.group(7)),
            int(match.group(8)),
        )
        for match in _F1_ROW_RE.finditer(text)
    ]
    templates = {row[0] for row in rows}
    if templates != {"precedence", "response", "succession", "init", "end", "Overall"}:
        raise ValueError(f"bảng F1 thiếu mẫu, đọc được {sorted(templates)}")
    overall_row = next(row for row in rows if row[0] == "Overall")
    return F1Data(
        model_id=model.group(1),
        model_revision=model.group(2),
        measured=int(measured.group(1)),
        failures=int(measured.group(2)),
        per_template=tuple(row for row in rows if row[0] != "Overall"),
        overall=(
            overall_row[1],
            overall_row[2],
            overall_row[3],
            overall_row[4],
            overall_row[5],
            overall_row[6],
            overall_row[7],
        ),
    )


_PLAN_TASK_ROW_RE = re.compile(r"^\|\s*\d+\.\d+\s*\|")
_ZERO_HASH = "0" * 40


def _read_lock(repo_root: Path) -> tuple[str | None, str | None]:
    """Commit khóa 12.1 (None nếu chưa khóa — file tạm ghi rõ CHƯA KHÓA)."""
    lock_path = repo_root / "configs" / "phan-do.lock.toml"
    if not lock_path.is_file():
        return None, None
    try:
        with lock_path.open("rb") as handle:
            record = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError):
        return None, None
    if record.get("locked_at") == "CHUA-KHOA":
        return None, None
    lock_commit = str(record.get("lock_commit", ""))
    if lock_commit == _ZERO_HASH or not lock_commit:
        return None, None
    return lock_commit, str(record.get("locked_config_hash", "")) or None


def _count_plan_task_rows(repo_root: Path) -> int | None:
    """Đếm dòng task trong plan file (để đối chiếu số "65 task" lỗi thời)."""
    plan_path = repo_root / "docs" / "plans" / "phase-1-core" / "Plan giai đoạn 1 — lõi học.md"
    if not plan_path.is_file():
        return None
    return sum(
        1
        for line in plan_path.read_text(encoding="utf-8").splitlines()
        if _PLAN_TASK_ROW_RE.match(line)
    )


def build_snapshot(
    *,
    repo_root: Path,
    commit: str,
    date: str,
    inputs: dict[str, str],
    data_hash: str | None,
    seed: int | None,
) -> Snapshot:
    """Ảnh chụp đầu vào (Phụ lục A mục 1) từ repo + đầu vào đã nạp."""
    # database_url="" là mẫu dùng trong codebase cho lần chạy không cần DB
    # (wabo_rules.py); generator không đọc DB nên chỉ cần giá trị giữ chỗ.
    settings = Settings(database_url="")
    lock_commit, lock_hash = _read_lock(repo_root)
    return Snapshot(
        commit=commit,
        date=date,
        lock_commit=lock_commit,
        lock_hash=lock_hash,
        data_hash=data_hash,
        seed=seed,
        model_id=settings.model_id,
        model_revision=settings.model_revision,
        settings_fields=tuple(sorted(Settings.model_fields)),
        plan_task_rows=_count_plan_task_rows(repo_root),
        inputs=tuple(
            (name, hashlib.sha256(text.encode("utf-8")).hexdigest())
            for name, text in sorted(inputs.items())
        ),
    )


def find_verdict_words(report: str) -> list[str]:
    """Từ verdict cổng 1 lọt vào báo cáo kết quả (R4) — phải rỗng."""
    return [word for word in VERDICT_WORDS if word in report]


def find_unsourced_numbers(report: str, registry: set[str]) -> list[str]:
    """Số trong báo cáo không có nguồn trong bảng ánh xạ (R1).

    Bỏ qua băm hex (commit/sha256), ngày sinh, và số thập phân chấm
    (tham chiếu task như 12.1, mã ánh xạ như B1.3) trước khi quét.
    Nhãn "sha256" cũng được bỏ qua — nó là tên hàm băm, không phải số.
    """
    cleaned = _HEX_HASH.sub("", report)
    cleaned = cleaned.replace("sha256", "sha")
    cleaned = _DATE_TOKEN.sub("", cleaned)
    cleaned = _DOT_DECIMAL.sub("", cleaned)
    return sorted(
        {token for token in _NUMBER_TOKEN.findall(cleaned)} - registry - STRUCTURAL_NUMBERS
    )


def _missing_line(label: str, waiting_task: str | None) -> str:
    reason = f" — chờ {waiting_task}" if waiting_task else ""
    return f"{MISSING}{reason}"


def render_report(
    snapshot: Snapshot,
    parsed: dict[str, object],
    missing: list[MappingEntry],
) -> tuple[str, Recorder]:
    """Lắp báo cáo theo Phụ lục A từ đầu vào đã phân tích.

    Trả (văn bản báo cáo, recorder ghi mọi số đo đã render).
    """
    rec = Recorder()
    lines: list[str] = []
    lines.append("# Báo cáo kết quả giai đoạn 1")
    lines.append("")
    lines.append(
        "Sinh bằng lệnh: `python -m tools.generate_phase1_report` — mọi số "
        "trong báo cáo này đều do một lệnh sinh ra (xem bảng ánh xạ trong "
        "đề xuất 13.2); mục chưa có đầu vào ghi `CHƯA CÓ`, không bịa số."
    )
    lines.append("")
    lines.append("## 1. Ảnh chụp đầu vào")
    lines.append("")
    lines.append(f"- Commit `feat/integration` lúc sinh: `{snapshot.commit}`")
    lines.append(f"- Ngày sinh (UTC+7): {snapshot.date}")
    if snapshot.lock_commit is None:
        lines.append("- Khóa cấu hình 12.1: CHƯA KHÓA — chờ 12.1 (bước khóa)")
    else:
        lines.append(f"- Khóa cấu hình 12.1: commit `{snapshot.lock_commit}`")
    if snapshot.lock_hash is None:
        lines.append("- `config_hash` (khóa đo): CHƯA CÓ — chờ khóa 12.1")
    else:
        lines.append(f"- `config_hash` (khóa đo): `{snapshot.lock_hash}`")
    if snapshot.data_hash is None:
        lines.append("- `data_hash` (BPIC 2015): CHƯA CÓ — chờ lệnh chia")
    else:
        lines.append(f"- `data_hash` (BPIC 2015, cả năm đô thị): `{snapshot.data_hash}`")
    if snapshot.seed is None:
        lines.append("- Seed: CHƯA CÓ — chờ đầu vào hiệu chỉnh")
    else:
        lines.append(
            f"- Seed: {rec.plain(str(snapshot.seed))} "
            "(bộ chuẩn bán tổng hợp + đo F1 6.5 + hiệu chỉnh 9.6)"
        )
    lines.append(
        f"- Model: {snapshot.model_id} (revision `{snapshot.model_revision}`) "
        "— mặc định Settings, mẫu dùng ở 6.5/9.1"
    )
    fields = ", ".join(snapshot.settings_fields)
    lines.append(
        f"- Trường Settings ({rec.plain(str(len(snapshot.settings_fields)))}): {fields}"
    )
    lines.append("- Đầu vào đã dùng:")
    for name, digest in snapshot.inputs:
        lines.append(f"  - `{name}` (sha256 `{digest}`)")
    if missing:
        lines.append("- Đầu vào còn thiếu:")
        for entry in missing:
            lines.append(f"  - {entry.id} {entry.label} — chờ {entry.waiting_task}")
    else:
        lines.append("- Đầu vào còn thiếu: không còn mục thiếu.")
    lines.append("")
    _render_data(lines, rec, parsed, missing)
    lines.append("")
    lines.append("## 10. Caveat + câu hỏi mở")
    lines.append("")
    _render_caveat(lines, rec, snapshot, parsed)
    return "\n".join(lines) + "\n", rec


def _render_data(
    lines: list[str],
    rec: Recorder,
    parsed: dict[str, object],
    missing: list[MappingEntry],
) -> None:
    """Các mục 2-9 của báo cáo (Phụ lục A)."""
    missing_ids = {entry.id for entry in missing}
    lines.append("## 2. Dữ liệu")
    lines.append("")
    if "B1.1" in missing_ids:
        lines.append(_missing_line("Hồ sơ 5 đô thị BPIC 2015", "lệnh hồ sơ"))
    else:
        profiles = parsed["profile"]
        assert isinstance(profiles, list)
        lines.append("| Đô thị | case | sự kiện | loại hoạt động |")
        lines.append("| --- | --- | --- | --- |")
        for row in profiles:
            assert isinstance(row, ProfileRow)
            lines.append(
                f"| {rec.plain(str(row.municipality))} "
                f"| {rec.integer(row.cases)} | {rec.integer(row.events)} "
                f"| {rec.integer(row.activity_types)} |"
            )
        lines.append("")
        lines.append("Nguồn: `python -m praxon_core.datasets.profile`")
    lines.append("")
    if "B1.2" in missing_ids:
        lines.append(_missing_line("Phép chia 60/20/20", "lệnh chia"))
    else:
        split_data = parsed["split"]
        assert isinstance(split_data, tuple)
        split_rows = split_data[0]
        assert isinstance(split_rows, list)
        lines.append("| Đô thị | tổng case | học | hiệu chỉnh | đo |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in split_rows:
            assert isinstance(row, SplitRow)
            lines.append(
                f"| {rec.plain(str(row.municipality))} "
                f"| {rec.integer(row.total)} | {rec.integer(row.train)} "
                f"| {rec.integer(row.calibration)} | {rec.integer(row.test)} |"
            )
        lines.append("")
        lines.append("Nguồn: `python -m praxon_core.datasets.split`")
    lines.append("")
    if "B1.6" in missing_ids:
        lines.append(_missing_line("BPIC 2019", "lệnh bpic2019"))
    else:
        bpic = parsed["bpic2019"]
        assert isinstance(bpic, Bpic2019Data)
        lines.append(
            f"- Tổng case: {rec.integer(bpic.total)} "
            f"(trong năm 2018: {rec.integer(bpic.in_year)}; "
            f"ngoài năm: {rec.integer(bpic.out_of_year)}; "
            f"thiếu Item Category: {rec.integer(bpic.missing_item_category)}; "
            f"không có thời điểm bắt đầu: {rec.integer(bpic.no_start)})"
        )
        lines.append("")
        lines.append("| Loại matching | case (2018) | luật | quyết định |")
        lines.append("| --- | --- | --- | --- |")
        for value, cases, rule_id, verdict in bpic.matching:
            rule_text = f"luật {rule_id}" if rule_id.isdigit() else rule_id
            lines.append(f"| {value} | {rec.integer(cases)} | {rule_text} | {verdict} |")
        lines.append(
            f"- Hiệu chỉnh min_matching_cases={rec.integer(bpic.threshold)}: "
            f"cả {rec.plain(str(len(bpic.matching)))} loại đều đủ ngưỡng "
            f"(nhỏ nhất '{bpic.min_type}': {rec.integer(bpic.min_cases)} case, "
            f"gấp {rec.decimal(bpic.ratio, 1)} lần) — ngưỡng được giữ nguyên."
        )
        lines.append("")
        lines.append("Nguồn: `python -m praxon_core.learning.bpic2019`")
    lines.append("")
    if "B1.5" in missing_ids:
        lines.append(
            "F1 bộ sinh (độ khó, 5.3): " + _missing_line("", "lệnh sinh chưa xác nhận")
        )
    lines.append("")
    lines.append("## 3. Trích luật từ văn bản (F1, 6.5)")
    lines.append("")
    if "B1.3" in missing_ids:
        lines.append(
            _missing_line(
                "",
                "chạy lại lệnh đo `python -m tools.measure_f1_text_to_ltl` "
                "(cần llama-server chạy; lần đo 6.5 đã xong nhưng đầu ra "
                "lệnh chưa lưu thành file, không chép số từ báo cáo review)",
            )
        )
    else:
        f1 = parsed["f1"]
        assert isinstance(f1, F1Data)
        lines.append(
            f"Mô hình: {f1.model_id} (revision `{f1.model_revision}`); "
            f"số câu đo: {rec.integer(f1.measured)}; "
            f"gọi mô hình hỏng: {rec.integer(f1.failures)}"
        )
        lines.append("")
        lines.append("| Mẫu | precision | recall | F1 | F1 GPT-4 | TP | FP | FN |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for template, precision, recall, f1_value, gpt4, tp, fp, fn in f1.per_template:
            lines.append(
                f"| {template} | {rec.decimal(precision)} | {rec.decimal(recall)} "
                f"| {rec.decimal(f1_value)} | {rec.decimal(gpt4)} "
                f"| {rec.integer(tp)} | {rec.integer(fp)} | {rec.integer(fn)} |"
            )
        lines.append(
            f"| Overall | {rec.decimal(f1.overall[0])} "
            f"| {rec.decimal(f1.overall[1])} | {rec.decimal(f1.overall[2])} "
            f"| {rec.decimal(f1.overall[3])} | {rec.integer(f1.overall[4])} "
            f"| {rec.integer(f1.overall[5])} | {rec.integer(f1.overall[6])} |"
        )
        lines.append("")
        lines.append(
            "Nguồn: `python -m tools.measure_f1_text_to_ltl` (temperature=0, thinking tắt)"
        )
    lines.append("")
    lines.append("## 4. Luật Wabo (9.1)")
    lines.append("")
    lines.append(_missing_line("", "9.1 đo thật (đang chạy trong sandbox Docker)"))
    lines.append("")
    lines.append("## 5. Hiệu chỉnh cổng Beta (9.6)")
    lines.append("")
    if "B1.10" in missing_ids:
        lines.append(_missing_line("", "lệnh hiệu chỉnh"))
    else:
        rows = parsed["calibration"]
        assert isinstance(rows, tuple)
        calib_rows, selected, _seed = rows
        assert isinstance(calib_rows, list)
        lines.append(
            "| Độ mạnh | trung vị trace để đẩy | biên bất biến | lên sai | gỡ sai | lên |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in calib_rows:
            assert isinstance(row, CalibrationRow)
            median = rec.decimal(row.median_traces, 1) if row.median_traces is not None else "-"
            lines.append(
                f"| {rec.decimal(row.strength, 1)} | {median} "
                f"| {rec.decimal(row.invariant_margin)} "
                f"| {rec.integer(row.false_promotes)} "
                f"| {rec.integer(row.false_retires)} "
                f"| {rec.integer(row.promoted)} |"
            )
        lines.append(f"Chọn: {rec.decimal(selected, 1)}.")
        lines.append("")
        prior = _read_prior_strength()
        lines.append(
            f"- Độ mạnh đã áp: {rec.decimal(prior, 1)} "
            "(`prior_strength_default = 2` trong "
            "`learning/default_rule_table.toml`, merge `ed677db`)."
        )
        if "B1.6" not in missing_ids:
            bpic = parsed["bpic2019"]
            assert isinstance(bpic, Bpic2019Data)
            lines.append(
                f"- `min_matching_cases = {rec.integer(bpic.threshold)}` "
                f"(giữ nguyên theo 9.5 — nhỏ nhất {rec.integer(bpic.min_cases)} "
                f"case, gấp {rec.decimal(bpic.ratio, 1)} lần ngưỡng)."
            )
        lines.append("")
        lines.append("Nguồn: `python -m praxon_core.learning.calibration`")
    lines.append("")
    lines.append("## 6. Bốn chỉ số (12.2 qua lệnh 13.1)")
    lines.append("")
    lines.append(_missing_line("", "13.1 (lệnh) + 12.2 (lần chạy đo)"))
    lines.append("")
    lines.append("## 7. Đường cong khởi động lạnh (8.4)")
    lines.append("")
    if "B1.12" in missing_ids:
        lines.append(_missing_line("", "lệnh cold_start"))
    else:
        points = parsed["cold_start"]
        assert isinstance(points, list)
        lines.append("| trace | luật | precision | recall | vi phạm | neg.transfer | chế độ |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for point in points:
            assert isinstance(point, ColdStartPoint)
            lines.append(
                f"| {rec.integer(point.n_traces)} | {rec.integer(point.n_rules)} "
                f"| {rec.decimal(point.precision, 3)} "
                f"| {rec.decimal(point.recall, 3)} "
                f"| {rec.decimal(point.violation_rate, 3)} "
                f"| {rec.decimal(point.negative_transfer, 3)} | {point.mode} |"
            )
        lines.append("")
        lines.append("Nguồn: `python -m praxon_core.eval.cold_start`")
    lines.append("")
    lines.append("## 8. Tái lập (12.3)")
    lines.append("")
    lines.append(_missing_line("", "12.3"))
    lines.append("")
    lines.append("## 9. Phép thử đứt phiên (11.3)")
    lines.append("")
    lines.append(_missing_line("", "11.3 (lần chạy Kaggle chờ 11.1 + 11.2)"))


def _read_prior_strength() -> float:
    """Độ mạnh mặc định từ `default_rule_table.toml` (B1.11)."""
    root = Path(__file__).resolve().parent.parent
    path = (
        root
        / "packages"
        / "core"
        / "src"
        / "praxon_core"
        / "learning"
        / ("default_rule_table.toml")
    )
    with path.open("rb") as handle:
        table = tomllib.load(handle)
    policy = table.get("policy")
    value = policy.get("prior_strength_default") if isinstance(policy, dict) else None
    if not isinstance(value, (int, float)):
        raise ValueError("thiếu prior_strength_default trong default_rule_table.toml")
    return float(value)


def _render_caveat(
    lines: list[str],
    rec: Recorder,
    snapshot: Snapshot,
    parsed: dict[str, object],
) -> None:
    """Mục 10 — caveat + câu hỏi mở (bắt buộc, không được rỗng, R5)."""
    lines.append(
        '- Luật Wabo (9.1) khi đo xong sẽ mang `status="active"` (không phải '
        "`trial`) và bằng chứng đo trên toàn bộ trace gộp, kể cả phần đo — "
        "hai quyết định đã ghi trong docstring của `learning/wabo_rules.py` "
        "để review; nếu Thuận muốn `trial` thì đổi một dòng."
    )
    if "f1" in parsed:
        f1 = parsed["f1"]
        assert isinstance(f1, F1Data)
        succession = next(row for row in f1.per_template if row[0] == "succession")
        cases = succession[5] + succession[7]
        lines.append(
            f"- F1 succession chỉ dựa trên {rec.integer(cases)} ca nên nhiễu "
            "lớn, không kết luận từ mẫu này."
        )
    else:
        lines.append(
            "- F1 succession: chưa có đầu vào đo — khi có đầu ra F1 sẽ ghi rõ "
            "số ca của mẫu succession (mẫu nhỏ thì không kết luận)."
        )
    lines.append(
        "- Đáp án BPIC 2015 lấy từ phần đo nên có nhiễu riêng — số tuyệt đối "
        "hơi bi quan; báo cáo này so các điều kiện bằng chênh lệch, không "
        "so số tuyệt đối."
    )
    lines.append(
        "- Plan file từng stale 26 task (review đợt 2, §3.3) — số task trong "
        "báo cáo này đếm từ commit merge, không lấy từ cột Trạng thái của "
        "plan file."
    )
    lines.append(
        "- Hai mục còn mở từ review đợt 2 đã xong: rubric dòng 10 "
        "(merge `150ec6d`) và target_scope (merge `6c12991`); rubric §2.2 "
        "(merge `b76796b`), spec prose 4→2 (merge `1ab9269`), target_scope "
        "option B (merge `ac1f210`)."
    )
    if snapshot.plan_task_rows is None:
        lines.append(
            "- Plan file ghi một con số task đã lỗi thời — không đếm được "
            "dòng task lúc sinh báo cáo."
        )
    else:
        lines.append(
            f'- Plan file ghi "65 task" nhưng đếm được '
            f'{rec.integer(snapshot.plan_task_rows)} dòng task — số "65" '
            "là số lỗi thời."
        )


_PARSERS = {
    "profile-bpic2015.txt": ("profile", parse_profile),
    "split-bpic2015.txt": ("split", parse_split),
    "bpic2019.txt": ("bpic2019", parse_bpic2019),
    "calibration-beta.txt": ("calibration", parse_calibration),
    "cold-start.txt": ("cold_start", parse_cold_start),
    "f1-text-to-ltl.txt": ("f1", parse_f1),
}


def _load_inputs(inputs_dir: Path) -> dict[str, str]:
    """Đầu ra đã lưu của các lệnh nguồn (file nào chưa có là mục CHƯA CÓ)."""
    inputs: dict[str, str] = {}
    if not inputs_dir.is_dir():
        return inputs
    for path in sorted(inputs_dir.glob("*.txt")):
        inputs[path.name] = path.read_text(encoding="utf-8")
    return inputs


def _git_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"không đọc được commit của {repo_root}")
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    """Lệnh sinh báo cáo: `python -m tools.generate_phase1_report`."""
    parser = argparse.ArgumentParser(
        prog="tools.generate_phase1_report",
        description=(
            "Sinh báo cáo kết quả giai đoạn 1 từ đầu ra đã lưu trong docs/reports/inputs/."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="gốc repo (mặc định: suy ra từ vị trí script)",
    )
    parser.add_argument(
        "--inputs-dir",
        type=Path,
        default=None,
        help="thư mục đầu vào (mặc định: <repo>/docs/reports/inputs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="file báo cáo (mặc định: <repo>/docs/reports/ket-qua-giai-doan-1.md)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="ngày sinh YYYY-MM-DD (mặc định: hôm nay, UTC+7)",
    )
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root
    inputs_dir: Path = args.inputs_dir or repo_root / "docs" / "reports" / "inputs"
    output: Path = args.output or repo_root / "docs" / "reports" / "ket-qua-giai-doan-1.md"
    if args.date is None:
        date = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    else:
        try:
            date = datetime.strptime(args.date, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print(f"ngày không hợp lệ: {args.date} (cần YYYY-MM-DD)", file=sys.stderr)
            return 1

    inputs = _load_inputs(inputs_dir)
    missing = [
        entry for entry in MAPPING if entry.input_file and entry.input_file not in inputs
    ]
    # B1.5 chưa có lệnh sinh — mục này luôn CHƯA CÓ cho tới khi tìm được lệnh.
    missing.append(next(entry for entry in MAPPING if entry.id == "B1.5"))
    # B2.2/B2.3/B2.4/B2.5 chưa có đầu vào — luôn CHƯA CÓ cho tới khi có
    # lệnh/lần chạy/lệnh khóa tương ứng.
    missing.extend(entry for entry in MAPPING if entry.id in {"B2.2", "B2.3", "B2.4", "B2.5"})
    missing.sort(key=lambda entry: entry.id)

    parsed: dict[str, object] = {}
    try:
        for filename, (key, parse) in _PARSERS.items():
            if filename in inputs:
                parsed[key] = parse(inputs[filename])
    except ValueError as error:
        print(f"đầu vào {filename} sai định dạng: {error}", file=sys.stderr)
        return 1

    split_data: tuple[list[SplitRow], str] | None = parsed.get("split")  # type: ignore[assignment]
    calib_data: tuple[list[CalibrationRow], float, int] | None = parsed.get(  # type: ignore[assignment]
        "calibration"
    )
    try:
        commit = _git_commit(repo_root)
        snapshot = build_snapshot(
            repo_root=repo_root,
            commit=commit,
            date=date,
            inputs=inputs,
            data_hash=split_data[1] if split_data is not None else None,
            seed=calib_data[2] if calib_data is not None else None,
        )
    except (RuntimeError, ValueError) as error:
        print(f"không dựng được ảnh chụp đầu vào: {error}", file=sys.stderr)
        return 1

    report, recorder = render_report(snapshot, parsed, missing)
    unsourced = find_unsourced_numbers(report, recorder.values)
    if unsourced:
        print(
            "số không có nguồn trong bảng ánh xạ: " + ", ".join(unsourced),
            file=sys.stderr,
        )
        return 1
    verdict = find_verdict_words(report)
    if verdict:
        print(
            "báo cáo chứa từ verdict cổng 1: " + ", ".join(verdict),
            file=sys.stderr,
        )
        return 1
    caveat = report.split("## 10. Caveat + câu hỏi mở", 1)[1].strip()
    if not caveat:
        print("mục caveat rỗng — báo cáo không được sinh", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"đã sinh {output}")
    if missing:
        print("mục CHƯA CÓ:")
        for entry in missing:
            print(f"  - {entry.id} {entry.label} — chờ {entry.waiting_task}")
    else:
        print("không còn mục thiếu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
