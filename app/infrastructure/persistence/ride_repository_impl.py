from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.domain.entities.ride import RideMission, Location, MissionStatus
from app.domain.repositories.ride_repositories import IRideRepository
from app.infrastructure.persistence.models import MissionModel

class SQLAlchemyRideRepository(IRideRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: MissionModel) -> RideMission:
        pickup_shape = to_shape(model.pickup_location)
        dropoff_shape = to_shape(model.dropoff_location)
        
        return RideMission(
            id=uuid.UUID(model.id),
            client_id=model.client_id,
            driver_id=model.driver_id,
            type=model.type,
            status=MissionStatus(model.status),
            pickup=Location(latitude=pickup_shape.y, longitude=pickup_shape.x),
            dropoff=Location(latitude=dropoff_shape.y, longitude=dropoff_shape.x),
            price=float(model.price_total),
            package_description=model.package_description,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    async def create(self, ride: RideMission) -> RideMission:
        model = MissionModel(
            id=str(ride.id),
            client_id=ride.client_id,
            driver_id=ride.driver_id,
            type=ride.type,
            status=ride.status.value,
            pickup_location=f"SRID=4326;POINT({ride.pickup.longitude} {ride.pickup.latitude})",
            dropoff_location=f"SRID=4326;POINT({ride.dropoff.longitude} {ride.dropoff.latitude})",
            price_total=ride.price,
            package_description=ride.package_description,
            created_at=ride.created_at,
            updated_at=ride.updated_at
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, ride_id: str) -> Optional[RideMission]:
        stmt = select(MissionModel).where(MissionModel.id == ride_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def update_status(self, ride_id: str, status: str, driver_id: Optional[str] = None) -> RideMission:
        stmt = select(MissionModel).where(MissionModel.id == ride_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise Exception("Ride mission not found")
        
        model.status = status
        if driver_id:
            model.driver_id = driver_id
        model.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
