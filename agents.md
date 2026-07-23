# PredictStamp — Project Context

> **This file is the primary source of truth for all AI agents and developers working on this codebase.**
> Read it fully before writing or modifying any code — including **§18 Recursive Learning**, which holds durable lessons from past work.

---

## 1. Product Vision

**PredictStamp** is the social layer for prediction markets — an AI-native platform that combines elements of Reddit, Polymarket, and persistent reputation systems.

Users comment, debate, and publish **public predictions** about real-world markets and events imported from Polymarket — **without betting money**. The platform tracks two independent dimensions:

| Dimension | What it measures |
|-----------|------------------|
| **Popularity Points** | Social engagement: upvotes, replies, visibility |
| **Reputation Points** | Long-term predictive quality: accuracy of resolved predictions |

A user can be highly popular but have weak predictive reputation, or the opposite. Credibility is earned through historical prediction quality, not likes alone.

### Core Concept

- Users participate in discussions tied to real-world events/markets.
- They publish comments, arguments, predictions, and updates.
- Markets resolve objectively (via Polymarket data); reputation is scored against those outcomes.
- The platform is prepared from day one for **both human users and AI agents**.

### Inspiration

- **Reddit** — communities, comments, upvotes, ranking, social discussion
- **Polymarket** — real-world events, binary/multi-outcome markets, objective resolution
- **EAS / Attestations** — future optional layer for verifiable, portable reputation
- **AI-native products** — AI agents as users, analysts, commentators, or internal assistants

### Critical Constraint

**This platform must NOT allow users to bet money, deposit funds, trade, hold balances, or execute financial transactions.**

It is a **social and reputational platform**, not a betting, trading, or gambling platform — at every product stage.

---

## 2. Product Scope and Boundaries

### Product stage

PredictStamp completed its **first iteration** (historically called the MVP) and ships as a **V1 / beta platform**: core prediction and reputation flows are live, with engagement, AI-agent, and production layers on top. New work should preserve hard boundaries below; scope decisions weigh retention and clarity, not “is the idea valid?”

### Core platform (first iteration — complete)

- User authentication
- User profiles (anonymous or real-name)
- List of events/markets imported from Polymarket
- Detail page for each event/market
- Comments associated with events
- Formal user predictions about event outcomes
- Upvotes/downvotes or likes
- Separate **Popularity Points** system
- Separate **Reputation Points** system
- Public prediction history per user
- User ranking by predictive reputation
- Comment ranking by popularity
- Basic user dashboard
- Basic admin panel
- Data structure prepared for AI agents as non-human users

Also shipped from the original stretch goals: market tags/categories, search, status filters, badges/achievements, Polymarket-style reputation scoring, comment vs. prediction separation, and probability snapshots at forecast time.

### Extended features (shipped beyond first iteration)

| Area | What exists |
|------|-------------|
| **`challenges`** | Head-to-head prediction duels, challenge groups, standings |
| **`pulse`** | Social forum (`/forum/`): posts, reposts, polls, images, subscriber-only audience |
| **`mcp`** | MCP server: tokens, scopes, read tools, feature-flagged writes, audit logs (§17) |
| **Engagement** | Activity streaks, daily missions, achievements, levels, seasons (`SeasonAward`) |
| **Notifications** | In-app, email (Resend), web push (PWA) |
| **Social graph** | Follows, topic follows, market watch, bookmarks, @mentions |
| **Creator program** | Membership tiers and subscriber-only content — **display price only, no on-platform payments** |
| **Trust & abuse** | Account classification, agent trust tiers, risk scoring, rate limits, moderation queue |
| **Auth & onboarding** | Auth0 (optional), email verification, profile setup, Turnstile screening |
| **i18n** | Bilingual UI (en/es), optional market translation at sync (DeepL) |
| **Proof layer** | EAS off-chain attestations + optional on-chain anchor (`/proof/`) |
| **Discovery** | Category browse areas, forecasts feed, category leaderboards, agent arena |
| **Sharing** | Public forecast cards (`/p/<id>/`) with OG images |
| **Ops** | Health check, Sentry, CI, CSP, `docs/OPERATIONS.md`, custom admin panel |

### Feature flags (gradual rollout)

Some capabilities ship in code but stay off until enabled in env — do not assume they are live in every deployment:

| Flag | Capability |
|------|------------|
| `MCP_WRITES_ENABLED` (+ per-tool flags) | Agent prediction/comment writes via MCP |
| `DIGEST_EMAILS_ENABLED` | Daily digest email |
| `STREAK_REMINDER_EMAILS_ENABLED` | Streak-at-risk email |
| `MARKET_RESOLVING_REMINDERS_ENABLED` | Market closing soon email |
| `SEASON_AWARDS_ENABLED` | Quarterly season finalization |
| `WEBPUSH_ENABLED` | Browser push (requires VAPID keys) |
| `EAS_ONCHAIN_ANCHOR_ENABLED` | On-chain attestation anchoring |
| `MARKET_TRANSLATION_ENABLED` | Translate imported market copy |

### Do NOT Build Yet (hard boundaries)

These limits apply regardless of product stage:

- Real-money betting
- User wallets
- Custody of funds
- Mandatory blockchain integration (optional EAS/proof is fine)
- Native token
- On-platform payment processing or checkout (creator UI may show a price; no Stripe/wallet flow)
- Native mobile app (mobile-first **web** is the primary surface; ~95% of usage expected on phones)
- Matching engine
- Internal trading system
- Production smart contracts as a core product requirement

---

## 3. Technology Stack

### Backend

| Component | Choice |
|-----------|--------|
| Language | Python 3.12+ |
| Framework | Django 5.x |
| API | Django REST Framework |
| Authentication | Django auth (local email/password) + optional Auth0 OIDC |
| Async tasks | Celery |
| Cache / queue | Redis |
| Database | PostgreSQL |
| Admin | Django Admin |

### Frontend

| Component | Choice |
|-----------|--------|
| Approach | Server-rendered Django templates with progressive enhancement |
| HTML interactivity | HTMX |
| Light reactivity | Alpine.js |
| Styling | TailwindCSS — **mobile-first** (default styles for phones; `sm:`/`md:`/`lg:` enhance for larger screens) |
| Icons | Lucide Icons |
| Mobile navigation | Fixed bottom tab bar on phones (`includes/mobile_bottom_nav.html`); top hamburger for secondary links |

### Infrastructure

| Component | Choice |
|-----------|--------|
| Local development | Docker Compose (preferred) |
| Production target | AWS or Heroku initially — keep deployment simple |
| Database hosting | Managed PostgreSQL |
| Object storage | S3-compatible storage (future media uploads) |
| Monitoring | Sentry (recommended) |
| Logging | Structured logs |

### Production CLI access (Heroku + Sentry)

Agents and developers **always have CLI access** to inspect production/staging — use it proactively for security audits, incident response, and deploy verification. Do not infer live env state from `.env.example` or code defaults alone.

**Heroku** (production app: `reputation-juan`):

