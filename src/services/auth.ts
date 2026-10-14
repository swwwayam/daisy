import { createAuthClient } from "better-auth/react";
import { convexClient, crossDomainClient } from "@convex-dev/better-auth/client/plugins";
import type { AuthClient } from "@convex-dev/better-auth/react";

const baseURL = (import.meta.env.VITE_CONVEX_SITE_URL as string | undefined)?.trim();

if (!baseURL) {
  throw new Error("Convex Auth is not configured. Add VITE_CONVEX_SITE_URL to .env.local.");
}

export const authClient = createAuthClient({
  baseURL,
  plugins: [convexClient(), crossDomainClient()],
});

// The provider's public type currently loses Better Auth's inferred session
// shape when cross-domain and Convex plugins are combined.
export const convexAuthClient = authClient as unknown as AuthClient;

export async function getAccessToken(): Promise<string> {
  const { data, error } = await authClient.convex.token({ fetchOptions: { throw: false } });
  if (error || !data?.token) throw new Error("Your session has expired. Sign in again.");
  return data.token;
}
