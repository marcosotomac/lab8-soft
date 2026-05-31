# Tasks: Implementacion Python Rewards

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900-1,300 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 tooling/domain → PR 2 API/persistence → PR 3 messaging/worker/docs |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Python tooling, package skeleton, domain rules, contract tests | PR 1 | Base slice; no broker required. |
| 2 | FastAPI endpoint, SQLAlchemy models/repositories, API/persistence tests | PR 2 | Depends on PR 1. |
| 3 | RabbitMQ adapters, worker flow, optional smoke test, README coverage docs | PR 3 | Depends on PR 2; stop after batch review. |

## Phase 1: Tooling and Package Foundation

- [x] 1.1 Create `pyproject.toml` with FastAPI, aio-pika, SQLAlchemy, pytest, coverage.py, ruff, mypy, and pytest/coverage config producing root `coverage.xml`.
- [x] 1.2 Create package skeleton and `__init__.py` files under `src/rewards/{domain,application,infrastructure,interfaces,config}` and matching `tests/` folders.
- [x] 1.3 Create `src/rewards/config/settings.py` with env-only `APP_ENV`, `DATABASE_URL`, `RABBITMQ_*`, and `REWARD_RATE` defaults safe for tests.

## Phase 2: Domain and Application Core

- [x] 2.1 Create `src/rewards/domain/models.py` for reward actions, events, rewards, duplicate outcomes, and validation-friendly value types.
- [x] 2.2 Create `src/rewards/domain/reward_rules.py` with configurable reward calculation and document the unresolved fixed-vs-rate rule.
- [x] 2.3 Create `src/rewards/application/ports.py` protocols for action repository, reward repository, event publisher, transaction boundary, and failure reporting.
- [x] 2.4 Create `src/rewards/application/use_cases.py` for `RegisterRewardAction` and `ProcessRewardEvent`, including idempotency and transient failure behavior.

## Phase 3: Persistence and API

- [x] 3.1 Create `src/rewards/infrastructure/db/models.py` with SQLAlchemy action/reward tables and unique `idempotency_key` constraints.
- [x] 3.2 Create `src/rewards/infrastructure/db/repositories.py` implementing repository ports with SQLite-compatible sessions.
- [x] 3.3 Create `src/rewards/interfaces/api/main.py` with `POST /reward-actions`, request/response schemas, validation errors, and duplicate-safe responses.
- [x] 3.4 Add tests in `tests/api/` and `tests/infrastructure/db/` for valid, invalid, duplicate, and persistence scenarios.

## Phase 4: Messaging and Worker

- [x] 4.1 Create `src/rewards/infrastructure/messaging/contracts.py` for `reward.action.registered` schema version 1 serialization and rejection of invalid contracts.
- [x] 4.2 Create `src/rewards/infrastructure/messaging/rabbitmq.py` declaring exchange/queue bindings and publisher/consumer ack, reject, and retry decisions.
- [x] 4.3 Create `src/rewards/interfaces/worker/main.py` that loads settings, opens broker/db resources, and runs the reward event consumer.
- [x] 4.4 Add tests in `tests/infrastructure/messaging/` and `tests/application/` for contract-valid, contract-invalid, duplicate, and persistence-unavailable events.

## Phase 5: Quality Evidence and Documentation

- [x] 5.1 Add `tests/domain/` coverage for reward rules and idempotency branches so coverage can target at least 85%.
- [x] 5.2 Update `README.md` with install, run API, run worker, test, and `coverage run -m pytest && coverage xml -o coverage.xml` commands without secrets.
- [x] 5.3 Review `sonar-project.properties` only for coverage path compatibility; do not print or hardcode secrets.
