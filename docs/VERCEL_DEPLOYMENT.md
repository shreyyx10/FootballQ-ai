# Deploying the Frontend to Vercel

The frontend (`frontend/`) is a standard Next.js 14 App Router project and
deploys to Vercel's free Hobby plan with no special configuration beyond
environment variables.

## 1. Push the repository to GitHub

Vercel deploys from a Git repository. Push `footballq-ai/` to a GitHub repo
(public or private).

## 2. Import the project in Vercel

1. Go to the Vercel dashboard → **Add New… → Project**.
2. Import the `footballq-ai` repository.
3. Set **Root Directory** to `frontend`.
4. Framework preset should auto-detect as **Next.js**. Build command
   (`npm run build`) and output directory (`.next`) are already set in
   `vercel.json` and Next.js defaults — leave them as-is.

## 3. Configure environment variables

In the Vercel project's **Settings → Environment Variables**, add (for
Production, and Preview if desired):

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_APP_NAME` | `FootballQ AI` |
| `NEXT_PUBLIC_API_BASE_URL` | `https://<your-function-app>.azurewebsites.net/api` |
| `NEXT_PUBLIC_ENVIRONMENT` | `production` |

`NEXT_PUBLIC_API_BASE_URL` must point at your deployed Azure Functions API
(see [AZURE_FUNCTIONS_DEPLOYMENT.md](AZURE_FUNCTIONS_DEPLOYMENT.md)). Never
set this to a `localhost` URL in the production environment.

## 4. Deploy

Click **Deploy**. Vercel runs `npm install` and `npm run build` from
`frontend/`. The site will be available at a generated
`<project>.vercel.app` URL (or your custom domain). The project's intended
public URL is `footballq-ai.vercel.app`.

## 5. Update the API's CORS allowlist

Once you know your Vercel URL, set `ALLOWED_ORIGINS` on the Azure Function
App (see [AZURE_FUNCTIONS_DEPLOYMENT.md](AZURE_FUNCTIONS_DEPLOYMENT.md)) to
include it, e.g.:

```
ALLOWED_ORIGINS=https://footballq-ai.vercel.app
```

Without this, the browser will block API responses due to CORS even though
the API itself is reachable.

## 6. Verify

Open the deployed site and check:

- `/` loads with no console errors.
- `/scout` returns a response for a sample query (e.g. "Find me a young
  winger under 23").
- `/compare`, `/similarity`, and `/tactical-fit` return data for the sample
  players/teams.
- `/architecture` and `/about` render static content correctly.
- A non-existent route (e.g. `/does-not-exist`) renders the custom 404 page.

## Security headers

`vercel.json` sets `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, and `Permissions-Policy` on every response, and
`next.config.js` mirrors these for local builds. No additional configuration
is required.

## Troubleshooting

- **CORS errors in the browser console** → confirm `ALLOWED_ORIGINS` on the
  Function App exactly matches the Vercel URL (including `https://`, no
  trailing slash).
- **API calls return network errors** → confirm
  `NEXT_PUBLIC_API_BASE_URL` is correct and the Function App is running (hit
  `/api/health` directly in a browser).
- **Build fails on `next lint` or type errors** → run `npm run lint` and
  `npx tsc --noEmit` locally from `frontend/` to reproduce.
