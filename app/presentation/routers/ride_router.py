import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.domain.entities.ride import Location
from app.domain.exceptions import WebhookSignatureError
from app.infrastructure.rides.mock_ride_infrastructure import ws_manager
from app.infrastructure.rides.rabbitmq_service import RabbitMQService
from app.infrastructure.rides.redis_geo_repository import RedisGeoRepository
from app.infrastructure.payment.mobile_money_service import MobileMoneyService
from app.infrastructure.persistence.models import MissionModel
from app.infrastructure.security.jwt_handler import decode_token
from app.application.dto.ride_dto import SyncMissionDTO
from app.application.use_cases.request_ride import RequestRideUseCase
from app.application.use_cases.accept_ride import AcceptRideUseCase
from app.application.use_cases.payment_webhook import PaymentWebhookUseCase
from app.application.use_cases.update_ride_status import UpdateRideStatusUseCase
from app.application.use_cases.sync_mission import SyncMissionUseCase
from app.presentation.dependencies import RideRepo, CurrentUserId, AdminPayload, get_db

from app.config import settings

logger = logging.getLogger("boli-api.rides")

ride_router = APIRouter(prefix="/rides", tags=["Rides"])

# Injection (instances globales, config-driven)
redis_geo_repo = RedisGeoRepository(redis_url=settings.REDIS_URL)
rabbitmq_service = RabbitMQService(amqp_url=settings.RABBITMQ_URL)
mobile_money_service = MobileMoneyService(
    api_base_url=settings.MOBILE_MONEY_API_URL,
    api_key=settings.MOBILE_MONEY_API_KEY,
)


# ── Payloads ─────────────────────────────────────────────────
# NB : l'identité (client_id / driver_id) n'est JAMAIS lue dans le body ;
# elle est dérivée du token JWT. Voir les endpoints ci-dessous.
class RequestRidePayload(BaseModel):
    pickup: Location
    dropoff: Location
    type: str = "vtc"
    package_description: Optional[str] = None


class UpdateStatusPayload(BaseModel):
    status: str


class PaymentWebhookPayload(BaseModel):
    ride_id: str
    success: bool
    transaction_id: str


# NB : `/sync` est une opération *administrative* (réservée aux admins) qui
# synchronise une mission au nom d'un client/chauffeur tiers : `client_id` doit
# donc rester dans le payload (il ne s'agit pas d'une action au nom de l'appelant).
class SyncMissionPayload(BaseModel):
    ride_id: str
    client_id: str
    driver_id: Optional[str] = None
    merchant_id: Optional[str] = None
    type: str  # 'vtc', 'food', 'delivery', 'package'
    status: str
    price: float
    package_description: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None


# ── Endpoints ────────────────────────────────────────────────
@ride_router.post("/request")
async def request_ride(
    payload: RequestRidePayload,
    client_id: CurrentUserId,
    ride_repo: RideRepo,
):
    """Crée une demande de course pour l'utilisateur authentifié."""
    use_case = RequestRideUseCase(ride_repo, redis_geo_repo, ws_manager)
    mission = await use_case.execute(
        client_id, payload.pickup, payload.dropoff, payload.type, payload.package_description
    )
    return {
        "status": "success",
        "mission": {
            "id": str(mission.id),
            "client_id": mission.client_id,
            "driver_id": mission.driver_id,
            "type": mission.type,
            "status": mission.status.value,
            "pickup": {"latitude": mission.pickup.latitude, "longitude": mission.pickup.longitude},
            "dropoff": {"latitude": mission.dropoff.latitude, "longitude": mission.dropoff.longitude},
            "price": mission.price,
            "package_description": mission.package_description,
            "created_at": mission.created_at.isoformat() if mission.created_at else None,
            "updated_at": mission.updated_at.isoformat() if mission.updated_at else None,
        },
    }


@ride_router.post("/{ride_id}/accept")
async def accept_ride(ride_id: str, driver_id: CurrentUserId, ride_repo: RideRepo):
    """Le chauffeur authentifié accepte une course. `driver_id` vient du token."""
    use_case = AcceptRideUseCase(ride_repo, rabbitmq_service)
    mission = await use_case.execute(ride_id, driver_id)
    return {"status": "success", "mission": mission}


