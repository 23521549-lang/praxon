"""Generator phát lại trace từ episode (task 7.1, spec: bảng vai vòng học).

Hàm thuần: nhận một lô case từ `episode` của một tenant, trả một
`Trajectory` cho mỗi case — trình tự hoạt động thật (theo `occurred_at`)
kèm thuộc tính case. Không gọi mô hình, không đọc cơ sở dữ liệu (đầu vào
truyền vào, không phải truy vấn).

Một hàng `episode` là một sự kiện: `occurred_at` là thời điểm sự kiện xảy
ra, `case_id` nối sự kiện vào case của nó. Phát lại là nhóm sự kiện theo
`case_id` rồi xếp theo `occurred_at` để dựng lại trace.

Hợp đồng `payload` (jsonb, tạm — chờ parser 3.1/3.2 chốt): mỗi hàng có
`"activity"` là tên hoạt động (str, bắt buộc) và `"case_attributes"` là
thuộc tính cấp case, phi chuẩn hóa vào từng hàng (dict, vắng thì `{}`).
Các khóa khác trong payload Generator bỏ qua (dành cho vai khác). Nếu
parser chốt hình dạng khác (ví dụ một hàng là cả case với `"events"`),
chỉ thay hai hàm `_activity_from_payload` / `_case_attributes_from_payload`
(lớp chuyển đổi mỏng), không viết lại logic phát lại (nhóm theo case,
xếp theo thời gian).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EpisodeRow(BaseModel):
    """Một hàng `episode`, đúng các cột trong spec (dòng 47) và V1.

    `id` là khóa chính của hàng trong DB (V1: `episode.id uuid PRIMARY
    KEY`) — bên gọi cấp từ cột `episode.id` khi đọc DB (hoặc UUID tạo ra
    khi tổng hợp); `replay` dùng nó để gắn bằng chứng episode vào
    `Trajectory` (không có `id` thì Insight không mang được bằng chứng).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    tenant_id: str
    case_id: str
    payload: dict[str, Any]
    occurred_at: datetime
    ingested_at: datetime


class Trajectory(BaseModel):
    """Một trajectory: trình tự hoạt động thật kèm thuộc tính case.

    Spec (dòng 75): đầu ra của Generator. `activities` giữ đúng thứ tự xảy
    ra (theo `occurred_at`); `attributes` là thuộc tính cấp case.
    `episode_ids` là id episode của các hàng tạo nên trajectory, cùng thứ
    tự với `activities` (phần tử thứ i của `episode_ids` là hàng sinh ra
    hoạt động thứ i) — Reflector dùng cặp này để gắn bằng chứng episode
    vào Insight (chỉ episode nào thực sự thể hiện luật).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    case_id: str
    activities: tuple[str, ...]
    attributes: dict[str, Any]
    episode_ids: tuple[UUID, ...]


def _activity_from_payload(payload: dict[str, Any]) -> str:
    """Đọc tên hoạt động từ payload của một hàng episode.

    Hợp đồng (tạm, chờ parser 3.1/3.2 chốt): `payload["activity"]` là str.
    Thiếu hoặc không phải str thì ValueError — dữ liệu sai hình dạng phải
    lộ ra ngay, không im lặng bỏ qua.
    """
    activity = payload.get("activity")
    if not isinstance(activity, str):
        raise ValueError("payload thiếu 'activity' dạng chuỗi")
    return activity


def _case_attributes_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Đọc thuộc tính case từ payload của một hàng episode.

    Hợp đồng (tạm, chờ parser 3.1/3.2 chốt): `payload["case_attributes"]`
    là dict; vắng thì mặc định `{}`. Không phải dict thì ValueError.
    """
    attributes = payload.get("case_attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("payload['case_attributes'] phải là dict")
    return attributes


def replay(tenant_id: str, rows: list[EpisodeRow]) -> list[Trajectory]:
    """Phát lại một lô case từ episode thành trajectory.

    - Chỉ nhận hàng của đúng một tenant: hàng khác tenant thì ValueError.
    - Nhóm hàng theo `case_id`; thứ tự trajectory trả về theo thứ tự case
      xuất hiện lần đầu trong đầu vào.
    - Trong mỗi case, xếp hàng theo `occurred_at` (sắp xếp ổn định:
      `occurred_at` bằng nhau giữ nguyên thứ tự đầu vào); hoạt động của
      case là dãy hoạt động của các hàng theo thứ tự đó. `episode_ids`
      lấy từ các hàng theo cùng thứ tự đó nên phần tử thứ i của
      `episode_ids` là hàng sinh ra hoạt động thứ i của `activities`.
    - Thuộc tính case lấy từ hàng sớm nhất của case (sau khi xếp theo thời
      gian); các hàng trong một case mang cùng thuộc tính (phi chuẩn hóa),
      nên hàng nào cũng cho cùng kết quả khi dữ liệu nhất quán.
    """
    for row in rows:
        if row.tenant_id != tenant_id:
            raise ValueError(
                f"hàng case {row.case_id} thuộc tenant {row.tenant_id}, không phải {tenant_id}"
            )
    case_order: list[str] = []
    by_case: dict[str, list[EpisodeRow]] = {}
    for row in rows:
        if row.case_id not in by_case:
            by_case[row.case_id] = []
            case_order.append(row.case_id)
        by_case[row.case_id].append(row)
    trajectories: list[Trajectory] = []
    for case_id in case_order:
        case_rows = sorted(by_case[case_id], key=lambda row: row.occurred_at)
        activities = [_activity_from_payload(row.payload) for row in case_rows]
        attributes = _case_attributes_from_payload(case_rows[0].payload)
        trajectories.append(
            Trajectory(
                tenant_id=tenant_id,
                case_id=case_id,
                activities=tuple(activities),
                attributes=attributes,
                episode_ids=tuple(row.id for row in case_rows),
            )
        )
    return trajectories
