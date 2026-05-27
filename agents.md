# ProofRep — Proof of Reputation — Project Context

> **This file is the primary source of truth for all AI agents and developers working on this codebase.**
> Read it fully before writing or modifying any code — including **§15 Recursive Learning**, which holds durable lessons from past work.

---

## 1. Product Vision

**ProofRep** (Proof of Reputation) is the social layer for prediction markets — an AI-native platform that combines elements of Reddit, Polymarket, and persistent reputation systems.

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

The MVP is a **social and reputational platform**, not a betting, trading, or gambling platform.

---

## 2. MVP Scope and Boundaries

### Must Have (MVP)

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

### Should Have (MVP stretch)

- Market tags or categories
- Event search
- Filters by status: open, closed, resolved
- Basic badge system
- Reputation model rewarding early correct predictions and penalizing incorrect ones
- Clear separation between general comments and formal predictions
- Snapshots of Polymarket probabilities at the time of each prediction

### Do NOT Build Yet

- Real-money betting
- User wallets
- Custody of funds
- Mandatory blockchain integration
- Native token
- Payment marketplace
- Complex monetization system
- Native mobile app
- Matching engine
- Internal trading system
- Production smart contracts

---

## 3. Technology Stack

### Backend

| Component | Choice |
|-----------|--------|
| Language | Python 3.12+ |
| Framework | Django 5.x |
| API | Django REST Framework |
| Authentication | Django auth initially; future compatibility for Auth0, OAuth, social login |
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
| Styling | TailwindCSS |
| Icons | Lucide Icons |

### Infrastructure

| Component | Choice |
|-----------|--------|
| Local development | Docker Compose (preferred) |
| Production target | AWS or Heroku initially — keep deployment simple |
| Database hosting | Managed PostgreSQL |
| Object storage | S3-compatible storage (future media uploads) |
| Monitoring | Sentry (recommended) |
| Logging | Structured logs |

### External Integrations

**Polymarket**
- Import markets, events, outcomes, resolution status, metadata, and probabilities via public APIs or CLI.
- **Never** enable trading, wallet, settlement, or betting functionality.

**EAS (future)**
- Optional future integration for reputation attestations, proofs, or hashes.
- Do not implement blockchain in the MVP unless explicitly requested.

**MCP (future)**
- Architecture must be AI-native and compatible with future MCP integrations.
- Allow AI agents to query markets, users, reputation, comments, and predictions.

---

## 4. Architecture

### Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Users, profiles, authentication, AI agent profiles |
| `markets` | Polymarket imports, market metadata, status, resolution |
| `predictions` | Formal predictions, scoring, resolution |
| `comments` | Discussion threads, comments, votes |
| `reputation` | Reputation events, scoring logic, rankings |
| `integrations` | External integrations (Polymarket) |
| `dashboard` | User dashboard and platform pages |

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

- Add `is_ai_agent` field to users or profiles.
- Create extensible `AIAgentProfile` structure.
- Do not assume all users are human.
- Prepare clean internal APIs for future agent access.
- Design with future MCP compatibility in mind.
- Maintain clear traceability between human and AI agent actions.
- AI agents may publish predictions and reasoning but must be clearly identified.

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
| `is_anonymous` | Whether profile is anonymous |
| `is_ai_agent` | Whether user is an AI agent |
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
| `predicted_outcome` | Chosen outcome |
| `confidence` | User-stated confidence (affects scoring) |
| `probability_at_prediction_time` | Snapshot of market probability |
| `reasoning` | Optional explanation |
| `status` | pending / resolved / void |
| `is_correct` | Boolean after resolution |
| `created_at`, `updated_at`, `resolved_at` | Timestamps |

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

Optional profile for non-human AI users.

| Field | Type / Notes |
|-------|--------------|
| `user` | FK → User |
| `agent_name` | Display name for the agent |
| `model_provider` | e.g. OpenAI, Anthropic |
| `model_name` | e.g. gpt-4, claude-3 |
| `system_description` | What the agent does |
| `is_verified_agent` | Platform-verified flag |
| `created_at`, `updated_at` | Timestamps |

---

## 6. Product Rules

### Reputation System

**Principle:** Reputation measures historical predictive quality, **not** likes or social popularity.

