# HdRezka DB Filter

A local search page querying a custom PostgreSQL database of movies. Regular search does not make live queries to Rezka or IMDb: data must be imported into the database first.

## Features

- users are configured via `APP_USERS`;
- individual movie states for each user: `seen`, `hidden`, `favorite`, `watchlist`;
- search results history by `user_id + query_hash`;
- inclusion filters for genres and countries;
- exclusion ban-lists for genres and countries;
- IMDb rating min/max filter;
- IMDb rating sorting (highest first or lowest first);
- random movie selection preserving all active filters;
- card mode and text list mode;
- dark theme;
- loading more new releases, popular movies, or genre catalogs via `Load More` button;
- automatic Rezka cookies update via Playwright/headless;
- Telegram alerts for crawler, FastAPI, and cookie-refresh failures;
- Dockerfile and Docker Compose to run the web application with PostgreSQL;
- GitHub Actions CI with tests verification and Docker build;
- publication of production images to GitHub Container Registry;
- SSH deployment to VPS via GitHub Actions with candidate container and rollback;
- production infrastructure files synchronization on VPS before deployment;
- systemd backup timer for PostgreSQL;
- Grafana + Loki + Promtail for centralized Docker logs;
- local seed/reset/test scripts without network requests.

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Database

```bash
docker run --name hdrezka-postgres \
  -e POSTGRES_USER=hdrezka_user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=hdrezka_filter \
  -p 5432:5432 \
  -d postgres:16

cp .env.example .env
export DATABASE_URL="postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter"
psql "$DATABASE_URL" -f migrations/001_init.sql
```

If Rezka returns `403`, open `https://rezka.ag/new/` in a browser,
go to DevTools -> Network -> Copy as cURL, and copy the actual values of
`User-Agent`, `Accept-Language`, and `Cookie` to `.env`:

```env
REZKA_USER_AGENT=...
REZKA_ACCEPT_LANGUAGE=...
REZKA_COOKIE=...
```

