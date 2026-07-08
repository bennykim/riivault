-- =========================================================================
-- riivault — Reddit 데이터 인텔리전스 플랫폼 스키마
-- 설계 원칙:
--   (1) 이원 저장: raw_* (≤48h TTL, 처리 전용) ↔ 파생/집계 (영구 자산)
--   (2) 시계열 최적화: TimescaleDB hypertable + pgvector(임베딩)
--   (3) Reddit 정책 정합: 원문 미영구보관, 삭제 이벤트 반영, 비식별 집계만 자산화
--   (4) Stack A(그린필드): 수집=Python asyncpraw+APScheduler, 저장=Postgres 단일 DB
-- 대상: PostgreSQL 15+ / TimescaleDB / pgvector (또는 Supabase Postgres)
-- =========================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================
-- 1) 원문 임시 계층 (≤48h TTL, 처리 후 파기) — 자산 아님
-- =========================================================
CREATE TABLE IF NOT EXISTS raw_submission (
    reddit_id      TEXT PRIMARY KEY,            -- t3_xxx
    subreddit      TEXT NOT NULL,
    author_hash    TEXT,                        -- 해시(비식별). 원문 author 미보관
    title          TEXT,
    selftext       TEXT,
    score          INT,
    upvote_ratio   REAL,
    num_comments   INT,
    flair          TEXT,
    created_utc    TIMESTAMPTZ NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ NOT NULL         -- fetched_at + 48h, 배치 파기
);
CREATE INDEX IF NOT EXISTS idx_raw_sub_expires ON raw_submission (expires_at);
CREATE INDEX IF NOT EXISTS idx_raw_sub_subreddit ON raw_submission (subreddit, created_utc);

CREATE TABLE IF NOT EXISTS raw_comment (
    reddit_id      TEXT PRIMARY KEY,            -- t1_xxx
    submission_id  TEXT,
    subreddit      TEXT NOT NULL,
    author_hash    TEXT,
    body           TEXT,
    score          INT,
    created_utc    TIMESTAMPTZ NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_com_expires ON raw_comment (expires_at);

CREATE TABLE IF NOT EXISTS raw_hn_item (         -- Hacker News 원문 임시 계층 (≤48h TTL)
    hn_id          TEXT PRIMARY KEY,            -- Algolia objectID
    kind           TEXT NOT NULL,              -- story|comment
    author_hash    TEXT,                        -- 해시(비식별). 원문 author 미보관
    title          TEXT,
    body           TEXT,                        -- story_text or comment_text
    url            TEXT,
    points         INTEGER,
    num_comments   INTEGER,
    created_utc    TIMESTAMPTZ NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ NOT NULL DEFAULT now() + interval '48 hours'  -- 배치 파기
);
CREATE INDEX IF NOT EXISTS idx_raw_hn_expires ON raw_hn_item (expires_at);

-- =========================================================
-- 2) 엔티티 & 소스 (마스터)
-- =========================================================
CREATE TABLE IF NOT EXISTS entity (
    entity_id      BIGSERIAL PRIMARY KEY,
    type           TEXT NOT NULL,               -- product|ticker|brand|topic|subreddit|keyword
    canonical_name TEXT NOT NULL,
    aliases        TEXT[],                       -- 엔티티 해소용 별칭
    metadata       JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (type, canonical_name)
);

CREATE TABLE IF NOT EXISTS source (
    source_id      SMALLSERIAL PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE          -- reddit|hackernews|github|producthunt|google_trends
);
INSERT INTO source (name) VALUES
    ('reddit'), ('hackernews'), ('github'), ('producthunt'), ('google_trends')
    ON CONFLICT (name) DO NOTHING;

