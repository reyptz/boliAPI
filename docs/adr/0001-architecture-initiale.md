# ADR 0001 : Choix de l'Architecture Initiale et Stack Technique

- **Statut** : Accepté
- **Date** : 2026-06-09
- **Décideur** : Architecte Système

## Contexte et Problématique

Pour l'application **Boli** (VTC & Livraison), nous avons besoin d'une architecture résiliente, hautement performante pour le suivi GPS temps réel, et souveraine (sans dépendances coûteuses aux API de cartographie Google Maps). De plus, l'application doit être capable de gérer les zones à faible connectivité réseau.

## Décisions

1. **Architecture Globale** :
   - Adoption des principes de la **Clean Architecture** (domain, application, presentation, infrastructure) tant sur le backend FastAPI que sur le frontend Flutter pour découpler les règles métier pures des détails de persistance ou de framework.

2. **Backend Temps Réel & Matching** :
   - Utilisation de **FastAPI** avec des connexions **WebSockets** persistantes pour collecter les coordonnées GPS des chauffeurs en temps réel avec un minimum de latence.
   - Utilisation de **Redis** en mémoire (`GEOADD`, `GEORADIUS`) pour le matching spatial rapide des chauffeurs à proximité (< 2ms de latence).

3. **Moteur d'Itinéraires & Cartes** :
   - Utilisation de **OSRM (Open Source Routing Machine) / Valhalla** avec des fichiers de données **OpenStreetMap (OSM)** locaux auto-hébergés pour supprimer les frais d'API cartographiques tiers.

4. **Base de Données Relationnelle** :
   - **PostgreSQL** avec l'extension spatiale **PostGIS** pour la persistance à long terme et les calculs géographiques complexes (indexation $R\text{-tree}$).

5. **Client Mobile** :
   - **Flutter** pour générer une application mobile Android/iOS unique, avec intégration d'un cache local (*Offline-First*) et de transitions/retours haptiques fluides.

## Conséquences

- Indépendance totale vis-à-vis des coûts d'API récurrents.
- Excellente maintenabilité du code grâce à la Clean Architecture.
- Résilience aux pannes réseau avec une gestion élégante du mode hors-ligne.
