# Production deployment

## Services

Deploy the Vite frontend on Vercel, the Convex functions to a production
deployment, and the Python API and training worker to a persistent compute host.
The current 50 MB upload endpoint and continuously running ML worker are not
intended to run inside a Vercel Function. Keep uploads directed to the Python API.

## Frontend

Import the GitHub repository into Vercel. Use the directory containing
`package.json` as its root, the Vite preset, `npm run build` as its build command,
and `dist` as its output directory.

Configure these build-time variables for the Production environment:

| Variable | Value |
| --- | --- |
| `VITE_CONVEX_URL` | Production Convex cloud HTTPS URL |
| `VITE_CONVEX_SITE_URL` | Production Convex site HTTPS URL |
| `VITE_DAISY_API_URL` | Public Python API HTTPS base URL |

Production builds reject missing URLs, HTTP, localhost, URL credentials,
query strings and fragments. `npm run dev` still supports local development.
For local production-build testing, supply the three deployment URLs through
environment variables or an untracked `.env.production.local` file.
Redeploy after changing build-time variables. Never put a secret in a `VITE_` variable.

## Convex and Google sign-in

Deploy the existing schema/functions with `npx convex deploy`. Set the following
on the production deployment, independently from development:

- `SITE_URL`: the public frontend HTTPS origin.
- `BETTER_AUTH_SECRET`: a newly generated private authentication secret.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: the production OAuth credentials.
- `DAISY_BACKEND_SECRET`: a generated private secret shared only with the Python services.

In Google Cloud, authorize the public frontend origin and add this redirect,
using the production site's actual URL:

```text
https://<production-convex-site>/api/auth/callback/google
```

Do not reuse the development callback or point production at development data.

## Python API and worker

Configure both services with the same production values:

```text
DAISY_ENV=production
DAISY_AUTH_PROVIDER=convex
DAISY_PERSISTENCE=convex
CONVEX_SITE_URL=<production Convex site HTTPS URL>
DAISY_BACKEND_SECRET=<same private value configured in Convex>
CORS_ORIGINS=<public frontend HTTPS origin>
GROQ_API_KEY=<private provider key>
```

From `backend/`, install `requirements.lock`. Start the API using
`python -m uvicorn main:app --host 0.0.0.0 --port 8000` (adapt the port to the
compute host), and a separate process using `python worker.py`. Configure the
host to restart both processes after failures. Ensure `/health/ready` reports
healthy storage and an active worker before accepting users.

## Release verification

Run `npm run typecheck`, `npx tsc -p convex/tsconfig.json --noEmit`,
`npm run test:convex`, `npm run build`, and the backend pytest suite.
GitHub Actions checks frontend/Convex compilation, Convex tests and the Python suite.
Its placeholder URLs are for compilation only and are not live deployment endpoints.

On the deployed site, test registration/Google sign-in, CSV upload, training,
refresh/resume, cancellation, and the trained model download. Check that another
account cannot access those datasets or models. Test worker restart and file
recovery after local cache loss. Publishing this configuration does not migrate
historical Supabase data or passwords.

References: [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite),
[Convex on Vercel](https://docs.convex.dev/production/hosting/vercel),
[Vercel Function limits](https://vercel.com/docs/functions/limitations).
