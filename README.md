# Boli Backend API (FastAPI)

API souveraine, résiliente et performante pour la Super-App **Boli** (VTC, livraison, marketplace).  
Développée avec **FastAPI**, **SQLAlchemy Async**, **PostgreSQL/PostGIS** et **Redis**.

## Architecture

Architecture Clean / Domain-Driven Design (DDD) :

```
app/
├── domain/
│   ├── entities/         # Modèles métier (RideMission, User, Wallet)
│   └── repositories/     # Interfaces abstraites
├── application/
│   └── use_cases/        # Cas d'usage (request_ride, accept_ride, update_ride_status, ...)
├── infrastructure/
│   ├── persistence/      # Implémentations SQLAlchemy + modèles ORM
│   └── messaging/        # WebSocketManager, MessageQueue
└── presentation/
    ├── routers/          # Endpoints FastAPI (auth, rides, wallet, marketplace)
    └── dependencies.py   # Injection de dépendances (DB, JWT, repos)
```

## Stack Technique

- **FastAPI** — API REST asynchrone
- **SQLAlchemy 2.0 (async)** — ORM avec PostgreSQL+asyncpg
- **PostGIS** — Types géographiques (`GEOMETRY(Point, 4326)`)
- **Pydantic** — Validation des payloads
- **WebSockets** — Notifications temps réel chauffeurs/clients
- **Redis** — Cache & Geo-spatial indexing (matching chauffeurs)
- **Alembic** — Migrations de base de données
- **Prometheus** — Métriques exposées sur `/metrics`

## Configuration

Créer un fichier `.env` à la racine :

```env
DATABASE_URL=postgresql+asyncpg://boli_user:boli_password@127.0.0.1:5433/boli_db
JWT_SECRET=votre_secret_jwt_securise
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
APP_NAME=BoliAPI
APP_VERSION=0.1.0
DEBUG=true
```

*Note: En production, l'API force l'usage de SSL (`ssl=require`) pour PostgreSQL.*

## 🚀 Lancement

### Local

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Docker

```bash
docker build -t boli-api .
docker run -p 8000:8000 --env-file .env boli-api
```

L'API sera disponible sur `http://localhost:8000`  
Documentation interactive : `http://localhost:8000/docs`

## 📡 Endpoints Principaux

### Authentification
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/auth/register` | Inscription client/chauffeur |
| `POST` | `/auth/login` | Connexion JWT |
| `POST` | `/auth/refresh` | Rafraîchissement du token |

### Courses & Livraisons
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/rides/request` | Demande de course VTC / colis |
| `POST` | `/rides/{ride_id}/accept` | Acceptation par un chauffeur |
| `POST` | `/rides/{ride_id}/status` | Mise à jour de statut |
| `POST` | `/rides/sync` | Synchronisation Firestore ↔ PostgreSQL |
| `GET`  | `/rides/history` | Historique des courses |

### Marketplace
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET`  | `/marketplace/stores` | Commerces à proximité (filtrage catégorie) |
| `GET`  | `/marketplace/stores/{id}/products` | Produits d'un commerce |

### Wallet
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET`  | `/wallet/balance` | Solde utilisateur |
| `POST` | `/wallet/deposit` | Recharge / paiement (montant négatif = paiement) |
| `GET`  | `/wallet/transactions` | Historique des transactions |

## Modèles de Données Clés

### `RideMission` (PostgreSQL)
```
id              UUID PRIMARY KEY
client_id       VARCHAR
driver_id       VARCHAR (nullable)
merchant_id     VARCHAR (nullable)
type            VARCHAR  -- 'vtc' | 'food' | 'package'
status          VARCHAR  -- 'pending' | 'going_to_pickup' | 'arrived' | 'processing' | 'completed' | 'cancelled'
price           FLOAT
pickup_point    GEOMETRY(Point, 4326)
dropoff_point   GEOMETRY(Point, 4326)
package_description TEXT (nullable)
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### `Order` (Firestore)
Document temps réel synchronisé avec PostgreSQL via `/rides/sync` :
```json
{
  "storeId": "restaurant_123",
  "customerId": "user_456",
  "items": [...],
  "total": 12500,
  "status": "paid",
  "deliveryStatus": "pending",
  "driverId": null,
  "driverLat": null,
  "driverLng": null,
  "pickupLat": 12.6450,
  "pickupLng": -8.0050,
  "deliveryLat": 12.6392,
  "deliveryLng": -8.0029
}
```

## Flux de Données

### Demande de course VTC
1. Client sélectionne destination → `POST /rides/request`
2. Backend crée mission PostgreSQL + document Firestore
3. Notification WebSocket aux chauffeurs à proximité
4. Chauffeur accepte → `POST /rides/{id}/accept` (status: `going_to_pickup`)
5. Firestore mis à jour → client voit le statut en temps réel
6. Statuts successifs : `arrived` → `processing` → `completed`
7. Chaque transition appelle `/rides/sync` pour persister dans PostgreSQL

### Livraison
1. Client commande via marketplace → Firestore `orders` (status: `pending`)
2. Livreur voit commande dans `availableDeliveriesStreamProvider`
3. Livreur accepte → status `assigned`
4. Flux : `going_to_store` → `picked_up` → `on_the_way` → `delivered`
5. Synchronisation `/rides/sync` à chaque étape avec `type: 'food' | 'package'`

## 🔒 Sécurité

- **JWT** obligatoire sur tous les endpoints protégés (`CurrentUserId`)
- **Rate limiting** via `slowapi`
- **CORS** configuré pour le client Flutter
- **Headers sécurisés** (HSTS, X-Content-Type-Options, etc.)

## 🧪 Tests

```bash
$env:PYTHONPATH="."
pytest tests/ -v
```

## 📄 Licence
MIT — Voir [LICENSE](../LICENSE)
