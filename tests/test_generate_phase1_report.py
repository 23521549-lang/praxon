"""Test generator báo cáo kết quả giai đoạn 1 (task 13.2)."""

from pathlib import Path

import pytest
from tools.generate_phase1_report import (
    MAPPING,
    MappingEntry,
    Snapshot,
    build_snapshot,
    find_unsourced_numbers,
    find_verdict_words,
    main,
    parse_bpic2019,
    parse_calibration,
    parse_cold_start,
    parse_f1,
    parse_profile,
    parse_split,
    render_report,
)

from praxon_core.learning.calibration import (
    CalibrationResult,
    StrengthOutcome,
    format_calibration_table,
)
from praxon_core.learning.calibration import main as calibration_main

REPO_ROOT = Path(__file__).resolve().parent.parent

PROFILE_FIXTURE = """\
Đô thị 1: 100 case, 1000 sự kiện, 10 loại hoạt động
  case bắt đầu: 2010-10-05 → 2015-08-01
Đô thị 2: 200 case, 2000 sự kiện, 20 loại hoạt động
  case bắt đầu: 2010-10-06 → 2015-08-02
Đô thị 3: 300 case, 3000 sự kiện, 30 loại hoạt động
  case bắt đầu: 2010-10-07 → 2015-08-03
Đô thị 4: 400 case, 4000 sự kiện, 40 loại hoạt động
  case bắt đầu: 2010-10-08 → 2015-08-04
Đô thị 5: 500 case, 5000 sự kiện, 50 loại hoạt động
  case bắt đầu: 2010-10-09 → 2015-08-05
"""

SPLIT_FIXTURE = "\n".join(
    [
        "Đô thị 1: 100 case → học 60, hiệu chỉnh 20, đo 20",
        "  ranh giới: học tới 2012-12-06, đo từ 2014-02-18",
        "  tệp sha256: 7591f70d4a4d536ead76a56c2fa493fbe22bf2ec7e06c8ddd29da79bd666e516",
        "  data_hash: a38645fb3f1797579f61f9ea327a1f0bac570921621de5bb0310f4a666792620",
        "Đô thị 2: 200 case → học 120, hiệu chỉnh 40, đo 40",
        "  ranh giới: học tới 2012-12-24, đo từ 2014-02-28",
        "  tệp sha256: fd7704bd3c473afe04cf003ea3220a24d6dcd521fa6c639fb8475dd0826201a6",
        "  data_hash: 700c9125bc80af4a221b3f75bcb2b35b445ee3099d580c6dc9baf178cf2f4405",
        "Đô thị 3: 300 case → học 180, hiệu chỉnh 60, đo 60",
        "  ranh giới: học tới 2013-03-06, đo từ 2014-02-28",
        "  tệp sha256: 920985874a9ccba1f86aba138e796a4ce9a37f06f90d311fcb4c27dfca7dd6b7",
        "  data_hash: fa192b02bfd9cf62dfe3d4f86225fa1cedc4bc145c526e27cd25956d0130df03",
        "Đô thị 4: 400 case → học 240, hiệu chỉnh 80, đo 80",
        "  ranh giới: học tới 2013-04-22, đo từ 2014-04-11",
        "  tệp sha256: f508c083b972821de17d47a335f0905d108f1b9654a4db0aed9dc8c4ef8f0494",
        "  data_hash: f7143b4858287009267acf279546df32eb01081843abae5efc6ef4f573b02d79",
        "Đô thị 5: 500 case → học 300, hiệu chỉnh 100, đo 100",
        "  ranh giới: học tới 2013-02-19, đo từ 2014-03-17",
        "  tệp sha256: 48ca302b19b5aa4964cd85b67a306e484655159ab2b55cf3c487ee7eb66d51ed",
        "  data_hash: 54f83c88e9ab355ffae1d68521af72725b726717df6af6e628ecc8933d8e93de",
        "data_hash chung (cả năm đô thị): "
        "0edb706dcf2afb637a0c7b57ee9d284fc8958ee50b9594a05e3365ec5a805b92",
    ]
)

_BPIC2019_REASON = "Luật 2 khớp: Ràng buộc mới, từ trace hoặc từ tài liệu"