Cookies can be updated via Playwright/headless:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/python -m app.cookie_refresher refresh
```

By default, the cookie is written to `runtime/rezka_cookie.txt`. The application reads
this file first, and falls back to `REZKA_COOKIE` from `.env`. To update daily
at 02:00 when FastAPI starts:

```env
REZKA_COOKIE_REFRESH_ENABLED=1
REZKA_COOKIE_REFRESH_HOUR=2
REZKA_COOKIE_REFRESH_MINUTE=0
REZKA_COOKIE_FILE=runtime/rezka_cookie.txt
```

If you also want to overwrite the `REZKA_COOKIE=` line in the local `.env` file, enable:

```env
REZKA_COOKIE_REFRESH_WRITE_ENV=1
```

Test data:

```bash
.venv/bin/python tests_local/seed_test_data.py
```

Reset test movies and user states:

```bash
.venv/bin/python tests_local/reset_test_db.py
```

## Crawler

```bash
.venv/bin/python -m app.crawler run
```

In the interface, the `Load More` button performs a small incremental import into the database.
If a genre is selected in the current search, the crawler queries the corresponding Rezka catalog,
for example `/films/detective/`, `/series/detective/`, `/cartoons/detective/` or `/animation/detective/`,
and applies current include/ban filters before saving. If no genre is selected, it uses the new releases source `/new/`.
In the "Import Source" field, you can explicitly choose "New Releases" or "Popular by filters".
If a genre is recognized for the current request, popular queries the `best` catalog, for example:

```text
https://rezka.ag/films/best/detective/
https://rezka.ag/films/best/detective/page/2/
```

For `Type = Anime`, the `/animation/` section is used, e.g., `/animation/best/horror/`;
for cartoons, `/cartoons/` is used, and for series, `/series/` is used.

Countries are not added to the URL and are applied only as a post-filter after reading the movie page.
If the genre is not recognized, the general popular feed is used:

```text
https://rezka.ag/new/?filter=popular
https://rezka.ag/new/page/2/?filter=popular
```

By default, a single import click is limited to:

```env
CRAWLER_LOAD_MORE_PAGE_LIMIT=3
CRAWLER_LOAD_MORE_ITEM_LIMIT=30
CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT=0
CRAWLER_LOAD_MORE_SLEEP_SECONDS=0
```

The database is populated via the `Load More` button, the CLI command `python -m app.crawler run`,
or the optional passive crawler. The cookie-refresh scheduler only updates cookies for Rezka
and does not run the crawler.

`CRAWLER_LOAD_MORE_ITEM_LIMIT` specifies the target count of saved matching movies,
not the number of scanned cards. The crawler applies the current genre/country inclusion,
exclusion filters, content type, and IMDb range before saving. For narrow filters,
like `Detective + UK`, the crawler may check many candidates, skip non-matching countries,
and save less than the limit if there are too few matching movies within `CRAWLER_LOAD_MORE_PAGE_LIMIT` pages.

The UI incremental load stores resume progress separately for each set of filters and source.
Thus, different requests do not interfere with each other's `last_page`, but repeated clicks
with the exact same filters will continue going deeper into the same catalog.

The passive crawler is enabled separately and is disabled by default:

```env
PASSIVE_CRAWLER_ENABLED=1
PASSIVE_CRAWLER_INTERVAL_SECONDS=3600
PASSIVE_CRAWLER_INITIAL_DELAY_SECONDS=300
PASSIVE_CRAWLER_PAGE_LIMIT=2
PASSIVE_CRAWLER_ITEM_LIMIT=10
PASSIVE_CRAWLER_BAN_COUNTRIES=Russia,USSR
```

It runs in the background alongside FastAPI, selecting one catalog per cycle, picking the catalog
that has progressed the least in terms of `last_page`. The resume progress is stored separately
in `catalog_crawl_state` with the prefix `passive:v1`, so it does not interfere with the UI import.
By default, the crawler cycles through `new`, `popular`, genre, and best catalogs for `films`,
`series`, `cartoons`, and `animation`. Movies from countries like `Russia` and `USSR` are discarded before writing to the DB.
If a catalog returns an empty page, the passive crawler marks it as `exhausted` and excludes it from the regular rotation.

To manually run the passive crawler once:

```bash
docker compose run --rm app python -m app.passive_crawler run-once
```

The crawler saves movie links and poster image URLs, but does not download the images themselves.
The IMDb rating and `imdb_id` are extracted from the Rezka page, if available.

By default, the crawler goes through new releases:

```text
https://rezka.ag/new/
https://rezka.ag/new/page/2/
```

Crawling by genres is available separately:

```bash
.venv/bin/python -m app.crawler run --source genres
```

Popular and best catalogs are available separately:

```bash
.venv/bin/python -m app.crawler run --source popular
.venv/bin/python -m app.crawler run --source best --best-slugs detective
```

Quick smoke-run:

```bash
CRAWLER_PAGE_LIMIT=1 CRAWLER_ITEM_LIMIT=5 CRAWLER_IMDB_ITEM_LIMIT=2 .venv/bin/python -m app.crawler run
```

## Running Web Application

```bash
.venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Debug:

```bash
HDREZKA_DEBUG=1 .venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

## Env Notes

`HDREZKA_DEBUG=0` disables verbose debug logging. Setting it to `1` will write SQL/debug parameters to stdout or `docker compose logs app`.

`REZKA_COOKIE_REFRESH_WRITE_ENV=0` means the Playwright cookie refresher will not overwrite `.env`; new cookies will only be written to `REZKA_COOKIE_FILE`, e.g., `runtime/rezka_cookie.txt`. Setting it to `1` will also replace the `REZKA_COOKIE=` line in the local `.env`.

`REZKA_FETCH_MODE=requests` uses the legacy HTTP client for Rezka. If Rezka returns `403` to standard HTTP requests, you can enable the browser-based fetch:

```env
REZKA_FETCH_MODE=playwright
REZKA_PLAYWRIGHT_BROWSER=firefox
REZKA_PLAYWRIGHT_HEADLESS=1
REZKA_PLAYWRIGHT_PROFILE_DIR=runtime/rezka_browser_profile
```

Optional proxy for browser Rezka requests only:

```env
REZKA_PLAYWRIGHT_PROXY=http://user:password@host:port
```

The crawler reuses a single persistent browser profile across and between runs. If Playwright still gets `403` on the VPS, the issue is typically with the outbound IP/datacenter rather than cookies.

`CRAWLER_SOURCE=new` sets the default CLI crawler source. Valid values: `new` crawls `/new/`, `popular` crawls `/new/?filter=popular`, `best` crawls `/{section}/best/{slug}/`, `genres` crawls genre catalogs. In the UI, `auto` selects a genre catalog if a genre is recognized from the query or filter; otherwise, it falls back to `new`. The UI source "Popular by filters" selects `best` if a genre is recognized, otherwise it falls back to general `popular`.

## Telegram Alerts

Create a Telegram bot via BotFather, obtain the token and chat ID, and add them to `.env`:

```env
TELEGRAM_ALERTS_ENABLED=1
TELEGRAM_BOT_TOKEN=123456:replace_me
TELEGRAM_CHAT_ID=123456789
```

If these values are empty or `TELEGRAM_ALERTS_ENABLED=0`, the application simply will not send alerts.

## Docker Compose Local

The recommended way to run the application is via Docker Compose. It spins up PostgreSQL, the web app, and a one-time database initialization service.

```bash
cp .env.example .env
mkdir -p runtime

