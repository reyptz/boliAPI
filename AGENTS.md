# Spécifications de l'Agent d'Orchestration (Back-End) - BoliAPI

Cet agent (développé en **FastAPI** pour la haute performance asynchrone) sert de passerelle intelligente (API Gateway & Matching Engine). Il orchestre les flux en temps réel et fait le pont avec le cœur transactionnel lourd (**Expo / Firebase / SuguJate**).

## 1. Responsabilités de l'Agent

* **Ingestion des Flux Temps Réel :** Terminaison des milliers de connexions WebSockets des chauffeurs actifs.
* **Matching Géospatial Éclair :** Calcul de proximité immédiat en mémoire vive (RAM).
* ** découplage des Services :** Isolement du trafic VTC temps réel pour éviter d'impacter la base de données Firebase de SuguJate lors des pics de charge.

---

## 2. Pipeline Technique de Traitement (Matching VTC)

Quand un client initie une demande de course, l'agent exécute l'algorithme suivant sans toucher à la base de données relationnelle :

### Étape 1 : Réception & Validation (FastAPI)
L'agent intercepte la requête du client, valide son JWT et interroge **Redis** pour vérifier que l'abonnement client est actif ou que le Wallet est provisionné.

### Étape 2 : Requête In-Memory (Redis Geo)
L'agent exécute une recherche géospatiale pour localiser les chauffeurs disponibles dans un rayon de 3KM :
```python
# Pseudo-code de l'agent FastAPI
drivers = redis_client.georadius(
    name="active_drivers",
    longitude=client_lon,
    latitude=client_lat,
    radius=3000,
    unit="m",
    withcoord=True
)

### Étape 3 : Dispatch Événementiel
L'agent pousse la demande de course dans la file d'attente RabbitMQ ou Redis Pub/Sub dédiée aux IDs des chauffeurs sélectionnés. Les téléphones des chauffeurs reçoivent la notification instantanément via leur WebSocket ouvert.

## 3. Robustesse et Sécurité (SecOps Infra)
### Protection contre la saturation (Rate Limiting)
L'agent intègre un middleware basé sur l'algorithme Token Bucket stocké dans Redis. Un utilisateur ou un bot tentant de spammer les requêtes de recherche de chauffeurs est banni temporairement après $X$ requêtes/seconde.