BPIC2019_FIXTURE = "\n".join(
    [
        "BPIC 2019 (10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1): BPI_Challenge_2019.xes",
        "tổng case: 251734 (trong năm 2018: 251268; ngoài năm: 466; "
        "thiếu Item Category: 0; không có thời điểm bắt đầu: 0)",
        "loại matching (Item Category) | case (2018) | luật | quyết định",
        f"2-way match | 891 | 2 | auto_approve ({_BPIC2019_REASON})",
        f"3-way match, invoice after GR | 15131 | 2 | auto_approve ({_BPIC2019_REASON})",
        f"3-way match, invoice before GR | 220752 | 2 | auto_approve ({_BPIC2019_REASON})",
        f"Consignment | 14494 | 2 | auto_approve ({_BPIC2019_REASON})",
        "hiệu chỉnh min_matching_cases=30: cả 4 loại đều đủ ngưỡng "
        "(nhỏ nhất '2-way match': 891 case, gấp 29.7 lần) — ngưỡng được giữ nguyên.",
    ]
)

CALIBRATION_FIXTURE = """\
Hiệu chỉnh cổng Beta (task 9.6)
Bộ chuẩn: hạt 42, 300 trace (180 học / 60 hiệu chỉnh / 60 đo)
độ mạnh | trung vị trace | biên bất biến | lên sai | gỡ sai | lên
2.0 | 13.0 | 0.2930 | 0 | 0 | 20
4.0 | 16.0 | 0.1181 | 0 | 0 | 20
6.0 | 20.0 | 0.0324 | 0 | 0 | 20
Chọn: 2.0
"""

COLD_START_FIXTURE = """\
Đường cong khởi động lạnh — tenant acme
trace | luật | precision | recall | vi phạm | neg.transfer | chế độ
    0 |    0 | 0.000 | 0.000 | 0.000 | 0.000 | trial (giám sát)
    5 |   20 | 1.000 | 0.357 | 0.050 | 0.000 | active
   10 |   20 | 1.000 | 0.357 | 0.050 | 0.000 | active
   20 |   20 | 1.000 | 0.357 | 0.050 | 0.000 | active
   40 |   20 | 1.000 | 0.357 | 0.050 | 0.000 | active
"""


def _f1_row(
    template: str,
    precision: float,
    recall: float,
    f1: float,
    gpt4: float,
    tp: int,
    fp: int,
    fn: int,
) -> str:
    return (
        f"{template:<12}{precision:>8.4f}{recall:>8.4f}"
        f"{f1:>8.4f}{gpt4:>10.4f}{tp:>5}{fp:>5}{fn:>5}"
    )


F1_FIXTURE = "\n".join(
    [
        "Do F1 trich mau Declare tren bo 104 cau (task 6.5)",
        "Mo hinh: Qwen/Qwen3-8B-GGUF (revision 7c41481f57cb95916b40956ab2f0b139b296d974)",
        "So cau do: 104; goi mo hinh hong: 0",
        "",
        "Mau         P       R      F1  F1 GPT-4   TP   FP   FN",
        _f1_row("precedence", 0.8, 0.7, 0.7467, 0.6835, 20, 5, 8),
        _f1_row("response", 0.9, 0.8, 0.8471, 0.7971, 40, 4, 10),
        _f1_row("succession", 1.0, 0.3333, 0.5, 1.0, 1, 0, 2),
        _f1_row("init", 0.95, 0.9, 0.9243, 0.9, 19, 1, 2),
        _f1_row("end", 0.6, 0.5, 0.5455, 0.2857, 6, 4, 6),
        _f1_row("Overall", 0.85, 0.75, 0.7969, 0.7946, 86, 14, 28),
        "",
        "F1 tong (micro) cua bai do nay; moc GPT-4 0,7946 la Overall",
        "trong bang Summary cua bai bao (xem ghi chu trong eval/text_to_ltl.py).",
    ]
)

FULL_INPUTS = {
    "profile-bpic2015.txt": PROFILE_FIXTURE,
    "split-bpic2015.txt": SPLIT_FIXTURE,
    "bpic2019.txt": BPIC2019_FIXTURE,
    "calibration-beta.txt": CALIBRATION_FIXTURE,
    "cold-start.txt": COLD_START_FIXTURE,
    "f1-text-to-ltl.txt": F1_FIXTURE,
}


def _parse_all(inputs: dict[str, str]) -> dict[str, object]:
    return {
        "profile": parse_profile(inputs["profile-bpic2015.txt"]),
        "split": parse_split(inputs["split-bpic2015.txt"]),
        "bpic2019": parse_bpic2019(inputs["bpic2019.txt"]),
        "calibration": parse_calibration(inputs["calibration-beta.txt"]),
        "cold_start": parse_cold_start(inputs["cold-start.txt"]),
        "f1": parse_f1(inputs["f1-text-to-ltl.txt"]),
    }


