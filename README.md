# Rewards — Arquitectura Clean/Hexagonal con mensajería

Servicio de recompensas orientado a eventos. La API registra la cena y publica el evento
`reward.action.registered`; el worker lo consume, calcula la recompensa y la persiste.

- **Arquitectura:** Clean/Hexagonal (domain → application → interfaces/infrastructure)
- **Broker:** RabbitMQ (`rewards.events` / `rewards.processing`)
- **Calidad:** tests + coverage + Sonar

Documento de arquitectura y casos de uso: [`docs/architecture.md`](docs/architecture.md).

## Quick path

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Ejecutar API (producer)

```bash
DATABASE_URL="sqlite+pysqlite:///./rewards.db" \
REWARD_EVENT_PUBLISHER="rabbitmq" \
RABBITMQ_URL="amqp://..." \
uvicorn rewards.interfaces.api.main:create_app --factory --reload
```


## Ejecutar worker (consumer)

```bash
DATABASE_URL="sqlite+pysqlite:///./rewards.db" \
RABBITMQ_URL="amqp://..." \
python -m rewards.interfaces.worker.main
```

## Pruebas y cobertura

```bash
python -m pytest
coverage run -m pytest && coverage xml -o coverage.xml
```

`coverage.xml` se genera en la raíz y es el reporte que usa Sonar.

## Sonar

```bash
sonar-scanner
```
