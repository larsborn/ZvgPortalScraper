# ZvgPortal Scraper

This is Python-based code able to scrape data from https://www.zvg-portal.de/.

## Installation

Even though dependencies of this application are minimal, it is recommended to run it in a virtual environment:

```bash
$ cd /path/to/ZvgPortal/
$ git clone 'https://github.com/larsborn/ZvgPortalScraper.git' .
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -U pip
$ pip install -r requirements.txt
```

## Usage

Set the `PYTHONPATH` environment variable and then you can execute `app.py`:

```bash
$ export PYTHONPATH=/path/to/ZvgPortal/  # the directory _containing_ the "zvg_portal" directory

$ python zvg_portal/app.py --help
usage: app.py [-h] [--debug] 
              [--print-stats] [--print-entries]
              [--base-url BASE_URL] [--raw-data-directory RAW_DATA_DIRECTORY] [--user-agent USER_AGENT]
              [--nsqd-address NSQD_ADDRESS] [--nsqd-port NSQD_PORT]
              [--client-side-crt CLIENT_SIDE_CRT] [--client-side-key CLIENT_SIDE_KEY]

optional arguments:
  -h, --help            show this help message and exit
  --debug
  --print-stats
  --print-entries
  --base-url BASE_URL
  --nsqd-address NSQD_ADDRESS
  --nsqd-port NSQD_PORT
  --client-side-crt CLIENT_SIDE_CRT
  --client-side-key CLIENT_SIDE_KEY
  --raw-data-directory RAW_DATA_DIRECTORY
  --user-agent USER_AGENT

```

For example like so:

```bash
$ python zvg_portal/app.py --nsqd-address nsqd.example.com --nsqd-port 4151
```

### Continuous mode

By default the scraper runs once and exits. Pass `--interval` (or set the `INTERVAL` environment variable) to run it as a self-scheduling daemon that sleeps between iterations:

```bash
$ python zvg_portal/app.py --interval 6h --nsqd-address nsqd.example.com --nsqd-port 4151
```

Accepted formats: `90s`, `30m`, `6h`, `1h30m`, or a plain integer (seconds). Unparseable values cause the process to exit with an error at startup.

Behavior in this mode:

- The first iteration runs immediately on startup; subsequent iterations start after the configured interval has elapsed since the previous one finished (sleep-after-finish, not wall-clock cadence).
- If an iteration raises an exception, it is logged with a traceback and the loop continues. Consecutive failures trigger exponential backoff up to 16× the configured interval; backoff resets after the first successful iteration.
- `SIGTERM` and `SIGINT` (`docker stop` / Ctrl+C) request a clean shutdown — the loop finishes its current iteration (or aborts the sleep) and exits without partial NSQ publishes.

Use continuous mode when you want a single long-running container on one host. Prefer external scheduling (host cron, Kubernetes `CronJob`, ofelia sidecar — see below) when you already operate one, when you need wall-clock scheduling, or when you want container-restart-as-recovery semantics.

## Running with Docker

A container image is published to the GitHub Container Registry on every version tag:

```
ghcr.io/larsborn/zvgportalscraper
```

The image is based on `python:3.13-slim-bookworm`, generates the `de_DE` / `de_DE.UTF-8` locales required by the application, and runs as an unprivileged `scraper` user (UID 1000).

### Pull the pre-built image

```bash
$ docker pull ghcr.io/larsborn/zvgportalscraper:latest
```

Tags follow the release version. For example, pushing tag `v1.2.3` publishes the image as `1.2.3`, `1.2`, `1`, `latest`, and `sha-<short>`. Pin a specific version in production rather than relying on `latest`.

### Build the image locally (alternative)

If you would rather build from source (e.g. for local changes), the repository ships a `Dockerfile`:

```bash
$ docker build -t zvg-portal-scraper .
```

### Run the scraper

Run it as a one-shot job. All CLI flags are forwarded to `app.py`:

```bash
$ docker run --rm \
    -v zvg-raw:/data/raw \
    ghcr.io/larsborn/zvgportalscraper:latest \
    --nsqd-address nsqd.example.com --nsqd-port 4151
```

