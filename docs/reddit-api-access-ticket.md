# riivault — Reddit Data API access request (v0.2)

Non-commercial · read-only · derived aggregates only
Submit target: on or after 2026-08-05

## Paste-ready ticket body

Copy the entire block below (one click on most renderers' copy button) and paste it as-is into the Reddit access request form.

```text
SUMMARY
riivault is a non-commercial trend-research project. It turns public
discussion in one niche (SaaS / indie-hacker communities) into derived
time-series signals — daily mention counts and sentiment averages per
tracked product. It publishes free aggregate summaries at riivault.space.
No paywall, no ads, no data resale, no revenue, no business entity.

This is a resubmission with a materially narrowed and hardened scope.
A previous request was declined; rather than re-file the same proposal,
the scope was cut, the compliance behaviour was pinned in code, and the
public site was corrected. Specifics are in "WHAT CHANGED" below.

WHAT WE READ
- Endpoint: subreddit "new" listings only — /r/{subreddit}/new via
  asyncpraw, limit=100 per request.
- We do NOT read comment trees, /hot, /top, search, user pages, modmail,
  or any private data.
- Subreddits (5, fixed and enumerated): r/SaaS, r/indiehackers,
  r/microsaas, r/startups, r/Entrepreneur.
- Frequency: two requests per subreddit per run (one subreddit lookup,
  one listing), 12 runs per day (every 2 hours), with cursor-based
  incremental dedup.
- Steady-state volume: ~120 requests/day = ~0.08 QPM average against the
  100 QPM free-tier allowance. A token-bucket scheduler caps us at 90 QPM
  even in a burst.

WHAT WE NEVER DO
No posting, no voting, no commenting, no automation, no bot account, no
writes of any kind. The API client is constructed with read_only pinned
to true, so no code path can write regardless of credentials.

HOW WE HANDLE THE DATA
- Raw content: held in a temporary processing buffer with a hard 48-hour
  TTL (expires_at column), then permanently deleted by a purge job that
  runs every 2 hours. Raw content is never a retained asset and there is
  no reconstructable archive.
- Deletion / removal: when content is deleted or removed on Reddit, the
  purge job detects it, deletes our raw copy, invalidates any derived
  reference to it, and records the action in a deletion log.
- What we retain permanently: only de-identified aggregates — daily
  mention counts and daily sentiment averages per tracked product. No
  text, no usernames, no per-post rows.
- Authors: stored only as a SHA-256 hash, never in plaintext, and used
  solely to count distinct authors per day.
- Third-party processing: Reddit content is processed exclusively by our
  own code (keyword entity matching and a local VADER sentiment model)
  inside our own infrastructure. It is never sent to any external
  service, including LLM APIs. Our non-Reddit sources do use an LLM for
  classification; Reddit content is deliberately excluded from that path.
- Model training: Reddit content is never used as training input for any
  model, and we do not fine-tune, embed, or otherwise build models on it.
- Redistribution: no raw Reddit content is redistributed or displayed.
  The public site shows only aggregate statistics.

WHY NOT DEVVIT
We observe 5 public communities that we do not moderate. Devvit apps are
installed per-subreddit by that community's own moderators, so they
structurally cannot cover communities we do not run. We also store
derived time series in an external Postgres database and publish on an
off-Reddit website. Devvit's in-Reddit hosting and storage model does not
support this. We recognise this places us in the third-party data-consumer
category and have narrowed the request accordingly.

COMMERCIAL STATUS
Non-commercial. There is no monetisation of any kind today: no paywall,
no subscription, no advertising, no sponsorship, no data sales, and no
company operating this. If that ever changes we will stop non-commercial
collection and request commercial terms first.

TECHNICAL
- App type: web app (a scheduled server-side collector plus a public
  read-only website). Not a script app, not a personal-use tool.
- Auth: OAuth2 client credentials, read-only.
- User-Agent: <platform>:<app ID>:<version> (by /u/<username>), validated
  against that pattern in code — the client refuses to start if the
  User-Agent does not comply.
- Infrastructure: scheduled GitHub Actions job -> managed Postgres.
- Source code is public and auditable at
  github.com/bennykim/riivault (the collector, the 48h purge job, and the
  deletion handling can all be read directly).

WHAT CHANGED SINCE THE PREVIOUS REQUEST
1. Scope halved: 10 subreddits -> 5, all enumerated above.
2. Comment collection dropped from the request entirely. The earlier
   request mentioned comment trees; that was never implemented, and we
   are not asking for it.
3. Reddit content is now excluded from all third-party/LLM processing.
4. read_only is pinned in code and the User-Agent format is enforced at
   client construction, so neither can regress.
5. The public site no longer uses Reddit branding and no longer
   attributes any figure to Reddit. Until access is granted it shows only
   Hacker News, GitHub, and Product Hunt data, labelled as such.
6. The compliance pipeline is no longer a plan. It has been running
   continuously in production since 2026-07-08 against public non-Reddit
   sources (Hacker News, GitHub, and Product Hunt, plus npm / PyPI /
   Stack Exchange adoption metrics): 48-hour purge, aggregate-only
   retention, hashed authors. The same code paths would handle Reddit
   content, and they can be inspected in the public repository today.

CONTACT
Reddit username: /u/GainNo6885
Project: https://riivault.space
Source: https://github.com/bennykim/riivault
```

## Fill in before submitting

- [x] Reddit username set: `/u/GainNo6885`.
- [ ] Set `REDDIT_USER_AGENT` in the deployment to the compliant format,
      e.g. `web:riivault:v0.2 (by /u/GainNo6885)`. The checked-in default is
      a placeholder that fails validation on purpose.
- [ ] Confirm riivault.space has been free of Reddit branding for at
      least two weeks before submitting (corrected 2026-07-22).
- [ ] Select the non-commercial / developer category on the form.
