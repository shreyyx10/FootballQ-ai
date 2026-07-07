# Free Deployment Overview

FootballQ AI deploys across three free-tier services. This page is the
high-level map; each linked guide has copy-pasteable steps.

| Layer | Service | Guide |
|---|---|---|
| Frontend | Vercel Hobby | [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) |
| API | Azure Functions Consumption plan | [AZURE_FUNCTIONS_DEPLOYMENT.md](AZURE_FUNCTIONS_DEPLOYMENT.md) |
| Database (optional) | Azure SQL Database free offer | [AZURE_SQL_SETUP.md](AZURE_SQL_SETUP.md) |

## Recommended order

1. **Deploy the API first** (Azure Functions). The frontend needs its base
   URL. The API works immediately with the in-memory `LocalSeedDataStore`,
   even before Azure SQL exists.
2. **Deploy the frontend** (Vercel), setting `NEXT_PUBLIC_API_BASE_URL` to
   the Azure Functions base URL from step 1, and `ALLOWED_ORIGINS` on the API
   to the resulting `*.vercel.app` URL.
3. **(Optional) Provision Azure SQL** and run the seed script, then set
   `AZURE_SQL_CONNECTION_STRING` on the Function App. The API will start
   using Azure SQL automatically and falls back to local data if anything
   goes wrong.

## Minimum viable deployment

The absolute minimum to get a working public demo:

- Deploy `api/` to Azure Functions with only `ALLOWED_ORIGINS` set to your
  Vercel URL (everything else uses safe defaults: mock LLM, local seed data,
  no Qdrant).
- Deploy `frontend/` to Vercel with `NEXT_PUBLIC_API_BASE_URL` set to the
  Function App's base URL (`https://<app-name>.azurewebsites.net/api`).

That's it — `/scout`, `/compare`, `/similarity`, and `/tactical-fit` all work
against the bundled sample dataset with mock-LLM narratives.

## Adding real data / a real LLM later

Both are optional, independent upgrades:

- **Azure SQL**: follow [AZURE_SQL_SETUP.md](AZURE_SQL_SETUP.md) and
  [DATA_PIPELINE.md](DATA_PIPELINE.md). Set
  `AZURE_SQL_CONNECTION_STRING` on the Function App once the schema is
  created and seeded.
- **Real LLM narratives**: set `ENABLE_REAL_LLM=true` and `OPENAI_API_KEY` on
  the Function App. See [COST_SAFETY.md](COST_SAFETY.md) before doing this —
  it is the only component that can incur real cost.

## Local development

```bash
# Backend
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
func start   # requires Azure Functions Core Tools

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:7071/api` in
`frontend/.env.local` for local development only — this value must never be
used in the deployed production build.
