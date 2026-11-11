# 011 — Deployment Exposure Audit & Single-Origin Fix

**Date:** 2026-11-12
**Study context:** Browser-testing handoff (`docs/agent-browser-testing-handoff.md`) against the
deployed `oki` host. The host returned `404` on `/`, `/login` and `/health`, so the audit started
from the deployment rather than the UI.

**Summary:** Production had been undeployable since the auth/RBAC commit (two `:?` env vars missing
from Dokploy's environment) and, once serving, every cookie-authenticated mutation failed with `403`
because the API lived on its own public subdomain. Fixed by making the frontend host the single
public entry point with the API at `/api`, and by auditing/closing host-level exposure.

---

## Key Findings

### 1. Prod deploy died at compose interpolation for ~7 weeks

Dokploy's compose service `app` (`Wwaoy7RGlt8s08NqlyhI9`, branch `main`,
`./docker-compose.production.yml`) had `composeStatus = error`. The log:

```
error while interpolating services.backend.environment.FRONTEND_URL: required variable FRONTEND_URL is missing a value
error while interpolating services.backend.environment.JWT_SECRET_KEY: required variable JWT_SECRET_KEY is missing a value
Error: ❌ Docker command failed
```

- `docker-compose.production.yml` declares both with `:?`; Dokploy's environment had 17 vars and
  neither of them.
- Last **successful** deployment: `2026-09-21`. Every push since failed in ~3s, before any build, so
  Traefik had no route → `404` on every path. "Pushed and deployed" was not the same as "serving".
- `.env.production` (the canonical pasted file) was never updated with the auth section that
  `.env.production.example` gained, which is how the two vars went missing.
