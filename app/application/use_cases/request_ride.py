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

    async def execute(self, client_id: str, pickup: Location, dropoff: Location) -> RideMission:
        # 1. Trouver les chauffeurs actifs à < 3km
        driver_ids = await self.geo_repo.get_drivers_within_radius(pickup, 3.0)

        if not driver_ids:
            raise Exception("Aucun chauffeur disponible à proximité.")

        # 2. Création de la Mission (Statut: pending)
        distance_km = self._calculate_distance(pickup.longitude, pickup.latitude, dropoff.longitude, dropoff.latitude)
        # Forfait de base 1000 FCFA + 500 FCFA / km
        calculated_price = round(1000.0 + (distance_km * 500.0))
        price = float(max(1500, calculated_price)) # Minimum 1500 FCFA
        
        mission = RideMission(
            id=uuid4(),
            client_id=client_id,
            status=MissionStatus.pending,
            pickup=pickup,
            dropoff=dropoff,
            price=price,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # 3. Sauvegarde en base
        await self.ride_repo.create(mission)

        # 4. Notification WebSocket des chauffeurs
        await self.ws_manager.notify_drivers(driver_ids, {
            "type": "NEW_RIDE_AVAILABLE",
            "ride_id": str(mission.id),
            "pickup": {"lat": pickup.latitude, "lng": pickup.longitude},
            "dropoff": {"lat": dropoff.latitude, "lng": dropoff.longitude},
            "price": price
        })

        return mission
