# Đầu vào của báo cáo kết quả giai đoạn 1

Mỗi file ở đây là đầu ra đã lưu (stdout nguyên văn) của một lệnh nguồn,
dùng để sinh `../ket-qua-giai-doan-1.md` bằng
`python -m tools.generate_phase1_report`. File nào chưa có thì mục tương
ứng trong báo cáo là `CHƯA CÓ` — không bịa số.

Kiểm lại một file: chạy lại đúng lệnh dưới đây rồi `diff` với file đã lưu.
Đầu ra phải giống hệt (trừ bpic2019: `tệp sha256` là băm của file XES nên
không đổi khi cache không đổi).

## Đã có

| File | Lệnh sinh (chạy trong gốc repo, venv của worktree) |
| --- | --- |
| `profile-bpic2015.txt` | `python -m praxon_core.datasets.profile` |
| `split-bpic2015.txt` | `python -m praxon_core.datasets.split` |
| `bpic2019.txt` | `python -m praxon_core.learning.bpic2019` |
| `calibration-beta.txt` | `python -m praxon_core.learning.calibration` |
| `cold-start.txt` | `python -m praxon_core.eval.cold_start` |

- `profile-bpic2015.txt` và `split-bpic2015.txt` đọc 5 log BPIC 2015 từ
  cache ngoài kho (`~/.cache/praxon/bpic2015/`).
- `bpic2019.txt` đọc log BPIC 2019 từ cache
  (`~/.cache/praxon/bpic2019/`, XES 728.558.522 byte).
- `calibration-beta.txt` chạy đúng bộ chuẩn của 9.6 (hạt 42, 300 trace),
  không gọi mô hình.
- `cold-start.txt` chạy trên bộ tổng hợp (hạt 42), không gọi mô hình.

## Chưa có

| File | Lệnh sinh | Chờ |
| --- | --- | --- |
| `f1-text-to-ltl.txt` | `python -m tools.measure_f1_text_to_ltl` | Chạy lại đo 6.5 khi có llama-server chạy (lần đo 6.5 đã xong nhưng đầu ra lệnh chưa lưu thành file) |
| `wabo-rules.txt` | `python -m praxon_core.learning.wabo_rules --config <toml>` | 9.1 đo thật (đang chạy trong sandbox Docker) |

Các mục còn lại (bốn chỉ số 12.2, tái lập 12.3, đứt phiên 11.3, khóa
12.1) chưa có lệnh/file đầu vào — xem bảng ánh xạ B2.2–B2.5 trong đề
xuất 13.2.
