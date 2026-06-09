from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.entities.ride import RideMission, Location

class IRideRepository(ABC):
    @abstractmethod
    async def create(self, ride: RideMission) -> RideMission:
        pass

    @abstractmethod
    async def get_by_id(self, ride_id: str) -> Optional[RideMission]:
        pass

    @abstractmethod
    async def update_status(self, ride_id: str, status: str, driver_id: Optional[str] = None) -> RideMission:
        pass

class IGeoLocationRepository(ABC):
    @abstractmethod
    async def update_driver_location(self, driver_id: str, location: Location):
        pass

    @abstractmethod
    async def get_drivers_within_radius(self, location: Location, radius_km: float) -> List[str]:
        pass

class IMessageQueueService(ABC):
    @abstractmethod
    async def publish_payment_request(self, ride_id: str, amount: float, client_id: str):
        pass

class IWebSocketManager(ABC):
    @abstractmethod
    async def notify_drivers(self, driver_ids: List[str], message: dict):
        pass

    @abstractmethod
    async def notify_client(self, client_id: str, message: dict):
        pass
