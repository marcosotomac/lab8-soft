# Python Quality Tooling Specification

## Purpose

Tests, coverage, and Sonar evidence.

## Requirements

### Requirement: Test Execution Workflow

The project MUST provide a documented test command covering reward rules, API behavior, event seams, and persistence without secrets.

#### Scenario: Tests run locally

- GIVEN dependencies and non-secret local configuration are available
- WHEN the documented test command is executed
- THEN the suite MUST run to completion and identify failures

#### Scenario: Secrets are absent

- GIVEN credential-like variables are absent
- WHEN tests are executed
- THEN tests MUST NOT print, require, or hardcode secrets
- AND external-service tests SHOULD use local seams

### Requirement: Coverage Evidence

The project MUST produce Sonar-compatible `coverage.xml` and SHOULD target at least 85 percent coverage.

#### Scenario: Coverage report generated

- GIVEN the automated tests pass
- WHEN the documented coverage command is executed
- THEN root `coverage.xml` MUST be produced for Sonar Python coverage import

#### Scenario: Coverage below target

- GIVEN generated coverage is below target
- WHEN quality evidence is reviewed
- THEN the result SHOULD require remediation before final delivery
