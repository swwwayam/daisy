import { createClient, type GenericCtx } from "@convex-dev/better-auth";
import { convex, crossDomain } from "@convex-dev/better-auth/plugins";
import { betterAuth } from "better-auth/minimal";
import type { DataModel } from "./_generated/dataModel";
import { components } from "./_generated/api";
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
