import { createAuthClient } from "better-auth/react";
import { convexClient, crossDomainClient } from "@convex-dev/better-auth/client/plugins";
import type { AuthClient } from "@convex-dev/better-auth/react";

const baseURL = (import.meta.env.VITE_CONVEX_SITE_URL as string | undefined)?.trim();

const validBaseURL = (() => { try { return !!baseURL && ["https:", "http:"].includes(new URL(baseURL).protocol); } catch { return false; } })();
export const authConfigurationError = !validBaseURL ? "Authentication is not configured. Set a valid VITE_CONVEX_SITE_URL and restart the frontend." : null;

export const authClient = createAuthClient({
  baseURL: validBaseURL ? baseURL : "https://configuration-missing.invalid",
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