def _missing_for(inputs: dict[str, str]) -> list[MappingEntry]:
    missing = [
        entry for entry in MAPPING if entry.input_file and entry.input_file not in inputs
    ]
    missing.append(next(entry for entry in MAPPING if entry.id == "B1.5"))
    missing.extend(entry for entry in MAPPING if entry.id in {"B2.2", "B2.3", "B2.4", "B2.5"})
    return sorted(missing, key=lambda entry: entry.id)


def _snapshot(inputs: dict[str, str], parsed: dict[str, object]) -> Snapshot:
    split_data = parsed["split"]
    assert isinstance(split_data, tuple)
    data_hash = split_data[1]
    calib_data = parsed["calibration"]
    assert isinstance(calib_data, tuple)
    seed = calib_data[2]
    return build_snapshot(
        repo_root=REPO_ROOT,
        commit="0" * 40,
        date="2026-11-07",
        inputs=inputs,
        data_hash=data_hash,
        seed=seed,
    )


def test_parse_profile():
    rows = parse_profile(PROFILE_FIXTURE)
    assert [row.municipality for row in rows] == [1, 2, 3, 4, 5]
    assert rows[0].cases == 100
    assert rows[0].events == 1000
    assert rows[0].activity_types == 10
    assert rows[4].cases == 500


def test_parse_profile_thieu_do_thi():
    with pytest.raises(ValueError, match="đúng 5 đô thị"):
        parse_profile(PROFILE_FIXTURE.split("Đô thị 5")[0])


def test_parse_split():
    rows, data_hash = parse_split(SPLIT_FIXTURE)
    assert rows[0].total == 100
    assert rows[0].train == 60
    assert rows[0].calibration == 20
    assert rows[0].test == 20
    assert rows[4].total == 500
    assert data_hash == "0edb706dcf2afb637a0c7b57ee9d284fc8958ee50b9594a05e3365ec5a805b92"


def test_parse_bpic2019():
    data = parse_bpic2019(BPIC2019_FIXTURE)
    assert data.total == 251734
    assert data.in_year == 251268
    assert data.out_of_year == 466
    assert data.missing_item_category == 0
    assert data.no_start == 0
    assert data.matching[0] == ("2-way match", 891, "2", "auto_approve")
    assert data.matching[2][1] == 220752
    assert data.threshold == 30
    assert data.min_type == "2-way match"
    assert data.min_cases == 891
    assert data.ratio == 29.7


def test_parse_calibration():
    rows, selected, seed = parse_calibration(CALIBRATION_FIXTURE)
    assert seed == 42
    assert selected == 2.0
    assert rows[0].strength == 2.0
    assert rows[0].median_traces == 13.0
    assert rows[0].invariant_margin == 0.2930
    assert rows[1].strength == 4.0
    assert rows[1].median_traces == 16.0
    assert rows[1].invariant_margin == 0.1181
    assert rows[2].strength == 6.0
    assert rows[2].median_traces == 20.0
    assert rows[2].invariant_margin == 0.0324


def test_parse_cold_start():
    points = parse_cold_start(COLD_START_FIXTURE)
    assert [point.n_traces for point in points] == [0, 5, 10, 20, 40]
    assert points[0].n_rules == 0
    assert points[0].mode == "trial (giám sát)"
    assert points[1].n_rules == 20
    assert points[1].precision == 1.0
    assert points[1].recall == 0.357


def test_parse_f1():
    data = parse_f1(F1_FIXTURE)
    assert data.model_id == "Qwen/Qwen3-8B-GGUF"
    assert data.model_revision == "7c41481f57cb95916b40956ab2f0b139b296d974"
    assert data.measured == 104
    assert data.failures == 0
    assert data.per_template[0][0] == "precedence"
    assert data.per_template[0][3] == 0.7467
    succession = next(row for row in data.per_template if row[0] == "succession")
    assert succession[5] == 1
    assert succession[7] == 2
    assert data.overall[2] == 0.7969


def test_parse_f1_thieu_mau():
    with pytest.raises(ValueError, match="thiếu mẫu"):
        parse_f1(F1_FIXTURE.replace("succession", "success"))