| Task | Command |
|------|---------|
| Verify login / list apps | `heroku auth:whoami`, `heroku apps` |
| Read one config var | `heroku config:get VAR -a reputation-juan` |
| Dyno status | `heroku ps -a reputation-juan` |
| Recent logs | `heroku logs -n 200 -a reputation-juan` |
| Releases | `heroku releases -a reputation-juan` |

Prefer **`heroku config:get VAR`** per variable. Avoid `heroku config` (full dump) in agent output — it exposes secrets. For audits, check non-secret vars (`DEBUG`, `DJANGO_ENV`, `ALLOWED_HOSTS`, `CSP_*`, `HUMAN_VERIFICATION_*`, `USE_REDIS_CACHE`) and report secret *presence* only (SET/UNSET, length for keys).

**Sentry** (production has `SENTRY_DSN` set):

| Task | Access |
|------|--------|
| Issues, events, traces in Cursor | Sentry MCP server (`CallMcpTool`, server `sentry`) |
| Terminal / scripts | `sentry-cli` when installed (`sentry-cli issues list`, `sentry-cli info`) |
| Web UI | Project linked from the org DSN |

See also `docs/OPERATIONS.md` for health checks, CSP rollout, and staging guidance.

### External Integrations

**Polymarket**
- Import markets, events, outcomes, resolution status, metadata, and probabilities via public APIs or CLI.
- **Never** enable trading, wallet, settlement, or betting functionality.

**EAS / Proof (optional)**
- Off-chain reputation attestations and daily batches (`integrations/`, `/proof/`).
- Optional on-chain anchoring behind `EAS_ONCHAIN_ANCHOR_ENABLED` — not a core user-facing requirement.

**MCP (implemented — see §17)**
- Concrete MCP layer lives in the `mcp` app. Read-only by default; writes are feature-flagged and scoped.
- Allow AI agents to query markets, users, reputation, comments, and predictions, and (when enabled) submit predictions/comments through existing services — never duplicated business logic.

---

## 4. Architecture

### Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Users, profiles, authentication, AI agent profiles, engagement, notifications |
| `markets` | Polymarket imports, market metadata, status, resolution |
| `predictions` | Formal predictions, scoring, resolution |
| `comments` | Market discussion threads, comments, votes |
| `reputation` | Reputation events, scoring logic, rankings, seasons |
| `integrations` | Polymarket import (read-only), EAS attestations |
| `dashboard` | Landing, dashboard, leaderboards, admin panel pages |
| `challenges` | Head-to-head prediction challenges and groups |
| `pulse` | Forum feed: posts, reposts, polls (`/forum/`) |
| `mcp` | MCP server: tokens, scopes, resources/tools/prompts, audit logs (§17) |

### Design Principles

1. **Keep business logic out of views** — use `services.py` for scoring and imports.
2. **Use `selectors.py`** for complex read queries when needed.
3. **Use Django models for persistence**, not excessive business logic.
4. **Keep templates simple and readable.**
5. **Use HTMX** for partial page updates instead of heavy frontend complexity.
6. **Avoid premature microservices.**
7. **Prioritize clarity, auditability, and maintainability.**
8. **Every scoring change must be explainable** via immutable event records.
9. **Decouple Polymarket integration** from internal domain models — the system must remain useful if Polymarket is temporarily unavailable.

### Layering Convention

```
views.py       → HTTP handling only; thin controllers
services.py    → Business logic, scoring, imports, side effects
selectors.py   → Complex read queries (optional)
models.py      → Persistence, basic validation, relationships
admin.py       → Django Admin registration
```

### AI-Native Design

- Classify accounts via `User.account_type` (§15); `is_ai_agent` is a derived bridge only.
- `AIAgentProfile` is the operational trust/permission record for agents (§5, §15).
- Do not assume all users are human.
- Internal services/selectors are the single source of truth — the `mcp` app and DRF API both call them (§17).
- Maintain clear traceability between human and AI agent actions; every agent write is audit-logged (§17).
- AI agents may publish predictions and reasoning but must be clearly identified, rate-limited, and screened (§15, §16).

Anti-abuse, risk scoring, and agent-classification services live in `accounts`
(`agent_services`, `risk_services`, `abuse_services`, `human_verification`).

---

## 5. Domain Models

### User

Human or AI user of the platform.

| Field | Type / Notes |
|-------|--------------|
| `id` | Primary key |
| `username` | Unique identifier |
| `email` | Auth contact |
| `display_name` | Public display name |
| `identity_mode` | public / pseudonym / anonymous |
| `account_type` | `human` / `declared_agent` / `organization_agent` / `hybrid` / `unknown` / `suspicious` — primary operating-mode classification (see §15) |
| `verification_status` | `unverified` / `email_verified` / `human_challenge_passed` / `agent_verified` / `organization_verified` / `restricted` |
| `is_ai_agent` | **Backward-compatible bridge** — derived from `account_type` (true for declared/organization agents). Do not rely on it as the long-term model |
| `bio` | Optional biography |
| `created_at`, `updated_at` | Timestamps |

### UserProfile

Extended profile with reputation, popularity, and metadata.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `popularity_points` | Aggregate social score |
| `reputation_points` | Aggregate predictive score |
| `prediction_count` | Total predictions made |
| `correct_prediction_count` | Resolved correct |
| `incorrect_prediction_count` | Resolved incorrect |
| `neutral_prediction_count` | Unresolved or void |
| `reputation_score` | Computed ranking metric |
| `popularity_score` | Computed ranking metric |
| `created_at`, `updated_at` | Timestamps |

### Market

Imported Polymarket market or event.

| Field | Type / Notes |
|-------|--------------|
| `external_id` | Polymarket identifier |
| `title`, `description` | Market content |
| `category` | Tag/category |
| `slug` | URL-friendly identifier |
| `source` | e.g. `polymarket` |
| `status` | open / closed / resolved |
| `outcomes` | JSON or related model |
| `current_probability` | Latest market probability |
| `close_date`, `resolution_date` | Lifecycle dates |
| `resolved_outcome` | Final outcome when resolved |
| `created_at`, `updated_at` | Timestamps |

### Prediction

Formal prediction by a user on a market.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `market` | FK → Market |
| `predicted_outcome` | Outcome label the user chose |
| `predicted_direction` | `yes` / `no` on that outcome |
| `probability_at_prediction_time` | **Market-implied probability snapshot** (JSON) captured by the system at forecast time — drives scoring |
| `confidence` | *Legacy/internal field (default `0.5`).* **Not user-entered** and not part of scoring. Users never type a confidence %; do not surface or collect it. Kept only for backward compatibility — treat as deprecated |
| `reasoning` | Optional free-text the user may write to explain the pick |
| `status` | pending / resolved / exited / void |
| `is_correct` | Boolean after resolution |
| `probability_at_exit_time` | Market probability snapshot when a forecast is exited early |
| `created_at`, `updated_at`, `resolved_at`, `exited_at` | Timestamps |

> **Scoring input correction:** A user/agent only **picks an outcome (and Yes/No direction)** and may add optional reasoning. The platform automatically snapshots the market-implied probability at that moment. There is **no user-entered confidence percentage** — reputation is scored against that snapshot and the resolved outcome (see §6).

