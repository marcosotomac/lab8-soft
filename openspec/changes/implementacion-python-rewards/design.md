# Design: Implementacion Python Rewards

## Technical Approach

Create a new Python service using Clean/Hexagonal architecture: `src/rewards/domain` owns reward rules and entities, `src/rewards/application` owns use cases and ports, `src/rewards/infrastructure` adapts RabbitMQ and SQLAlchemy, and `src/rewards/interfaces` exposes FastAPI and the worker entrypoint. This satisfies the assignment focus on cohesion/coupling while matching the specs for API submission, event processing, idempotency, and Sonar-compatible quality evidence.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Application stack | FastAPI + aio-pika + SQLAlchemy + pytest/coverage.py | Flask, Django, Kafka, ActiveMQ | FastAPI gives validation and OpenAPI with little coupling; RabbitMQ/aio-pika matches the selected broker and lab complexity; SQLAlchemy keeps persistence behind repositories. |
| Architecture boundaries | Domain/application/infrastructure/interfaces packages | Flat scripts or framework-first structure | Keeps reward rules broker/API/database independent, making tests fast and proving high cohesion/low coupling. |
| Idempotency | Unique `idempotency_key` in actions/rewards repositories | In-memory dedupe or broker-only dedupe | Database uniqueness survives process restarts and satisfies duplicate API/event requirements. |
| Configuration | Environment variables read by `src/rewards/config/settings.py` | Hardcoded broker URLs or checked-in secrets | Meets security constraints and avoids leaking broker/Sonar credentials. |

## Data Flow

```text
Restaurant client
  -> FastAPI /reward-actions
  -> RegisterRewardAction use case
  -> RewardActionRepository checks idempotency
  -> RewardEventPublisher publishes reward.action.registered
  -> RabbitMQ exchange rewards.events / queue rewards.processing
  -> Worker consumes event
  -> ProcessRewardEvent use case
  -> RewardRepository persists one reward per idempotency key
```

Transient persistence failures are not acknowledged by the worker, leaving the message eligible for broker retry. Contract-invalid events are rejected, logged with failure context, and not persisted as rewards.

## File Changes

| File | Action | Description |
|---|---|---|
| `pyproject.toml` | Create | Python dependencies and tool config for pytest, coverage, ruff, and mypy. |
| `src/rewards/domain/models.py` | Create | Domain entities/value objects for reward actions, events, and rewards. |
| `src/rewards/domain/reward_rules.py` | Create | Pure reward calculation policy. |
| `src/rewards/application/ports.py` | Create | Repository and publisher protocols. |
| `src/rewards/application/use_cases.py` | Create | Register and process reward workflows with idempotency. |
| `src/rewards/infrastructure/db/models.py` | Create | SQLAlchemy tables and unique constraints. |
| `src/rewards/infrastructure/db/repositories.py` | Create | SQLAlchemy repository adapters. |
| `src/rewards/infrastructure/messaging/contracts.py` | Create | Event payload validation/serialization. |
| `src/rewards/infrastructure/messaging/rabbitmq.py` | Create | aio-pika publisher/consumer adapter and topology declarations. |
| `src/rewards/interfaces/api/main.py` | Create | FastAPI app and request/response schemas. |
| `src/rewards/interfaces/worker/main.py` | Create | Consumer entrypoint. |
| `src/rewards/config/settings.py` | Create | Env-based settings. |
| `tests/` | Create | Unit, API, messaging-seam, and persistence tests. |
| `README.md` | Modify | Document local run/test/coverage commands and architecture. |

## Interfaces / Contracts

API: `POST /reward-actions` accepts `restaurant_id`, `customer_id`, `action_type`, `occurred_at`, `amount`, `idempotency_key`; returns accepted or duplicate-safe status without exposing broker internals.

Event `reward.action.registered` version `1`:

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "idempotency_key": "string",
  "restaurant_id": "string",
  "customer_id": "string",
  "action_type": "dinner_registered",
  "occurred_at": "ISO-8601 datetime",
  "amount": 120.50
}
```

Environment variables: `APP_ENV`, `DATABASE_URL`, `RABBITMQ_URL`, `RABBITMQ_EXCHANGE`, `RABBITMQ_REWARD_QUEUE`, `REWARD_RATE`. Tests use non-secret local defaults or injected fakes.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Reward rules, event contract validation, idempotency branching | pytest with pure domain objects and fake ports. |
| Integration-style | FastAPI validation and SQLAlchemy repositories | TestClient and temporary SQLite database. |
| Messaging seam | Publisher serialization, consumer ack/retry decisions | Fake aio-pika channel/message objects; optional RabbitMQ smoke test only when env enables it. |
| Quality | Sonar coverage evidence | `coverage run -m pytest && coverage xml -o coverage.xml`; target at least 85%. |

## Migration / Rollout

No migration required because no executable stack exists yet. Create the Python app in reviewable batches and stop after each implementation batch for user review.

## Open Questions

- [ ] Should reward calculation be fixed points/cashback for the assignment, or configurable only through `REWARD_RATE`?
- [ ] Should the optional notification event from the README be implemented now or documented as out of scope?
