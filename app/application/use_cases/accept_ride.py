from app.domain.entities.ride import RideMission, MissionStatus
from app.domain.repositories.ride_repositories import (
    IRideRepository, 
    IMessageQueueService
)

class AcceptRideUseCase:
    def __init__(
        self, 
        ride_repo: IRideRepository, 
        mq_service: IMessageQueueService
    ):
        self.ride_repo = ride_repo
        self.mq_service = mq_service

    async def execute(self, ride_id: str, driver_id: str) -> RideMission:
        # 1. Vérifier la mission
        mission = await self.ride_repo.get_by_id(ride_id)
        if not mission:
            raise Exception("Mission introuvable.")
            
        if mission.status != MissionStatus.pending:
            raise Exception(f"La course ne peut plus être acceptée. Statut actuel: {mission.status.value}")

        # 2. Mise à jour du statut (Statut: going_to_pickup — cohérent avec le frontend)
        updated_mission = await self.ride_repo.update_status(
            ride_id=ride_id, 
            status="going_to_pickup", 
            driver_id=driver_id
        )

        # 3. Enclenchement de la transaction financière asynchrone
        await self.mq_service.publish_payment_request(
            ride_id=str(updated_mission.id),
            amount=updated_mission.price,
            client_id=updated_mission.client_id
        )

        return updated_mission