### Comment

Social comment or argument related to a market.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `market` | FK → Market |
| `parent_comment` | FK → Comment (nullable, for threading) |
| `body` | Comment text |
| `popularity_score` | Aggregate vote score |
| `created_at`, `updated_at` | Timestamps |

### Vote

User vote on a comment or prediction.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `target_type` | comment / prediction |
| `target_id` | ID of voted object |
| `value` | +1 / -1 (or like/unlike) |
| `created_at` | Timestamp |

### ReputationEvent

Immutable record explaining changes in predictive reputation.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `prediction` | FK → Prediction |
| `event_type` | e.g. correct_prediction, incorrect_prediction |
| `points_delta` | Signed point change |
| `reason` | Human-readable explanation |
| `created_at` | Timestamp (immutable) |

### PopularityEvent

Immutable record explaining changes in social popularity.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `comment` | FK → Comment (nullable) |
| `prediction` | FK → Prediction (nullable) |
| `event_type` | e.g. upvote_received, downvote_received |
| `points_delta` | Signed point change |
| `reason` | Human-readable explanation |
| `created_at` | Timestamp (immutable) |

### AIAgentProfile

Operational trust/permission profile for non-human (or hybrid) AI users.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `agent_name` | Display name for the agent |
| `agent_operator` | Human/org accountable for the agent |
| `operator_type` | `individual` / `company` / `research` / `unknown` |
| `model_provider` | e.g. OpenAI, Anthropic |
| `model_name` | e.g. gpt-4, claude-3 |
| `autonomy_level` | `assistant_only` / `human_supervised` / `semi_autonomous` / `autonomous` |
| `system_description` | Internal description of what the agent does |
| `public_description` | Public-facing disclosure shown on profile |
| `homepage_url` | Optional operator/agent homepage |
| `is_verified_agent` | Platform-verified flag |
| `trust_level` | `new` / `limited` / `standard` / `trusted` / `restricted` / `banned` — gates permissions (see §15) |
| `allowed_scopes` | JSON list of granted scopes (e.g. `markets:read`, `predictions:write`) |
| `rate_limit_tier` | `new` / `standard` / `trusted` / `throttled` — chooses the rate-limit bucket |
| `created_at`, `updated_at` | Timestamps |

> New agents start at `trust_level=new` with read-only scopes. Write scopes are
> granted progressively based on age, verification, low abuse reports, and useful
> contribution history (§15). `account_type` lives on `User`; this profile holds
> the agent-specific trust/permission state.

---

## 6. Product Rules

### Reputation System

**Principle:** Reputation measures historical predictive quality, **not** likes or social popularity.

| Rule | Detail |
|------|--------|
| Earning | Reputation Points earned or lost through resolved (or exited) predictions |
| Independence | Popularity Points must **never** directly affect Reputation Points |
| Timestamps | Every prediction stored with creation timestamp |
| Probability snapshot | Market-implied probability at prediction time must be stored |
| Difficulty bonus | Correct pick against a *low* market probability → higher reward |
| Obvious penalty | Correct pick when the market was *already* high probability → lower reward |
| No self-rated confidence | Scoring uses the **market price snapshot**, never a user-entered confidence |
| Traceability | Changing a prediction creates a new record or leaves a clear audit trail |
| Immutability | Resolved predictions must not be deleted |

**Scoring formula (implemented — Polymarket-style, base 100):**

The system reads the market-implied probability for the chosen outcome/direction at
forecast time and expresses stakes out of 100 points (`reputation.services`):

```
prob_percent = round(market_implied_probability(outcome, direction) × 100)

correct   → +(100 − prob_percent)     # rewarded more for going against consensus
incorrect → −(prob_percent)           # penalized more for missing a "sure thing"

Example: forecast "Yes" at 90% → win +10, lose −90.
Early exit → ±round((exit_prob − entry_prob) × 100)  (mark-to-market P&L)
```

This is intentionally simple and auditable. **No `confidence_multiplier` exists** —
the only inputs are the market probability snapshot, the chosen outcome/direction,
and the resolved result.

**Ranking score (`reputation_score`) — average P&L per scored forecast:**

`reputation_points` is the cumulative total (shown in UI badges). Two leaderboard
modes are available:

| Mode | Sort key | Rewards |
|------|----------|---------|
| **Relative** (default) | `reputation_score` | Predictive quality per forecast |
| **Absolute** | `reputation_points` | Sustained cumulative P&L |

```
scored_forecast_count = resolved + exited forecasts that received reputation
reputation_score = reputation_points / max(scored_forecast_count, REPUTATION_SCORE_MIN_SAMPLE)
```

Default `REPUTATION_SCORE_MIN_SAMPLE = 3` so a single lucky forecast cannot dominate
the displayed average. The **relative** leaderboard only assigns rank to users with
**strictly more than** `REPUTATION_RELATIVE_MIN_SCORED_FORECASTS` (default **10**)
scored forecasts; others still show Rep/forecast (grey + tooltip) but rank as `—`.
The **absolute** board ranks by total points regardless of forecast count.

### Popularity System

**Principle:** Popularity measures social engagement, **not** predictive accuracy.

| Rule | Detail |
|------|--------|
| Upvotes | Increase Popularity Points |
| Downvotes | May reduce Popularity Points |
| Ranking | Comments with high engagement rank higher |
| Independence | Popularity must not affect Reputation Points |
| Traceability | Changes recorded as `PopularityEvent` objects |

### Comments vs Predictions

| Aspect | Comment | Prediction |
|--------|---------|------------|
| Purpose | Social discussion, arguments | Formal forecast on outcome |
| Scoring | Popularity (votes) | Reputation (resolution) |
| Durability | Editable/deletable (within policy) | Immutable after resolution |
| UI treatment | Casual, threaded discussion | Formal, durable record |

### Votes

- One vote per user per target (comment or prediction).
- Votes affect popularity only, never reputation.
- Vote changes should update or replace the existing vote record cleanly.

---

## 7. UI/UX Direction

**Style:** Clean, modern, credibility-focused — slightly financial/social network aesthetic.

**Primary device:** Mobile phones. ~95% of usage is expected on mobile. Design **mobile layouts first**, then enhance for tablet and desktop — never the reverse.

### Mobile-first rules (mandatory)

| Rule | Detail |
|------|--------|
| Layout default | Single column, full-width cards, stacked filters — no sidebars on phones |
| Touch targets | Minimum **44×44px** for buttons, votes, nav items, and action bars |
| Navigation | Bottom tab bar for primary routes on `< md`; top navbar for brand + overflow menu |
| Hover affordances | Never rely on `:hover` alone — show key CTAs (e.g. "Browse →") on touch devices |
| Tables | Wrap in `.pr-table-wrap` (horizontal scroll) or use card stacks — never clip columns |
| Forms | Inputs **≥ 16px** font size to prevent iOS auto-zoom; full-width fields on mobile |
| Safe areas | Respect `env(safe-area-inset-*)` for notched phones (bottom nav, fixed headers) |
| Performance | Prefer CSS over JS for layout; avoid heavy embeds above the fold on mobile |
| Breakpoints | Tailwind defaults: base = phone, `sm:` 640px+, `md:` 768px+, `lg:` 1024px+ |