-- =========================================================
-- 3) 파생·집계 계층 (영구 자산) — hypertable
-- =========================================================
CREATE TABLE IF NOT EXISTS mention_daily (
    day              DATE NOT NULL,
    entity_id        BIGINT NOT NULL REFERENCES entity(entity_id),
    source_id        SMALLINT NOT NULL REFERENCES source(source_id),
    subreddit        TEXT NOT NULL DEFAULT '',   -- 세분 분석(옵션), '' = 전체
    mention_count    INT NOT NULL,
    unique_authors   INT NOT NULL,
    score_sum        BIGINT,
    upvote_ratio_avg REAL,
    comment_sum      BIGINT,
    PRIMARY KEY (day, entity_id, source_id, subreddit)
);
SELECT create_hypertable('mention_daily', 'day', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS sentiment_daily (
    day            DATE NOT NULL,
    entity_id      BIGINT NOT NULL REFERENCES entity(entity_id),
    source_id      SMALLINT NOT NULL REFERENCES source(source_id),
    sentiment_mean REAL,                         -- -1..+1
    sentiment_std  REAL,
    pos_ratio      REAL,
    neg_ratio      REAL,
    neu_ratio      REAL,
    sample_size    INT,
    PRIMARY KEY (day, entity_id, source_id)
);
SELECT create_hypertable('sentiment_daily', 'day', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS topic_daily (         -- 토픽 클러스터 시계열
    day            DATE NOT NULL,
    topic_id       BIGINT NOT NULL,
    entity_id      BIGINT REFERENCES entity(entity_id),
    label          TEXT,
    volume         INT,
    momentum       REAL,                         -- 증감 속도
    PRIMARY KEY (day, topic_id)
);
SELECT create_hypertable('topic_daily', 'day', if_not_exists => TRUE);

-- VoC 원장(누적 자산): 정규화 요약 + 임베딩(원문 미저장)
CREATE TABLE IF NOT EXISTS feature_request (
    fr_id           BIGSERIAL PRIMARY KEY,
    entity_id       BIGINT NOT NULL REFERENCES entity(entity_id),
    kind            TEXT NOT NULL,               -- feature_request|pain_point|bug|praise|switch_intent
    normalized_text TEXT NOT NULL,               -- 정규화 요약(원문 아님)
    embedding       VECTOR(1024),                -- 의미 중복제거·클러스터
    first_seen      DATE NOT NULL,
    last_seen       DATE NOT NULL,
    occurrences     INT NOT NULL DEFAULT 1,
    momentum        REAL,
    example_ref     TEXT                         -- 링크만(원문 미저장), 삭제 시 무효화
);
CREATE INDEX IF NOT EXISTS idx_fr_entity_kind ON feature_request (entity_id, kind, last_seen);
-- 임베딩 근접검색 인덱스(대략적) — 데이터 축적 후 생성 권장
-- CREATE INDEX ON feature_request USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS emerging_signal (     -- 조기신호 검증 이력(모델 학습 라벨)
    signal_id      BIGSERIAL PRIMARY KEY,
    entity_id      BIGINT REFERENCES entity(entity_id),
    detected_at    DATE NOT NULL,
    signal_type    TEXT,                         -- spike|new_topic|sentiment_flip|migration
    strength       REAL,
    validated      BOOLEAN,                      -- 사후 검증
    outcome        JSONB
);

CREATE TABLE IF NOT EXISTS subreddit_snapshot (  -- 커뮤니티 메타 시계열
    day            DATE NOT NULL,
    subreddit      TEXT NOT NULL,
    subscribers    INT,
    active_users   INT,
    posts_per_day  INT,
    PRIMARY KEY (day, subreddit)
);
SELECT create_hypertable('subreddit_snapshot', 'day', if_not_exists => TRUE);

-- =========================================================
-- 4) 컴플라이언스 & 운영
-- =========================================================
CREATE TABLE IF NOT EXISTS deletion_log (        -- Reddit 삭제/수정 반영
    reddit_id      TEXT PRIMARY KEY,
    detected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    action         TEXT                          -- purged_raw|invalidated_ref
);

CREATE TABLE IF NOT EXISTS collection_run (      -- 수집 잡 관측성
    run_id         BIGSERIAL PRIMARY KEY,
    source_id      SMALLINT REFERENCES source(source_id),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    api_calls      INT,
    items_ingested INT,
    errors         INT,
    rate_limited   BOOLEAN
);

-- =========================================================
-- 5) 제품 계층 (MVP Must: 뉴스레터·주간 이슈·수집 커서)
-- =========================================================
CREATE TABLE IF NOT EXISTS newsletter_subscriber (
    email           TEXT PRIMARY KEY,
    subscribed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed       BOOLEAN NOT NULL DEFAULT FALSE,
    unsubscribed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS weekly_issue (            -- "이번 주 Reddit" 발행 스냅샷
    issue_no       SERIAL PRIMARY KEY,
    week_start     DATE NOT NULL UNIQUE,             -- 월요일
    week_end       DATE NOT NULL,
    headline       TEXT NOT NULL,
    dek            TEXT,
    lead_entity_id BIGINT REFERENCES entity(entity_id),
    payload        JSONB,                            -- 렌더 스냅샷(파생 지표만, 원문 없음)
    published_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS collect_cursor (          -- 서브레딧별 증분 수집 커서
    subreddit        TEXT PRIMARY KEY,
    last_fullname    TEXT,                           -- 마지막 수집 t3_xxx
    last_created_utc TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 6) 운영 도우미: 48h 원문 파기 (스케줄러/cron에서 호출)
-- =========================================================
-- DELETE FROM raw_submission WHERE expires_at < now();
-- DELETE FROM raw_comment    WHERE expires_at < now();
