"""Bộ tải log BPIC 2015 từ 4TU.ResearchData (task 3.1, ADR 0004).

Nguồn gốc là 5 dataset riêng từng đô thị trên 4TU, mỗi dataset một article
figshare. Metadata lấy qua API công khai của figshare, không cần khóa: mỗi
tệp `.xes` đi kèm `computed_md5` do chính 4TU công bố, và băm tải về phải
khớp giá trị đó thì tệp mới được dùng.

Log tải lúc chạy vào cache ngoài kho (mặc định `~/.cache/praxon/bpic2015`),
không đóng gói vào kho — bất biến của dự án, cổng `check_thirdparty_data`
canh. Tệp đã có trong cache và md5 còn khớp thì không tải lại.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIGSHARE_API_URL = "https://api.figshare.com/v2/articles"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "praxon" / "bpic2015"
REQUEST_TIMEOUT_SECONDS = 120
CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class BPIC2015Dataset:
    """Một đô thị trong bộ BPIC 2015: định danh nguồn gốc trên 4TU.

    DOI từng dataset lấy từ API figshare ngày 6/11/2026. DOI collection
    trong ADR 0004 (`10.4121/uuid:31a308ef-c844-48da-948c-305d167a0ec1`)
    trỏ cả 5 dataset; mỗi dataset có DOI riêng của nó.
    """

    slug: str
    municipality: int
    article_id: int
    article_url: str
    doi: str
    xes_filename: str
    expected_cases: int


BPIC2015_DATASETS: tuple[BPIC2015Dataset, ...] = (
    BPIC2015Dataset(
        slug="m1",
        municipality=1,
        article_id=12709154,
        article_url=(
            "https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_1/12709154/1"
        ),
        doi="10.4121/uuid:a0addfda-2044-4541-a450-fdcc9fe16d17",
        xes_filename="BPIC15_1.xes",
        expected_cases=1199,
    ),
    BPIC2015Dataset(
        slug="m2",
        municipality=2,
        article_id=12697349,
        article_url=(
            "https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_2/12697349/1"
        ),
        doi="10.4121/uuid:63a8435a-077d-4ece-97cd-2c76d394d99c",
        xes_filename="BPIC15_2.xes",
        expected_cases=832,
    ),
    BPIC2015Dataset(
        slug="m3",
        municipality=3,
        article_id=12718370,
        article_url=(
            "https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_3/12718370/1"
        ),
        doi="10.4121/uuid:ed445cdd-27d5-4d77-a1f7-59fe7360cfbe",
        xes_filename="BPIC15_3.xes",
        expected_cases=1409,
    ),
    BPIC2015Dataset(
        slug="m4",
        municipality=4,
        article_id=12697898,
        article_url=(
            "https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_4/12697898/1"
        ),
        doi="10.4121/uuid:679b11cf-47cd-459e-a6de-9ca614e25985",
        xes_filename="BPIC15_4.xes",
        expected_cases=1053,
    ),
    BPIC2015Dataset(
        slug="m5",
        municipality=5,
        article_id=12713285,
        article_url=(
            "https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_5/12713285/1"
        ),
        doi="10.4121/uuid:b32c6fe5-f212-4286-9774-58dd53511cf8",
        xes_filename="BPIC15_5.xes",
        expected_cases=1156,
    ),
)


@dataclass(frozen=True)
class DownloadedLog:
    """Một log đã tải và kiểm băm xong, nằm trong cache lúc chạy."""

    dataset: BPIC2015Dataset
    path: Path
    size_bytes: int
    md5: str
    sha256: str
    source_url: str
    from_cache: bool


class DownloadError(Exception):
    """Tải hoặc kiểm băm thất bại: dừng, không dùng tệp dở dang."""


def fetch_article(article_id: int, api_base: str | None = None) -> dict[str, Any]:
    """Lấy metadata một article từ API công khai của figshare (4TU)."""
    base = api_base if api_base is not None else FIGSHARE_API_URL
    url = f"{base}/{article_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "praxon-core/0.0.0"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise DownloadError(
            f"metadata article {article_id} trả HTTP {exc.code}: {url}"
        ) from exc
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise DownloadError(
            f"không lấy được metadata article {article_id} từ {url}: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise DownloadError(f"metadata article {article_id} không phải JSON object")
    return parsed


def select_xes_file(article: dict[str, Any]) -> dict[str, Any]:
    """Chọn mục tệp `.xes` duy nhất trong metadata của một article."""
    files: list[dict[str, Any]] = [
        entry
        for entry in article.get("files", [])
        if str(entry.get("name", "")).endswith(".xes")
    ]
    if len(files) != 1:
        raise DownloadError(
            f"article {article.get('id')}: cần đúng 1 tệp .xes, thấy {len(files)}"
        )
    return files[0]


def _hash_file(path: Path, algorithm: str) -> str:
    """Băm một tệp bằng thuật toán cho trước, đọc theo khối."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _download_file(url: str, target: Path, expected_md5: str) -> None:
    """Tải một URL về tệp tạm, kiểm md5 trong lúc tải, đổi tên nguyên tử.

    Md5 không khớp thì xóa tệp tạm và báo lỗi; không bao giờ để lại tệp
    dở dang mang tên tệp đích.
    """
    tmp_path = target.with_suffix(f"{target.suffix}.tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "praxon-core/0.0.0"})
    digest = hashlib.md5()
    try:
        with (
            urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response,
            tmp_path.open("wb") as handle,
        ):
            while chunk := response.read(CHUNK_BYTES):
                digest.update(chunk)
                handle.write(chunk)
    except (urllib.error.URLError, TimeoutError) as exc:
        tmp_path.unlink(missing_ok=True)
        raise DownloadError(f"không tải được {url}: {exc}") from exc
    if digest.hexdigest() != expected_md5:
        tmp_path.unlink(missing_ok=True)
        raise DownloadError(f"băm md5 của {url} không khớp giá trị 4TU công bố")
    tmp_path.replace(target)


def _write_manifest(
    dataset: BPIC2015Dataset,
    path: Path,
    source_url: str,
    md5: str,
    sha256: str,
    downloaded_at: str,
) -> None:
    """Ghi manifest cạnh tệp log: băm và nguồn gốc của lần tải này."""
    manifest = {
        "slug": dataset.slug,
        "municipality": dataset.municipality,
        "article_id": dataset.article_id,
        "article_url": dataset.article_url,
        "doi": dataset.doi,
        "filename": dataset.xes_filename,
        "source_url": source_url,
        "size_bytes": path.stat().st_size,
        "md5": md5,
        "sha256": sha256,
        "downloaded_at": downloaded_at,
    }
    manifest_path = path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def download_bpic2015(
    dataset: BPIC2015Dataset,
    cache_dir: Path | None = None,
    *,
    api_base: str | None = None,
) -> DownloadedLog:
    """Tải log `.xes` của một đô thị, kiểm md5 do 4TU công bố, ghi manifest.

    Tệp đã có trong cache và md5 còn khớp thì không tải lại. Tệp trong
    cache hỏng md5 thì tải lại đè lên; tải thất bại thì báo lỗi.
    """
    directory = cache_dir or DEFAULT_CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / dataset.xes_filename
    article = fetch_article(dataset.article_id, api_base)
    entry = select_xes_file(article)
    expected_md5 = str(entry["computed_md5"])
    source_url = str(entry["download_url"])
    if target.is_file() and _hash_file(target, "md5") == expected_md5:
        from_cache = True
        downloaded_at = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC).isoformat()
    else:
        _download_file(source_url, target, expected_md5)
        from_cache = False
        downloaded_at = datetime.now(UTC).isoformat()
    sha256 = _hash_file(target, "sha256")
    _write_manifest(dataset, target, source_url, expected_md5, sha256, downloaded_at)
    return DownloadedLog(
        dataset=dataset,
        path=target,
        size_bytes=target.stat().st_size,
        md5=expected_md5,
        sha256=sha256,
        source_url=source_url,
        from_cache=from_cache,
    )