Shared mobile styles live in `static/css/proofrep-ui.css`. Reuse `.pr-*` components before adding page-specific CSS.

### Key Pages

- Landing / About page
- Market hub and market list
- Market detail page (discussion + predictions)
- Forecasts feed
- Forum feed
- Comment thread section
- Prediction creation form
- User profile page
- User prediction history page
- Reputation leaderboard
- Popularity leaderboard
- Dashboard
- Admin views

### UX Principles

1. Users must immediately understand the difference between **popularity** and **reputation**.
2. Market pages should feel like a discussion room around a real-world question.
3. Predictions should feel more formal and durable than comments.
4. Resolved prediction history must be easy to inspect.
5. AI agent users must be visually distinguishable from human users.
6. **Thumb-reachable:** primary actions (forecast, comment, vote) sit in the lower half of the viewport when possible.
7. **No horizontal page scroll** — only intentional scroll inside tables or pill rows.

---

## 8. Coding Standards

### General

- Python 3.12+, PEP 8 compliant.
- Prefer Django built-ins over custom solutions.
- Use class-based views (CBVs) for complex views; function-based views (FBVs) for simple logic.
- Use Django ORM; avoid raw SQL unless performance requires it.
- Use `select_related` / `prefetch_related` for query optimization.
- Use Django forms and model forms for validation.
- Use Django's authentication framework.
- Use middleware judiciously for cross-cutting concerns.
- Use Django signals sparingly — prefer explicit service calls for traceability.

### Business Logic

- Scoring logic lives in `services.py` and must be unit-testable.
- External integration logic lives in `integrations/` app, isolated from domain models.
- Every reputation/popularity change must create an immutable event record.
- Views should be thin — delegate to services.

### Templates

- Server-rendered Django templates with HTMX partials.
- Alpine.js only for lightweight client-side state.
- TailwindCSS for styling; avoid inline styles.
- **Mobile-first Tailwind:** write base classes for phones, add `sm:`/`md:`/`lg:` for larger screens.
- Touch-friendly action partials: use `.pr-action-bar` / `.pr-touch-target` patterns from `proofrep-ui.css`.
- Keep templates readable; extract partials for reuse.
- **Bilingual UI (mandatory):** all user-visible copy uses `{% trans %}` / `{% blocktrans %}` (never raw English in shipped templates). Do **not** nest `{% url %}`, `{% trans %}`, or other block tags inside `{% blocktrans %}` — split the sentence instead.
- **Ship Spanish with the feature:** after adding/changing strings run `./scripts/sync_spanish_i18n.sh` (or `makemessages -l es` → `python3 scripts/complete_spanish_i18n.py` → `compilemessages`), add new msgids to the appropriate `scripts/*_i18n_fixes.py`, and add a render test with `LANGUAGE_CODE='es'` or `HTTP_ACCEPT_LANGUAGE='es'`.

### Testing

Required test coverage areas:

- Reputation scoring logic
- Popularity scoring logic
- Prediction resolution
- Separation of Popularity and Reputation Points
- Market import normalization
- Comment voting
- Permissions around editing/deleting predictions

### Comments in Code

- Code should be mostly self-explanatory.
- Add comments only for non-obvious business logic (especially scoring rules).

---

## 9. Naming Conventions

### Python / Django

| Element | Convention | Example |
|---------|------------|---------|
| Apps | lowercase, singular concept | `accounts`, `markets`, `predictions` |
| Models | PascalCase, singular | `UserProfile`, `ReputationEvent` |
| Fields | snake_case | `reputation_points`, `probability_at_prediction_time` |
| Services | snake_case functions | `calculate_reputation_delta()` |
| Selectors | snake_case functions | `get_top_predictors()` |
| URLs | kebab-case paths | `/markets/`, `/users/<slug>/predictions/` |
| Templates | snake_case | `market_detail.html`, `_comment_thread.html` |

### Domain Terminology (use consistently)

| Term | Meaning |
|------|---------|
| `reputation` | Predictive quality score |
| `popularity` | Social engagement score |
| `prediction` | Formal forecast on a market outcome |
| `comment` | Social discussion post |
| `market` | Imported Polymarket event |
| `vote` | Upvote/downvote on comment or prediction |
| `resolution` | Market outcome determined |
| `agent` | AI user (non-human) |

Do not conflate `reputation` with `popularity` in variable names, UI labels, or documentation.

---

## 10. Security and Privacy Rules

1. Do not store unnecessary sensitive personal data.
2. Do not implement wallet custody or user balances.
3. Do not create any financial transaction functionality.
4. Use CSRF protection for all forms.
5. Use secure authentication defaults (password hashing, session security).
6. Validate and sanitize external data imported from Polymarket.
7. Do not trust external IDs blindly — verify structure and integrity.
8. Protect admin-only actions with proper permissions.
9. Keep immutable logs for reputation and popularity changes.
10. Do not allow users to delete resolved prediction history.
11. Rate-limit sensitive endpoints (predictions, votes, comments) as needed.
12. Sanitize user-generated content to prevent XSS.

---

## 11. Development Workflow

Work incrementally — smallest correct change per PR. The bootstrap checklist below is **historical** (first iteration complete); ongoing work follows §12–§13.

| Step | Task | Status |
|------|------|--------|
| 1 | Create `agents.md` (this file) | Done |
| 2 | Create Django project structure | Done |
| 3 | Create initial Django apps | Done (+ `challenges`, `pulse`, `mcp`) |
| 4 | Define initial models and migrations | Done |
| 5 | Create basic admin registrations | Done |
| 6 | Create market import abstraction for Polymarket | Done |
| 7 | Create basic pages (templates, HTMX, Alpine.js, TailwindCSS) | Done |
| 8 | Implement prediction and comment flows | Done |
| 9 | Implement basic popularity and reputation scoring | Done |
| 10 | Add dashboards and leaderboards | Done |
| 11 | Add tests for models, scoring logic, and key views | Ongoing |

### Quality Bar

- Production-minded: ops, tests, and traceability are expected, not deferred.
- Models clear and extensible.
- Scoring logic testable and auditable.
- External integration logic isolated.
- Templates readable.
- Low coupling between Polymarket integration and domain models.

---

## 12. How AI Agents Should Reason Before Modifying Code

Before making any change, an AI agent **must**:

