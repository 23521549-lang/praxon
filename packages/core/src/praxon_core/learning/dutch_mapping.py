"""Bảng gắn khái niệm tiếng Hà Lan (Wabo) với hoạt động log BPIC 2015 (task 9.2).

Bảng gắn là một bước có kiểm (spec dòng 174): gắn khái niệm trong văn bản
tiếng Hà Lan với tên hoạt động trong log; gắn sai thì luật sai, và cổng
Beta loại luật sai — nên gắn sai chỉ tốn công, không làm hệ áp sai.

Nguồn dữ liệu (đo ngày 7/11/2026, ghi trong tệp TOML kèm theo):
- Văn bản Wabo: wetten.nl, BWBR0024779, bản 2015-01-01 (có hiệu lực
  01-01-2015-31-03-2015; Wabo có hiệu lực 01-10-2010-31-12-2023, bị
  Omgevingswet thay thế từ 01-01-2024). Tải về cache ngoài kho
  ``~/.cache/praxon/wabo/wabo-2015-01-01.html`` (977.356 byte, SHA-256
  ``0e4d66c6…``); không commit văn bản vào kho.
- Tên hoạt động và tần suất: thuộc tính ``activityNameNL`` của 262.628 sự
  kiện trong 5 log BPIC 2015 (cache ``~/.cache/praxon/bpic2015``). Chỉ các
  code có ĐÚNG MỘT tên NL trên cả 5 đô thị mới được gắn (478/500 code ổn
  định; 22 code có nhiều tên NL theo đô thị bị loại khỏi bảng).

Quy tắc gắn: mỗi mục là một bước thủ tục trong Wabo (khái niệm XUẤT HIỆN
trong văn bản, ``wabo_count`` là số lần xuất hiện đếm từ văn bản đã tải)
ánh xạ sang các hoạt động log thực hiện đúng bước đó (tên NL ổn định).
``canonical`` là code đại diện cho bước đó (sự kiện xảy ra, không phải
bước đăng ký ngày / ghi sổ); lý do chọn ghi trong ``note`` từng mục.
Khái niệm không gắn được ghi ở mục chưa gắn kèm lý do, KHÔNG bịa gắn.

Cách dùng (task 9.1): Reflector trích luật thứ tự từ Wabo theo khái niệm;
``canonical_activity`` cho hoạt động log cụ thể để đo luật đó bằng cổng
Beta; ``activities_for`` cho toàn bộ tập để đo từng hoạt động trong tập.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_DUTCH_MAPPING_FILENAME = "dutch_mapping.toml"


class MappedActivity(BaseModel):
    """Một hoạt động log thuộc về một khái niệm: mã + tên NL + tần suất."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    dutch_name: str = Field(min_length=1)
    events: int = Field(gt=0)


class ConceptMapping(BaseModel):
    """Một khái niệm Wabo và các hoạt động log thực hiện nó."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    term: str = Field(min_length=1)
    wabo_count: int = Field(ge=0)
    log_phrase: str | None = None
    canonical: str = Field(min_length=1)
    activities: list[MappedActivity] = Field(min_length=1)
    note: str = ""

    @model_validator(mode="after")
    def _check_canonical_and_codes(self) -> ConceptMapping:
        codes = [activity.code for activity in self.activities]
        if len(set(codes)) != len(codes):
            raise ValueError(f"khái niệm {self.term!r} có mã hoạt động trùng: {codes}")
        if self.canonical not in codes:
            raise ValueError(
                f"khái niệm {self.term!r}: canonical {self.canonical!r} "
                "không nằm trong danh sách hoạt động"
            )
        return self


class UnmappedConcept(BaseModel):
    """Một khái niệm Wabo chưa gắn được, kèm lý do (không bịa gắn)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    term: str = Field(min_length=1)
    wabo_count: int = Field(ge=0)
    reason: str = Field(min_length=1)


class WaboSource(BaseModel):
    """Nguồn văn bản Wabo mà bảng gắn dựa vào."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_url: str = Field(min_length=1)
    version: str = Field(min_length=1)
    valid_during: str = Field(min_length=1)
    sha256_html: str = Field(min_length=1)


class DutchMappingTable(BaseModel):
    """Bảng gắn đã nạp: nguồn Wabo + khái niệm đã gắn + khái niệm chưa gắn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    wabo: WaboSource
    concept: list[ConceptMapping] = Field(min_length=1)
    unmapped: list[UnmappedConcept] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_terms_unique(self) -> DutchMappingTable:
        terms = [entry.term for entry in self.concept]
        if len(set(terms)) != len(terms):
            raise ValueError(f"khái niệm trùng: {terms}")
        unmapped_terms = [entry.term for entry in self.unmapped]
        if len(set(unmapped_terms)) != len(unmapped_terms):
            raise ValueError(f"khái niệm chưa gắn trùng: {unmapped_terms}")
        overlap = set(terms) & set(unmapped_terms)
        if overlap:
            raise ValueError(f"khái niệm vừa gắn vừa chưa gắn: {sorted(overlap)}")
        return self

    def activities_for(self, term: str) -> tuple[MappedActivity, ...]:
        """Toàn bộ hoạt động log của một khái niệm đã gắn."""
        for entry in self.concept:
            if entry.term == term:
                return tuple(entry.activities)
        raise KeyError(f"khái niệm chưa gắn hoặc không có: {term!r}")

    def canonical_activity(self, term: str) -> str:
        """Hoạt động log đại diện cho một khái niệm đã gắn."""
        for entry in self.concept:
            if entry.term == term:
                return entry.canonical
        raise KeyError(f"khái niệm chưa gắn hoặc không có: {term!r}")

    def is_mapped(self, term: str) -> bool:
        """Khái niệm có trong bảng gắn không."""
        return any(entry.term == term for entry in self.concept)

    def unmapped_terms(self) -> tuple[str, ...]:
        """Các khái niệm chưa gắn được (kèm lý do trong bảng)."""
        return tuple(entry.term for entry in self.unmapped)


def load_dutch_mapping(path: Path) -> DutchMappingTable:
    """Nạp bảng gắn từ tệp TOML, kiểm bằng Pydantic lúc nạp."""
    raw: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    return DutchMappingTable.model_validate(raw)


def default_dutch_mapping() -> DutchMappingTable:
    """Bảng gắn mặc định — tệp TOML cạnh module này."""
    path = Path(__file__).with_name(DEFAULT_DUTCH_MAPPING_FILENAME)
    return load_dutch_mapping(path)
