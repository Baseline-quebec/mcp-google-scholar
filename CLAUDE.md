# Google Scholar MCP Server

Serveur MCP Python pour la recherche d'articles et de profils sur Google Scholar, par scraping direct (`requests` + `beautifulsoup4`).

## Resume du projet

Claude recherche des articles academiques (mots-cles ou recherche avancee) et recupere des informations de profil auteur sur Google Scholar. Tous les outils sont en lecture seule et n'accedent qu'a des pages publiques ; aucun secret n'est requis.

**Important** : ce repo est un fork durci de `JackKuo666/Google-Scholar-MCP-Server`. La dependance `scholarly` et sa chaine transitive a risque (`free-proxy`, `fake-useragent`, `selenium`) ont ete retirees pour des raisons de supply chain. Ne pas les reintroduire.

## Conventions

Ce projet suit les conventions Baseline.

### Stack

- **Python >= 3.13** (runtime epingle a 3.14), gestionnaire : **uv**
- **FastMCP** (`mcp[cli]`) pour le serveur MCP, transport stdio
- **requests** + **beautifulsoup4** pour le scraping (aucun navigateur, aucun proxy)
- **Linting** : ruff + ruff format
- **Tests** : pytest
- Dependances epinglees avec bornes majeures dans `pyproject.toml` et `requirements.txt`

### Commandes

```bash
uv venv --python 3.14 .venv         # Creer l'environnement
source .venv/bin/activate
uv pip install -r requirements.txt  # Installer les dependances
uv run ruff check .                 # Linting
uv run pytest -q                    # Tests
uv run python google_scholar_server.py  # Lancer le serveur MCP
```

## Architecture

```
google_scholar_server.py (FastMCP, stdio)
    |
    | enregistre les 3 outils @mcp.tool(), delegue via asyncio.to_thread
    v
google_scholar_web_search.py (scraping synchrone requests + bs4)
    |
    v
scholar.google.com (pages publiques HTML)
```

- `_parse_results` : parse une page de resultats en liste d'articles.
- `_find_author_id` : resout un nom d'auteur vers un id de profil Scholar.
- `_is_blocked` : detecte l'interstitiel CAPTCHA / rate-limit (marqueurs precis, pas le simple mot "captcha").
- `_parse_int` : parse un entier avec separateur de milliers (citations), 0 si echec.

Les recherches mots-cles / avancee et la page profil verifient toutes `_is_blocked` (echec explicite via cle `error`, jamais de resultat vide silencieux).

## Outils MCP (3 total)

| Outil | Parametres | Type |
|-------|-----------|------|
| `search_google_scholar_key_words` | query, num_results=5 | Lecture |
| `search_google_scholar_advanced` | query, author, year_range, num_results=5 | Lecture |
| `get_author_info` | author_name | Lecture |

## Securite

- Surface d'attaque supply chain minimisee : pas de `scholarly` / `free-proxy` / `fake-useragent` / `selenium`.
- Aucun secret, aucune ecriture, aucun appel reseau hors `scholar.google.com`.
- Sans proxies, Google Scholar peut servir un CAPTCHA sur requetes intensives ; les outils degradent via une cle `error` plutot que de masquer l'echec.
- Bumps de dependances volontaires (a integrer a la revue hebdo MCP deps de Baseline).
