# CI/CD — ansible-lint-kit

Système de CI/CD entièrement automatisé avec GitHub Actions : chaque changement
est testé, la version est déterminée automatiquement (SemVer), le changelog est
maintenu, et les releases sont publiées de façon contrôlée.

## Architecture

| Workflow | Déclencheur | Rôle |
|---|---|---|
| `.github/workflows/ci.yml` | push sur `main` / `feature/**`, pull requests | Tests, qualité, sécurité — **bloquant** |
| `.github/workflows/release.yml` | manuel (`workflow_dispatch`) | Publication contrôlée des releases |

Tous les jobs tournent sur les runners self-hosted Alienware
(`runs-on: [self-hosted, alienware]`). Aucun runner payant.

### Pipeline CI (`ci.yml`)

| Job | Contenu |
|---|---|
| Runner preflight | sonde Linux/WSL du runner (échoue si pas Linux) |
| Unit tests (Python 3.10 / 3.12) | `pytest` + couverture (`--cov=alk`, `coverage.xml` dans les artefacts `reports/`) + smoke test CLI |
| E2E migration (ansible-core 2.16 / 2.18) | `tests/e2e.sh` : dépôt Ansible 2.9 → `alk check --fix` → dépôt moderne valide |
| Quality gates | `yamllint` sur `.github/` + rapport `alk check` auto sur `examples/` |
| Security audit (pip-audit) | audit des dépendances contre les vulnérabilités connues (OSV) — **échoue si une faille est trouvée** (pip mis à jour d'abord, paquet local exclu via `--skip-editable`) |

Gardes-fous : `concurrency` (annule les runs supplantés), `timeout-minutes` par job,
PRs de forks ignorées sur les runners self-hosted (repo public), venvs isolés par job.

### Outils (`tools/`)

- **`tools/release.py`** — détermine la prochaine version et prépare la release :
  - analyse les commits conventionnels depuis le dernier tag (`feat:` → MINOR,
    `fix:`/`perf:`/`docs:`/... → PATCH, `BREAKING CHANGE` / `!` → MAJOR) ;
  - **ambiguïté** (aucun commit conventionnel) → refuse de deviner, exige `--version X.Y.Z` ;
  - génère la section CHANGELOG (Added/Changed/Fixed/Security/Deprecated/Removed),
    sans doublon ;
  - bump synchronisé de `pyproject.toml` et `alk/__init__.py`.
  - `--dry-run` : affiche le plan sans rien modifier. `--apply` : écrit les fichiers.
- **`tools/publish.py`** — publie (utilisé par `release.yml`) :
  - refuse si le tag ou la release existe déjà (pas de doublon) ;
  - refuse si la CI n'est pas vérifiée / si des modifications non liées traînent ;
  - commit `chore(release): X.Y.Z`, push sur `main`, tag `vX.Y.Z`, build
    (sdist + wheel) et création de la GitHub Release avec les notes du changelog
    et les artefacts.

## Publier une release

1. Merger le travail sur `main` (la CI doit être verte).
2. Aller dans **Actions → Release → Run workflow**.
3. Laisser `dry_run: true` pour vérifier le plan (version proposée + changelog),
   ou passer `dry_run: false` pour publier. Option `version` pour forcer `X.Y.Z`.
4. Le workflow vérifie que la CI est verte sur le HEAD de `main`, puis publie :
   commit, tag `vX.Y.Z`, GitHub Release + artefacts.

**Garanties :** aucune publication si un contrôle obligatoire échoue ;
aucune release en double (tag/release existant → échec clair) ;
aucun secret dans les logs (seul `GITHUB_TOKEN` est utilisé, jamais affiché).

## Versionnement

Écrire les commits au format conventionnel pour une détection automatique :

```
feat: add --vault-password-file support      → MINOR
fix: correct sudo regex                      → PATCH
feat!: drop Python 3.9                       → MAJOR
```

Sans commit conventionnel, la release demande une version explicite —
elle ne devine jamais.

## Maintenance

- **Ajouter un job CI** : éditer `ci.yml` (penser à l'ajouter au gate du
  `release.yml`, qui exige *tous* les checks verts).
- **Changer de runners** : modifier les `runs-on:` des workflows.
- **Dépendances** : `pip-audit` couvre les vulnérabilités connues ; ajouter
  `pytest-cov` etc. via les extras `dev`/`tools` de `pyproject.toml`.
- **Protection de branche** : `main` n'est actuellement pas protégée. Activer
  « Require status checks to pass » sur `main` (avec les jobs CI) empêcherait
  tout push direct contournant la CI — recommandé.
- **Tests des outils** : `tests/test_release.py` couvre la classification SemVer,
  le changelog et le bump de version.
