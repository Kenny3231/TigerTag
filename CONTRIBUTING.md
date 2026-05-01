# Contribuer à ha-tigertag

Merci de votre intérêt pour contribuer à ce projet !

## Comment contribuer

### Signaler un bug
1. Vérifiez que le bug n'est pas déjà signalé dans les [Issues](https://github.com/Kenny3231/TigerTag/issues)
2. Ouvrez une nouvelle issue avec le template "Bug report"
3. Incluez :
   - La version de Home Assistant
   - La version de l'intégration
   - Les logs (activer le debug dans `configuration.yaml`)
   - Les étapes pour reproduire

### Proposer une fonctionnalité
1. Ouvrez une issue avec le template "Feature request"
2. Décrivez le cas d'usage et pourquoi c'est utile

### Soumettre une Pull Request
1. Forkez le dépôt
2. Créez une branche : `git checkout -b feature/ma-fonctionnalite`
3. Committez vos changements : `git commit -m 'feat: description'`
4. Poussez : `git push origin feature/ma-fonctionnalite`
5. Ouvrez une Pull Request

## Standards de code

- Python : suivre les conventions HA (async, coordinators, etc.)
- JavaScript : ES2020+, pas de dépendances externes
- Toujours tester avec une vraie instance HA avant de soumettre
- Mettre à jour `CHANGELOG.md` et `translations/` si nécessaire

## Structure des commits

```
feat: nouvelle fonctionnalité
fix: correction de bug
docs: documentation uniquement
refactor: refactoring sans changement fonctionnel
```