docker compose up -d db
docker compose run --rm init-db
docker compose up -d --build app
```

Open:

```text
http://127.0.0.1:8000/
```

`init-db` applies migrations, deletes test movies/states/logs, and creates users defined in `.env`:

```env
APP_USERS=user1:User 1,user2:User 2
```

Running `init-db` again will clear the database. Do not run it if you want to keep already crawled movies.

Useful commands:

```bash
docker compose logs -f app
docker compose logs -f db
docker compose restart app
docker compose down
docker compose up -d --build app
```

Manual cookie-refresh execution inside Compose:

```bash
docker compose run --rm app python -m app.cookie_refresher refresh
```

Manual crawler execution:

```bash
docker compose run --rm app python -m app.crawler run --source popular --page-limit 1 --item-limit 10
```

Manual crawler execution via Playwright without modifying `.env`:

```bash
docker compose run --rm -e REZKA_FETCH_MODE=playwright -e REZKA_PLAYWRIGHT_BROWSER=firefox app python -m app.crawler run --source new --page-limit 1 --item-limit 5
```

## Git and GitHub SSH

For a normal `git push`, using SSH remote is more convenient. First, generate or check your local key:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
```

Add the public key to your GitHub account: Settings -> SSH and GPG keys. Then switch the remote URL:

```bash
git remote set-url origin git@github.com:despa1r0/hdrezka_search.git
ssh -T git@github.com
git push
```

If `ssh -T git@github.com` confirms that GitHub successfully authenticated the user, subsequent push/pull operations will go through SSH.

## CI/CD

The GitHub Actions workflow is located at `.github/workflows/ci.yml`.

What the workflow does:

- `test`: installs Python dependencies, compiles code, runs health endpoint tests, and runs `docker build`;
- `publish`: on the `master` branch, it builds and publishes the image to `ghcr.io/despa1r0/hdrezka_search`;
- `deploy`: if `CD_ENABLED=true`, it copies production infrastructure files to the VPS, and then runs `scripts/deploy.sh` with an immutable image tag based on the Git SHA.

To enable CD, the following GitHub secrets are required:

```text
VPS_SSH_PRIVATE_KEY
VPS_KNOWN_HOSTS
VPS_HOST
VPS_PORT
VPS_USER
```

And a repository variable:

```text
CD_ENABLED=true
```

`VPS_SSH_PRIVATE_KEY` must be a dedicated deploy key for GitHub Actions to access the VPS. Add its public key to `/home/deploy/.ssh/authorized_keys` on the VPS (or to the `authorized_keys` of the user specified in `VPS_USER`).

`VPS_KNOWN_HOSTS` can be obtained from your local machine:

```bash
ssh-keyscan -p 22 VPS_HOST
```

If `VPS_PORT` is not set, the deploy script defaults to `22`.

Before updating the app, the deploy job syncs the following to the VPS:

```text
docker-compose.prod.yml
docker-compose.observability.yml
scripts/deploy.sh
scripts/backup-db.sh
ops/
```

Local VPS files like `.env`, `runtime/`, and `backups/` are excluded from the sync process and are not overwritten.

After a successful push to `master` with `CD_ENABLED=true`, the execution flow is:

```text
test -> publish image to GHCR -> sync infra files -> candidate healthcheck -> app update
```

If `test`, `publish`, or the candidate healthcheck fails, the production app will not be updated.

## VPS + Tailscale

Recommended setup: Tailscale is installed on the VPS, and Docker exposes the web container only on the Tailscale IP. This makes the app accessible only to members of your tailnet, keeping it closed to the public internet.

On a clean Ubuntu/Debian VPS:

