# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet suit le [Semantic Versioning](https://semver.org/lang/fr/).

---

## [2.0.0] — 2025-05-01

### Première version publique

#### Fonctionnalités
- Synchronisation de l'inventaire TigerTag dans Home Assistant
- Sensor par bobine avec tous les attributs (poids, couleur, températures, liens)
- Entité number pour modification du poids directement depuis HA
- Gestion des Twin Tags (bobines avec 2 puces RFID) — déduplication automatique
- Image produit officielle pour TigerTag+ ou SVG coloré dynamique pour TigerTag classiques
- Sensor de statistiques globales (count_unique, total_weight_kg, count_low_stock…)
- Lieux de stockage configurables (Garage, Salon, Bureau…) persistés localement
- Tare masterspool personnalisable par bobine
- Intégration Bambu Lab — envoi configuration filament vers AMS via `bambu_lab.set_filament`
- Rafraîchissement automatique (5 min) + service `refresh` pour forçage immédiat
- Nettoyage automatique des bobines supprimées (`deleted: true`) et des entités orphelines
- Carte Lovelace custom `tigertag-card` avec grille, recherche, filtres et panneau détail
- Traductions FR, EN, ES
- Enregistrement automatique de la carte Lovelace (mode UI) ou instruction pour mode YAML

#### Services HA
- `tigertag.update_spool_weight` — mise à jour poids (Twin Tag géré automatiquement)
- `tigertag.set_spool_room` — assignation lieu de stockage
- `tigertag.set_spool_tare` — tare custom masterspool
- `tigertag.set_bambu_ams_filament` — envoi vers AMS Bambu Lab
- `tigertag.refresh` — rafraîchissement forcé

#### Technique
- Nettoyage des Firestore Timestamps de l'API (dicts non sérialisables par HA)
- Filtrage `deleted: true` à la source dans l'API
- `entity_id` forcés avec préfixe `tigertag_` indépendamment du nom donné à l'appareil
- Cache local des tables de référence (24h) avec fallback hors ligne
- Persistance locale des emplacements AMS, lieux et tares entre les redémarrages

---

## À venir

- Support multi-imprimantes (A1, X1, P1…)
- Tableau de bord AMS visuel avec les emplacements
- Support des bobines multicolores (gradient, conique)
- Gestion des profils de séchage
