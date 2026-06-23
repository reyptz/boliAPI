from typing import List
from uuid import uuid4
from datetime import datetime, timezone
from app.domain.entities.ride import RideMission, MissionStatus, Location
from app.domain.repositories.ride_repositories import (
    IRideRepository, 
    IGeoLocationRepository, 
    IWebSocketManager
)

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

    def _calculate_distance(self, lon1, lat1, lon2, lat2):
        from math import radians, cos, sin, asin, sqrt
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        return c * 6371

    async def execute(self, client_id: str, pickup: Location, dropoff: Location, type: str = "vtc", package_description: str | None = None) -> RideMission:
        # 1. Trouver les chauffeurs actifs à < 3km (optionnel)
        driver_ids = await self.geo_repo.get_drivers_within_radius(pickup, 3.0)

        # 2. Création de la Mission (Statut: pending)
        distance_km = self._calculate_distance(pickup.longitude, pickup.latitude, dropoff.longitude, dropoff.latitude)

        if type == "package":
            calculated_price = round(500.0 + (distance_km * 200.0))
            price = float(max(700, calculated_price))
        elif type == "delivery":
            calculated_price = round(700.0 + (distance_km * 200.0) + 200.0)
            price = float(max(1000, calculated_price))
        else:
            calculated_price = round(500.0 + (distance_km * 250.0))
            price = float(max(1000, calculated_price))

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
