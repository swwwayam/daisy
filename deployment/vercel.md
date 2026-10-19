# Production deployment

## Services

Use Vercel Hobby for this personal/non-commercial frontend and the Convex Free
plan for authentication and storage. The Python API and training worker need
separate compute. For no additional hosting subscription, they can run on the
owner's existing laptop, reached through a free HTTPS tunnel. This option needs
the laptop to stay on, online, and awake while people use DAISY.
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
- `DAISY_ACCESS_ADMIN_EMAILS`: `swayamballal2005@gmail.com` for this release.
  This grants owner rights only when the authenticated provider marks the email
  verified. Use Google sign-in for the owner account. An unverified password
  signup with that email cannot become an owner.
- Optional `DAISY_ACCESS_ADMIN_IDS`: comma-separated Better Auth user IDs for
  explicit trusted owner accounts when verified-email bootstrap is unavailable.
  Copy the actual authenticated user's ID from the auth dashboard; never accept
  an ID supplied by an access requester.

## Invite-only workspace

The landing page and sign-in page are public. New accounts can sign in and
submit one access request, but cannot create a workspace or use the Python API
until approved. Approval is stored against the authenticated user ID, not an
email typed into a form. Existing non-owner accounts also need approval.

The verified owner sees **Manage access requests** above the workspace. Approve,
deny, or revoke accounts there. Requests are stored in Convex; no request or
approval emails are sent. Unverified requester addresses are labeled explicitly.
If an account is approved before its email is verified, confirm its identity
through a trusted channel first. Denied/revoked accounts cannot reset their
status by submitting another request; an owner can approve them later.

Each authenticated Convex-backed Python API request checks the live approval
endpoint. An unavailable gate fails closed, and revocation blocks subsequent
requests even with a still-valid session token. Already-running requests and
previously queued training jobs are not cancelled by revocation. Local and
production API services must use the updated gate together with the matching
Convex deployment. Deploying only the frontend is insufficient.

## Zero-subscription backend option

Keep the existing API and separate worker on the owner's laptop. Cloudflare
Quick Tunnels provide a temporary public HTTPS endpoint without a Cloudflare
account or domain. These are for development/demo use and have no uptime guarantee.
The tunnel exposes only the API port, with DAISY's authentication and approval
gate enforcing access. It must not expose the development frontend, files or
other local services. Configure and verify the gate before exposing the API.

The proxy command is `cloudflared tunnel --url http://127.0.0.1:8000`. It returns
a `trycloudflare.com` HTTPS endpoint to use for `VITE_DAISY_API_URL`. The hostname
changes whenever a new tunnel starts; update the Vercel variable and redeploy
the frontend after a change. Do not enable the tunnel until
the owner confirms use of their laptop for public API traffic. Closing the
laptop, stopping either process, or losing internet interrupts application use.
This is a personal/demo deployment, not an always-on availability guarantee.
Tailscale Personal with Funnel is an alternative for a stable device hostname
without buying a domain, subject to its current account and plan requirements.

Keep Vercel on Hobby and Convex on Free, not paid trials or pay-as-you-go plans.
Use only the AI provider's free allowance, with no paid account or automatic
top-ups. Limits can pause or reject requests; when limits are reached, wait for
reset rather than enabling billing. Queue polling and worker heartbeats also
consume Convex usage, even when nobody submits a training job.

Release order: configure production Convex/owner/OAuth settings and deploy the
Convex functions, start the updated API and worker, verify approval checks,
configure the HTTPS tunnel, then build/deploy Vercel with the real API URL.
Set `SITE_URL` and `CORS_ORIGINS` to the stable Vercel production origin. Use a
separate Convex development deployment for local work. Public production
frontends cannot point at localhost. Laptop electricity and internet are still
provided by the owner; no hosted compute subscription is provisioned here.

A local build with placeholder HTTPS URLs verifies compilation only; it does
not establish a working deployment. No paid hosting configuration is included.

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
