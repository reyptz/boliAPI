from typing import List, Dict, Optional
from datetime import datetime, timezone
import math
from uuid import uuid4
from app.domain.entities.ride import RideMission, Location, MissionStatus
from app.domain.repositories.ride_repositories import (
    IRideRepository,
    IGeoLocationRepository,
    IMessageQueueService,
    IWebSocketManager
)
from fastapi import WebSocket

class MockRideRepository(IRideRepository):
    def __init__(self):
        self._rides: Dict[str, RideMission] = {}

    async def create(self, ride: RideMission) -> RideMission:
        self._rides[str(ride.id)] = ride
        return ride

    async def get_by_id(self, ride_id: str) -> Optional[RideMission]:
        return self._rides.get(ride_id)

    async def update_status(self, ride_id: str, status: str, driver_id: Optional[str] = None) -> RideMission:
        ride = self._rides.get(ride_id)
        if not ride:
            raise Exception("Ride not found")
        
        ride.status = MissionStatus(status)
        if driver_id:
            ride.driver_id = driver_id
        ride.updated_at = datetime.now(timezone.utc)
        return ride

class MockGeoRepository(IGeoLocationRepository):
    def __init__(self):
        # driver_id -> Location
        self._driver_locations: Dict[str, Location] = {}

    async def update_driver_location(self, driver_id: str, location: Location):
        self._driver_locations[driver_id] = location

    async def get_drivers_within_radius(self, location: Location, radius_km: float) -> List[str]:
        # Implementation naïve du GEORADIUS avec Haversine
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Rayon de la terre en km
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = math.sin(dLat/2) * math.sin(dLat/2) + \
                math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
                math.sin(dLon/2) * math.sin(dLon/2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

        nearby_drivers = []
        for d_id, loc in self._driver_locations.items():
            dist = haversine(location.latitude, location.longitude, loc.latitude, loc.longitude)
            if dist <= radius_km:
                nearby_drivers.append(d_id)
        
        # S'il n'y a pas de chauffeurs, on mock pour le test
        if not nearby_drivers:
            nearby_drivers.append("mock_driver_1")

        return nearby_drivers

import asyncio
import httpx

class MockRabbitMQService(IMessageQueueService):
    def __init__(self):
        self.messages = []

    async def publish_payment_request(self, ride_id: str, amount: float, client_id: str):
        print(f"[RabbitMQ Mock] Publishing payment request for Ride {ride_id}, Amount: {amount}")
        self.messages.append({
            "ride_id": ride_id,
            "amount": amount,
            "client_id": client_id
        })
        
        # Simuler un webhook de confirmation de paiement après 2 secondes
        async def simulate_webhook():
            await asyncio.sleep(2)
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://127.0.0.1:8001/api/v1/rides/webhooks/payment",
                        json={
                            "ride_id": ride_id,
                            "success": True,
                            "transaction_id": f"OM_{uuid4().hex[:8].upper()}"
                        }
                    )
                    print(f"[Mobile Money Mock] Auto-webhook status: {response.status_code}")
            except Exception as e:
                print(f"[Mobile Money Mock] Error sending webhook: {e}")
                
        asyncio.create_task(simulate_webhook())


class WebSocketConnectionManager(IWebSocketManager):
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def notify_drivers(self, driver_ids: List[str], message: dict):
        for d_id in driver_ids:
            ws = self.active_connections.get(d_id)
            if ws:
                await ws.send_json(message)

    async def notify_client(self, client_id: str, message: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            await ws.send_json(message)

# Global instances for the mock implementation
mock_ride_repo = MockRideRepository()
mock_geo_repo = MockGeoRepository()
mock_mq_service = MockRabbitMQService()
ws_manager = WebSocketConnectionManager()
