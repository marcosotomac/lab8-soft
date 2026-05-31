# Reward Event Processing Specification

## Purpose

Event contracts, rewards, persistence, and failures.

## Requirements

### Requirement: Reward Event Contract

Reward events MUST contain event id, idempotency key, restaurant id, customer id, action type, occurrence time, and schema version. Invalid events MUST be rejected.

#### Scenario: Contract-compliant event consumed

- GIVEN an event with required fields and supported schema version
- WHEN the event is consumed
- THEN the system MUST process it for reward calculation

#### Scenario: Contract-invalid event consumed

- GIVEN an event with missing fields or unsupported schema version
- WHEN the event is consumed
- THEN the system MUST reject it without persisting a reward and expose the failure

### Requirement: Reward Calculation and Persistence

The system MUST calculate rewards from valid actions and persist one reward per idempotency key.

#### Scenario: Valid event rewards customer

- GIVEN a valid reward event
- WHEN processing succeeds
- THEN the system MUST persist customer, restaurant, action, amount, and source event data
- AND the event MUST NOT become new work again

#### Scenario: Duplicate event received

- GIVEN a reward has already been persisted for an idempotency key
- WHEN an event with the same idempotency key is consumed again
- THEN the system MUST keep the existing outcome and create no additional reward

### Requirement: Processing Failure Handling

The system MUST preserve valid events after transient failures and expose failure context.

#### Scenario: Persistence unavailable

- GIVEN a valid event and unavailable persistence
- WHEN processing is attempted
- THEN the system MUST avoid successful completion and keep event context for retry or diagnosis
