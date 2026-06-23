"""
Modèles ORM SQLAlchemy pour la Super-App Boli.
Contient les entités Authentification, VTC, Wallet et Marchands/Marketplace avec PostGIS.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.database import Base


class UserModel(Base):
    """Table `users` — stockage des utilisateurs et rôles."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True, index=True
    )

    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="client")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    subscription_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reset_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relations
    wallet: Mapped[WalletModel | None] = relationship(
        "WalletModel", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    driver: Mapped[DriverModel | None] = relationship(
        "DriverModel", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # Un marchand peut exister sans compte Boli (sourcé depuis l'ERP SuguJate),
    # donc pas de cascade delete-orphan ici.
    merchant: Mapped[MerchantModel | None] = relationship(
        "MerchantModel", back_populates="user", uselist=False
    )
    transactions: Mapped[list[TransactionModel]] = relationship(
        "TransactionModel", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserModel id={self.id} phone={self.phone} role={self.role}>"


class WalletModel(Base):
    """Table `wallets` — Portefeuille numérique de l'utilisateur."""

    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    balance: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.00
    )
    currency: Mapped[str] = mapped_column(
        String(5), nullable=False, default="XOF"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[UserModel] = relationship("UserModel", back_populates="wallet")


class TransactionModel(Base):
    """Table `transactions` — Historique des transactions financières."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False  # 'deposit', 'payment', 'earning'
    )
    description: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserModel] = relationship("UserModel", back_populates="transactions")


class DriverModel(Base):
    """Table `drivers` — Profil chauffeur & véhicule."""

    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'moto', 'auto'
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=5.00)

    user: Mapped[UserModel] = relationship("UserModel", back_populates="driver")


class MerchantModel(Base):
    """
    Table `merchants` — Fiche marchand exposée au marketplace Boli.

    Alimentée par la sync depuis SuguJate (Firestore `stores`). Un marchand
    n'a pas forcément de compte utilisateur Boli : `erp_merchant_id` (= storeId
    Firestore) est le pont stable, `owner_user_id` est optionnel.
    """

    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # Lien optionnel vers un compte Boli.
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Pont vers SuguJate : identifiant du store Firestore (clé d'upsert).
    erp_merchant_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")  # 'vendeur', 'restaurant', 'ferme'…
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Point spatial PostGIS (SRID 4326)
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[UserModel | None] = relationship("UserModel", back_populates="merchant")
    products: Mapped[list[ProductModel]] = relationship(
        "ProductModel", back_populates="merchant", cascade="all, delete-orphan"
    )


class ProductModel(Base):
    """Table `products` — Catalogue de produits du marchand."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    # Pont vers SuguJate : identifiant du produit Firestore (clé d'upsert).
    erp_product_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    merchant: Mapped[MerchantModel] = relationship("MerchantModel", back_populates="products")


class MissionModel(Base):
    """Table `missions` — Courses VTC, livraisons de repas ou colis."""

    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    client_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    driver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drivers.id"), nullable=True
    )
    merchant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'vtc', 'food', 'delivery', 'package'
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    package_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Localisations PostGIS
    pickup_location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    dropoff_location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    price_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CarpoolTripModel(Base):
    """Table `carpool_trips` — Trajets de covoiturage interurbain."""

    __tablename__ = "carpool_trips"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    driver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    departure_city: Mapped[str] = mapped_column(String(50), nullable=False)
    arrival_city: Mapped[str] = mapped_column(String(50), nullable=False)
    departure_location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    arrival_location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    departure_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_per_seat: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    vehicle_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bookings: Mapped[list["CarpoolBookingModel"]] = relationship(
        "CarpoolBookingModel", back_populates="trip", cascade="all, delete-orphan"
    )


class CarpoolBookingModel(Base):
    """Table `carpool_bookings` — Réservations de places covoiturage."""

    __tablename__ = "carpool_bookings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("carpool_trips.id", ondelete="CASCADE"), nullable=False
    )
    passenger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    seats_booked: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    trip: Mapped["CarpoolTripModel"] = relationship("CarpoolTripModel", back_populates="bookings")
