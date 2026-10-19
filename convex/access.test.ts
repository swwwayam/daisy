/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "./_generated/api";
import schema from "./schema";

const modules = import.meta.glob("./**/*.ts");
afterEach(() => vi.unstubAllEnvs());
function setup() {
  vi.stubEnv("DAISY_ACCESS_ADMIN_EMAILS", "owner@example.invalid");
  vi.stubEnv("DAISY_ACCESS_ADMIN_IDS", "");
  const t = convexTest(schema, modules);
  return { t, owner: t.withIdentity({ subject: "owner", email: "owner@example.invalid", emailVerified: true }), user: t.withIdentity({ subject: "member", email: "member@example.invalid", name: "Member", emailVerified: true }) };
}

test("anonymous and unapproved users cannot use the workspace or review requests", async () => {
  const { t, user } = setup();
  expect(await t.query(api.access.current)).toBeNull();
  await expect(t.mutation(api.access.requestAccess, { reason: "hello" })).rejects.toThrow("Sign in");
  await expect(user.mutation(api.accounts.ensurePersonalWorkspace)).rejects.toThrow("approved first");
  await expect(user.query(api.access.listRequests, { status: "pending", paginationOpts: { numItems: 20, cursor: null } })).rejects.toThrow("Administrator");
});

test("request is idempotent and approval is bound to the authenticated subject", async () => {
  const { t, owner, user } = setup();
  await user.mutation(api.access.requestAccess, { reason: "Evaluate CSVs" });
  await user.mutation(api.access.requestAccess, { reason: "duplicate" });
  const requests = await owner.query(api.access.listRequests, { status: "pending", paginationOpts: { numItems: 20, cursor: null } });
  expect(requests.page).toHaveLength(1);
  const request = requests.page[0];
  expect(request.authId).toBe("member");
  await expect(user.mutation(api.access.review, { id: request._id, status: "approved" })).rejects.toThrow("Administrator");
  await owner.mutation(api.access.review, { id: request._id, status: "approved" });
  expect((await user.query(api.access.current))?.status).toBe("approved");
  await expect(user.mutation(api.accounts.ensurePersonalWorkspace)).resolves.toBeTruthy();
  const impostor = t.withIdentity({ subject: "other", email: "member@example.invalid" });
  expect((await impostor.query(api.access.current))?.status).toBe("unrequested");
});

test("revocation blocks an existing identity and cannot be undone by requesting again", async () => {
  const { owner, user } = setup();
  await user.mutation(api.access.requestAccess, { reason: "" });
  const { page } = await owner.query(api.access.listRequests, { status: "pending", paginationOpts: { numItems: 20, cursor: null } });
  await owner.mutation(api.access.review, { id: page[0]._id, status: "approved" });
  await owner.mutation(api.access.review, { id: page[0]._id, status: "revoked" });
  await user.mutation(api.access.requestAccess, { reason: "retry" });
  expect((await user.query(api.access.current))?.status).toBe("revoked");
  await expect(user.mutation(api.accounts.ensurePersonalWorkspace)).rejects.toThrow("approved first");
});

test("unverified owner email cannot bootstrap administrator privileges", async () => {
  const { t, owner } = setup();
  expect((await owner.query(api.access.current))?.isAdmin).toBe(true);
  const impostor = t.withIdentity({ subject: "fake-owner", email: "owner@example.invalid", emailVerified: false });
  expect((await impostor.query(api.access.current))?.isAdmin).toBe(false);
  await expect(impostor.query(api.access.listRequests, { status: "pending", paginationOpts: { numItems: 20, cursor: null } })).rejects.toThrow("Administrator");
});

test("explicit admin IDs work without email verification; unset configuration fails closed", async () => {
  const { t } = setup();
  vi.stubEnv("DAISY_ACCESS_ADMIN_IDS", "trusted-owner");
  const trusted = t.withIdentity({ subject: "trusted-owner" });
  expect((await trusted.query(api.access.current))?.isAdmin).toBe(true);
  vi.stubEnv("DAISY_ACCESS_ADMIN_IDS", ""); vi.stubEnv("DAISY_ACCESS_ADMIN_EMAILS", "");
  expect((await trusted.query(api.access.current))?.status).toBe("unrequested");
});

test("oversized requests and admin list pages are rejected", async () => {
  const { owner, user } = setup();
  await expect(user.mutation(api.access.requestAccess, { reason: "x".repeat(501) })).rejects.toThrow("500");
  await expect(owner.query(api.access.listRequests, { status: "pending", paginationOpts: { numItems: 51, cursor: null } })).rejects.toThrow("50");
});

test("HTTP approval endpoint uses the authenticated identity and does not cache permissions", async () => {
  const { t, owner, user } = setup();
  vi.stubEnv("SITE_URL", "https://app.example.invalid");
  vi.stubEnv("CONVEX_SITE_URL", "https://example.convex.site");
  vi.stubEnv("BETTER_AUTH_SECRET", "test-only-secret-that-is-long-enough");
  expect((await t.fetch("/api/daisy/access")).status).toBe(401);
  const pending = await user.fetch("/api/daisy/access");
  expect(await pending.json()).toEqual({ approved: false });
  expect(pending.headers.get("Cache-Control")).toBe("no-store");
  expect(await (await owner.fetch("/api/daisy/access")).json()).toEqual({ approved: true });
});