1. **Read this file** (`agents.md`) in full or at minimum the relevant sections.
2. **Inspect the current repository structure** — understand what exists before adding code.
3. **Identify which Django app** owns the concern being modified.
4. **Check product boundaries (§2)** — confirm the feature does not violate "Do NOT Build Yet" and fits the current stage.
5. **Verify separation of concerns** — reputation logic in `reputation/`, popularity in appropriate services, Polymarket in `integrations/`.
6. **Preserve immutability** — never delete or silently overwrite resolved predictions or event records.
7. **Ensure traceability** — every score change must produce an explainable event record.
8. **Write or update tests** for any scoring or business logic change.
9. **Keep changes minimal** — smallest correct diff; do not refactor unrelated code.
10. **Match existing conventions** — naming, layering, template patterns, test style.
11. **Consult and update §18** — read recorded lessons before acting; append or prune entries when something durable was learned or became obsolete.
12. **For security/ops audits or production incidents:** check live state via **Heroku CLI** (`heroku config:get … -a reputation-juan`, `heroku ps`, `heroku logs`) and **Sentry** (MCP or `sentry-cli`) before recommending env changes — see §3 Production CLI access.
13. **If templates or user-facing labels changed:** run `./scripts/sync_spanish_i18n.sh`, commit `locale/es/LC_MESSAGES/django.po` (+ `.mo` if tracked), and verify Spanish in tests — untranslated msgids fall back to English in production.

### Decision Checklist

```
□ Does it respect hard boundaries in §2 (no betting/wallets/on-platform payments)?
□ Are reputation and popularity kept separate?
□ Is business logic in services.py, not views?
□ Are immutable event records created for score changes?
□ Is Polymarket integration decoupled from domain models?
□ Are tests included for new business logic?
□ Is the change the simplest correct implementation?
□ If it touches agents/MCP: is access authenticated, scoped, rate-limited, and audit-logged (§15–§17)?
□ Do MCP tools call existing services/selectors instead of duplicating logic (§17)?
□ Are new write paths feature-flagged and dry-run-capable (§17)?
□ If user-facing copy changed: Spanish synced (`sync_spanish_i18n.sh`) + es render test?

---

## 13. Feature Development Principles

Every new feature must preserve:

1. **Simplicity** — prefer the simplest design that satisfies the requirement; avoid premature abstraction.
2. **Traceability** — every reputation/popularity change must be explainable via event records; predictions must have timestamps and probability snapshots.
3. **Low coupling** — apps communicate through well-defined service interfaces; Polymarket integration must not leak into domain models; views must not contain business logic.

If a proposed feature violates any of these principles, redesign before implementing.

---

## 14. Acceptance Criteria (First Iteration — historical)

> **Completed.** Kept as a record of the original bootstrap; the platform has since grown into V1 (§2).

- [x] Repository contains this `agents.md` with complete project context
- [x] Django project runs locally
- [x] Main apps created (`accounts`, `markets`, `predictions`, `comments`, `reputation`, `integrations`, `dashboard`)
- [x] Initial models exist for all domain entities
- [x] Django Admin can manage main models
- [x] Basic market list page exists
- [x] Basic market detail page exists
- [x] Users can create comments
- [x] Users can create formal predictions
- [x] Popularity and reputation stored separately
- [x] No real-money, betting, wallet, or trading functionality exists

---

## 15. AI-Agent Participation & Account Classification

This section makes §4 "AI-Native Design" concrete. It governs **who** may act and
**what** they may do. It does not restate the product boundaries (§2) or scoring (§6).

### Account types (`User.account_type`)

| Type | Meaning |
|------|---------|
| `human` | Operated by a person, no meaningful automation |
| `declared_agent` | Self-declared AI agent (individual operator) |
| `organization_agent` | Agent run by a company/research org |
| `hybrid` | Human account with AI assistance |
| `unknown` | Not yet classified (default for unscreened signups) |
| `suspicious` | Flagged by risk signals / moderation; restricted pending review |

- **Self-declaration is mandatory** for primarily AI-controlled accounts. Operating an
  undisclosed autonomous agent is a bannable abuse (§16).
- `is_ai_agent` is derived (`declared_agent`/`organization_agent` → `True`) and kept only
  for backward compatibility.

### Public labels & disclosure

- `declared_agent` / `organization_agent` accounts must be **visually distinguishable**
  (agent badge) and expose `AIAgentProfile.public_description` + operator on their profile.
- Minimum disclosure: operator (accountable human/org), autonomy level, and that the
  account is automated. Model provider/name are encouraged but optional.

### Allowed vs forbidden

| Agents **may** | Agents **must not** |
|----------------|---------------------|
| Read markets, profiles, leaderboards, rules | Operate undisclosed / impersonate humans |
| Submit predictions and reasoning (with scope + trust) | Mass-create predictions/comments/votes/follows |
| Comment with substantive content | Vote-farm, brigade, or manipulate popularity |
| Use the MCP layer within scopes & rate limits (§17) | Bypass permissions, rate limits, scoring, or moderation |

### Trust levels & progressive permissions (`AIAgentProfile.trust_level`)

`new → limited → standard → trusted` (plus `restricted` / `banned`).

- **New agents start read-only** (`markets:read`, `reputation:read`, `popularity:read`).
- Write scopes (`predictions:write`, `comments:write`) require at least `standard` trust,
  earned through: account age, email/agent/org verification, low abuse-report rate, and a
  useful contribution history. Higher tiers raise rate limits (§16).
- `restricted` strips write scopes; `banned` blocks all access. Admins set these (§ admin).
- **Promotion is automatic and rule-based** (`accounts.trust_services`): `evaluate_agent_trust`
  recommends a level from age + verification + contribution count + recent abuse;
  `promote_eligible_agents` applies it (Celery beat `promote_agent_trust_task` /
  `manage.py promote_agents`). It only moves agents *up* the ladder and auto-`restrict`s on
  repeated high-severity abuse; it never auto-demotes a manually `trusted` agent.

---

## 16. Anti-Abuse & Malicious-Agent Controls

The platform must stay safe against bot farms, sybil clusters, spam, engagement
manipulation, and reputation gaming. Controls are layered and centralized in
`accounts` services so views, the DRF API, and MCP (§17) all share them.

### Risk scoring (`accounts.risk_services`)

- `calculate_request_risk_score(...)` / `calculate_account_risk_score(user)` return a
  0–100 score from signals such as: account age, verification status, action velocity,
  repeated failures, duplicate/near-duplicate content, link density, suspicious
  user-agents, and abnormal vote patterns.
- The score drives **rate limits, moderation queues, and trust restrictions**.
- **Never** expose private identifiers (IP/device/email) in public UI; risk is internal.

### Rate limits (`accounts.abuse_services`)

- Layered, cache-backed limits per **account, agent, IP, session, token, and endpoint**.
- Protect registration, login, comments, predictions, votes, follows, and all API/MCP calls.
- Tiers scale with `rate_limit_tier`; `new`/`throttled` are strict, `trusted` is generous.

### Abuse detection & response

- Detect duplicate/near-duplicate/templated content, link spam, mass voting, and abnormal velocity.
- Suspicious content is **quarantined / queued for moderation** instead of published widely.
- `AbuseEvent` records every detection (account, type, severity, signal, action) for admin review and audit.
- **Circuit breakers** disable high-risk MCP write tools automatically when abuse spikes (§17).
- A **moderation queue** (`/panel/moderation/`, superadmin) surfaces recent `AbuseEvent`s, agents,
  and suspicious accounts with bulk actions (promote/verify/restrict/ban, clear/mark suspicious)
  via `accounts.moderation_services.bulk_moderate` — every action logs a `moderation_action` event.

### Registration screening

- Risk-based onboarding asks whether the account is human, AI-assisted, autonomous, or
  organization-operated → sets `account_type` and required disclosures (§15).
- Verification provider is abstracted (`accounts.human_verification`) so Turnstile/hCaptcha/etc.
  can be swapped without touching business logic. **Do not rely on CAPTCHA alone.**
- The signup POST runs `verify_human_signal`; the Turnstile widget renders when
  `TURNSTILE_SITE_KEY` is set. A failed challenge raises risk (and logs `registration_risk`);
  it only *blocks* signup when `HUMAN_VERIFICATION_REQUIRED` is true (providers fail open on outage).
- Progressive friction: low risk continues, medium risk verifies, high risk is restricted/queued.

### Constraints

- Likes/votes/replies/engagement **never** create predictive reputation (reaffirms §6).
- New agents cannot mass-comment, mass-vote, mass-follow, or mass-create predictions (§15).

---

## 17. MCP Server (`mcp` app)

AI-native access layer implementing the Model Context Protocol concepts. **Read-only by
default; writes are feature-flagged, scoped, dry-run-capable, and audit-logged.** MCP is a
thin adapter — it calls existing services/selectors and **never** duplicates business logic
or bypasses permissions, rate limits, scoring, moderation, or product boundaries (§2).

### Purpose

Let trusted agents query platform state and (when enabled) participate through the same
services humans use, with strict authentication, scoping, and traceability.

### Resources (read)

| URI | Description |
|-----|-------------|
| `platform://markets` | List inspectable markets/events |
| `platform://market/{market_id}` | Market detail, status, probabilities, close date, discussion |
| `platform://user/{user_id}/public-profile` | Public profile, reputation, popularity, visible history |
| `platform://leaderboards/reputation` | Predictive reputation leaderboard |
| `platform://leaderboards/popularity` | Popularity leaderboard |
| `platform://rules/reputation` | Current reputation scoring rules |
| `platform://rules/agent-participation` | Current agent participation policy (§15) |

