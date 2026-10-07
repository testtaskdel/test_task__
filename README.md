# Payment Service

FastAPI-сервис для создания и асинхронной обработки платежей.

## Стек

- FastAPI
- Pydantic v2
- SQLAlchemy 2 async
- PostgreSQL
- RabbitMQ + FastStream
- Alembic
- Docker Compose

## Запуск

```bash
docker compose up --build
```

API: http://localhost:8000  
Swagger: http://localhost:8000/docs  
RabbitMQ: http://localhost:15672  
Логин: `payments`  
Пароль: `payments`

Миграции запускаются при старте API.

## Создать платеж

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key' \
  -H 'Idempotency-Key: order-10001' \
  -d '{
    "amount": 1500.50,
    "currency": "RUB",
    "description": "Оплата заказа #10001",
    "metadata": {"order_id": 10001},
    "webhook_url": "https://example.com/webhooks/payment"
  }'
```

Ответ: `202 Accepted`.

```json
{
  "payment_id": "6b6b4d42-2a2b-46a2-9fef-46efc2bda0e8",
  "status": "pending",
  "created_at": "2026-10-06T17:00:00Z"
}
```

Повтор с тем же `Idempotency-Key` возвращает тот же платеж. Тот же ключ с другим запросом — `409 Conflict`.

## Получить платеж

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> \
  -H 'X-API-Key: dev-api-key'
```

## Идемпотентность

`Idempotency-Key` хранится в БД. Для запроса сохраняется SHA-256 хэш payload.

- тот же ключ + тот же payload → существующий платеж;
- тот же ключ + другой payload → `409 Conflict`.

## Тесты

```bash
pytest
python -m compileall app consumer migrations
```

## Повторный запуск

```bash
docker compose down
docker compose up --build
```

Для полной очистки БД:

```bash
docker compose down -v
docker compose up --build
```
