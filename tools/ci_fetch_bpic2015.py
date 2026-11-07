"""Lấy tệp BPIC 2015 cho CI: cache, bộ tải chính thức, rồi dự phòng Drive.

Thứ tự lấy dữ liệu (đề xuất sửa CI, phương án A):

1. Cache: tệp đã có trong cache và md5 khớp giá trị 4TU công bố thì dùng
   ngay, không tải. Md5 sai thì xóa tệp hỏng rồi đi tiếp.
2. Chính thức: gọi ``download_bpic2015`` đã có, tối đa 3 lần, nghỉ 30 giây
   giữa các lần. Bộ tải tự kiểm md5 và không để lại tệp dở dang.
3. Dự phòng: chỉ khi có URL qua tham số ``--fallback-url`` hoặc biến môi
   trường ``PRAXON_BPIC2015_FALLBACK_URL``. Tải zip bằng urllib, giải nén
   lấy đúng tệp ``.xes`` của dataset vào cache, kiểm md5 trước khi dùng.
   Md5 không khớp thì xóa tệp đã giải nén.

Quy tắc cứng: không bao giờ thoát 0 khi chưa có tệp md5 khớp trong cache.
Md5 lấy từ metadata figshare (không hard-code md5 mới vào code). Tool chỉ
dùng stdlib (urllib, hashlib, zipfile) cộng bộ tải đã có; không đọc
credential nào.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from praxon_core.datasets.bpic2015 import (
    BPIC2015_DATASETS,
    CHUNK_BYTES,
    DEFAULT_CACHE_DIR,
    REQUEST_TIMEOUT_SECONDS,
    BPIC2015Dataset,
    DownloadError,
    download_bpic2015,
    fetch_article,
    select_xes_file,
)

ENV_FALLBACK_URL: Final = "PRAXON_BPIC2015_FALLBACK_URL"
OFFICIAL_MAX_ATTEMPTS: Final = 3
OFFICIAL_RETRY_DELAY_SECONDS: Final = 30.0


@dataclass(frozen=True)
class FetchResult:
    """Một tệp đã lấy xong và kiểm md5 khớp, sẵn sàng cho test đo thật."""

    source: str
    path: Path
    md5: str


class FetchError(Exception):
    """Cả ba nguồn đều thất bại: giữ danh sách lỗi từng nguồn để báo rõ."""

    def __init__(self, errors: list[str]) -> None:
        """Giữ nguyên danh sách lỗi từng nguồn để thông báo phân biệt được."""
        super().__init__("; ".join(errors))
        self.errors = errors


def _dataset_by_slug(slug: str) -> BPIC2015Dataset:
    for dataset in BPIC2015_DATASETS:
        if dataset.slug == slug:
            return dataset
    raise ValueError(f"dataset không có trong registry BPIC 2015: {slug!r}")


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_md5(dataset: BPIC2015Dataset, api_base: str | None) -> str:
    """Md5 do 4TU công bố cho dataset, lấy từ metadata figshare."""
    article = fetch_article(dataset.article_id, api_base)
    return str(select_xes_file(article)["computed_md5"])


def _find_zip_entry(archive: zipfile.ZipFile, filename: str) -> str | None:
    """Tên entry trong zip mà basename khớp tệp cần lấy, hoặc None."""
    for name in archive.namelist():
        if name.rsplit("/", 1)[-1] == filename:
            return name
    return None


def _fetch_fallback(
    fallback_url: str,
    dataset: BPIC2015Dataset,
    cache_dir: Path,
    expected_md5: str,
) -> Path:
    """Tải zip dự phòng, giải nén tệp .xes vào cache, kiểm md5 rồi mới dùng."""
    target = cache_dir / dataset.xes_filename
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_tmp = cache_dir / f"{dataset.xes_filename}.zip.tmp"
    out_tmp = cache_dir / f"{dataset.xes_filename}.tmp"
    digest = hashlib.md5()
    try:
        request = urllib.request.Request(
            fallback_url, headers={"User-Agent": "praxon-core/0.0.0"}
        )
        try:
            with (
                urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response,
                zip_tmp.open("wb") as handle,
            ):
                while chunk := response.read(CHUNK_BYTES):
                    handle.write(chunk)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise DownloadError(
                f"không tải được zip dự phòng từ {fallback_url}: {exc}"
            ) from exc
        try:
            with zipfile.ZipFile(zip_tmp) as archive:
                entry = _find_zip_entry(archive, dataset.xes_filename)
                if entry is None:
                    raise DownloadError(f"zip dự phòng không có entry {dataset.xes_filename}")
                with archive.open(entry) as source, out_tmp.open("wb") as handle:
                    while chunk := source.read(CHUNK_BYTES):
                        digest.update(chunk)
                        handle.write(chunk)
        except zipfile.BadZipFile as exc:
            raise DownloadError(f"zip dự phòng hỏng: {exc}") from exc
        if digest.hexdigest() != expected_md5:
            raise DownloadError("băm md5 của tệp dự phòng không khớp giá trị 4TU công bố")
        out_tmp.replace(target)
        return target
    finally:
        zip_tmp.unlink(missing_ok=True)
        out_tmp.unlink(missing_ok=True)


def fetch(
    dataset_slug: str,
    cache_dir: Path,
    fallback_url: str | None,
    *,
    api_base: str | None = None,
    retry_delay_seconds: float = OFFICIAL_RETRY_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """Lấy tệp của một dataset BPIC 2015 theo thứ tự cache, chính thức, dự phòng.

    Trả về ``FetchResult`` khi có tệp md5 khớp trong cache. Ném
    ``FetchError`` khi cả ba nguồn đều thất bại; danh sách lỗi từng nguồn
    nằm trong ``exc.errors`` để thông báo phân biệt được từng nguồn.
    """
    dataset = _dataset_by_slug(dataset_slug)
    target = cache_dir / dataset.xes_filename
    errors: list[str] = []
    expected_md5: str | None = None

    # 1. Cache: kiểm md5 theo metadata figshare; sai thì xóa tệp hỏng.
    try:
        expected_md5 = _expected_md5(dataset, api_base)
    except DownloadError as exc:
        errors.append(f"metadata: {exc}")
    if expected_md5 is not None and target.is_file():
        if _md5_file(target) == expected_md5:
            return FetchResult(source="cache", path=target, md5=expected_md5)
        target.unlink()

    # 2. Chính thức: bộ tải đã có (tự kiểm md5, không để tệp dở dang).
    for attempt in range(1, OFFICIAL_MAX_ATTEMPTS + 1):
        try:
            log = download_bpic2015(dataset, cache_dir, api_base=api_base)
            source = "cache" if log.from_cache else "chinh-thuc"
            return FetchResult(source=source, path=log.path, md5=log.md5)
        except DownloadError as exc:
            errors.append(f"chinh-thuc lần {attempt}: {exc}")
            if attempt < OFFICIAL_MAX_ATTEMPTS:
                sleep(retry_delay_seconds)

    # 3. Dự phòng: cần md5 để kiểm; lấy lại metadata nếu lúc đầu chưa có.
    if expected_md5 is None:
        try:
            expected_md5 = _expected_md5(dataset, api_base)
        except DownloadError as exc:
            errors.append(f"metadata (cho dự phòng): {exc}")
    if not fallback_url:
        print(
            "cảnh báo: không có URL dự phòng "
            f"(tham số --fallback-url hoặc biến {ENV_FALLBACK_URL}); "
            "bỏ qua nguồn dự phòng.",
            file=sys.stderr,
        )
    elif expected_md5 is None:
        errors.append("dự phòng: không có md5 để kiểm (metadata không lấy được)")
    else:
        try:
            path = _fetch_fallback(fallback_url, dataset, cache_dir, expected_md5)
            return FetchResult(source="du-phong", path=path, md5=expected_md5)
        except DownloadError as exc:
            errors.append(f"dự phòng: {exc}")

    raise FetchError(errors)


def fetch_all(
    cache_dir: Path,
    fallback_url: str | None,
    *,
    api_base: str | None = None,
    retry_delay_seconds: float = OFFICIAL_RETRY_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    """Lấy đủ 5 tệp BPIC 2015 (M1-M5) theo đúng thứ tự của `fetch`.

    Thiếu một tệp thì lỗi ngay (fail-closed) — tên slug đi kèm từng lỗi
    để phân biệt được file nào hỏng. Các file đã lấy xong trước điểm lỗi
    vẫn nằm trong cache (đủ md5), lần chạy sau chỉ lấy phần còn thiếu.
    """
    results: list[FetchResult] = []
    for dataset in BPIC2015_DATASETS:
        try:
            results.append(
                fetch(
                    dataset.slug,
                    cache_dir,
                    fallback_url,
                    api_base=api_base,
                    retry_delay_seconds=retry_delay_seconds,
                    sleep=sleep,
                )
            )
        except FetchError as exc:
            raise FetchError([f"{dataset.slug}: {error}" for error in exc.errors]) from exc
    return results


def main(argv: list[str] | None = None) -> int:
    """Điểm vào CLI: ``python -m tools.ci_fetch_bpic2015 --dataset m1``."""
    parser = argparse.ArgumentParser(
        prog="tools.ci_fetch_bpic2015",
        description=(
            "Lấy tệp BPIC 2015 cho CI: cache, bộ tải chính thức, dự phòng Drive. "
            "Thoát 0 chỉ khi cache đã có tệp md5 khớp; thoát 1 khi cả ba nguồn "
            "đều thất bại."
        ),
    )
    parser.add_argument(
        "--dataset",
        choices=[dataset.slug for dataset in BPIC2015_DATASETS] + ["all"],
        default="m1",
        help=(
            "slug dataset trong registry BPIC 2015, hoặc 'all' để lấy đủ "
            "5 đô thị (mặc định: m1)."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache chứa tệp .xes (mặc định: ~/.cache/praxon/bpic2015).",
    )
    parser.add_argument(
        "--fallback-url",
        default=None,
        help=(
            "URL zip dự phòng (mặc định: biến môi trường "
            f"{ENV_FALLBACK_URL}). Không có URL thì bỏ qua nguồn dự phòng."
        ),
    )
    args = parser.parse_args(argv)
    fallback_url = args.fallback_url or os.environ.get(ENV_FALLBACK_URL)
    try:
        if args.dataset == "all":
            results = fetch_all(
                cache_dir=args.cache_dir,
                fallback_url=fallback_url,
            )
            for result in results:
                print(f"{result.source}: {result.path} md5={result.md5}")
            return 0
        result = fetch(
            dataset_slug=args.dataset,
            cache_dir=args.cache_dir,
            fallback_url=fallback_url,
        )
    except FetchError as exc:
        print("không lấy được dữ liệu BPIC 2015:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"{result.source}: {result.path} md5={result.md5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
