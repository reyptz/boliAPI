"""
Règles de tarification — centralisées pour éviter la duplication (DRY) entre
la demande de course (`RequestRideUseCase`) et le règlement financier
(`SyncMissionUseCase`).
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


class PricingService:
    """Calcule le prix d'une mission et la commission chauffeur associée."""

    # Tarifs de base (XOF) — à terme, externalisables en config/table admin.
    _VTC_BASE = 500.0
    _VTC_PER_KM = 250.0
    _VTC_MIN_PRICE = 1000.0

    _PACKAGE_BASE = 500.0
    _PACKAGE_PER_KM = 200.0
    _PACKAGE_MIN_PRICE = 700.0

    _DELIVERY_BASE = 700.0
    _DELIVERY_PER_KM = 200.0
    _DELIVERY_SURCHARGE = 200.0
    _DELIVERY_MIN_PRICE = 1000.0

    # Commission fixe versée au livreur pour une livraison de repas/colis
    # (le montant payé par le client va au marchand, pas au livreur).
    DELIVERY_DRIVER_FEE = 1500.0

    @staticmethod
    def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Distance orthodromique (km) entre deux points GPS."""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * asin(sqrt(a)) * 6371

    @classmethod
    def calculate_price(cls, mission_type: str, distance_km: float) -> float:
        """Calcule le prix total d'une mission selon son type et sa distance."""
        if mission_type == "package":
            price = cls._PACKAGE_BASE + distance_km * cls._PACKAGE_PER_KM
            return float(max(cls._PACKAGE_MIN_PRICE, round(price)))
        if mission_type == "delivery":
            price = cls._DELIVERY_BASE + distance_km * cls._DELIVERY_PER_KM + cls._DELIVERY_SURCHARGE
            return float(max(cls._DELIVERY_MIN_PRICE, round(price)))
        # 'vtc' (par défaut)
        price = cls._VTC_BASE + distance_km * cls._VTC_PER_KM
        return float(max(cls._VTC_MIN_PRICE, round(price)))
