/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as abuseProtection from "../abuseProtection.js";
import type * as access from "../access.js";
import type * as accessPolicy from "../accessPolicy.js";
import type * as accounts from "../accounts.js";
import type * as auth from "../auth.js";
import type * as backend from "../backend.js";
import type * as http from "../http.js";
import type * as ipIdentity from "../ipIdentity.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  abuseProtection: typeof abuseProtection;
  access: typeof access;
  accessPolicy: typeof accessPolicy;
  accounts: typeof accounts;
  auth: typeof auth;
  backend: typeof backend;
  http: typeof http;
  ipIdentity: typeof ipIdentity;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {
  betterAuth: import("@convex-dev/better-auth/_generated/component.js").ComponentApi<"betterAuth">;
  rateLimiter: import("@convex-dev/rate-limiter/_generated/component.js").ComponentApi<"rateLimiter">;
};
