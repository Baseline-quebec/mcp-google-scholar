# mcp-google-scholar

Serveur MCP pour la recherche d'articles et de profils sur Google Scholar, par scraping direct (`requests` + `beautifulsoup4`).

> Fork durci de [JackKuo666/Google-Scholar-MCP-Server](https://github.com/JackKuo666/Google-Scholar-MCP-Server). La dependance `scholarly` (non maintenue depuis 2023) et sa chaine transitive a risque (`free-proxy`, `fake-useragent`, `selenium`) ont ete retirees ; voir [SECURITY](#securite).

## Setup

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Aucun secret requis : le serveur n'accede qu'a des pages publiques de `scholar.google.com`.

## Usage

```bash
uv run python google_scholar_server.py
```

Transport stdio (FastMCP). Une fois lance, les trois outils sont disponibles cote assistant.

## MCP Tools (3)

| Outil | Type | Description |
|-------|------|-------------|
| `search_google_scholar_key_words` | Lecture | Recherche par mots-cles (`query`, `num_results=5`) |
| `search_google_scholar_advanced` | Lecture | Recherche avancee (`query`, `author`, `year_range`, `num_results=5`) |
| `get_author_info` | Lecture | Profil auteur : nom, affiliation, interets, citations, publications |

Chaque outil retourne des dictionnaires ; en cas d'echec, une cle `error` decrit la cause (incluant le cas CAPTCHA / rate-limit de Google Scholar).

## Development

```bash
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run pytest -q        # Tests
```

## Architecture

```
google_scholar_server.py      (FastMCP, transport stdio — couche outils MCP)
        |
google_scholar_web_search.py  (scraping requests + bs4 vers scholar.google.com)
```

## Securite

Ce fork existe pour reduire la surface d'attaque supply chain :

- **`scholarly` retire** : non maintenu depuis janvier 2023, il tirait `free-proxy` (telecharge des listes de proxy tierces a l'execution et y route le trafic), `fake-useragent` et `selenium`.
- **`get_author_info` reimplemente** en scraping direct, coherent avec les recherches deja existantes.
- **Backport `asyncio` retire** du `pyproject.toml` (le paquet PyPI `asyncio` masque le module stdlib sur Python moderne).
- **Versions epinglees** avec bornes majeures (`requests`, `beautifulsoup4`, `mcp`).
- **Detection CAPTCHA / rate-limit** pour des erreurs honnetes.

Compromis assume : sans proxies, Google Scholar peut servir un CAPTCHA sur les requetes intensives (surtout les profils auteurs). Les outils degradent proprement via une cle `error`.

## Licence

MIT (voir l'amont). Usage de recherche uniquement ; respecter les conditions d'utilisation de Google Scholar.
