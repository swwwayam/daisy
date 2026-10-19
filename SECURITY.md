# Signup and AI abuse protection

## Workspace approval

DAISY's workspace is invite only. Authentication allows an account to request
access; only an approved user ID can create a workspace or use the Convex-backed
Python API. The frontend gate is backed by live approval checks on the API.
Owner bootstrap requires a configured verified email or explicitly configured
trusted user ID. No owner email or role supplied by a browser is trusted.
See [deployment setup](deployment/vercel.md) for owner configuration, approval,
revocation scope and release order. Existing non-owner accounts require approval
after this change. This does not automatically cancel jobs already running.

New user creation (email/password and first Google login) reserves a registration
slot in Convex before creating the user. Existing users signing in do not consume
a slot. The default is **3 registration reservations per network per UTC day**.
An unsuccessful creation after reservation can still consume a slot. This is
deliberately conservative. Limits reset at 00:00 UTC, not in a rolling 24-hour
window. Removing an account does not refund its registration allowance.

The key comes from `ctx.meta.getRequestMetadata().ip`, never from a browser value
or a forwarded request header. IPv4-mapped IPv6 resolves to the same IPv4 key;
IPv6 addresses share their /64 prefix to reduce privacy-address cycling. Only
an HMAC of the normalized network is passed to the private limiter mutation.
`BETTER_AUTH_SECRET` is the HMAC key as well as the existing auth secret; rotating
it changes the network keys. No new raw IP log or application table is added.
The limiter component retains its opaque keys; this is pseudonymization, not
anonymous data or a complete retention policy. Missing IP metadata or auth secret
blocks registration rather than bypassing the gate.

Set these **on the Convex deployment**, not in frontend variables:

| Variable | Default | Meaning |
| --- | ---: | --- |
| `DAISY_SIGNUPS_PER_IP_DAY` | 3 | New-user reservations per IPv4 or IPv6 /64 per UTC day |
| `DAISY_AI_REQUESTS_PER_MINUTE` | 6 | Provider calls per account per fixed minute |
| `DAISY_AI_GLOBAL_REQUESTS_DAY` | 1000 | Provider-call reservations across all accounts per UTC day |
| `DAISY_AI_GLOBAL_TOKENS_DAY` | 2000000 | Conservative reserved input/output units across all accounts per UTC day |
| `DAISY_AI_ENABLED` | enabled | Set exactly `false` to pause AI reservations without disabling ML controls/downloads |

Existing account limits of 100 AI requests and 200,000 tokens per rolling day
still apply. Global token reservations use the existing input-byte bound plus
requested output tokens and overhead. They are not refunded on failed calls or
settled downward; this intentionally overestimates provider use. Existing owner
usage can still settle to measured tokens. These are usage caps, not a guaranteed
currency-denominated cost cap. The global caps apply to the Convex adapter;
legacy SQLite/Supabase/demo modes retain their previous account budgets.

All new limits are durable in the rate-limiter component and shared across API
replicas using the same deployment. The Python API reserves before calling Groq;
reservation/storage failure prevents the provider call. There is no automatic
retry at the limiter. Requests already reserved/in flight can finish after the
kill switch changes.

## Deployment and operational checks

1. Run `npx convex dev --once` for development. For launch, deploy the same code
   to production with `npx convex deploy` and configure production secrets and
   limits independently.
2. Restart the Python API after updating its adapter error handling. The rate
   limits themselves are read on the Convex deployment.
3. Test email signup and first Google signup from a controlled network, then
   existing-account sign-in. Test the fourth new registration is rejected and
   a different network is independent. Never enter real passwords in scripts.
4. Configure the provider's own project spending/usage limits and alerts where
   available. Keep Groq and backend-bridge keys server-only. Rotate leaked keys.
5. Add an edge WAF/rate limit and CAPTCHA to registration before broad public
   marketing. This change limits account creation and AI spend; it does not
   prevent volumetric attacks on authentication or the Python API.

Shared home, campus or office networks share the limit. VPNs, mobile networks
and proxies can provide new IPs, so an IP gate alone cannot establish a unique
person. Existing accounts, sessions, ownership checks and global AI limits remain
necessary. Verification/CAPTCHA and manual abuse review are additional launch work.
