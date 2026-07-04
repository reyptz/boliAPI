from uuid import uuid4
from datetime import datetime, timezone
from app.domain.entities.ride import RideMission, MissionStatus, Location
from app.domain.repositories.ride_repositories import (
    IRideRepository,
    IGeoLocationRepository,
    IWebSocketManager
)
from app.domain.services.pricing_service import PricingService

class RequestRideUseCase:
    def __init__(
        self,
        ride_repo: IRideRepository,
        geo_repo: IGeoLocationRepository,
        ws_manager: IWebSocketManager
    ):
        self.ride_repo = ride_repo
        self.geo_repo = geo_repo
        self.ws_manager = ws_manager

    async def execute(self, client_id: str, pickup: Location, dropoff: Location, type: str = "vtc", package_description: str | None = None) -> RideMission:
        # 1. Trouver les chauffeurs actifs à < 3km (optionnel)
        driver_ids = await self.geo_repo.get_drivers_within_radius(pickup, 3.0)

        # 2. Création de la Mission (Statut: pending)
        distance_km = PricingService.haversine_km(
            pickup.longitude, pickup.latitude, dropoff.longitude, dropoff.latitude
        )
        price = PricingService.calculate_price(type, distance_km)

        mission = RideMission(
            id=uuid4(),
            client_id=client_id,
            type=type,
            status=MissionStatus.pending,
            pickup=pickup,
            dropoff=dropoff,
            price=price,
            package_description=package_description,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # 3. Sauvegarde en base
        await self.ride_repo.create(mission)

        # 4. Notification WebSocket des chauffeurs, seulement s'il y en a
        if driver_ids:
            try:
                await self.ws_manager.notify_drivers(driver_ids, {
                    "type": "NEW_RIDE_AVAILABLE",
                    "ride_id": str(mission.id),
                    "pickup": {"lat": pickup.latitude, "lng": pickup.longitude},
                    "dropoff": {"lat": dropoff.latitude, "lng": dropoff.longitude},
                    "price": price
                })
            except Exception:
                pass

        return mission
