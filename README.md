# Zomboid Admin Dashboard

A small web UI that runs **in the same Linux container** as a Project Zomboid dedicated server. Log in, see whether the process is up, and edit the files that actually control the server:

- `Zomboid/Server/<name>.ini` — public name, passwords, ports, `WorkshopItems`, `Mods`
- `Zomboid/Server/<name>_SandboxVars.lua` — vanilla sandbox plus extra pages discovered from each mod’s `media/sandbox-options.txt`

## Why Save and restart exists

If you edit those files while the dedicated server is running, Project Zomboid often **writes its in-memory copy back on shutdown** and your changes disappear. The dashboard’s primary action is **Save and restart**: stop, wait for exit, backup the configs, write the new files, then start.

## Setup

```bash
cd /path/to/Zomboid-web
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# edit .env
chmod +x run.sh
./run.sh
```

Then open `http://127.0.0.1:8080` (or SSH-tunnel that port). Default bind is localhost on purpose.

### `.env` you must set

| Variable | Purpose |
| --- | --- |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Dashboard login |
| `SESSION_SECRET` | Cookie signing key (long random string) |
| `ZOMBOID_HOME` | Data dir that contains `Server/`, `Logs/`, `Saves/` |
| `PZ_SERVER_NAME` | File prefix, usually `servertest` |
| `STEAM_WORKSHOP_DIR` | Workshop cache, typically `.../steamapps/workshop/content/108600` |
| `PZ_START_CMD` / `PZ_STOP_CMD` | How this container already starts/stops PZ |
| `PZ_STATUS_CMD` | Optional; e.g. `systemctl is-active zomboid` |

If PZ is a systemd unit:

```
PZ_START_CMD=systemctl start zomboid
PZ_STOP_CMD=systemctl stop zomboid
PZ_STATUS_CMD=systemctl is-active zomboid
```

If it is a script:

```
PZ_START_CMD=/home/steam/pzserver/start-server.sh
PZ_STOP_CMD=pkill -f ProjectZomboid64
```

Use whatever already works on this box. The dashboard only shells out to those commands.

### Optional systemd unit for the dashboard

```ini
[Unit]
Description=Zomboid Admin Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/Zomboid-web
EnvironmentFile=/opt/Zomboid-web/.env
ExecStart=/opt/Zomboid-web/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Exposing it beyond localhost

Keep `BIND_HOST=127.0.0.1` and put Caddy or nginx in front with TLS. Example Caddy snippet:

```
pz-admin.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Do not put this on the public internet without TLS and a strong `ADMIN_PASSWORD`. Treat it like RCON: anyone logged in can change sandbox, mods, and restart the world.

### RCON (player list)

Set `RCONPassword` (and usually `RCONPort=27015`) in the server `.ini`. The dashboard reads that password from the file and queries `players` for the dashboard count.

## Pages

- **Dashboard** — online/offline, uptime, CPU/RAM, players, start/stop/restart, log tail
- **Server** — curated `.ini` fields plus a searchable list of every other key
- **Workshop** — Workshop IDs (Steam titles), Mod IDs from `mod.info`, add by URL/ID, reorder (drag or arrows), mismatch warnings
- **Sandbox** — vanilla groups plus a new section per mod that ships `sandbox-options.txt`

Config backups land in `BACKUP_DIR` (default `./backups/<timestamp>/`).

## Tests

```bash
.venv/bin/pytest
```

## Out of scope (v1)

Live world map, Discord, giving items, scheduled restarts, and full world backups. This tool is for the config files that are painful to edit by hand.