def test_bao_cao_day_du_khong_co_so_chua_nguon():
    parsed = _parse_all(FULL_INPUTS)
    snapshot = _snapshot(FULL_INPUTS, parsed)
    report, recorder = render_report(snapshot, parsed, _missing_for(FULL_INPUTS))
    assert find_unsourced_numbers(report, recorder.values) == []
    assert find_verdict_words(report) == []
    assert "CHƯA CÓ" in report
    assert "| 1 | 100 | 1.000 | 10 |" in report
    assert "| 2-way match | 891 | luật 2 | auto_approve |" in report
    assert "| 2,0 | 13,0 | 0,2930 | 0 | 0 | 20 |" in report
    assert "0,7969" in report
    assert "F1 succession chỉ dựa trên 3 ca" in report
    assert report.split("## 10. Caveat + câu hỏi mở", 1)[1].strip() != ""


def test_chay_lai_ra_cung_file():
    parsed = _parse_all(FULL_INPUTS)
    snapshot = _snapshot(FULL_INPUTS, parsed)
    missing = _missing_for(FULL_INPUTS)
    first, _recorder = render_report(snapshot, parsed, missing)
    second, _recorder = render_report(snapshot, parsed, missing)
    assert first == second


def test_thieu_dau_vao_thi_muc_do_chua_co(tmp_path, capsys):
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir()
    (inputs_dir / "profile-bpic2015.txt").write_text(PROFILE_FIXTURE, encoding="utf-8")
    (inputs_dir / "split-bpic2015.txt").write_text(SPLIT_FIXTURE, encoding="utf-8")
    output = tmp_path / "ket-qua-giai-doan-1.md"
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--inputs-dir",
            str(inputs_dir),
            "--output",
            str(output),
            "--date",
            "2026-11-07",
        ]
    )
    assert exit_code == 0
    report = output.read_text(encoding="utf-8")
    assert "## 5. Hiệu chỉnh cổng Beta (9.6)" in report
    assert "CHƯA CÓ — chờ lệnh hiệu chỉnh" in report
    assert "CHƯA CÓ — chờ lệnh cold_start" in report
    assert "CHƯA CÓ — chờ 9.1 đo thật" in report
    assert "| 1 | 100 | 1.000 | 10 |" in report
    captured = capsys.readouterr()
    assert "mục CHƯA CÓ:" in captured.out
    assert "B1.10" in captured.out


def test_so_khong_nguon_bi_bat():
    assert find_unsourced_numbers("một số 9.999 không có nguồn", set()) == ["9.999"]
    assert find_unsourced_numbers("tỉ lệ 60/20/20 và 104 câu", set()) == []
    assert find_unsourced_numbers("commit abcdef1234567 ngày 2026-11-07", set()) == []
    assert find_unsourced_numbers("băm sha256 của file đầu vào", set()) == []


def test_tu_verdict_bi_bat():
    assert find_verdict_words("kết quả ĐẠT") == ["ĐẠT"]
    assert find_verdict_words("báo cáo kết quả giai đoạn 1") == []


def test_format_calibration_table():
    result = CalibrationResult(
        strengths=(2.0, 4.0, 6.0),
        outcomes=(
            StrengthOutcome(
                strength=2.0,
                false_promotes=0,
                false_retires=0,
                promoted=20,
                retired=0,
                undecided=0,
                median_traces_to_promote=13.0,
                invariant_margin=0.2930,
            ),
            StrengthOutcome(
                strength=4.0,
                false_promotes=0,
                false_retires=0,
                promoted=20,
                retired=0,
                undecided=0,
                median_traces_to_promote=None,
                invariant_margin=0.1181,
            ),
            StrengthOutcome(
                strength=6.0,
                false_promotes=0,
                false_retires=0,
                promoted=20,
                retired=0,
                undecided=0,
                median_traces_to_promote=20.0,
                invariant_margin=0.0324,
            ),
        ),
        selected_strength=2.0,
    )
    table = format_calibration_table(result)
    assert "2.0 | 13.0 | 0.2930 | 0 | 0 | 20" in table
    assert "4.0 | - | 0.1181 | 0 | 0 | 20" in table
    assert "6.0 | 20.0 | 0.0324 | 0 | 0 | 20" in table
    assert "Chọn: 2.0" in table


def test_cli_hieu_chinh_in_dung_ba_hang(capsys):
    exit_code = calibration_main([])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "2.0 | 13.0 | 0.2930 | 0 | 0 | 20" in out
    assert "4.0 | 16.0 | 0.1181 | 0 | 0 | 20" in out
    assert "6.0 | 20.0 | 0.0324 | 0 | 0 | 20" in out
    assert "Chọn: 2.0" in out
