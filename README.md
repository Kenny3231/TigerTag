# TigerTag — Intégration Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/Kenny3231/tigertag.svg)](https://github.com/Kenny3231/tigertag/releases)
![Maintenance](https://img.shields.io/maintenance/yes/2025.svg)

> **⚠️ Avertissement** : Cette intégration est un projet communautaire **non officiel et non affilié** à TigerTag Project. Elle utilise l'API publique de TigerTag et n'est pas endorsée, soutenue ou maintenue par TigerTag Project.

---

## À propos

Cette intégration Home Assistant permet de synchroniser votre inventaire de bobines de filament [TigerTag](https://tigertag.io) directement dans Home Assistant.

Elle inclut :
- Une **intégration HA** (sensors, entités number) pour chaque bobine
- Une **carte Lovelace custom** (`tigertag-card`) pour gérer visuellement votre stock

---

## Fonctionnalités

- 📦 **Inventaire synchronisé** — toutes vos bobines TigerTag dans HA (rafraîchissement toutes les 5 min + bouton manuel)
- ⚖️ **Modification du poids** — modifiez le poids restant directement depuis la carte ou via service HA
- 🔗 **Twin Tag** — déduplication automatique des bobines avec 2 puces RFID
- 🖼️ **Images produit** — photo officielle pour les TigerTag+, SVG coloré dynamique pour les TigerTag classiques
- 🗂️ **Lieux de stockage** — assignez chaque bobine à une pièce (Garage, Salon, Bureau…)
- 🏭 **Intégration Bambu Lab** — envoi de la configuration filament vers l'AMS de votre imprimante
- 📊 **Sensor statistiques** — nombre de bobines, poids total, stock faible, bobines dans l'AMS
- 🌡️ **Paramètres d'impression** — températures buse/plateau, séchage exposés comme attributs
- 🗑️ **Nettoyage automatique** — les bobines supprimées dans l'app TigerTag disparaissent de HA
- 🌍 **Traductions** — Français, English, Español

---

## Prérequis

- Home Assistant 2024.1 ou supérieur
- Compte TigerTag avec une clé API 
- [HACS](https://hacs.xyz) installé

### Optionnel
- Intégration [ha-bambulab](https://github.com/greghesp/ha-bambulab) pour l'envoi vers l'AMS Bambu Lab

---

## Installation via HACS

### Méthode recommandée (HACS)

1. Ouvrez HACS dans Home Assistant
2. Cliquez sur le menu ⋮ → **Dépôts personnalisés**
3. Ajoutez l'URL : `https://github.com/Kenny3231/tigertag`
4. Catégorie : **Intégration**
5. Cliquez sur **TigerTag** → **Télécharger**
6. Redémarrez Home Assistant

### Installation manuelle

1. Copiez le dossier `custom_components/tigertag/` dans votre dossier `config/custom_components/`
2. Redémarrez Home Assistant

---

## Configuration

### 1. Ajouter l'intégration

**Paramètres → Appareils et services → Ajouter une intégration → TigerTag**

Renseignez :
- **Adresse e-mail** : votre e-mail TigerTag
- **Clé API** : disponible dans l'app TigerTag → Paramètres → API

### 2. Définir vos lieux de stockage

À l'étape suivante, entrez vos lieux séparés par des virgules :
```
Garage, Salon, Bureau, Cave
```

Vous pouvez les modifier à tout moment via **Paramètres → Appareils → TigerTag Studio → Configurer**.

### 3. Ajouter la ressource Lovelace (mode YAML uniquement)

Si votre Lovelace est en **mode YAML**, ajoutez dans `configuration.yaml` :

```yaml
lovelace:
  resources:
    - url: /local/tigertag-card.js
      type: module
```

En **mode UI**, la ressource est enregistrée automatiquement.

### 4. Ajouter la carte au dashboard

```yaml
type: custom:tigertag-card
mqtt_topic: device/VOTRE_SERIAL/request  # optionnel, pour Bambu Lab
low_stock_threshold: 250                  # seuil alerte stock faible (défaut: 250g)
rooms:                                    # optionnel, remplace les lieux de la config
  - Garage
  - Salon
```

---

## Entités créées

Pour chaque bobine TigerTag :

| Entité | Type | Description |
|--------|------|-------------|
| `sensor.tigertag_{uid}` | Sensor | Poids disponible + tous les attributs |
| `number.tigertag_{uid}` | Number | Poids modifiable |

### Sensor global

| Entité | Description |
|--------|-------------|
| `sensor.tigertag_statistiques` | Statistiques globales de l'inventaire |

### Attributs du sensor bobine

| Attribut | Description |
|----------|-------------|
| `uid` | Identifiant unique de la puce RFID |
| `brand` | Marque |
| `material` | Matériau (PLA, PETG, ABS…) |
| `color_name` | Nom de la couleur |
| `color_hex` | Couleur en hexadécimal (#rrggbb) |
| `img_url` | URL de l'image produit (TigerTag+) |
| `nozzle_temp_min/max` | Températures de buse recommandées |
| `bed_temp_min/max` | Températures plateau recommandées |
| `dry_temp` | Température de séchage |
| `dry_time_hours` | Durée de séchage |
| `ams_location` | Emplacement AMS Bambu Lab (ex: `sensor.p2s_ams_1_emplacement_1`) |
| `room_location` | Lieu de stockage |
| `has_twin` | `true` si la bobine a 2 puces RFID |
| `is_plus` | `true` si TigerTag+ (image officielle disponible) |
| `container_weight` | Tare officielle (g) |
| `container_weight_custom` | Tare personnalisée (override) |
| `link_msds/tds/rohs/reach` | Liens vers les fiches techniques |

---

## Services disponibles

### `tigertag.update_spool_weight`
Met à jour le poids d'une bobine. Gère automatiquement les Twin Tags.

```yaml
service: tigertag.update_spool_weight
data:
  uid: "8293117825192064"
  weight: 750
  container_weight: 250  # optionnel
```

### `tigertag.set_spool_room`
Assigne une bobine à un lieu de stockage.

```yaml
service: tigertag.set_spool_room
data:
  uid: "8293117825192064"
  room: "Garage"
```

### `tigertag.set_spool_tare`
Définit une tare personnalisée (masterspool non officiel).

```yaml
service: tigertag.set_spool_tare
data:
  uid: "8293117825192064"
  tare: 180
```

### `tigertag.refresh`
Force un rafraîchissement immédiat de l'inventaire.

```yaml
service: tigertag.refresh
```

---

## Exemples d'automatisations

### Alerte stock faible
```yaml
automation:
  trigger:
    platform: numeric_state
    entity_id: sensor.tigertag_statistiques
    attribute: count_low_stock
    above: 0
  action:
    service: notify.mobile_app
    data:
      message: "{{ state_attr('sensor.tigertag_statistiques', 'count_low_stock') }} bobine(s) en stock faible !"
```

---

## Carte Lovelace — tigertag-card

La carte est automatiquement disponible après installation.

### Fonctionnalités de la carte
- Grille de bobines avec image produit ou SVG coloré dynamique
- Recherche par marque, matériau, couleur, UID
- Filtres par lieu, AMS, stock faible
- Panneau latéral avec détail complet, modification du poids, gestion emplacement
- Détection automatique des imprimantes Bambu Lab et leurs trays AMS
- Déduplication automatique des Twin Tags

### Configuration YAML complète
```yaml
type: custom:tigertag-card
title: Mon stock de filaments
```

---

## Débogage

Activez les logs détaillés dans `configuration.yaml` :

```yaml
logger:
  default: warning
  logs:
    custom_components.tigertag: debug
```

---

## Contributions

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

### Structure du projet

```
custom_components/tigertag/
├── __init__.py          # Setup, services, enregistrement carte Lovelace
├── api.py               # Client HTTP TigerTag API
├── bambu.py             # Traduction TigerTag → protocole AMS Bambu Lab
├── config_flow.py       # Interface de configuration HA
├── const.py             # Constantes
├── coordinator.py       # DataUpdateCoordinator
├── helpers.py           # Fonctions partagées
├── number.py            # Entités poids modifiables
├── sensor.py            # Entités sensors + statistiques
├── storage.py           # Persistance locale
├── tigertag-card.js     # Carte Lovelace custom
├── services.yaml        # Déclaration des services
├── manifest.json        # Manifeste HACS
└── translations/        # Traductions FR/EN/ES
    ├── fr.json
    ├── en.json
    └── es.json
```

---

## Licence

Ce projet est sous licence **MIT**. Voir [LICENSE](LICENSE).

---

## Clause de non-responsabilité

Ce projet est **indépendant et non affilié** à TigerTag Project. Les marques TigerTag, TigerTag+ et TigerTag Studio sont la propriété de leurs détenteurs respectifs. L'utilisation de cette intégration se fait aux risques et périls de l'utilisateur. L'auteur décline toute responsabilité en cas de perte de données ou de dysfonctionnement.

Cette intégration utilise l'API publique de TigerTag. Son fonctionnement peut être affecté par des changements de l'API sans préavis.

---

## Remerciements

- [TigerTag Project](https://tigertag.io) pour leur système de gestion de filaments
- [greghesp/ha-bambulab](https://github.com/greghesp/ha-bambulab) pour l'intégration Bambu Lab
- La communauté Home Assistant