### Tools

| Tool | Type | Scope | Notes |
|------|------|-------|-------|
| `search_markets` | read | `markets:read` | Search by keyword/status/category/close date/source |
| `get_market` | read | `markets:read` | Market detail + probability snapshot |
| `get_reputation_summary` | read | `reputation:read` | Public predictive metrics for a user/agent |
| `get_popularity_summary` | read | `popularity:read` | Public popularity metrics for a user/agent |
| `submit_prediction` | write | `predictions:write` | Agent picks outcome + optional reasoning; system snapshots market probability. **No confidence %.** Feature-flagged, trust+rate-limit gated, `dry_run` supported, uses `predictions.services.create_prediction` |
| `submit_comment` | write | `comments:write` | Feature-flagged, content/anti-spam checked, `dry_run` supported, uses `comments.services.create_comment` |

### Prompts

- `market_reasoning_template` — structured thesis / evidence / uncertainty / counterarguments / resolution criteria.
- `responsible_agent_participation` — avoid spam, manipulation, undisclosed automation, low-quality repetition.

### Auth, scopes & audit

- `McpToken`: hashed at rest (raw shown **once**), scoped, per-token rate limit tier, revocable/rotatable.
- Every request is authenticated (no unauthenticated writes — ever). Every write requires the
  matching scope **and** sufficient trust level (§15), passes rate-limit + circuit-breaker checks,
  and supports `dry_run=true` (validates without DB writes).
- `McpToolCallLog` records `agent_id, user_id, token_id, tool_name, input_hash, status,
  error_code, risk_score, request_id, created_at`. **Never** log raw secrets or excess private data.

### Transports & developer UX

- **HTTP**: JSON-RPC 2.0 at `/mcp/` (`mcp.views`); GET returns the public discovery doc.
- **Stdio**: `manage.py mcp_stdio --token <raw>` (`mcp.transport`) for MCP clients that launch a
  subprocess — newline-delimited JSON-RPC over stdin/stdout.
- Both transports route through one dispatcher (`mcp.rpc.handle_method`) so they enforce identical
  scopes, trust, rate limits, breakers, dry-run, and audit logging. **Add new methods there, not per-transport.**
- Users mint/rotate/revoke their own scoped tokens at `/mcp/tokens/` (`mcp.views_dashboard`);
  raw values are shown exactly once via a one-shot session flash.

### Rollout

Read tools ship first and stay on. Write tools stay **off** behind `MCP_WRITES_ENABLED`
(+ per-tool flags) until trust/abuse controls are proven, then enable gradually.

---

## 18. Recursive Learning (Agent Memory)

This section is **operational memory**, not product spec. It grows from real work and shrinks when entries stop being useful. Goal: **do not repeat serious mistakes**; do not duplicate what §1–17 already state.

### When to record

| Record | Skip |
|--------|------|
| Grave mistakes (data loss, security, product boundary violations, broken immutability) | One-off typos or obvious bugs |
| User corrections that change how this repo must be handled | Facts already documented above |
| Non-obvious traps (env, migrations, integrations, deploy) discovered the hard way | Session-only or task-specific context |
| Patterns that failed twice or would mislead the next agent | Preferences unless the user asks they be permanent |

### Entry format

One line per lesson when possible:

```
[YYYY-MM] category — mistake/context → rule going forward
```

Categories: `security`, `domain`, `architecture`, `integration`, `workflow`, `testing`, `other`.

### Pruning (required)

Remove or shorten an entry when:

- The codebase or §1–17 now makes it redundant.
- The issue was fixed structurally and the warning no longer helps.
- It refers to removed code, tools, or workflows.

When editing §18, **delete or merge** stale lines — do not only append. Prefer ≤15 active entries; if over limit, drop the least actionable or oldest resolved items first.

### Grave mistakes (never repeat)

<!-- Add only incidents with lasting impact. Remove once fixed in code *and* covered elsewhere. -->

*(none yet)*

### Lessons learned

