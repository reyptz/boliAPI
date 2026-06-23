from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.presentation.dependencies import CurrentUserId, get_db

carpool_router = APIRouter(prefix="/carpool", tags=["Carpool"])


class CreateTripPayload(BaseModel):
    departure_city: str
    arrival_city: str
    departure_lat: float
    departure_lng: float
    arrival_lat: float
    arrival_lng: float
    departure_date: str
    price_per_seat: float
    total_seats: int
    vehicle_description: Optional[str] = None
    notes: Optional[str] = None


class BookTripPayload(BaseModel):
    seats: int = 1


def _trip_to_dict(trip) -> dict:
    from geoalchemy2.shape import to_shape
    dep = to_shape(trip.departure_location)
    arr = to_shape(trip.arrival_location)
    return {
        "id": trip.id,
        "driver_id": trip.driver_id,
        "departure_city": trip.departure_city,
        "arrival_city": trip.arrival_city,
        "departure_lat": dep.y,
        "departure_lng": dep.x,
        "arrival_lat": arr.y,
        "arrival_lng": arr.x,
        "departure_date": trip.departure_date.isoformat() if trip.departure_date else None,
        "price_per_seat": float(trip.price_per_seat),
        "total_seats": trip.total_seats,
        "available_seats": trip.available_seats,
        "status": trip.status,
        "vehicle_description": trip.vehicle_description,
        "notes": trip.notes,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
    }


