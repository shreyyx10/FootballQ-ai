# Deploying the API to Azure Functions

The API (`api/`) is a Python v2-programming-model Azure Functions app
(`function_app.py`) intended for the **Consumption (free grant)** plan.

## Prerequisites

- An Azure account (free tier is sufficient).
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
  installed and logged in (`az login`).
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
  installed (`func --version` should report 4.x).
- Python 3.10+ locally (matches the version used in `api/__pycache__`).

## 1. Create the Azure resources

```bash
# Variables — adjust names as needed (must be globally unique)
RESOURCE_GROUP=footballq-ai-rg
LOCATION=eastus
STORAGE_ACCOUNT=footballqaistorage
FUNCTION_APP=footballq-ai-api

az group create --name $RESOURCE_GROUP --location $LOCATION

az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --name $FUNCTION_APP \
  --storage-account $STORAGE_ACCOUNT \
  --os-type Linux
```

The Consumption plan (`--consumption-plan-location`) is the free-grant plan —
do not select a Premium or Dedicated (App Service) plan.

## 2. Configure Application Settings (environment variables)

Set these via the Azure Portal (Function App → **Configuration → Application
settings**) or CLI. None of these are required to get a working demo — the
defaults are safe — but `ALLOWED_ORIGINS` should be set to your frontend's
URL before going live:

```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --settings \
    ENVIRONMENT=production \
    ALLOWED_ORIGINS="https://footballq-ai.vercel.app" \
    USE_MOCK_LLM=true \
    ENABLE_REAL_LLM=false \
    ENABLE_QDRANT=false \
    RATE_LIMIT_ENABLED=true \
    LOG_LEVEL=INFO \
    MCP_ENABLED=false
```

`AZURE_SQL_CONNECTION_STRING`, `OPENAI_API_KEY`, and `QDRANT_API_KEY` are
**only** set here (Application Settings) — never committed to source. Leave
them unset to use the local seed dataset and mock LLM mode.

## 3. Deploy the code

From the `api/` directory:

```bash
cd api
func azure functionapp publish $FUNCTION_APP
```

This packages `function_app.py`, `shared/`, `seed/`, `host.json`, and
`requirements.txt`, and installs dependencies remotely (Linux Consumption
plan uses remote build by default).

## 4. Verify

```bash
curl https://$FUNCTION_APP.azurewebsites.net/api/health
```

Expected response:

```json
{"status": "ok", "service": "FootballQ AI API", "mode": "free-demo"}
```

Then test a data endpoint:

```bash
curl https://$FUNCTION_APP.azurewebsites.net/api/players?position=Winger
```

See [API_REFERENCE.md](API_REFERENCE.md) for the full request/response
catalogue and more `curl` examples.

## 5. Connect the frontend

Set `NEXT_PUBLIC_API_BASE_URL=https://$FUNCTION_APP.azurewebsites.net/api`
in your Vercel project (see [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)),
and ensure `ALLOWED_ORIGINS` above includes your Vercel URL.

## Troubleshooting

- **`func azure functionapp publish` fails on dependency build** — ensure
  `--runtime-version 3.10` matches a version supported by `azure-functions`,
  `pydantic`, and `pyodbc` in `requirements.txt`.
- **500 errors with no detail** — by design, the API never returns stack
  traces. Check **Application Insights / Log stream** in the Azure Portal for
  the server-side `log_safe_exception` entry (exception type + truncated
  message only).
- **CORS errors** — confirm `ALLOWED_ORIGINS` matches the frontend origin
  exactly, including scheme and no trailing slash.
- **pyodbc / ODBC driver errors** — only relevant once
  `AZURE_SQL_CONNECTION_STRING` is set. See
  [AZURE_SQL_SETUP.md](AZURE_SQL_SETUP.md). Without it, the API uses the
  local seed data store and these errors do not occur.
