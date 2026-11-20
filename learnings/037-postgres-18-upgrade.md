# 037 — PostgreSQL 18 Upgrade (Fresh Volume)

- **Date:** 2026-11-20
- **Study context:** The stack was on `pgvector/pgvector:pg16` only because of the dead `vector`
  extension (removed in [`036`](036-pgvector-removal.md)). With the app database disposable, this was
  the cheapest moment to move to the current major rather than pin a legacy one.
- **Status:** Decision **approved and applied**. Host volumes cleared; deploy runs from Dokploy.
- **Decision owner:** user.

## Summary

Move to **PostgreSQL 18** on a fresh volume: `postgres:18-trixie` in production and staging,
`postgres:18-alpine` in the dev Compose file and CI. The change is small but **not** a tag swap — the
volume mount path has to change too, or the cluster silently lands outside the volume.

## Key findings

### 1. PG18 images use the versioned Debian data directory

Verified from the published images (`18`, `18-bookworm`, `18-alpine` all agree):

| Property | Value |
|---|---|
| `PGDATA` | `/var/lib/postgresql/18/docker` |
| Declared `VOLUME` | `/var/lib/postgresql` |
| Base | Debian 13 trixie, glibc 2.41 (`18` and `18-trixie`) |
| PostgreSQL | 18.7 |

The Compose files mounted `pgdata:/var/lib/postgresql/data`. Left unchanged, the cluster is created
under `/var/lib/postgresql/18/docker` **inside the container's writable layer**: the app starts, the
health check passes, backups run — and every container recreate silently starts an empty database.
The mount must be the parent directory:

```yaml
- pgdata:/var/lib/postgresql
```

### 2. The backup sidecar must move with the server

`backup` runs `postgres:16-alpine` and calls `pg_dump`. `pg_dump` refuses to dump from a server whose
major version is newer than its own ("server version mismatch"), so the nightly dump would start
failing after the upgrade. It moves to `postgres:18-alpine`. `docker/scripts/restore-db.sh` is
unaffected — it uses the server container's own `pg_restore`.

### 3. No dependency changes were needed

| Concern | Finding |
|---|---|
| asyncpg | Locked at **0.31.0**, which supports PostgreSQL "9.5 to 18" and has `Test on PostgreSQL 18 (#1290)` in its changelog. No bump required. |
| SQLAlchemy 2.x / Alembic 1.18.4 | No PG18 issues. |
| Extensions | Only `pg_trgm` (migrations `004`/`006`), bundled in every PG18 variant. No pgvector remains. |
| Auth | The official image defaults to `scram-sha-256` when `POSTGRES_PASSWORD` is set. No `pg_hba` changes. |
| Dumps | `pg_dump -Fc` archives from PG16 restore into PG18 with `pg_restore` 18. |

### 4. Tag choice

`bookworm` was only ever needed to match the glibc 2.36 of the pre-existing `pgdata` volume
(see [`036`](036-pgvector-removal.md) §"Note on the Postgres image tag"). On a fresh volume that
constraint disappears, so production and staging use `18-trixie`.

Dev and CI use `18-alpine` to stay light. The trade-off is that Alpine is musl libc and initialises
with a different collation than the glibc images, so ordering and `LIKE`/`pg_trgm` behaviour can
differ between CI and production. Nothing in the test suite depends on it, but it is a real
divergence — moving dev and CI to `18-trixie` is a one-line change if it ever bites.

## What changed

| File | Change |
|---|---|
| `docker-compose.production.yml` | `postgres:18-trixie`, mount `/var/lib/postgresql`, `backup` → `postgres:18-alpine` |
| `docker-compose.staging.yml` | Same as production |
| `docker-compose.yml` (dev) | `postgres:18-alpine`, mount `/var/lib/postgresql` |
| `.github/workflows/ci.yml` | Postgres service → `postgres:18-alpine` |
| `docs/development/local-development.md` | `postgresql-18` / `postgresql-server-dev-18`, `brew postgresql@18` |
| `docs/architecture/*`, `docs/application/data-model.md`, `README.md` | Version strings, mount path, tag rationale |
| `CHANGELOG.md` | Changed entry |

Alembic needed **no** change: the 22 migrations are version-agnostic and run from scratch on an empty
database.

## Next steps

1. Clear the app-side volumes on the host, keep one pre-upgrade dump, then let Dokploy deploy.
2. Verify the cluster actually lives on the volume: `docker exec <postgres> ls /var/lib/postgresql/18/docker`.
3. Confirm `pg_dump --version` in the backup container matches the server major.

## References

- [`036`](036-pgvector-removal.md) — the pgvector removal that made this possible
- [`015`](015-service-inventory-and-gating.md) — host inventory and memory profile
- `docs/architecture/integrations.md` — the PostgreSQL section this record expands on