| Rule | Detail |
|------|--------|
| Earning | Reputation Points earned or lost through resolved predictions |
| Independence | Popularity Points must **never** directly affect Reputation Points |
| Timestamps | Every prediction stored with creation timestamp |
| Probability snapshot | Market probability at prediction time must be stored |
| Difficulty bonus | Correct prediction against low market probability → higher reward |
| Obvious penalty | Correct prediction when market already high probability → lower reward |
| Traceability | Changing a prediction creates a new record or leaves clear audit trail |
| Immutability | Resolved predictions must not be deleted |

**Initial scoring formula (keep simple and auditable):**

```
correct:   base_points × difficulty_multiplier × confidence_multiplier
incorrect: -base_penalty × confidence_multiplier

difficulty_multiplier  → higher when prediction was against market consensus
confidence_multiplier  → higher confidence increases both reward and penalty
```

Do not over-engineer the formula in MVP. Make it easy to audit and test.

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

### Key Pages

- Landing page
- Market list page
- Market detail page (discussion + predictions)
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
- Keep templates readable; extract partials for reuse.

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

Work incrementally. Do not generate the entire application in one step.

| Step | Task |
|------|------|
| 1 | Create `agents.md` (this file) |
| 2 | Create Django project structure |
| 3 | Create initial Django apps |
| 4 | Define initial models and migrations |
| 5 | Create basic admin registrations |
| 6 | Create market import abstraction for Polymarket |
| 7 | Create basic pages (templates, HTMX, Alpine.js, TailwindCSS) |
| 8 | Implement prediction and comment flows |
| 9 | Implement basic popularity and reputation scoring |
| 10 | Add dashboards and leaderboards |
| 11 | Add tests for models, scoring logic, and key views |

### Quality Bar

- Production-minded but MVP-friendly.
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
4. **Check MVP boundaries** — confirm the feature is in scope and not in the "Do NOT Build Yet" list.
5. **Verify separation of concerns** — reputation logic in `reputation/`, popularity in appropriate services, Polymarket in `integrations/`.
6. **Preserve immutability** — never delete or silently overwrite resolved predictions or event records.
7. **Ensure traceability** — every score change must produce an explainable event record.
8. **Write or update tests** for any scoring or business logic change.
9. **Keep changes minimal** — smallest correct diff; do not refactor unrelated code.
10. **Match existing conventions** — naming, layering, template patterns, test style.
11. **Consult and update §15** — read recorded lessons before acting; append or prune entries when something durable was learned or became obsolete.

### Decision Checklist

```
□ Is this feature in MVP scope?
□ Does it avoid betting/wallet/trading functionality?
□ Are reputation and popularity kept separate?
□ Is business logic in services.py, not views?
□ Are immutable event records created for score changes?
□ Is Polymarket integration decoupled from domain models?
□ Are tests included for new business logic?
□ Is the change the simplest correct implementation?
```

---

## 13. Feature Development Principles

Every new feature must preserve:

1. **Simplicity** — prefer the simplest design that satisfies the requirement; avoid premature abstraction.
2. **Traceability** — every reputation/popularity change must be explainable via event records; predictions must have timestamps and probability snapshots.
3. **Low coupling** — apps communicate through well-defined service interfaces; Polymarket integration must not leak into domain models; views must not contain business logic.

If a proposed feature violates any of these principles, redesign before implementing.

---

## 14. Acceptance Criteria (First Iteration)

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

## 15. Recursive Learning (Agent Memory)

This section is **operational memory**, not product spec. It grows from real work and shrinks when entries stop being useful. Goal: **do not repeat serious mistakes**; do not duplicate what §1–14 already state.

### When to record

| Record | Skip |
|--------|------|
| Grave mistakes (data loss, security, MVP boundary violations, broken immutability) | One-off typos or obvious bugs |
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

- The codebase or §1–14 now makes it redundant.
- The issue was fixed structurally and the warning no longer helps.
- It refers to removed code, tools, or workflows.

When editing §15, **delete or merge** stale lines — do not only append. Prefer ≤15 active entries; if over limit, drop the least actionable or oldest resolved items first.

### Grave mistakes (never repeat)

<!-- Add only incidents with lasting impact. Remove once fixed in code *and* covered elsewhere. -->

*(none yet)*

### Lessons learned

<!-- Durable, project-specific knowledge not covered above. Review and prune each time you touch this file. -->

*(none yet)*

---

*Last updated: 2026-05-27. Update §1–14 when architecture, scope, or conventions change; update §15 when durable lessons are learned or retired.*
