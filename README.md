# Boli Backend API (FastAPI)

API souveraine, résiliente et performante développée avec **FastAPI**, **Redis** et **PostgreSQL/PostGIS** pour la Super-App **Boli**.

## Fonctionnalités Clés
- **Ingestion Temps Réel** : Suivi des positions GPS des chauffeurs via WebSockets.
- **Matching Spatial** : Appairage en temps réel avec Redis Geo spatial in-memory.
- **Sécurisation** : Rate limiting avec `slowapi` et middleware de headers HTTP sécurisés.
- **Observabilité** : Logger structuré des requêtes HTTP et métriques Prometheus sur `/metrics`.

---

## Configuration

L'application charge ses variables d'environnement depuis le fichier `.env` à la racine de ce dossier :

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

*Note: En production, pour des connexions sécurisées à la base PostgreSQL, l'API force l'usage de SSL (`ssl=require`).*

---

## 🚀 Lancement & Exécution

### Exécution locale
1. Installez les packages requis :
   ```bash
   pip install -r requirements.txt
   ```
2. Démarrez l'API :
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### Docker
Vous pouvez lancer le serveur avec l'image Docker configurée dans le [Dockerfile](file:///c:/Users/Acer/Downloads/Projet/Dev/Boli/boliAPI/Dockerfile).

---

## 🧪 Tests Unitaires
Pour lancer le banc d'essais `pytest` :
```bash
$env:PYTHONPATH="."
pytest tests/ -v
```

---

## 📄 Licence
Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](../LICENSE) principal pour plus de détails.