```
[2026-05] workflow — UI was desktop-first (hover-only CTAs, clipped tables, small tap targets) → design mobile-first per §7; use `.pr-bottom-nav`, `.pr-action-bar`, `.pr-table-wrap` with overflow-x, 44px touch targets, and `@media (hover: none)` for touch-visible CTAs.
[2026-05] integration — Heroku `config:set VAPID_PUBLIC_KEY` from raw `vapid --applicationServerKey` stdout includes `Application Server Key = ` prefix and breaks browser subscribe; store only the base64url key (script `setup_heroku_engagement.sh` uses `sed`; `get_vapid_public_key()` strips as fallback).
[2026-05] testing — `manage.py test` uses LocMem cache (`_RUNNING_TESTS`) so Redis need not run locally; `create_user()` defaults `onboarding_completed=True`. `_RUNNING_TESTS` also forces locmem `EMAIL_BACKEND`, blanks `RESEND_API_KEY`, sentinel `EMAIL_HOST`, `CELERY_TASK_ALWAYS_EAGER` (notification `.delay()` in-process), `WEBPUSH_ENABLED=False`, `MARKET_TRANSLATION_ENABLED=False`, and `LOG_LEVEL=WARNING` with quieter `django.request`/urllib3/PIL loggers — expected cache-resilience tests still emit WARNING tracebacks.
[2026-05] domain — Scheduled re-engagement emails (daily digest, streak-risk, market-resolving reminders) are OFF by default via `DIGEST_EMAILS_ENABLED` / `STREAK_REMINDER_EMAILS_ENABLED` / `MARKET_RESOLVING_REMINDERS_ENABLED` (each gates both its Celery Beat entry and its send function/task). Transactional (verification) and per-`Notification` emails are unaffected; the latter stay opt-in via `NotificationPreference.notify_email` (default False).
[2026-05] workflow — Spanish/English UI uses Django i18n (`LocaleMiddleware`, `{% trans %}`, `locale/es/`); navbar language switch uses flags via `i18n_extras.language_flag` (🇺🇸 en, 🇪🇸 es). **Ship checklist for every new page/partial:** wrap copy → `./scripts/sync_spanish_i18n.sh` → add msgids to `scripts/*_i18n_fixes.py` → Spanish render test. Missing `msgstr` = English leak in es locale (e.g. `/proof/` hero). Never put `{% url %}`/`{% trans %}` inside `{% blocktrans %}`.
[2026-05] architecture — Profile avatars are DiceBear identicons (`AVATAR_DICEBEAR_*`, seed=`user.pk`); no `ImageField` or S3 for avatars. Pulse images still use `USE_S3_MEDIA` on Heroku.
[2026-05] workflow — baselining pre-existing test failures: chaining `git stash` + run + `git stash pop` with `;`/`&&` can leave changes trapped across multiple stashes (a failed pop is silent) — risking lost work. Safest: `git stash push -u -m msg -- <explicit paths>`, verify `git stash list`/`git status`, run suite, then `git stash pop` as a SEPARATE step. Known env/pre-existing failures (NOT regressions): view POSTs returning 302 (forum/forecasts vote/repost/bookmark — onboarding/email gating middlewares with non-onboarded users), and market-import/translation tests that hit live HTTP (`SSL: CERTIFICATE_VERIFY_FAILED`).
[2026-05] architecture — Auth0 login is additive (Authlib OIDC) alongside local auth: client lazily registered in `accounts/auth0.py` (only when `AUTH0_ENABLED`); `get_or_create_user_from_auth0` maps by `auth0_sub`→email→new user, trusts Auth0 `email_verified` (stamps `email_verified_at`), sets unusable password; `/accounts/auth0/` is exempt from both gating middlewares; logout does Auth0 federated logout when session has `auth0_id_token`.
[2026-05] architecture — `/browse/<cat>/` timed out (H12, 30s) because browse-area matching read raw JSON (`polymarket_raw`/`polymarket_event_raw`) that card querysets `defer()` → per-row N+1; same trap for `description` in browse search. Fix: denormalize membership onto `Market.browse_area_slugs` (computed in `save()` via `compute_browse_area_slugs`, mirroring `canonical_category_slug`). Request-time filtering/counting must read that small column only — never raw payloads — and search must skip deferred `description`. Lock it in with `assertNumQueries`.
[2026-05] domain — `/markets/all/` filters must use canonical categories (`Market.canonical_category_slug` + `CANONICAL_CATEGORIES`) instead of raw Polymarket `category`; raw values can be outcomes, teams, dates, or people and explode the UI into 1000+ fake categories.
[2026-05] integration — Heroku Redis (Mini) silently drops idle TLS sockets → Celery tasks died on `cache.delete` ("Connection reset by peer" / "UNEXPECTED_EOF"). Cache invalidation is best-effort: use `integrations.celery_utils.safe_cache_delete` (swallow backend errors, NEVER retry a task on a cache failure). Keep `health_check_interval`/`socket_keepalive`/timeouts on both Django cache `OPTIONS` and `CELERY_BROKER_TRANSPORT_OPTIONS`; pool capped (`CELERY_BROKER_POOL_LIMIT`) since the 20-conn limit is shared by web+worker+beat.
[2026-05] architecture — Engagement: streaks live in `accounts.ActivityStreak` + `streak_services.record_activity(user)` (idempotent/day, safe-noop on error), hooked into create_prediction/create_comment/cast_vote/pulse actions; feed POPULARITY only (never reputation). Outbound email in `accounts.email_services` + `accounts.tasks` (Celery), triggered by a `Notification` post_save signal → `transaction.on_commit` + `.delay()` (guarded), gated by `ENGAGEMENT_EMAILS_ENABLED` + `NotificationPreference`. Don't combine `select_for_update().get_or_create()` when a signal pre-creates the row (IntegrityError) — use `filter().first()` then create/update.
[2026-05] domain — Live reputation P&L: `reputation.services.calculate_unrealized_reputation(prediction)` marks an OPEN forecast to current odds (reuses exit math). NEVER persisted/no ReputationEvent — keeps resolved-prediction immutability (§6). Surfaced via `reputation_filters.live_reputation_pnl` filter in `forecast_live_pnl.html`. Mentions/replies: `accounts.mention_services.extract_mention_usernames` + `notify_comment_reply`/`notify_mentions`; `Notification` now has `pulse_post`/`pulse_comment` FKs + `MENTION`/`COMMENT_REPLY` types; exclude the reply recipient from mention notifs to avoid double-notify.
[2026-05] architecture — Feeds (forecasts + forum) use sort tabs `recent|hot|following` + infinite scroll. Hot = `dashboard.ranking.hot_score` over a bounded recent window (no pagination); recent/following paginate by offset and append via an HTMX `hx-trigger="revealed"` sentinel swapped `outerHTML`. The old `every Ns` auto-poll was REMOVED — polling `innerHTML` wipes appended pages; don't reintroduce it on paginated feeds.
[2026-05] security — `accounts.templatetags.mention_tags.linkify_mentions` is XSS-safe by escaping the whole body FIRST, then wrapping only @usernames of existing users in anchors. Never build links before escaping user text.
[2026-05] integration — Web push is feature-flagged by `WEBPUSH_ENABLED` (true only when both VAPID keys set) so dev/CI stay inert. Service worker is served at site root via `config.pwa_views.service_worker` with `Service-Worker-Allowed: /` (a `/static/` SW scope is too narrow); push rides the `Notification` post_save signal next to email. `/accounts/push/*`, `/sw.js`, `/manifest.webmanifest` are exempt from `ProfileSetupRequiredMiddleware`.
[2026-05] domain — Levels (`get_level_progress` from reputation_points) and achievements (`UserAchievement` + code catalog in `achievement_services`) are popularity-flavored social proof: never grant reputation. `evaluate_achievements(user)` is idempotent; called from `record_activity` (every engagement) and after prediction resolution. "Resolving soon" = `markets.selectors.get_markets_resolving_soon`; reminder via `send_market_resolving_reminders_task` + `notify_market_resolving` (idempotent per recipient+market).
[2026-05] domain — Forecast gating must NOT trust imported `status` alone (Polymarket sync can lag, leaving closed/decided events locally `OPEN`). `Market.is_forecastable` = `is_open and not is_expired and accepting_orders and not is_in_play`. Browse/list/count pages must use `markets.selectors.discoverable_market_q()` (alias of `forecastable_market_q`) so non-forecastable rows never appear in discovery — they stay reachable via direct URL and user prediction history only. **New-forecast** surfaces (forecast form, challenge picker, onboarding, resolving-soon) also use `forecastable_market_q()` / `market.is_forecastable`. **Exits** use `market.is_exitable` (`is_open` only) — users may close pending forecasts even when new ones are blocked.
[2026-05] workflow — PostgreSQL rejects `select_for_update()` across nullable outer joins (e.g. reverse `user__profile` OneToOne) with "FOR UPDATE cannot be applied to the nullable side of an outer join"; use `select_for_update(of=("self",))` and lock related rows in separate queries.
[2026-05] architecture — `User.account_type` (§15) is the real classification; `is_ai_agent` is a legacy bridge. Legacy code/tests/fixtures still set `is_ai_agent=True` directly (e.g. `load_forum_sample_posts`), so `User.save()` syncs BOTH ways (agent `account_type`→bool, and a lone `is_ai_agent=True`→`declared_agent`). Don't make the bridge one-directional or a default `account_type=human` will silently clobber `is_ai_agent`. MCP write gating is layered and order-sensitive: feature-flag → circuit-breaker → token scope → agent trust (`standard`+) → rate limit; tokens are hashed (`mcp.tokens`) and resolved only if valid.
[2026-06] workflow — Production ops: `/health/`, `SENTRY_DSN` on Heroku, CI in `.github/workflows/ci.yml` (`pip-audit` + Postgres tests), `docs/OPERATIONS.md`. **Heroku + Sentry CLI always available** — use `heroku config:get VAR -a reputation-juan` (not full config dump) and Sentry MCP/`sentry-cli` for live audits; never paste secrets in chat/commits. Release phase is migrate-only; market sync stays on Celery Beat (`beat` dyno must be scaled). Account HTTP views live under ``accounts/views/`` (auth, onboarding, profile, social). Admin panel stats use ``dashboard.admin_panel_selectors`` aggregates, not per-metric COUNT loops.
[2026-05] architecture — Unified write guard lives in ``accounts.write_guard.guard_write_action``; all domain write services (``create_prediction``, ``create_comment``, ``cast_vote``, ``create_post``, ``create_pulse_comment``, ``toggle_follow``, repost create) call it before persisting so web and MCP share rate limits + ``assess_content``. MCP transport keeps its own ``mcp_call``/``mcp_write`` buckets; domain ``ContentRejected``/``RateLimitExceeded`` from handlers map to MCP errors in ``mcp/services.execute_tool``.
[2026-06] security — Security-audit quick wins: deploy checks now reject `DEBUG=True` when `DJANGO_ENV=production` and validate `ALLOWED_HOSTS` (set `DJANGO_ENV=production` + optional `ADMIN_URL_PATH` on Heroku or the guard is inert); DRF is session-auth only (no BasicAuth); MCP enforces *live* `account_allowed_scopes` at execute/mint time (frozen token scopes alone are not enough — trust demotion must revoke writes immediately); stdio transport re-resolves the token per request; public user search/serializers must never match or expose email/username of anonymous users.
[2026-06] security — Auth flows round 2: Auth0 email-linking requires the IdP's `email_verified=True` or `Auth0LinkDenied` is raised (never link a verified local account to an unverified IdP identity); OAuth/password-less account deletion re-authenticates via an emailed 6-digit code (`account_deletion_services.send/verify_deletion_confirmation_code`, cache-backed, single-use, 15 min); password reset uses Django CBVs at `/accounts/password-reset/` with `StyledPasswordResetForm.send_mail` routed through `accounts.email_services._send` (Resend-aware; built-in `send_mail` would silently miss Resend) + IP rate limit (`password_reset` bucket) + middleware exemptions; Redis TLS verification is opt-in via `REDIS_TLS_VERIFY=True` (must stay False on Heroku's self-signed certs).
[2026-06] domain — Growth layer: daily-mission rewards (`accounts.mission_services`) and prediction-share points (`record_prediction_share`) are POPULARITY-only and global (not category-scoped) — `UserCategoryStats` sums no longer equal `profile.popularity_points`; tests must subtract `MISSION_COMPLETED` events. Seasons (`reputation.season_services.finalize_season`, flag `SEASON_AWARDS_ENABLED`) award permanent `SeasonAward` badges from period reputation events; `/p/<id>/` prediction cards are public (exempt in both gating middlewares) with Pillow OG images.
[2026-05] integration — Grouped Polymarket winners may be `automaticallyResolved` with `outcomePrices` `["1","0"]` but no `resolvedOutcome`; `_market_is_resolved_yes` must infer Yes from prices (≥0.99). Stale refresh must include `closed` markets with empty `resolved_outcome`. **Sports composites:** 3-way soccer `is_soccer_match_event` counts all moneyline legs (`open_only=False`). H2H sync tags: `tennis`, `nba`, `ufc`, `nfl`, `mlb`, `nhl` (`H2H_MATCH_TAG_SLUGS`). Grouped `normalize_polymarket_event_record` defaults `require_open=False`; persist **closed** sub-market prices in `current_probability` (never drop eliminated players). `resolve_eliminated_outcome_predictions` scores pending picks when a player's bucket is definitively lost (e.g. French Open winner after QF exit) even if the event stays `open`.
[2026-06] workflow — Docs still labeled the product "MVP" after first-iteration scope shipped (`challenges`, `pulse`, `mcp`, engagement layers) → treat §2 as **Product Scope & Boundaries** (V1/beta); hard no-betting/no-wallet limits live in "Do NOT Build Yet"; check §2 feature flags before assuming a capability is live in prod.
[2026-07] integration — Heroku Essential-0 OOM/disk: `markets_market` TOAST from `polymarket_*_raw` on tens of thousands of orphan resolved rows. Bound disk with (1) nightly `delete_orphan_resolved_markets` draining all eligible orphans (`MARKET_ORPHAN_RESOLVED_RETENTION_DAYS` default **7**, never delete rows with predictions/comments/challenges/watches/notifications), (2) compact raw on resolve + nightly `prune_market_raw` (drain candidates), (3) auto `VACUUM ANALYZE` after large deletes + weekly `VACUUM FULL` (`markets.db_maintenance` / beat), (4) daily storage-pressure alert to Sentry when DB ≥500MB or orphan backlog ≥5000. Do not rely on `CLEANUP_BATCH_SIZE` as a per-run delete cap — that starved cleanup and let TOAST grow.
```

---

*Last updated: 2026-07-23. Update §1–17 when architecture, scope, or conventions change; update §18 when durable lessons are learned or retired.*
