import type { UserIdentity } from "convex/server";
import type { QueryCtx, MutationCtx } from "./_generated/server";

export function isAccessAdmin(identity: UserIdentity): boolean {
  const ids = (process.env.DAISY_ACCESS_ADMIN_IDS ?? "").split(",").map(value => value.trim()).filter(Boolean);
  if (ids.includes(identity.subject)) return true;
  const emails = (process.env.DAISY_ACCESS_ADMIN_EMAILS ?? "").split(",").map(value => value.trim().toLowerCase()).filter(Boolean);
  // Email/password signup currently permits unverified email addresses. Such
  // accounts must never gain administrator rights by claiming an owner's email.
  return identity.emailVerified === true && typeof identity.email === "string" && emails.includes(identity.email.toLowerCase());
}

export async function accessForIdentity(ctx: QueryCtx | MutationCtx, identity: UserIdentity) {
  const isAdmin = isAccessAdmin(identity);
  const request = await ctx.db.query("accessRequests").withIndex("by_auth_id", q => q.eq("authId", identity.subject)).unique();
  return { isAdmin, status: isAdmin ? "approved" as const : request?.status ?? "unrequested" as const };
}

export async function requireApprovedAccess(ctx: QueryCtx | MutationCtx) {
  const identity = await ctx.auth.getUserIdentity();
  if (!identity) throw new Error("Sign in to use DAISY.");
  const access = await accessForIdentity(ctx, identity);
  if (access.status !== "approved") throw new Error("Your DAISY access request must be approved first.");
  return identity;
}
