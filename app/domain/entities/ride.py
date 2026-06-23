from enum import Enum
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

class MissionStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    going_to_pickup = "going_to_pickup"
    processing = "processing"
    completed = "completed"
    cancelled = "cancelled"

class Location(BaseModel):
    latitude: float
    longitude: float

class RideMission(BaseModel):
    id: uuid.UUID
    client_id: str
    driver_id: Optional[str] = None
    type: str = "vtc"
    status: MissionStatus
    pickup: Location
    dropoff: Location
    price: float
    package_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
