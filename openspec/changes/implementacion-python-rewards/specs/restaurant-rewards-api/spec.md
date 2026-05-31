# Restaurant Rewards API Specification

## Purpose

Restaurant reward registration behavior.

## Requirements

### Requirement: Register Reward Action

The system MUST accept actions with restaurant, customer, action, occurrence time, and idempotency key, then expose them for reward processing.

#### Scenario: Valid action accepted

- GIVEN a request with all required fields
- WHEN the client submits the reward action
- THEN the system MUST acknowledge it and expose it for reward processing

#### Scenario: Invalid action rejected

- GIVEN a request with missing or invalid fields
- WHEN the client submits the reward action
- THEN the system MUST reject it with validation details and withhold it from processing

### Requirement: Duplicate Submission Handling

The system MUST treat repeated idempotency keys as duplicates and SHALL NOT create multiple processable actions.

#### Scenario: Duplicate action submitted

- GIVEN a reward action was accepted for an idempotency key
- WHEN the same idempotency key is submitted again
- THEN the system MUST return a duplicate-safe response and expose only one processable action
