# UTEC — CS3081 Ingeniería de Software

**Departamento de Ciencia de la Computación**  
**CS3081 - Ingeniería de Software**  
**Tarea 8**  
**Fecha:** 16/05/2026  

# Buen diseño - Cohesión y Acoplamiento

**Profesor:** Teófilo Chambilla

## Objetivo

La presente tarea tiene como objetivo que el estudiante diseñe e implemente una solución de software aplicando principios de buen diseño, arquitectura de software y calidad de código. La solución deberá evidenciar modularidad, abstracción, bajo acoplamiento y alta cohesión, considerando un escenario basado en mensajería y procesamiento de eventos.

- Diseñar una solución de software que soporte los atributos de modularidad, abstracción, bajo acoplamiento y alta cohesión.
- Implementar la solución utilizando un patrón arquitectónico adecuado, como Arquitectura Hexagonal, Clean Architecture, Microservicios o Arquitectura Orientada a Eventos.
- Modelar el sistema mediante un Diagrama de Casos de Uso, identificando actores, funcionalidades principales y relaciones relevantes.
- Incorporar un mecanismo de mensajería utilizando RabbitMQ, Apache Kafka o ActiveMQ, según el enfoque técnico elegido por el equipo.
- Aplicar buenas prácticas de calidad de software, incluyendo pruebas automatizadas, análisis estático de código y control de duplicidad.

## Introducción

Ir a un restaurante suele representar un gasto mayor que cocinar en casa; sin embargo, los programas de recompensas y fidelización permiten que los clientes obtengan beneficios por sus consumos. Estos programas ofrecen acumulación de puntos, reembolsos o beneficios especiales cada vez que un cliente consume en restaurantes afiliados.

Por ejemplo, Jesús desea ahorrar dinero para la educación de sus hijos. Cada vez que realiza una cena en un restaurante participante, una parte del consumo es transformada en puntos o recompensas que son abonadas a su cuenta personal.

Actualmente, debido a la necesidad de procesar grandes volúmenes de transacciones en tiempo real, las empresas utilizan arquitecturas orientadas a eventos y plataformas de mensajería como RabbitMQ, Apache Kafka o ActiveMQ, permitiendo desacoplar los sistemas y mejorar la escalabilidad, disponibilidad y resiliencia de las aplicaciones.

Implemente el proceso indicado en la Figura 1 considerando una arquitectura basada en mensajería y eventos:

- El restaurante registra la información de la cena realizada por el cliente.
- El sistema del restaurante procesa internamente la transacción y publica un mensaje en un Broker de Mensajería (RabbitMQ, Apache Kafka o ActiveMQ) con la siguiente información:
  - Monto consumido.
  - Número de tarjeta del cliente.
  - Código del restaurante afiliado.
  - Fecha y hora de la transacción.
- El Broker de Mensajería se encarga de la administración de colas, tópicos o eventos, garantizando la entrega de mensajes entre productores y consumidores.
- Un microservicio consumidor correspondiente al sistema de recompensas recibe el mensaje y calcula automáticamente los puntos, cashback o beneficios asociados al cliente.
- El sistema actualiza la cuenta de recompensas del cliente.
- Opcionalmente, el sistema puede publicar un nuevo evento para el envío de una notificación por correo electrónico, SMS o aplicación móvil indicando que la recompensa fue procesada exitosamente.

## Consideraciones Técnicas

El diseño debe considerar principios de:

- Alta cohesión.
- Bajo acoplamiento.
- Modularidad.
- Escalabilidad.
- Arquitectura orientada a eventos.

Asimismo, se recomienda aplicar algún patrón arquitectónico como:

- Arquitectura Hexagonal.
- Microservicios.
- Event-Driven Architecture (EDA).
- Clean Architecture.

## Entregable

El proyecto deberá ser analizado mediante la plataforma SonarCloud con el objetivo de evaluar y mejorar la calidad del software desarrollado. El equipo deberá evidenciar buenas prácticas de ingeniería de software relacionadas con mantenibilidad, seguridad, confiabilidad y pruebas automatizadas.

El proyecto deberá alcanzar métricas vistas en clase en los siguientes atributos de calidad:

- Reliability (Confiabilidad).
- Security (Seguridad).
- Maintainability (Mantenibilidad).
- Duplications (Duplicación de código).

Asimismo, el sistema deberá alcanzar una cobertura mínima de pruebas (Test Coverage) del 85%.

Para evidenciar el cumplimiento de estas actividades, se deberá subir a Canvas lo siguiente:

- Enlace público del análisis realizado en SonarCloud (Coordinar con los ACL del curso).
- Enlace del repositorio del proyecto en GitHub.
- Evidencia de ejecución de pruebas automatizadas.
- Documento breve describiendo la arquitectura implementada y el patrón arquitectónico utilizado.

## Figura 1: Proceso del programa de recompensas

El proceso representado en la figura incluye los siguientes elementos:

1. **Registra la Cena**.
2. **PRODUCER — Sistema Restaurant**.
3. **AMQP — Apache ActiveMQ**
   - Exchange.
   - Routes.
   - Queue.
   - Cola de Mensaje de la Cenas registradas.
4. **CONSUMER — Registra los puntos o el reembolso de dinero**.

Además, el diagrama muestra:

- **Publish**: el Producer publica el mensaje hacia el broker.
- **Consume**: el Consumer consume el mensaje desde la cola.
- **Mensaje que incluye la información del usuario y la Cena**.

**Figure 1:** Proceso del programa de recompensas.

## Implementación Python — Rewards

Servicio de recompensas con arquitectura Clean/Hexagonal: dominio y casos de uso aislados,
adaptadores para FastAPI, SQLAlchemy y RabbitMQ, y pruebas automatizadas con cobertura para Sonar.

Documento de arquitectura y casos de uso: [`docs/architecture.md`](docs/architecture.md).

### Instalación local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### Ejecutar API

```bash
DATABASE_URL="sqlite+pysqlite:///./rewards.db" \
REWARD_EVENT_PUBLISHER="rabbitmq" \
RABBITMQ_URL="amqp://..." \
uvicorn rewards.interfaces.api.main:create_app --factory --reload
```

La API expone `POST /reward-actions` para registrar acciones de recompensa. En tests y desarrollo
sin broker puede usarse `REWARD_EVENT_PUBLISHER="memory"`; en runtime real usá `rabbitmq`. No guardes
credenciales del broker en el repositorio.

### Ejecutar worker RabbitMQ

```bash
DATABASE_URL="sqlite+pysqlite:///./rewards.db" \
RABBITMQ_URL="amqp://..." \
python -m rewards.interfaces.worker.main
```

El worker consume eventos `reward.action.registered` desde el exchange `rewards.events` y la cola
`rewards.processing`. Cambiá esos nombres con `RABBITMQ_EXCHANGE` y `RABBITMQ_REWARD_QUEUE` si tu
broker local usa otra topología.

### Pruebas y cobertura

```bash
python -m pytest
coverage run -m pytest && coverage xml -o coverage.xml
```

`coverage.xml` queda en la raíz del repositorio y coincide con la ruta esperada por Sonar para
cobertura Python.

### Análisis con Sonar

Para ejecutar el análisis local, primero instalá `sonar-scanner` y asegurate de tener configurada
la autenticación fuera del repositorio, por ejemplo con variables de entorno o con la configuración
local del scanner. No hardcodees tokens en archivos del proyecto.

```bash
sonar-scanner
```
