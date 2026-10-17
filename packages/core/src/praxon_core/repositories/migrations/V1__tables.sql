-- V1 — Bảng và ràng buộc toàn vẹn (plan con 2, task 2.2/2.4).
--
-- Trường các bảng theo đúng mục "Lược đồ dữ liệu" của spec. Hai điểm diễn giải
-- được ghi rõ để review (không phải thay đổi ngầm):
--
-- 1. Bảng `run` có thêm cột `tenant_id`. Spec liệt kê "trường chính" của run mà
--    không có tenant_id, nhưng bất biến BĐ2 đòi RLS trên "mọi bảng có dữ liệu
--    tenant" — một run thuộc về vòng học của một tenant, nên nó là dữ liệu tenant.
-- 2. Exclusion constraint gồm 5 cột `(tenant_id, scope, canonical_key, valid_during,
--    known_during)`, trong khi spec viết 4 cột (thiếu tenant_id). Không có tenant_id
--    thì fact của tenant A chặn fact cùng khóa của tenant B — một kênh can thiệp
--    chéo tenant, vi phạm BĐ2. Thêm tenant_id là để BĐ2 đúng ở cả tầng ràng buộc.
-- 3. Khóa chính bảng `event` đặt tên `event_id` theo đúng spec; các bảng còn lại dùng `id`.
-- 4. Quy ước: fact có `scope = 'global'` mang `tenant_id = 'global'` (xem V3).

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Episodic: đầu vào thô, chỉ thêm (BĐ1).
CREATE TABLE episode (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   text        NOT NULL,
    case_id     text        NOT NULL,
    payload     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now()
);

-- Semantic: tri thức song thời gian (mô hình của Graphiti, lưu trên Postgres).
CREATE TABLE fact (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text        NOT NULL,
    scope            text        NOT NULL CHECK (scope IN ('tenant', 'global')),
    canonical_key    text        NOT NULL,
    template         text        NOT NULL,
    activation       text,
    target           text,
    condition        text,
    statement        text        NOT NULL,
    status           text        NOT NULL DEFAULT 'trial'
                                 CHECK (status IN ('trial', 'active', 'retired')),
    support          integer     NOT NULL DEFAULT 0 CHECK (support >= 0),
    confidence       double precision NOT NULL DEFAULT 0
                                 CHECK (confidence >= 0 AND confidence <= 1),
    valid_during     tstzrange   NOT NULL,
    known_during     tstzrange   NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    source_episode_ids uuid[]   NOT NULL DEFAULT '{}',
    candidate_id     uuid        UNIQUE,
    -- BĐ5: không hai fact cùng khóa cùng hiệu lực. Thay thế = đóng fact cũ
    -- (thu hẹp known_during) rồi thêm fact mới, trong một giao dịch.
    CONSTRAINT fact_no_overlap EXCLUDE USING gist (
        tenant_id    WITH =,
        scope        WITH =,
        canonical_key WITH =,
        valid_during WITH &&,
        known_during WITH &&
    )
);

-- Cắt ngang: đề xuất tri thức. Curator tạo, Governor ghi quyết định.
CREATE TABLE candidate (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            text        NOT NULL,
    target_scope         text        NOT NULL CHECK (target_scope IN ('tenant', 'global')),
    payload              jsonb       NOT NULL DEFAULT '{}'::jsonb,
    rationale            text        NOT NULL DEFAULT '',
    evidence_episode_ids uuid[]      NOT NULL DEFAULT '{}',
    rule_id              text,
    metrics_at_decision  jsonb       NOT NULL DEFAULT '{}'::jsonb,
    status               text        NOT NULL DEFAULT 'proposed'
                                    CHECK (status IN ('proposed', 'approved', 'rejected')),
    decided_by           text,
    decided_at           timestamptz,
    rubric_clause        text
);

-- Cắt ngang: một lần chạy đo. Ghi bởi bộ điều phối, chỉ thêm.
CREATE TABLE run (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      text        NOT NULL,
    seed           bigint      NOT NULL,
    model_id       text        NOT NULL,
    model_revision text        NOT NULL DEFAULT '',
    code_commit    text        NOT NULL,
    config_hash    text        NOT NULL,
    data_hash      text        NOT NULL,
    tokens_in      bigint      NOT NULL DEFAULT 0 CHECK (tokens_in >= 0),
    tokens_out     bigint      NOT NULL DEFAULT 0 CHECK (tokens_out >= 0),
    wall_time      double precision NOT NULL DEFAULT 0 CHECK (wall_time >= 0),
    status         text        NOT NULL DEFAULT 'running'
                               CHECK (status IN ('running', 'succeeded', 'failed'))
);

-- Cắt ngang: nhật ký quyết định và tool call. Chỉ thêm (BĐ1).
CREATE TABLE event (
    event_id     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       uuid        REFERENCES run (id),
    tenant_id    text        NOT NULL,
    actor        text        NOT NULL,
    action       text        NOT NULL,
    target       text,
    decision     text,
    decided_by   text,
    reason       text,
    payload_hash text        NOT NULL,
    occurred_at  timestamptz NOT NULL DEFAULT now()
);
