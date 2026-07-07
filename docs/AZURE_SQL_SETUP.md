# Azure SQL Database Setup (Optional)

The API works fully without a database (it falls back to an in-memory
`LocalSeedDataStore` seeded from the same sample files). This guide is for
provisioning the optional Azure SQL Database free offer.

## 1. Create the Azure SQL Database

Azure provides **one free Azure SQL Database per subscription** (a small
amount of vCore-hours and storage). Create it via the Azure Portal:

1. **Create a resource → SQL Database**.
2. Choose **Create new** server, set an admin username/password (store these
   securely — do not commit them).
3. Under **Compute + storage**, select the **free offer** tier if available
   in your subscription/region.
4. Under **Networking**, enable **Allow Azure services and resources to
   access this server** so the Function App can connect, and optionally add
   your client IP for running the seed script locally.

## 2. Run the schema script

Using `sqlcmd`, Azure Data Studio, or the Azure Portal's **Query editor**,
run `api/seed/schema.sql` against the new database. This script is
idempotent — it drops and recreates `Players`, `ScoutingNotes`,
`TeamProfiles`, `TeamStats`, `MatchLogs`, `PipelineRuns`, `ScoutQueries`,
and `ApiLogs`, plus indexes. `TeamStats`, `MatchLogs`, and `PipelineRuns`
are only populated if you enable the optional FBref pipeline - see
[FBREF_PIPELINE.md](FBREF_PIPELINE.md).

The script also documents (commented out) creating a least-privilege
application login with only `db_datareader` and `db_datawriter` — never
`db_owner`/`db_ddladmin`. Uncomment and adapt those lines if you want a
separate application login.

## 3. Build the connection string

Format (ODBC Driver 18):

```
Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<db-name>;Uid=<user>;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

**Never commit this value.** It contains a password.

## 4. Seed the sample data

Locally (requires "ODBC Driver 18 for SQL Server" installed):

```bash
cd api/seed
export AZURE_SQL_CONNECTION_STRING="<connection string from step 3>"
pip install pyodbc
python seed_azure_sql.py
```

`seed_azure_sql.py` reads `sample_players.csv`, `sample_scouting_notes.json`,
and `sample_team_profiles.json`, and inserts them using parameterised queries
only. It clears the relevant tables first, so it's safe to re-run.

## 5. Configure the Function App

In Azure Functions Application Settings (see
[AZURE_FUNCTIONS_DEPLOYMENT.md](AZURE_FUNCTIONS_DEPLOYMENT.md)), set:

```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP \
  --resource-group $RESOURCE_GROUP \
  --settings AZURE_SQL_CONNECTION_STRING="<connection string from step 3>"
```

Once set, `AzureSqlDataStore` is used automatically
(`Settings.database_configured` returns `True`). If any query raises for any
reason, the API falls back to the local seed data — so a temporary database
outage degrades gracefully rather than breaking the site.

## Unsetting / rolling back

To revert to the local seed dataset, remove the
`AZURE_SQL_CONNECTION_STRING` application setting (or set it to an empty
string) and restart the Function App. No code changes are needed.

## Cost notes

The free Azure SQL offer covers the storage and compute this sample dataset
needs many times over (5 small tables, <100 rows of seed data plus logging
tables). See [COST_SAFETY.md](COST_SAFETY.md) for monitoring recommendations.
