"""DTOs liés aux courses/missions (transport de données entre couches)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SyncMissionDTO(BaseModel):
    """Payload de synchronisation d'une mission (upsert + règlement financier)."""

    ride_id: str
    client_id: str
    driver_id: Optional[str] = None
    merchant_id: Optional[str] = None
    type: str  # 'vtc', 'food', 'delivery', 'package'
    status: str
    price: float
    package_description: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
