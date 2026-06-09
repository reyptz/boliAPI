import redis.asyncio as redis
from typing import List
from app.domain.entities.ride import Location
from app.domain.repositories.ride_repositories import IGeoLocationRepository

class RedisGeoRepository(IGeoLocationRepository):
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.geo_key = "drivers:locations"

    async def update_driver_location(self, driver_id: str, location: Location):
        """
        Met à jour la position du chauffeur dans l'index spatial Redis.
        """
        # redis.geoadd(name, (longitude, latitude, member))
        await self.redis.geoadd(self.geo_key, (location.longitude, location.latitude, driver_id))

    async def get_drivers_within_radius(self, location: Location, radius_km: float) -> List[str]:
        """
        Trouve tous les chauffeurs actifs dans un rayon donné.
        """
        try:
            # georadius(name, longitude, latitude, radius, unit)
            nearby_drivers = await self.redis.georadius(
                name=self.geo_key,
                longitude=location.longitude,
                latitude=location.latitude,
                radius=radius_km,
                unit='km'
            )
            return nearby_drivers
        except Exception as e:
            # S'il n'y a aucun index, retourne une liste vide au lieu de crasher
            return []