```bash
sudo apt update
sudo apt install -y git curl
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Re-login via SSH for the `docker` group membership to take effect, then install Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4
```

Copy the Tailscale IP. Next, clone the project:

```bash
git clone https://github.com/despa1r0/hdrezka_search.git
cd hdrezka_search

cp .env.example .env
nano .env
```

For a production layout, it's best to keep the project in `/opt/hdrezka_search`:

```bash
sudo mkdir -p /opt/hdrezka_search
sudo chown "$USER:$USER" /opt/hdrezka_search
```

The CD and backup scripts expect this specific path.

In the `.env` file on the VPS, set the configuration. You can replace the sample `APP_USERS` with the actual ones:

```env
COMPOSE_PROJECT_NAME=hdrezka_search
POSTGRES_USER=hdrezka_user
POSTGRES_PASSWORD=replace_with_strong_password
POSTGRES_DB=hdrezka_filter
APP_BIND=YOUR_TAILSCALE_IP_HERE
APP_PORT=8000
APP_USERS=client1:Client 1,client2:Client 2
DATABASE_URL=postgresql://hdrezka_user:replace_with_strong_password@db:5432/hdrezka_filter
REZKA_COOKIE_REFRESH_ENABLED=1
REZKA_COOKIE_REFRESH_HOUR=2
REZKA_COOKIE_REFRESH_MINUTE=0
TELEGRAM_ALERTS_ENABLED=1
TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHAT_ID=replace_me
```

`APP_BIND` is important: it ensures Docker only listens on the Tailscale IP of the VPS, not on the public interface.

### Fresh Start (No DB Migration)

Only for an empty database:

```bash
mkdir -p runtime
docker compose up -d db
docker compose run --rm init-db
docker compose up -d --build app
```

`init-db` deletes movies/states. Do not run it if you are migrating existing data.

### Migrating Existing Database

Generate a dump on the source machine:

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/hdrezka_filter_$(date +%Y%m%d_%H%M%S).dump
```

Copy the dump to the VPS, for example:

```bash
scp backups/hdrezka_filter_20260609_153444.dump user@VPS_IP:/opt/hdrezka_search/backups/
```

Restore the dump on the VPS instead of running `init-db`:

```bash
cd /opt/hdrezka_search
mkdir -p runtime backups
docker compose up -d db
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backups/hdrezka_filter_20260609_153444.dump
docker compose up -d --build app
```

If you need to rename existing users while preserving their `seen`, `favorite`, and `shown_items` status, configure the new `APP_USERS` in `.env` and run:

```bash
docker compose run --rm app python -m app.admin rename-existing-users
docker compose restart app
```

This command maps users by their current ID and their position in `APP_USERS`. The number of users in the DB must match the number of users in `APP_USERS`.

Access the application from a phone connected to the same Tailnet:

```text
http://YOUR_VPS_TAILSCALE_IP:8000/
```

If `ufw` is active, allow the port only on the Tailscale interface:

```bash
sudo ufw allow in on tailscale0 to any port 8000 proto tcp
```

Updating after a new push:

```bash
git pull
docker compose up -d --build app
```

For production compose utilizing the published GHCR image:

```bash
cd /opt/hdrezka_search
IMAGE_TAG=latest docker compose -f docker-compose.prod.yml up -d db gluetun app
```

Once CD is enabled, manual updates on the VPS are generally unnecessary: pushing to `master` will build the image and trigger the deployment job to restart the `app` container on the VPS.

### Background Tasks

The passive crawler runs only when `PASSIVE_CRAWLER_ENABLED=1`. When FastAPI starts, it launches a daemon thread that crawls one catalog every `PASSIVE_CRAWLER_INTERVAL_SECONDS` seconds, writing suitable movies to the database. If this is `0` or empty, the database is populated only via the "Load More" button or the CLI command `python -m app.crawler run`.

Automatic cookie updates via Playwright run only when `REZKA_COOKIE_REFRESH_ENABLED=1`. On FastAPI startup, a daemon thread is spawned to refresh cookies once a day at `REZKA_COOKIE_REFRESH_HOUR:MINUTE`, writing them to `REZKA_COOKIE_FILE` (typically `runtime/rezka_cookie.txt`).

### PostgreSQL Backups

The backup script is located at `scripts/backup-db.sh`. It performs `pg_dump -Fc`, verifies the dump with `pg_restore --list`, writes a `.sha256` checksum, and removes older backups based on the retention policy.

Manual verification on the VPS:

```bash
cd /opt/hdrezka_search
BACKUP_RETENTION_DAYS=14 scripts/backup-db.sh
ls -lh backups
```

Systemd units are located in `ops/systemd/`. Installation:

```bash
sudo cp ops/systemd/hdrezka-backup.service /etc/systemd/system/
sudo cp ops/systemd/hdrezka-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hdrezka-backup.timer
systemctl list-timers hdrezka-backup.timer
```

Before enabling, ensure that `User=` and `Group=` settings in `hdrezka-backup.service` match the VPS user authorized to run Docker commands.

## Monitoring and Logs

The project includes a minimal observability stack:

```text
Grafana  -> UI for log visualization
Loki     -> log storage
Promtail -> collects Docker container logs
```

Configurations are located at:

```text
docker-compose.observability.yml
ops/loki/loki.yml
ops/promtail/promtail.yml
ops/grafana/provisioning/datasources/loki.yml
```

Add configuration values to production `.env`. Setting `OBS_BIND` to the Tailscale IP is recommended over public IP binding:

```env
OBS_BIND=YOUR_TAILSCALE_IP_HERE
GRAFANA_PORT=3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=replace_with_strong_password
LOKI_PORT=3100
```

Start the observability stack on the VPS:

```bash
cd /opt/hdrezka_search
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d loki promtail grafana
```

Verify:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml ps
docker logs --tail 100 hdrezka-promtail
docker logs --tail 100 hdrezka-loki
docker logs --tail 100 hdrezka-grafana
```

