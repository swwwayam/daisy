/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import rateLimiter from "@convex-dev/rate-limiter/test";
import { afterEach, expect, test, vi } from "vitest";
import { internal } from "./_generated/api";
import schema from "./schema";
import { signupIpKey, signupNetwork } from "./ipIdentity";
import { createAuth } from "./auth";
import type { GenericCtx } from "@convex-dev/better-auth";
import type { DataModel } from "./_generated/dataModel";

const modules = import.meta.glob("./**/*.ts");
afterEach(() => { vi.unstubAllEnvs(); vi.useRealTimers(); });

test("new-user hook takes IP from platform metadata and fails closed without it", async () => {
  vi.stubEnv("SITE_URL", "https://daisy.example");
  vi.stubEnv("CONVEX_SITE_URL", "https://test.convex.site");
  vi.stubEnv("BETTER_AUTH_SECRET", "test-only-secret-for-hook-testing-12345");
  const reserve = vi.fn().mockResolvedValue({ ok: true });
  const metadata = vi.fn().mockResolvedValue({ ip: "192.0.2.1" });
  const ctx = { runMutation: reserve, meta: { getRequestMetadata: metadata } } as unknown as GenericCtx<DataModel>;
  const hook = createAuth(ctx).options.databaseHooks!.user!.create!.before!;
  const user = { id: "user", name: "Test", email: "test@example.invalid", emailVerified: false, createdAt: new Date(), updatedAt: new Date() };
  expect(await hook(user)).toEqual({ data: user });
  expect(reserve).toHaveBeenCalledWith(internal.abuseProtection.reserveSignup, { ipKey: await signupIpKey("192.0.2.1", "test-only-secret-for-hook-testing-12345") });
  reserve.mockResolvedValue({ ok: false });
  await expect(hook(user)).rejects.toThrow("Daily account registration limit");
  metadata.mockResolvedValue({ ip: null });
  reserve.mockClear();
  await expect(hook(user)).rejects.toThrow("temporarily unavailable");
  expect(reserve).not.toHaveBeenCalled();
});

test("equivalent IP spellings share a private key; IPv6 privacy addresses share a /64", async () => {
  expect(signupNetwork("::ffff:192.0.2.1")).toBe("192.0.2.1");
  expect(signupNetwork("2001:db8:abcd:1234::1")).toBe(signupNetwork("2001:0db8:abcd:1234::999"));
  expect(signupNetwork("2001:db8:abcd:1235::1")).not.toBe(signupNetwork("2001:db8:abcd:1234::1"));
  const key = await signupIpKey("192.0.2.1", "test-only-secret");
  expect(key).toMatch(/^[a-f0-9]{64}$/);
  expect(key).toBe(await signupIpKey("::ffff:192.0.2.1", "test-only-secret"));
  expect(key).not.toBe(await signupIpKey("192.0.2.1", "different-test-secret"));
  expect(() => signupNetwork("192.0.2.1, 203.0.113.1")).toThrow();
  expect(() => signupNetwork("999.0.0.1")).toThrow();
});

test("concurrent registrations admit exactly three per network; a different network remains available", async () => {
  const t = convexTest(schema, modules);
  rateLimiter.register(t);
  const results = await Promise.all(Array.from({ length: 8 }, () => t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "a".repeat(64) })));
  expect(results.filter(r => r.ok)).toHaveLength(3);
  expect(results.filter(r => !r.ok)).toHaveLength(5);
  expect((await t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "b".repeat(64) })).ok).toBe(true);
  await expect(t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "192.0.2.1" })).rejects.toThrow("Invalid signup key");
});

test("registration budget resets at the next UTC day", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-16T12:00:00Z"));
  const t = convexTest(schema, modules);
  rateLimiter.register(t);
  for (let i = 0; i < 3; i++) expect((await t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "c".repeat(64) })).ok).toBe(true);
  expect((await t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "c".repeat(64) })).ok).toBe(false);
  vi.setSystemTime(new Date("2026-10-17T00:00:01Z"));
  expect((await t.mutation(internal.abuseProtection.reserveSignup, { ipKey: "c".repeat(64) })).ok).toBe(true);
});

test("shared AI limits cannot be evaded by changing accounts and blocked calls do not create usage", async () => {
  vi.stubEnv("DAISY_AI_GLOBAL_REQUESTS_DAY", "2");
  const t = convexTest(schema, modules);
  rateLimiter.register(t);
  const dispatch = internal.backend.dispatch;
  expect(await t.mutation(dispatch, { op: "reserveAi", owner: "one", amount: 1000 })).toHaveProperty("id");
  expect(await t.mutation(dispatch, { op: "reserveAi", owner: "two", amount: 1000 })).toHaveProperty("id");
  expect(await t.mutation(dispatch, { op: "reserveAi", owner: "three", amount: 1000 })).toHaveProperty("error", "Shared daily AI safety budget reached. Try again tomorrow.");
  expect(await t.run(ctx => ctx.db.query("aiUsage").collect())).toHaveLength(2);
});

test("AI kill switch, conservative token reservation, and owner burst limits run before spend", async () => {
  const t = convexTest(schema, modules);
  rateLimiter.register(t);
  vi.stubEnv("DAISY_AI_ENABLED", "false");
  expect(await t.mutation(internal.backend.dispatch, { op: "reserveAi", owner: "one", amount: 100 })).toHaveProperty("error");
  vi.stubEnv("DAISY_AI_ENABLED", "true");
  vi.stubEnv("DAISY_AI_GLOBAL_TOKENS_DAY", "500");
  expect(await t.mutation(internal.backend.dispatch, { op: "reserveAi", owner: "one", amount: 501 })).toHaveProperty("error");
  vi.stubEnv("DAISY_AI_REQUESTS_PER_MINUTE", "1");
  expect(await t.mutation(internal.backend.dispatch, { op: "reserveAi", owner: "one", amount: 100 })).toHaveProperty("id");
  expect(await t.mutation(internal.backend.dispatch, { op: "reserveAi", owner: "one", amount: 100 })).toHaveProperty("error", "Too many AI requests. Wait a minute.");
});
