# Deploying to Render

This puts the application on the internet using [Render](https://render.com) and the `render.yaml` Blueprint in this
repository. For running it on your own machine see [SETUP.md](SETUP.md); for running it on a server you control with
Docker Compose see [SETUP.md §7](SETUP.md#7-production-deployment).

## What gets created

| Render service | Type | Built from | Purpose |
|---|---|---|---|
| `scheduling-db` | PostgreSQL (free) | — | the database |
| `scheduling-backend` | Web service (Docker, free) | `backend/Dockerfile` | the API; on every start it waits for the DB, runs migrations and loads the sample data **once** |
| `scheduling-frontend` | Static site (free) | `frontend/` (`npm ci && npm run build`) | the React app |

The browser loads the app from the frontend's URL and calls the API on the backend's URL (two different origins — unlike
the Docker Compose setup, where nginx puts both behind one). That is why two values must be filled in (step 3).

## Read this first: what "free" means on Render

Taken from [Render's free-tier documentation](https://render.com/docs/free) — check it again before you rely on it,
because Render changes these terms.

| | Free-tier behaviour |
|---|---|
| **Backend (web service)** | Spins down after **15 minutes without traffic**; the next request waits **about a minute** for it to wake up. Each workspace gets 750 free instance hours per month — enough for one always-on service. |
| **PostgreSQL** | **Expires 30 days after creation.** You then have 14 days to upgrade to a paid plan; after that Render **deletes the database and its data**. 1 GB, and only one free database per workspace. |
| **Frontend (static site)** | Free; always on and fast (not subject to the sleep behaviour). |

The database expiry is the one that matters. Your options:

1. **Demo use (fine as-is).** The sample data is rebuilt automatically, so when the database expires you can create a new
   free one, point the backend at it and the app comes back with fresh sample data. Anything created by hand is lost.
2. **Upgrade the database** to a paid Render plan before it expires — nothing else changes.
3. **Use a database hosted elsewhere** (any PostgreSQL provider with a permanent free tier — check its current terms).
   Delete the `databases:` block and the `DATABASE_URL` entry's `fromDatabase` from `render.yaml`, create the variable as
   `sync: false` instead, and paste the provider's connection string when prompted. Both `postgres://…` and
   `postgresql://…` forms work; add `?sslmode=require` if the provider needs TLS.

## Steps

### 1. Push the repository to GitHub

`render.yaml` must be in the repository root. Never commit a `.env` file (it is already in `.gitignore`).

### 2. Choose your names (optional but recommended)

The service names in `render.yaml` become the public URLs — `https://<name>.onrender.com` — **if nobody else on Render
already uses the name**; otherwise Render adds a random suffix. Names like `scheduling-backend` are likely taken, so
edit the three `name:` values (and the matching `fromDatabase.name`) to something unique, for example
`yourname-scheduling-backend`. Commit and push the change.

### 3. Create the Blueprint

1. In the Render dashboard choose **New + → Blueprint**, connect your GitHub account and pick the repository.
2. Render reads `render.yaml` and asks for the two values marked `sync: false`:

   | Variable | On service | Value |
   |---|---|---|
   | `CORS_ORIGINS` | backend | the frontend's public URL, **no trailing slash**: `https://<frontend-name>.onrender.com` |
   | `VITE_API_URL` | frontend | the backend's public URL **plus `/api`**: `https://<backend-name>.onrender.com/api` |

3. Click **Apply**. Render builds everything; the first deploy takes several minutes (Docker build, database creation,
   migrations, and loading the sample data — which is slower on the free tier's small CPU than the ~20 seconds it takes
   locally). Wait until the backend shows **Live**.

If Render had to add a random suffix to a name, the URLs you typed are wrong. Open each service, read its real URL at the
top of the page, then fix the two variables under **Environment**: changing `CORS_ORIGINS` restarts the backend by itself;
after changing `VITE_API_URL` use **Manual Deploy → Clear build cache & deploy** on the frontend, because that value is
baked into the build.

### 4. Get the admin password and sign in

The Blueprint generates a random admin password instead of the public `Admin@123`. Open the **backend** service →
**Environment** → reveal `SEED_ADMIN_PASSWORD`, then open the frontend URL and sign in as `admin@college.edu` with it.
(The first request after a quiet period may take about a minute while the free backend wakes up.)

### 5. Verify

- `https://<backend-name>.onrender.com/api/health` returns `{"status":"ok"}`.
- The frontend URL shows the sign-in page; after signing in as admin the dashboard shows *Schedule is clash-free*.
- Browser developer tools show no CORS errors. If they do, see the table below.

## Keeping it safe

- `SECRET_KEY` (signs login tokens) and `SEED_ADMIN_PASSWORD` are generated by Render and live only in its dashboard —
  they are not in the repository or in the Docker image.
- **The sample faculty and student accounts keep their documented passwords** (`Faculty@123`, `Student@123`). That is
  fine for a demo that you want people to be able to try, but it means: do not put real personal data in this
  deployment, and treat it as a demonstration, not a production system.
- The application has no login rate limiting and no password reset yet (see *Known Limitations* in the README) — another
  reason to keep this a demo until those are added.
- `RESET_ON_START` must stay `false` on Render: `true` would wipe the database every time the backend restarts or wakes up.
- Only `CORS_ORIGINS` (your frontend URL) is allowed to call the API from a browser; other sites are refused.

## Updating the deployment

Push to the branch Render watches and it rebuilds and redeploys automatically. Database changes are applied by
`alembic upgrade head` on the backend's next start; existing data is kept.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Sign-in page loads but login shows *Cannot reach the server* or the console shows a CORS error | `CORS_ORIGINS` on the backend must equal the frontend's exact origin (`https://…onrender.com`, no trailing slash, no path). Or the backend is still waking up — wait a minute and retry. |
| Requests go to the frontend's own URL and return 404 / HTML | `VITE_API_URL` was missing or wrong when the frontend was built. Fix it and redeploy the frontend with **Clear build cache & deploy**. |
| Refreshing on a page such as `/admin` shows *Not Found* | The `routes` rewrite in `render.yaml` was not applied — check the static site's **Redirects/Rewrites** tab shows `/*` → `/index.html`. |
| Backend deploy fails or never becomes Live | Open its **Logs**. Common causes: the database and backend are in different regions (keep both on the same `region`), or `PORT` is not `8000`. |
| Everything worked, then the app errors after about a month | The free database expired — see *Read this first*. |
| Login says *Incorrect email or password* for the admin | Use the generated `SEED_ADMIN_PASSWORD` from the backend's Environment tab, not `Admin@123`. It is only applied when the sample data is first created, so editing the variable later does not change an existing account. |