def download_all_bpic2015(
    cache_dir: Path | None = None, *, api_base: str | None = None
) -> list[DownloadedLog]:
    """Tải cả năm log BPIC 2015, theo thứ tự đô thị 1 → 5."""
    return [
        download_bpic2015(dataset, cache_dir, api_base=api_base)
        for dataset in BPIC2015_DATASETS
    ]


def main(argv: list[str] | None = None) -> int:
    """Lệnh tải log BPIC 2015: `python -m praxon_core.datasets.bpic2015`."""
    parser = argparse.ArgumentParser(
        prog="praxon_core.datasets.bpic2015",
        description="Tải log BPIC 2015 từ 4TU.ResearchData vào cache lúc chạy.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache ngoài kho (mặc định: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        choices=[dataset.slug for dataset in BPIC2015_DATASETS],
        help="chỉ tải một đô thị (mặc định: cả năm)",
    )
    args = parser.parse_args(argv)
    datasets = [
        dataset
        for dataset in BPIC2015_DATASETS
        if args.dataset is None or dataset.slug == args.dataset
    ]
    try:
        logs = [download_bpic2015(dataset, args.cache_dir) for dataset in datasets]
    except DownloadError as exc:
        print(f"lỗi tải: {exc}", file=sys.stderr)
        return 1
    for log in logs:
        state = "cache" if log.from_cache else "mới tải"
        print(
            f"{log.dataset.slug}: {log.path.name} {log.size_bytes} byte "
            f"md5={log.md5} sha256={log.sha256} ({state})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
