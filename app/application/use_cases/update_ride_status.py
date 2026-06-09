from typing import Optional
from app.domain.entities.ride import RideMission, MissionStatus
from app.domain.repositories.ride_repositories import (
    IRideRepository, 
    IWebSocketManager
)

class UpdateRideStatusUseCase:
    def __init__(
        self, 
        ride_repo: IRideRepository, 
        ws_manager: IWebSocketManager
    ):
        self.ride_repo = ride_repo
        self.ws_manager = ws_manager

    async def execute(self, ride_id: str, status: str, driver_id: Optional[str] = None) -> RideMission:
        mission = await self.ride_repo.get_by_id(ride_id)
        if not mission:
            raise Exception("Mission introuvable.")

        # Si un nouveau chauffeur est spécifié, on l'associe
        updated_mission = await self.ride_repo.update_status(
            ride_id=ride_id, 
            status=status,
            driver_id=driver_id or mission.driver_id
        )

        message = {
            "type": "RIDE_STATUS_UPDATED",
            "ride_id": str(updated_mission.id),
            "status": updated_mission.status.value,
            "driver_id": updated_mission.driver_id
        }

        # Notifier les deux parties via WebSocket
        if updated_mission.client_id:
            await self.ws_manager.notify_client(updated_mission.client_id, message)
        if updated_mission.driver_id:
            await self.ws_manager.notify_client(updated_mission.driver_id, message)

        return updated_mission
