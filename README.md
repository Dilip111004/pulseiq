# PulseIQ Phase 4 - Authenticated Analytics API

Phase 4 extends PulseIQ with a FastAPI service that provides controlled access to selected workforce and business metrics.

## Features

- FastAPI-based analytics API
- Bearer-token authentication
- Role-based endpoint access
- Governed metric access
- Minimum group-size privacy suppression
- Metric definitions and metadata
- Interactive API documentation
- Localhost-only API configuration

## Technology

- Python
- FastAPI
- Uvicorn
- Pandas
- DuckDB
- SQL

## Project Files

- `src/api.py` - API implementation
- `src/auth.py` - Authentication and authorization
- `tests/test_pq19_api.py` - API tests

## Run the API

Run from the repository root:

`.\.venv_day16_test\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000`

## API Documentation

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

## API Endpoints

| Method | Endpoint | Access |
|---|---|---|
| GET | `/health` | Public |
| POST | `/auth/login` | Login and obtain bearer token |
| GET | `/metrics` | ADMIN, EXECUTIVE |
| GET | `/metrics/{metric_id}` | ADMIN, EXECUTIVE; M22 is ADMIN only |

## Supported Metrics

- M01
- M07
- M09
- M13
- M22

EXECUTIVE users cannot access M22.

### Metric Parameters

- M01, M07, M09 and M13 require `month=YYYY-MM`.
- M22 requires `sprint_id`.

## Authentication

- Token expiry: 1,800 seconds (30 minutes).
- `PULSEIQ_AUTH_USERS`: user configuration containing usernames, password hashes and permitted roles.
- `PULSEIQ_TOKEN_SECRET`: token signing secret with a minimum length of 32 characters.

Supported roles: ADMIN, EXECUTIVE, HR and MANAGER.

Keep passwords, password hashes, signing secrets and access tokens private. Never commit real credentials to GitHub.

## Privacy and Data Freshness

- Results below the configured minimum group size are suppressed.
- Invalid minimum-group-size configuration fails closed.
- Unsupported metrics return HTTP 404.
- `latest_source_date` represents the latest date in source data, not the ETL execution timestamp.
- The API listens on `127.0.0.1`.

Do not expose the API publicly until authentication, privacy, data provenance and deployment security have been reviewed.

## Testing

`.\.venv_day16_test\Scripts\python.exe -m pytest tests/test_pq19_api.py -q`

## Repository

https://github.com/Dilip111004/pulseiq
