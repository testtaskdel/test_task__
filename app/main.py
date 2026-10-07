import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import OutboxPublisher, broker, declare_topology
from app.config import get_settings
from app.db import get_session
from app.models import Payment
from app.errors import IdempotencyConflictError
from app.payment_service import create_payment_safely
from app.schemas import PaymentCreate, PaymentResponse
from app.security import ApiKey

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await broker.connect()
    await declare_topology(broker)
    stop_event = asyncio.Event()
    publisher = OutboxPublisher(stop_event)
    task = asyncio.create_task(publisher.run())

    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await broker.stop()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[ApiKey],
)
async def create_payment(
    payload: PaymentCreate,
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=255),
):
    try:
        return await create_payment_safely(session, payload, idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(
    "/api/v1/payments/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[ApiKey],
)
async def get_payment(
    payment_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
):
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
