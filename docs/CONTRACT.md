# riivault — 구현 계약서 (backend ↔ web)

> 이 문서가 단일 진실 소스다. backend와 web은 이 계약만 보고 독립 구현한다.
> 스키마: `/schema.sql` · 기획: `/BUSINESS_PLAN.md` · 최종 디자인: `/design/index.html`

## 아키텍처

```
[Reddit API] → collector(Python asyncpraw, 토큰버킷 ≤90QPM)
   → raw_*(≤48h TTL) → process(엔티티 매칭·감성·VoC) → 파생 테이블(영구)
   → purge(48h 파기 + deletion_log)
[FastAPI :8000] ← 파생 테이블만 읽음 (원문 절대 노출 금지)
[Next.js :3000] ← FastAPI (NEXT_PUBLIC_API_URL)
```

- DB: Postgres 16 + TimescaleDB + pgvector (docker-compose, `schema.sql` 자동 적용)
- `DATABASE_URL` 예: `postgresql://riivault:riivault@localhost:5433/riivault`
- API 원칙: **파생·집계만 응답. raw_* 테이블은 API에서 절대 SELECT하지 않는다.**

## REST API (prefix `/api/v1`, JSON, snake_case)

### GET /healthz
`{"status":"ok","db":true}`

### GET /api/v1/issue/current
프론트 메인 페이지 전체를 한 번에 구성하는 복합 응답.
`weekly_issue` 최신 행 + 파생 테이블 라이브 쿼리 조합. 발행 이슈가 없으면 **404** (프론트는 샘플 데이터 폴백).

```json
{
  "issue_no": 27,
  "week_start": "2026-06-29",
  "week_end": "2026-07-05",
  "generated_at": "2026-07-03T09:00:00Z",
  "niche": "SaaS",
  "communities": 34,
  "lead": {
    "eyebrow": "Lead signal · momentum +38%",
    "headline": "The AI-wrapper honeymoon is ending — churn complaints tripled in six weeks",
    "dek": "Across founder communities, ...",
    "momentum_pct": 38.0,
    "threads": 1240,
    "comments": 8900,
    "window_weeks": 12,
    "subreddits": ["r/SaaS", "r/indiehackers", "r/microsaas"],
    "chart_title": "Mention Index — \"AI wrapper\" churn",
    "delta_label": "+40% w/w",
    "delta_value": 168,
    "series": [{"period": "2026-04-13", "value": 34}]
  },
  "tracked": [
    {"entity_id": 1, "name": "Cursor", "context": "r/programming",
     "change_pct": 52.0, "spark": [3, 4, 5, 6, 8, 9, 11]}
  ],
  "pain_points": [
    {"fr_id": 1, "rank": 1, "text": "Per-seat pricing punishes small teams",
     "kind": "pain_point", "occurrences": 214, "momentum_pct": 61.0}
  ],
  "sentiment_focus": {
    "label": "\"AI note-takers\"",
    "current": -0.31, "trend": "falling",
    "series": [{"period": "2026-04-06", "value": 0.22}]
  },
  "migration": {
    "origin": "r/Notion", "n": 141, "title": "where r/Notion posters go",
    "destinations": [{"name": "r/Obsidian", "share": 0.41}]
  },
  "emerging": [
    {"signal_id": 1, "signal_type": "spike", "entity": "\"Local-first\" SaaS",
     "description": "Mentions up 4.2× in three weeks ...",
     "strength": 0.86, "detected_label": "Detected wk25"}
  ]
}
```

필드 규칙:
- `kind`: `pain_point | feature_request | switch_intent | bug | praise` (프론트 태그: pain/feat/switch 매핑)
- `signal_type`: `spike | new_topic | sentiment_flip | migration`
- `series[].period`: ISO 날짜 문자열(주 시작일 또는 일). `spark`: 숫자 7~12개 (오래된→최신).
- `momentum_pct`, `change_pct`: 백분율 숫자(52.0 = +52%). 음수 허용.
- `sentiment.value`: -1.0 ~ +1.0.

### GET /api/v1/entities?tracked=true
```json
{"items": [{"entity_id":1,"type":"product","name":"Cursor","context":"r/programming",
  "change_pct":52.0,"spark":[3,4,5,6,8,9,11]}]}
```
`change_pct` = 최근 7일 언급합 vs 직전 7일(직전 0이면 null). `spark` = 최근 7일 일별 mention_count 합.

### GET /api/v1/entities/{entity_id}/series?metric=mentions|sentiment&days=90
```json
{"entity_id":1,"metric":"mentions","series":[{"period":"2026-06-01","value":42}]}
```

### GET /api/v1/pain-points?days=7&limit=10
feature_request에서 `last_seen >= today-days`, momentum desc 정렬.
```json
{"items":[{"fr_id":1,"rank":1,"text":"...","kind":"pain_point","occurrences":214,"momentum_pct":61.0}]}
```

### GET /api/v1/signals?limit=6
emerging_signal 최신순. 응답 항목은 issue.emerging와 동일 형태.

### POST /api/v1/subscribe
요청 `{"email":"a@b.co"}` → 201 `{"ok":true}` (중복이면 200 `{"ok":true,"already":true}`, 형식 오류 422).

### 오류 포맷
FastAPI 기본 `{"detail": "..."}`.

## backend 규칙
- Python 3.12 (`backend/.python-version`), uv + pyproject, 패키지명 `riivault`.
- DB 접근: asyncpg 직접 SQL (ORM 없음). 스키마 변경 금지 — `/schema.sql`이 진실.
- Reddit 수집: asyncpraw, 토큰버킷 기본 90 QPM(설정 `REDDIT_QPM`), `collect_cursor`로 증분.
- 컴플라이언스: raw는 `expires_at = fetched_at + 48h`; purge 잡이 파기+`deletion_log` 기록. 재조회 시 `[deleted]/[removed]` 감지 → 즉시 파기 + `feature_request.example_ref` 무효화(NULL).
- NLP: 감성=VADER 기본, `ANTHROPIC_API_KEY` 있으면 LLM VoC 추출(없으면 해당 단계 skip+로그).
- CLI: `riivault collect-once` / `riivault aggregate` / `riivault purge` / `riivault publish-issue` / `riivault scheduler` / `riivault seed-demo` / `riivault api`.
- `seed-demo`: 디자인 샘플과 유사한 데모 데이터를 파생 테이블+weekly_issue에 삽입(개발 검증용).

## web 규칙
- Next.js 15 App Router + TypeScript, `web/`. Tailwind 불사용 — `design/index.html`의 CSS를 그대로 포팅(디자인 충실도 우선).
- 서버 컴포넌트에서 `GET /api/v1/issue/current` fetch (`cache: "no-store"`). 404/네트워크 오류 시 번들된 샘플 데이터(디자인과 동일 수치) 폴백 + 푸터에 "Sample data" 표기, 라이브면 "Live index".
- 차트: 외부 라이브러리 금지. 데이터 → SVG path 변환 유틸로 디자인과 동일한 look 재현.
- 구독 폼: POST /api/v1/subscribe, 성공/실패 메시지는 디자인 문구 유지.
- 환경변수: `NEXT_PUBLIC_API_URL` (기본 `http://localhost:8000`). 서버 fetch는 `API_URL` 우선.