@carpool_router.post("/trips")
async def create_trip(
    payload: CreateTripPayload,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel

    trip = CarpoolTripModel(
        driver_id=user_id,
        departure_city=payload.departure_city,
        arrival_city=payload.arrival_city,
        departure_location=f"SRID=4326;POINT({payload.departure_lng} {payload.departure_lat})",
        arrival_location=f"SRID=4326;POINT({payload.arrival_lng} {payload.arrival_lat})",
        departure_date=datetime.fromisoformat(payload.departure_date),
        price_per_seat=payload.price_per_seat,
        total_seats=payload.total_seats,
        available_seats=payload.total_seats,
        vehicle_description=payload.vehicle_description,
        notes=payload.notes,
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return _trip_to_dict(trip)


@carpool_router.get("/trips")
async def list_trips(
    departure_city: Optional[str] = None,
    arrival_city: Optional[str] = None,
    date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel

    stmt = select(CarpoolTripModel).where(
        CarpoolTripModel.status.in_(["open", "full"])
    )

    if departure_city:
        stmt = stmt.where(CarpoolTripModel.departure_city == departure_city)
    if arrival_city:
        stmt = stmt.where(CarpoolTripModel.arrival_city == arrival_city)
    if date:
        try:
            day = datetime.fromisoformat(date).date()
            from sqlalchemy import cast, Date
            stmt = stmt.where(cast(CarpoolTripModel.departure_date, Date) == day)
        except ValueError:
            pass

    stmt = stmt.order_by(CarpoolTripModel.departure_date.asc())
    result = await db.execute(stmt)
    trips = result.scalars().all()
    return [_trip_to_dict(t) for t in trips]


@carpool_router.get("/trips/{trip_id}")
async def get_trip(trip_id: str, db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.models import CarpoolTripModel

    stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    result = await db.execute(stmt)
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")
    return _trip_to_dict(trip)


@carpool_router.post("/trips/{trip_id}/book")
async def book_trip(
    trip_id: str,
    payload: BookTripPayload,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel, CarpoolBookingModel
    from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository

    stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    result = await db.execute(stmt)
    trip = result.scalar_one_or_none()

    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")
    if trip.status not in ("open",):
        raise HTTPException(status_code=400, detail="Ce trajet n'accepte plus de réservations.")
    if payload.seats > trip.available_seats:
        raise HTTPException(status_code=400, detail=f"Seulement {trip.available_seats} place(s) disponible(s).")
    if trip.driver_id == user_id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas réserver votre propre trajet.")

    total_cost = float(trip.price_per_seat) * payload.seats
    wallet_repo = SQLAlchemyWalletRepository(db)

    await wallet_repo.update_balance(
        user_id=user_id,
        amount=-total_cost,
        tx_type="payment",
        description=f"Covoiturage {trip.departure_city}→{trip.arrival_city} ({payload.seats} place(s))",
    )
    await wallet_repo.update_balance(
        user_id=trip.driver_id,
        amount=total_cost,
        tx_type="earning",
        description=f"Covoiturage {trip.departure_city}→{trip.arrival_city} ({payload.seats} place(s))",
    )

    booking = CarpoolBookingModel(
        trip_id=trip_id,
        passenger_id=user_id,
        seats_booked=payload.seats,
    )
    db.add(booking)

    trip.available_seats -= payload.seats
    if trip.available_seats <= 0:
        trip.status = "full"

    await db.commit()

    return {"status": "success", "booking_id": booking.id, "seats_booked": payload.seats}


@carpool_router.post("/trips/{trip_id}/cancel-booking")
async def cancel_booking(
    trip_id: str,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel, CarpoolBookingModel
    from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository

    stmt = select(CarpoolBookingModel).where(
        and_(
            CarpoolBookingModel.trip_id == trip_id,
            CarpoolBookingModel.passenger_id == user_id,
            CarpoolBookingModel.status == "confirmed",
        )
    )
    result = await db.execute(stmt)
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable.")

    trip_stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    trip_result = await db.execute(trip_stmt)
    trip = trip_result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")

    refund = float(trip.price_per_seat) * booking.seats_booked
    wallet_repo = SQLAlchemyWalletRepository(db)

    await wallet_repo.update_balance(
        user_id=user_id,
        amount=refund,
        tx_type="deposit",
        description=f"Remboursement covoiturage {trip.departure_city}→{trip.arrival_city}",
    )
    await wallet_repo.update_balance(
        user_id=trip.driver_id,
        amount=-refund,
        tx_type="payment",
        description=f"Remboursement covoiturage {trip.departure_city}→{trip.arrival_city}",
    )

    booking.status = "cancelled"
    trip.available_seats += booking.seats_booked
    if trip.status == "full":
        trip.status = "open"

    await db.commit()
    return {"status": "success", "refunded": refund}


@carpool_router.post("/trips/{trip_id}/start")
async def start_trip(
    trip_id: str,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel

    stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    result = await db.execute(stmt)
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")
    if trip.driver_id != user_id:
        raise HTTPException(status_code=403, detail="Seul le conducteur peut démarrer le trajet.")

    trip.status = "in_progress"
    await db.commit()
    return {"status": "success", "trip_status": "in_progress"}


@carpool_router.post("/trips/{trip_id}/complete")
async def complete_trip(
    trip_id: str,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel

    stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    result = await db.execute(stmt)
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")
    if trip.driver_id != user_id:
        raise HTTPException(status_code=403, detail="Seul le conducteur peut terminer le trajet.")

    trip.status = "completed"
    await db.commit()
    return {"status": "success", "trip_status": "completed"}


@carpool_router.delete("/trips/{trip_id}")
async def cancel_trip(
    trip_id: str,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel, CarpoolBookingModel
    from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository

    stmt = select(CarpoolTripModel).where(CarpoolTripModel.id == trip_id)
    result = await db.execute(stmt)
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable.")
    if trip.driver_id != user_id:
        raise HTTPException(status_code=403, detail="Seul le conducteur peut annuler le trajet.")

    wallet_repo = SQLAlchemyWalletRepository(db)
    bookings_stmt = select(CarpoolBookingModel).where(
        and_(CarpoolBookingModel.trip_id == trip_id, CarpoolBookingModel.status == "confirmed")
    )
    bookings_result = await db.execute(bookings_stmt)
    bookings = bookings_result.scalars().all()

    for booking in bookings:
        refund = float(trip.price_per_seat) * booking.seats_booked
        await wallet_repo.update_balance(
            user_id=booking.passenger_id,
            amount=refund,
            tx_type="deposit",
            description=f"Remboursement — trajet annulé {trip.departure_city}→{trip.arrival_city}",
        )
        await wallet_repo.update_balance(
            user_id=trip.driver_id,
            amount=-refund,
            tx_type="payment",
            description=f"Débit — trajet annulé {trip.departure_city}→{trip.arrival_city}",
        )
        booking.status = "cancelled"

    trip.status = "cancelled"
    await db.commit()
    return {"status": "success", "refunded_bookings": len(bookings)}


@carpool_router.get("/my-trips")
async def my_trips(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    from app.infrastructure.persistence.models import CarpoolTripModel, CarpoolBookingModel

    driver_stmt = select(CarpoolTripModel).where(CarpoolTripModel.driver_id == user_id)
    driver_result = await db.execute(driver_stmt)
    driver_trips = driver_result.scalars().all()

    passenger_stmt = (
        select(CarpoolTripModel)
        .join(CarpoolBookingModel, CarpoolBookingModel.trip_id == CarpoolTripModel.id)
        .where(
            and_(
                CarpoolBookingModel.passenger_id == user_id,
                CarpoolBookingModel.status == "confirmed",
            )
        )
    )
    passenger_result = await db.execute(passenger_stmt)
    passenger_trips = passenger_result.scalars().all()

    seen = set()
    all_trips = []
    for t in [*driver_trips, *passenger_trips]:
        if t.id not in seen:
            seen.add(t.id)
            all_trips.append(t)

    all_trips.sort(key=lambda t: t.departure_date, reverse=True)
    return [_trip_to_dict(t) for t in all_trips]