@ride_router.post("/{ride_id}/status")
async def update_status(
    ride_id: str,
    payload: UpdateStatusPayload,
    driver_id: CurrentUserId,
    ride_repo: RideRepo,
):
    """Met à jour le statut d'une course (chauffeur authentifié)."""
    use_case = UpdateRideStatusUseCase(ride_repo, ws_manager)
    mission = await use_case.execute(ride_id, payload.status, driver_id)
    return {"status": "success", "mission": mission}


def _verify_webhook_signature(raw_body: bytes, signature: str | None) -> None:
    """
    Vérifie la signature HMAC-SHA256 du webhook de paiement.
    En DEBUG sans secret configuré, la vérification est ignorée (tests locaux).
    """
    secret = settings.PAYMENT_WEBHOOK_SECRET
    if not secret:
        if settings.DEBUG:
            return
        raise WebhookSignatureError("Secret de webhook non configuré.")

    if not signature:
        raise WebhookSignatureError()

    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise WebhookSignatureError()


@ride_router.post("/webhooks/payment")
async def payment_webhook(request: Request, ride_repo: RideRepo):
    """
    Webhook de confirmation de paiement Mobile Money.
    La signature HMAC est obligatoire (en-tête `X-Signature`) pour empêcher
    toute confirmation de paiement forgée.
    """
    raw_body = await request.body()
    _verify_webhook_signature(raw_body, request.headers.get("X-Signature"))

    payload = PaymentWebhookPayload.model_validate_json(raw_body)
    use_case = PaymentWebhookUseCase(ride_repo, ws_manager)
    mission = await use_case.execute(payload.ride_id, payload.success, payload.transaction_id)
    return {"status": "success", "mission": mission}


@ride_router.post("/sync")
async def sync_mission(
    payload: SyncMissionPayload,
    _admin: AdminPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Synchronise/persiste une mission et déclenche le règlement financier.
    Réservé aux administrateurs (mouvements d'argent au nom d'un tiers).
    """
    use_case = SyncMissionUseCase(db)
    result = await use_case.execute(SyncMissionDTO(**payload.model_dump()))
    return {"status": "success", **result}


@ride_router.get("/history")
async def get_ride_history(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """Historique paginé des courses de l'utilisateur authentifié."""
    limit = max(1, min(limit, 100))
    stmt = (
        select(MissionModel)
        .where(or_(MissionModel.client_id == user_id, MissionModel.driver_id == user_id))
        .order_by(MissionModel.created_at.desc())
        .limit(limit)
        .offset(max(0, offset))
    )
    result = await db.execute(stmt)
    missions = result.scalars().all()

    out = []
    for m in missions:
        p_shape = to_shape(m.pickup_location)
        d_shape = to_shape(m.dropoff_location)
        out.append({
            "id": m.id,
            "client_id": m.client_id,
            "driver_id": m.driver_id,
            "merchant_id": m.merchant_id,
            "type": m.type,
            "status": m.status,
            "package_description": m.package_description,
            "price": float(m.price_total),
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "pickup": {"lat": p_shape.y, "lng": p_shape.x},
            "dropoff": {"lat": d_shape.y, "lng": d_shape.x},
        })
    return out


ws_router = APIRouter(tags=["WebSockets"])


@ws_router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Canal de notifications temps réel. L'identité est dérivée du JWT passé en
    query (`?token=...`) ; on n'accepte plus un `client_id` arbitraire, ce qui
    empêchait l'écoute des notifications d'autrui et le spoofing GPS.
    """
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=1008)  # Policy Violation
        return

    client_id = payload["sub"]
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("GPS:"):
                coords = data.replace("GPS:", "").split(",")
                if len(coords) == 2:
                    loc = Location(latitude=float(coords[0]), longitude=float(coords[1]))
                    # La position est toujours enregistrée sous l'identité du token.
                    await redis_geo_repo.update_driver_location(client_id, loc)
                    await ws_manager.notify_client(client_id, {
                        "type": "DRIVER_LOCATION_UPDATED",
                        "driver_id": client_id,
                        "latitude": loc.latitude,
                        "longitude": loc.longitude,
                    })
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
