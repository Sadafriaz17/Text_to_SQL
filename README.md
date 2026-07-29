# Text-to-SQL (Chinook DB + MCP Toolbox + LLM)

## Authentication

This project has two independent authentication layers, protecting two different things. A request has to pass both to reach real data.

### 1. API layer — FastAPI `/query` endpoint

The `/query` endpoint requires a valid API key sent in the `X-API-Key` header. Requests missing the header, or sending the wrong value, get a `401 Unauthorized` before any LLM/SQL logic runs.

- The expected key lives in `.env` as `SERVER_API_KEY`.
- `frontend/index.html` sends that same value on every request via its `API_KEY` constant near the top of the `<script>` block — it must match `SERVER_API_KEY` in `.env` exactly, or every query will fail with an "Unauthorized" error card in the UI.
- `/health` is intentionally left open (no key required) — it's just a liveness ping used to show the "Database connected" status badge, not a data-returning endpoint.
- If `SERVER_API_KEY` isn't set in `.env` at all, the server fails closed (`500`) rather than silently accepting unauthenticated requests.

### 2. Toolbox layer — MCP Toolbox for Databases

Independently of the API layer above, the Toolbox server itself (`toolbox_setup/tools.yaml`) requires a valid Google-signed ID token before it will run `list_tables` or `execute_sql` — this is enforced by Toolbox itself, not by our backend code, so it can't be bypassed by talking to Toolbox directly.

- Configured via an `authServices` entry (`toolbox-auth`, type `google`) in `tools.yaml`, checked against `GOOGLE_CLIENT_ID` in `.env`.
- The backend (`toolbox_setup/run_query.py`) mints a fresh ID token on every call from a Google service account key (`GOOGLE_SERVICE_ACCOUNT_KEY_FILE` in `.env`) — this is service-to-service authentication, not end-user login.

### Required `.env` values

```
SERVER_API_KEY=<random hex string, e.g. via: python -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=<Google OAuth Client ID>
GOOGLE_SERVICE_ACCOUNT_KEY_FILE=<filename of your service account JSON key, placed in toolbox_setup/>
```
