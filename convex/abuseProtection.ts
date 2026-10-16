import { RateLimiter, DAY, MINUTE } from "@convex-dev/rate-limiter";
import { v } from "convex/values";
import { components } from "./_generated/api";
import { internalMutation } from "./_generated/server";

function positiveLimit(name: string, fallback: number, maximum: number): number {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 1 || value > maximum) {
    throw new Error(`Invalid security limit: ${name}`);
  }
  return value;
}

// Fixed UTC-day windows; no rollover or asynchronous updates. One shared component
// enforces limits across instances. Failed provider calls keep their reservation.
export function abuseLimiter() {
  return new RateLimiter(components.rateLimiter, {
    signupByIp: { kind: "fixed window", rate: positiveLimit("DAISY_SIGNUPS_PER_IP_DAY", 3, 1000), period: DAY, start: 0 },
    aiByOwnerMinute: { kind: "fixed window", rate: positiveLimit("DAISY_AI_REQUESTS_PER_MINUTE", 6, 1000), period: MINUTE, start: 0 },
    aiGlobalDay: { kind: "fixed window", rate: positiveLimit("DAISY_AI_GLOBAL_REQUESTS_DAY", 1000, 100000), period: DAY, start: 0 },
    aiGlobalTokens: { kind: "fixed window", rate: aiGlobalTokenLimit(), period: DAY, start: 0 },
  });
}

export function aiGlobalTokenLimit() {
  return positiveLimit("DAISY_AI_GLOBAL_TOKENS_DAY", 2000000, 1000000000);
}

export const reserveSignup = internalMutation({
  args: { ipKey: v.string() },
  returns: v.object({ ok: v.boolean(), retryAfter: v.optional(v.number()) }),
  handler: async (ctx, { ipKey }) => {
    if (!/^[a-f0-9]{64}$/.test(ipKey)) throw new Error("Invalid signup key");
    const result = await abuseLimiter().limit(ctx, "signupByIp", { key: ipKey });
    return result.ok ? { ok: true } : { ok: false, retryAfter: result.retryAfter };
  },
});
