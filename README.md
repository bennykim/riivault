# riivault

Reddit 의견 데이터를 **파생 시계열 인텔리전스**(mention·sentiment·pain-point·emerging signal)로 가공해 보여주는 인사이트 미디어. 원문은 ≤48h 처리 버퍼에만 머물고, 영구 자산은 비식별 집계뿐이다.

- 기획: [BUSINESS_PLAN.md](BUSINESS_PLAN.md) · DB: [schema.sql](schema.sql) · API 계약: [docs/CONTRACT.md](docs/CONTRACT.md) · 최종 디자인: [design/index.html](design/index.html)

## 구조

```
backend/   Python 3.12 — asyncpraw 수집기 + 파생 파이프라인 + FastAPI (uv)
web/       Next.js 15 — "This Week on Reddit" 프론트 (디자인 1:1 포팅)
schema.sql Postgres 16 + TimescaleDB + pgvector DDL (compose가 자동 적용)
```

## Quickstart

```bash
cp .env.example .env            # Reddit/Anthropic 키는 선택 (없어도 데모 구동 가능)
docker compose up -d db         # TimescaleDB :5433, schema.sql 자동 적용

cd backend
uv sync
uv run riivault seed-demo       # 데모 파생 데이터 + 주간 이슈 발행
uv run riivault api             # FastAPI :8000

cd ../web
npm install
npm run dev                     # Next.js :3000
```

실수집(선택, Reddit 키 필요):

```bash
uv run riivault collect-once    # 1회 증분 수집 → 집계
uv run riivault collect-hn      # Hacker News 1회 증분 수집 (키 불필요, Algolia 공개 API)
uv run riivault scheduler       # 상시 스케줄러 (수집/집계/파기/주간 발행)
```

## 컴플라이언스 원칙 (Reddit Responsible Builder Policy)

1. 원문(raw_*)은 48h 후 자동 파기 — 영구 자산은 파생·집계만.
2. 삭제/수정 콘텐츠 감지 시 즉시 파기 + `deletion_log` 기록.
3. 비상업 무료 tier(≤100 QPM) 준수 — 토큰버킷 기본 90 QPM.
4. API/프론트는 파생 지표만 노출, 원문 재배포 없음.
