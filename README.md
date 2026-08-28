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
