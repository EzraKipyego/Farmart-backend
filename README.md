## Farmart backend

### Run with Docker

Set the database and M-Pesa values in `.env`, then start the API and PostgreSQL:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000/api`. Migrations run automatically when the web container starts.

To stop the services:

```bash
docker compose down
```

To remove the local PostgreSQL volume as well:

```bash
docker compose down -v
```

For M-Pesa callbacks, set `MPESA_CALLBACK_URL` to a publicly reachable URL such as an ngrok or Cloudflare Tunnel URL ending in `/api/payments/callback`.

### Deploy on Render

The included `render.yaml` provisions a Render PostgreSQL database and injects its internal `DATABASE_URL` into the web service. Do not set `DATABASE_URL` to `db`; `db` is only the Docker Compose hostname.

For a Docker-based Render Web Service, select the repository and Docker runtime. Render will use `Dockerfile`; do not run `python manage.py migrate` in the build command. The container entrypoint runs migrations when the service starts.

For a native Render runtime, use `pip install -r requirements.txt` as the build command and `python manage.py migrate && gunicorn farmart.wsgi:application --bind 0.0.0.0:$PORT` as the start command. Add the Render PostgreSQL Internal Database URL as `DATABASE_URL`, and add `DJANGO_SECRET_KEY` as a secret environment variable.
