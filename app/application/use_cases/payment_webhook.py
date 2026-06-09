from app.domain.entities.ride import RideMission, MissionStatus
from app.domain.repositories.ride_repositories import (
    IRideRepository, 
    IWebSocketManager
)

class PaymentWebhookUseCase:
    def __init__(
        self, 
        ride_repo: IRideRepository, 
        ws_manager: IWebSocketManager
    ):
        self.ride_repo = ride_repo
        self.ws_manager = ws_manager

    async def execute(self, ride_id: str, success: bool, transaction_id: str) -> RideMission:
        mission = await self.ride_repo.get_by_id(ride_id)
        if not mission:
            raise Exception("Mission introuvable.")

        if success:
            # Finalisation du statut
            updated_mission = await self.ride_repo.update_status(
                ride_id=ride_id, 
                status=MissionStatus.going_to_pickup.value
            )

            # Confirmation & assignation finale au client
            await self.ws_manager.notify_client(updated_mission.client_id, {
                "type": "DRIVER_ASSIGNED",
                "ride_id": str(updated_mission.id),
                "driver_id": updated_mission.driver_id,
                "status": updated_mission.status.value,
                "transaction_id": transaction_id
            })
            return updated_mission
        else:
            updated_mission = await self.ride_repo.update_status(
                ride_id=ride_id, 
                status=MissionStatus.pending.value,
                driver_id=None # On retire l'assignation
            )
            # Notifier le client de l'échec de paiement
            await self.ws_manager.notify_client(updated_mission.client_id, {
                "type": "PAYMENT_FAILED",
                "ride_id": str(updated_mission.id)
            })
            return updated_mission