Open Grafana:

```text
http://YOUR_VPS_TAILSCALE_IP:3000/
```

The Loki datasource is configured automatically. In Grafana, navigate to Explore and select `Loki`. Sample queries:

```logql
{container="hdrezka-app"}
{service="app"}
{container="hdrezka-postgres"}
{container="hdrezka-gluetun"}
```

The passive crawler writes JSON strings to the app container's stdout. To filter these logs:

```logql
{container="hdrezka-app"} |= "\"component\": \"passive_crawler\""
```

To show only errors from the passive crawler:

```logql
{container="hdrezka-app"} |= "\"component\": \"passive_crawler\"" |= "\"level\": \"error\""
```

Completed cycles:

```logql
{container="hdrezka-app"} |= "\"event\": \"cycle_finished\""
```

Loki is configured for filesystem storage with a 7-day retention period:

```yaml
retention_period: 168h
```

CPU/RAM/disk/container metrics are currently not included. You can add Prometheus/cAdvisor/node-exporter in a future step.

Stop the observability stack:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml stop grafana promtail loki
```

## Future Work Roadmap

Recommended sequence:

1. Configure GitHub SSH push from your local machine.
2. Structure the production VPS directory layout as `/opt/hdrezka_search`.
3. Verify production compose manually: `db`, `gluetun`, `app`, `/readyz`.
4. Configure GitHub Actions secrets/variables and enable CD.
5. Manually run the workflow to verify candidate deployment and rollback.
6. Install and test PostgreSQL backups.
7. Set up Grafana/Loki/Promtail on the VPS.
8. Add dashboards and alerts on top of Loki.
9. Integrate metrics via Prometheus/cAdvisor/node-exporter if needed.
10. Return to app-specific improvements: retry/backoff, crawler limits, test expansion.

## Stopping the Server

Stop `uvicorn` in your terminal using `Ctrl+C`.

## Verification Checks

```bash
.venv/bin/python -m compileall -q app tests_local main.py
.venv/bin/python -m unittest tests_local.test_health_endpoints
.venv/bin/python tests_local/test_search_logic.py
```

`test_search_logic.py` requires a running PostgreSQL instance and migrations applied.

## Project Structure

```text
app/
  clients/              # Rezka/IMDb clients for future crawler work
  repositories/         # SQL repository layer
  services/             # search, state, query hash
  utils/
  config.py
  database.py
  server.py
migrations/
  001_init.sql
ops/
  grafana/provisioning/  # Grafana datasource provisioning
  loki/                  # Loki config
  promtail/              # Docker log collection config
  systemd/               # backup timer/service
static/
  app.js
  styles.css
templates/
  index.html
tests_local/
  docker-compose.observability.yml
  docker-compose.prod.yml
main.py
requirements.txt
```

Detailed status and next stages: [PROJECT_STATUS.md](PROJECT_STATUS.md).
