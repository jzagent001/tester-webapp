# Deploying Self-Test

Two phases: first a trial on your Unraid NAS's local network, then opening it to the internet through a Cloudflare Tunnel with Cloudflare Access handling sign-in. The same container does both; only its environment settings change.

## How sign-in works

The app has no passwords or accounts of its own. It identifies people by email:

| `AUTH_MODE` | Who is signed in | Use for |
|---|---|---|
| `single` | Everyone is `SINGLE_USER_EMAIL` | Local development, the LAN trial |
| `cloudflare` | Whoever Cloudflare Access signed in (email one-time code) | Internet access |

In `cloudflare` mode the app checks the signed token Cloudflare adds to every request (`Cf-Access-Jwt-Assertion`) against your team's public keys and your Access application's audience tag. A request that didn't come through Cloudflare Access gets `401`, even from your own LAN.

Each user only ever sees their own banks and test results. **Set `SINGLE_USER_EMAIL` to the email you'll use with Cloudflare later**, so the banks you create during the trial are already yours when you switch.

## Settings

| Variable | Needed for | Example |
|---|---|---|
| `AUTH_MODE` | always | `single` or `cloudflare` |
| `SINGLE_USER_EMAIL` | `single` | `you@example.com` |
| `CF_ACCESS_TEAM_DOMAIN` | `cloudflare` | `yourteam.cloudflareaccess.com` |
| `CF_ACCESS_AUD` | `cloudflare` | the Access application's *Application Audience (AUD) Tag* |
| `OWNER_EMAIL` | once, only when upgrading a database created before users existed | `you@example.com` |
| `DATABASE_URL` | optional | defaults to `sqlite:////data/app.db` in the container |

The container refuses to start if the settings for its mode are missing, and says which.

## Phase 1: LAN trial on Unraid

### 1. Make a folder for the data

In the Unraid terminal:

```bash
mkdir -p /mnt/cache/appdata/tester-webapp
chown 99:100 /mnt/cache/appdata/tester-webapp
```

Use the **cache pool path** (`/mnt/cache/...`), or an appdata share set to *exclusive access*, rather than `/mnt/user/...`. SQLite on Unraid's `/mnt/user` FUSE layer is a known cause of locking problems and corruption. If your appdata isn't on a pool called `cache`, use your pool's name.

### 2. Get the image onto the NAS

**Option A, build on the NAS (simplest).** Copy this project folder to the NAS (e.g. to `/mnt/cache/appdata/tester-webapp-src` over the network share), then install the *Docker Compose Manager* plugin from Community Applications, add a stack pointing at that folder, edit `docker-compose.yml` (see step 3) and press **Compose Up**. It builds the image and starts the container. From the terminal instead: `cd /mnt/cache/appdata/tester-webapp-src && docker compose up -d --build`.

**Option B, build on your PC and copy the image.**

```bash
podman build --format docker -t tester-webapp:latest .     # or: docker build -t tester-webapp:latest .
podman save -o tester-webapp.tar tester-webapp:latest
# copy tester-webapp.tar to the NAS, then on the NAS:
docker load -i tester-webapp.tar
```

Then use the compose file with its `build: .` line removed. Podman names the image `localhost/tester-webapp:latest`; put that name in `image:` if Docker doesn't find `tester-webapp:latest`. Build on a PC with the same CPU architecture as the NAS (almost always x86-64).

### 3. Configure

In `docker-compose.yml`:

- `SINGLE_USER_EMAIL`: your email, lower-case.
- `ports`: `8765:8000` serves the app on `http://<nas-ip>:8765`. Change `8765` if it's taken.
- `volumes`: the folder from step 1.

### 4. Start and check

```bash
docker compose up -d --build
docker logs tester-webapp                    # should end with "Application startup complete"
docker exec tester-webapp python -m app.seed # optional: load the optical networking example bank for you
```

Open `http://<nas-ip>:8765`. Your email shows in the top bar. The Docker tab shows the container as *healthy* after about half a minute.

## Phase 2: open it up through Cloudflare

You need a domain on Cloudflare and a Zero Trust account (the free plan covers small groups; check the current user limit).

### 1. Create the tunnel

In the Cloudflare dashboard: **Zero Trust → Networks → Tunnels → Create a tunnel** (Cloudflared). Run the connector on Unraid, e.g. the *cloudflared* container from Community Applications, with the tunnel token Cloudflare shows you.

Add a **public hostname**, e.g. `selftest.yourdomain.com`, with service `http://<nas-ip>:8765`. If cloudflared and tester-webapp share a custom Docker network, `http://tester-webapp:8000` works too.

### 2. Put Cloudflare Access in front of it

**Zero Trust → Access → Applications → Add an application → Self-hosted**:

- Application domain: the same hostname, e.g. `selftest.yourdomain.com`.
- Session duration: something long, e.g. 1 month, so people aren't asked for a code too often.
- Identity provider: **One-time PIN** (email code). It's built in.
- Policy: **Allow**, include **Emails**, and list each person's email address. To let someone in later, add their email here. To remove them, delete it.

After saving, open the application's settings and copy the **Application Audience (AUD) Tag**. Your **team domain** is `<team name>.cloudflareaccess.com`. The team name is the one you chose when you set up Zero Trust; it's shown in the Zero Trust settings.

### 3. Switch the app to Cloudflare mode

In `docker-compose.yml`, comment out the two `single` lines and set:

```yaml
AUTH_MODE: cloudflare
CF_ACCESS_TEAM_DOMAIN: yourteam.cloudflareaccess.com
CF_ACCESS_AUD: <the AUD tag>
```

Then `docker compose up -d`. Visit `https://selftest.yourdomain.com`: Cloudflare asks for your email, sends a code, and you land in the app with the banks from your trial (as long as the email matches `SINGLE_USER_EMAIL` from phase 1).

`http://<nas-ip>:8765` now answers `401` because requests there don't carry a Cloudflare token. That's expected. You can remove the `ports:` mapping if cloudflared reaches the container over a Docker network.

### 4. Invite people

Add their emails to the Access policy and send them the link. They sign in with an email code, see an empty home page, and can download the question-writing kit from it.

## Updating

1. Back up (below).
2. Copy the new code to the NAS (option A) or load the new image (option B).
3. `docker compose up -d --build`.

Database migrations run automatically when the container starts. A failed migration leaves the database unchanged and the container stops with the reason in `docker logs`.

## Backups

The database is `app.db` in the data folder. While the container runs, SQLite also keeps `app.db-wal` and `app.db-shm` next to it: **always copy all three together, or stop the container first**. The *Appdata Backup* plugin stops containers while it copies, so it's safe. For a backup while running:

```bash
docker exec tester-webapp python -c "import sqlite3; sqlite3.connect('/data/app.db').backup(sqlite3.connect('/data/backup.db'))"
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| Container exits with `Can't start: AUTH_MODE=… needs …` | A setting for the chosen mode is missing. |
| Container exits with `…they need an owner. Set OWNER_EMAIL…` | The data folder has a database from before users existed. Set `OWNER_EMAIL` once, start, then remove it. |
| `401` on every page in Cloudflare mode | You're not going through the Cloudflare hostname, or `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` don't match the Access application. |
| `unable to open database file` | The data folder isn't writable by 99:100. Run the `chown` from phase 1 step 1. |
| Buttons do nothing after a while | The Cloudflare session expired. The page reloads into the sign-in screen by itself; if it doesn't, refresh. |
| Pages look unstyled | The browser can't reach `cdn.jsdelivr.net`, which serves the CSS and HTMX. |
