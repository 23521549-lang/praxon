"""Bộ dữ liệu cho Praxon (plan con 3).

Bất biến: dữ liệu bên thứ ba (log BPIC, bộ câu hỏi) tải lúc chạy,
không đóng gói vào kho. Bước CI chặn tệp .xes/.csv/.gz trong kho
ngoài thư mục fixture của test.
"""

from praxon_core.datasets.bpic2015 import (
    BPIC2015_DATASETS,
    BPIC2015Dataset,
    download_bpic2015,
)

__all__ = [
    "BPIC2015_DATASETS",
    "BPIC2015Dataset",
    "download_bpic2015",
]
