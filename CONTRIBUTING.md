# Contribuer à ParisMove AI

Merci de ton intérêt ! Ce guide résume les conventions du projet.

## Setup local

Voir la section *Démarrage rapide* du [README](README.md).

## Workflow Git

- Branche principale : `main` (protégée, merge par PR uniquement)
- Branche d'intégration : `develop`
- Branches de feature : `feat/<nom-court>` ou `fix/<nom-court>`

```bash
git checkout develop
git pull
git checkout -b feat/prim-client
# ... modifs ...
git push -u origin feat/prim-client
# Ouvrir une PR vers develop
```

## Convention de commits

[Conventional Commits](https://www.conventionalcommits.org/) :

- `feat:` nouvelle fonctionnalité
- `fix:` correction de bug
- `docs:` documentation uniquement
- `refactor:` refactoring sans changement fonctionnel
- `test:` ajout ou correction de tests
- `chore:` maintenance, dépendances, config

Exemple : `feat(ingestion): add PRIM client with retry and rate limiting`

## Checklist avant PR

- [ ] `ruff check .` passe sans erreur
- [ ] `mypy` passe sur le service modifié
- [ ] Tests unitaires ajoutés et `pytest` passe
- [ ] README ou docs mis à jour si nécessaire
- [ ] Pas de secret commité

## Style de code

- Python 3.11+, typage strict obligatoire pour le code de production
- Modules nommés en `snake_case`
- Classes en `PascalCase`
- Constantes en `UPPER_SNAKE_CASE`
- Pas de `from module import *`
- Docstrings pour toute fonction publique (style Google)
