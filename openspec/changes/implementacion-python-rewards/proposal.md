# Proposal: Implementacion Python Rewards

## Intent

Build a Python-first, event-driven restaurant rewards system with clear producer/consumer boundaries, automated tests, and Sonar-compatible coverage.

## Scope

### In Scope
- Python project setup with dependencies, tests, coverage, and config.
- FastAPI restaurant API that validates requests and publishes reward events.
- RabbitMQ messaging through `aio-pika`, using environment-driven broker settings.
- Consumer/use case that calculates rewards and persists results.
- Persistence layer for restaurant/customer/reward data.
- Tests for domain logic, API behavior, messaging seams, and Sonar `coverage.xml`.

### Out of Scope
- Production deployment, scaling, observability, or cloud infra.
- Real external provider integration beyond documented RabbitMQ/configuration needs.
- UI work unless assignment documents explicitly require it.

## Capabilities

### New Capabilities
- `restaurant-rewards-api`: FastAPI endpoints that accept restaurant reward actions and publish domain events.
- `reward-event-processing`: RabbitMQ event contracts, producer/consumer flow, reward calculation, idempotent persistence, and failure handling.
- `python-quality-tooling`: Python test, coverage, and Sonar-compatible quality workflow.

### Modified Capabilities
- None

## Approach

Use a small Clean/Hexagonal structure: domain models and reward rules at the center, application use cases around them, adapters for FastAPI, RabbitMQ (`aio-pika`), SQLAlchemy persistence, and env-based settings. RabbitMQ is selected for lab simplicity and local operability. Add pytest and coverage.py for review evidence.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | Python dependencies, tooling, test/coverage config. |
| `src/` | New | API, domain, use cases, messaging, persistence, settings. |
| `tests/` | New | Unit and integration-style tests. |
| `sonar-project.properties` | Modified | Align coverage report path if needed; do not expose credentials. |
| `README.md` / docs | Modified | Local run/test instructions if required. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Broker unavailable during tests | Med | Keep domain tests broker-free; use adapter seams and optional integration checks. |
| Event contract ambiguity | Med | Specify payloads and test producer/consumer serialization. |
| Secret leakage from existing files | Med | Read config cautiously, use env vars, and avoid printing credential-like values. |

## Rollback Plan

Revert new Python source, tests, and project config. If broker behavior fails, keep reward use cases runnable through direct tests while adapters are corrected.

## Dependencies

- Python, FastAPI, RabbitMQ, `aio-pika`, SQLAlchemy, pytest, coverage.py.
- Environment variables for broker and persistence configuration.

## Success Criteria

- [ ] Restaurant API publishes valid reward events without hardcoded credentials.
- [ ] Consumer calculates and persists rewards from RabbitMQ messages.
- [ ] Tests run locally and generate `coverage.xml` for Sonar.
- [ ] Implementation is split into reviewable batches with checkpoint pauses.