- Host had **no app volumes at all** (only Dokploy's own) — the first successful deploy built an
  empty database.

### 2. Cross-subdomain API broke CSRF (P0, blocked all mutations)

Symptom: `POST /api/books/upload?language=hin` → `403`; the identical request with a Bearer token
→ `201 Created`.

Mechanism:

- `POST /api/auth/login` sets `csrf_token` with **no `Domain`** attribute → host-only on
  `indic-book-metadata-extractor-api.agamya.us.kg`.
- The frontend runs on `indic-book-metadata-extractor.agamya.us.kg`, so `document.cookie` there is
  empty; `readCookie("csrf_token")` (`frontend/src/lib/api.ts`) returns `null`.
- No `X-CSRF-Token` header → `_check_csrf` (`backend/app/api/deps.py`) rejects →
  `403 CSRF validation failed`. Bearer auth skips the check (`from_cookie=False`), which is why curl
  worked.
- The auth design assumes one origin — the handoff doc said so, but the Dokploy domains did not.
  `COOKIE_DOMAIN=.agamya.us.kg` would have papered over it at the cost of widening every auth
  cookie to all of `agamya.us.kg`.

### 3. Public exposure inventory (before)

| Entry | Backs onto | Verdict |
|---|---|---|
| `…-extractor.agamya.us.kg/` | `frontend:3000` | intended |
| `…-extractor-api.agamya.us.kg/` | `backend:8000` | leak — `/docs` and `/openapi.json` were `200` |
| `…-extractor-flower.agamya.us.kg/` | `flower:5555` | leak (404 only because Flower was crash-looping) |
| `…-extractor-openrefine.agamya.us.kg/` | `openrefine:3333` | operator tool, kept public |
| `…-extractor-wikibase.agamya.us.kg/` | `wikibase:80` | publish target, kept public |
| `187.127.174.246:3000` | Dokploy panel | public admin surface |
| `187.127.174.246:8080` | Traefik API | **unauthenticated**; `/api/overview` returned every router/service/middleware |

- The host had **no firewall** (`ufw` inactive, `iptables -P INPUT ACCEPT`).
- The compose files themselves were clean: zero `ports:` in production, everything else `expose`,
  inter-service traffic over the Docker network by service name. All exposure came from the Dokploy
  domain entries plus Dokploy's own published ports.
- `mher/flower:latest` was still used in `production.yml`/`staging.yml` even though
  `fix(infra): run Flower from the backend image` had fixed only `docker-compose.yml` → Flower
  crash-looped under `Restarting (1)`.

---

## Recommendation

Single public entry point, adopted:

```
Host(app) && PathPrefix(/api)  →  backend:8000    (path preserved; higher priority)
Host(app)                      →  frontend:3000
```

- `NEXT_PUBLIC_API_URL=/api` (relative). Axios, `EventSource` and the page-image helpers
  (`${baseURL}/pages/…`) all become same-origin, so CSRF, cookies and SSE work by construction —
  this is what the code already assumed.
- Backend, worker, postgres, redis, ollama, mysql, elasticsearch, flower and backup stay
  internal-only. OpenRefine and Wikibase keep public hosts as operator tools.
- `/docs`, `/redoc` and `/openapi.json` now return `None` unless `DEBUG` is on.
- Dokploy panel (`:3000`) and Traefik API (`:8080`) stay **published at the server IP**. They were
  briefly blocked with a `DOCKER-USER` DROP, but `:3000` *is* the Dokploy panel, so that locked the
  operator out of his own control plane; it was reverted. Reach them via `ssh -N -L 3000:localhost:3000 oki`
  if you want an encrypted path, but do not close them without accepting the loss of IP access.

### 4. Production bind-mounted the application source out of Dokploy's working copy

Symptom: OCR died with `ModuleNotFoundError: No module named 'app.services.metrics'` from
`app/tasks/ocr_tasks.py:384`, while `metrics.py` is tracked in git, absent from `.gitignore` and
present in the built image.

- `docker-compose.production.yml` (and staging) mounted `./backend/app:/app/app`,
  `./backend/alembic:/app/alembic`, `./backend/alembic.ini:/app/alembic.ini` for the **backend and
  worker**. Every Dokploy deploy re-clones `code/`, replacing those directories.
- A container that survives a deploy (the worker, last recreated 22:27:38) keeps the *old inode*:
  host `backend/app` and the recreated backend were inode `1310807`, the running worker `1310812` —
  an orphaned, empty directory. The image's baked code was shadowed and `app` had no `services`
  package. The backend, recreated in the same deploy at 22:30:14, was fine.
- The image already `COPY`s `app/`, `alembic/` and `alembic.ini`, so the mounts were redundant as
  well as broken. Removed from production and staging; `docker-compose.yml` (dev) keeps them on
  purpose. Only `./docker/scripts/backend-entrypoint.sh:/entrypoint.sh:ro` remains (the image does
  not bake the entrypoint), which is read once at startup.

**Rollout order matters:** the frontend API URL is baked at build time, so the `/api` domain must be
added and the env updated **before** the deploy that rebuilds the frontend. Delete the `-api` /
`-flower` domains only after the single-origin path is verified.

---

## Next steps

1. Verify single-origin end to end (login → upload → SSE → page images) on the deployed host. **Done.**
2. Resume the §6 browser matrix — it was blocked at §6.2 by the 403, then at §6.3 by the OCR import error.
3. Consider baking `backend-entrypoint.sh` into the image (it is the last source bind; doing so means
   moving the script inside the `backend/` build context or switching the context to the repo root).

## References

- `docker-compose.production.yml` (`:?` vars, flower service), `.env.production.example`
- `backend/app/api/deps.py` (`_check_csrf`), `backend/app/api/auth.py` (`_set_auth_cookies`)
- `backend/app/main.py` (FastAPI docs gating), `frontend/src/lib/api.ts` (CSRF interceptor)
- `docs/agent-browser-testing-handoff.md`, `DEPLOY.md` §2–§3
- Dokploy compose service `Wwaoy7RGlt8s08NqlyhI9`; deployment log
  `/etc/dokploy/logs/indic-book-metadata-extractor-app-isbfmc/`