The image declares `VOLUME /data/raw` and sets `RAW_DATA_DIRECTORY=/data/raw`, so raw scraped files are written to a mounted volume (named volume `zvg-raw` in the example above — use a bind mount like `-v /host/path:/data/raw` to persist to a host directory instead).

All arguments accepted by `app.py` also have environment variable equivalents (`BASE_URL`, `NSQD_ADDRESS`, `NSQD_PORT`, `CLIENT_SIDE_CRT`, `CLIENT_SIDE_KEY`, `RAW_DATA_DIRECTORY`), which can be passed with `-e`:

```bash
$ docker run --rm \
    -v zvg-raw:/data/raw \
    -e NSQD_ADDRESS=nsqd.example.com \
    -e NSQD_PORT=4151 \
    ghcr.io/larsborn/zvgportalscraper:latest
```

### Docker Compose / Portainer stack

The following `docker-compose.yml` pulls the published image from GHCR and can be pasted directly into a Portainer stack (or used with `docker compose`):

```yaml
services:
  zvg-scraper:
    image: ghcr.io/larsborn/zvgportalscraper:latest
    container_name: zvg-scraper
    environment:
      NSQD_ADDRESS: nsqd.example.com
      NSQD_PORT: "4151"
      # BASE_URL: https://www.zvg-portal.de
      # CLIENT_SIDE_CRT: /certs/client.crt
      # CLIENT_SIDE_KEY: /certs/client.key
    volumes:
      - zvg-raw:/data/raw
      # - /host/path/to/certs:/certs:ro
    restart: "no"

volumes:
  zvg-raw:
```

For continuous mode, add `INTERVAL` and switch the restart policy:

```yaml
services:
  zvg-scraper:
    image: ghcr.io/larsborn/zvgportalscraper:latest
    container_name: zvg-scraper
    environment:
      INTERVAL: 6h
      NSQD_ADDRESS: nsqd.example.com
      NSQD_PORT: "4151"
    volumes:
      - zvg-raw:/data/raw
    restart: unless-stopped

volumes:
  zvg-raw:
```

In this mode the container stays up; `restart: unless-stopped` covers process crashes that the in-app backoff cannot.

A few things to keep in mind:

- By default the scraper is a **one-shot job** — the container runs once and exits. `restart: "no"` reflects that; Compose/Portainer will mark the stack as "exited" after a successful run, which is expected. To turn it into a self-scheduling daemon instead, set `INTERVAL` (see the second example above) — no external scheduler needed.
- To run it on a schedule, trigger the stack externally: a host cron job invoking `docker compose run --rm zvg-scraper`, a Kubernetes `CronJob`, or a companion scheduler like [ofelia](https://github.com/mcuadros/ofelia) deployed alongside the stack.
- Pin a specific version (e.g. `ghcr.io/larsborn/zvgportalscraper:0.1.0`) in production instead of `:latest` so stack redeployments are reproducible.
- If you would rather build from the cloned repo directly in Portainer, replace `image:` with `build: .` and point the stack at the repository.
- Client-side certificate paths (`CLIENT_SIDE_CRT` / `CLIENT_SIDE_KEY`) must resolve *inside* the container — mount them as a read-only volume as shown in the commented lines.

## Development

Install the development dependencies (includes runtime deps plus `black`, `isort` and `pre-commit`):

```bash
$ pip install -r requirements-dev.txt
```

Then install the git hook so formatters run automatically on every commit:

```bash
$ pre-commit install
```

Code style is enforced by [black](https://github.com/psf/black) and [isort](https://github.com/pycqa/isort) (config in `pyproject.toml`, line length 120). To format the entire codebase manually:

```bash
$ pre-commit run --all-files
```

Run the unit tests from the repository root with:

```bash
$ PYTHONPATH=. python3 -m unittest discover -s tests
```

If `pytest` is installed, the same suite also runs with:

```bash
$ PYTHONPATH=. python3 -m pytest
```
