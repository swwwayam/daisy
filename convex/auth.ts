import { createClient, type GenericCtx } from "@convex-dev/better-auth";
import { convex, crossDomain } from "@convex-dev/better-auth/plugins";
import { betterAuth } from "better-auth/minimal";
import type { DataModel } from "./_generated/dataModel";
import { components, internal } from "./_generated/api";
import { APIError } from "better-auth/api";
import { signupIpKey } from "./ipIdentity";
import { query } from "./_generated/server";
import authConfig from "./auth.config";

const siteUrl = process.env.SITE_URL!;

export const authComponent = createClient<DataModel>(components.betterAuth);

export const createAuth = (ctx: GenericCtx<DataModel>) => {
  const googleClientId = process.env.GOOGLE_CLIENT_ID;
  const googleClientSecret = process.env.GOOGLE_CLIENT_SECRET;

  return betterAuth({
    baseURL: process.env.CONVEX_SITE_URL,
    trustedOrigins: [siteUrl],
    database: authComponent.adapter(ctx),
    databaseHooks: {
      user: {
        create: {
          before: async (user) => {
            // This hook runs only for new users, including OAuth, not sign-in.
            // Never use X-Forwarded-For or accept an IP supplied by the client.
            if (!("runMutation" in ctx) || !("meta" in ctx) || !("getRequestMetadata" in ctx.meta)) {
              throw new APIError("SERVICE_UNAVAILABLE", { message: "Account registration is temporarily unavailable." });
            }
            const { ip } = await ctx.meta.getRequestMetadata();
            if (!ip || !process.env.BETTER_AUTH_SECRET) {
              throw new APIError("SERVICE_UNAVAILABLE", { message: "Account registration is temporarily unavailable." });
            }
            const ipKey = await signupIpKey(ip, process.env.BETTER_AUTH_SECRET);
            const result: { ok: boolean; retryAfter?: number } = await ctx.runMutation(internal.abuseProtection.reserveSignup, { ipKey });
            if (!result.ok) {
              throw new APIError("TOO_MANY_REQUESTS", { message: "Daily account registration limit reached for this network. Try again tomorrow or sign in to an existing account." });
            }
            return { data: user };
          },
        },
      },
    },
    emailAndPassword: {
      enabled: true,
      requireEmailVerification: false,
      minPasswordLength: 8,
    },
    socialProviders:
      googleClientId && googleClientSecret
        ? { google: { clientId: googleClientId, clientSecret: googleClientSecret } }
        : undefined,
    plugins: [crossDomain({ siteUrl }), convex({ authConfig })],
  });
};

export const getCurrentUser = query({
  args: {},
  handler: async (ctx) => await authComponent.getAuthUser(ctx),
});
