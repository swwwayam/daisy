import { paginationOptsValidator, paginationResultValidator } from "convex/server";
import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { accessForIdentity, isAccessAdmin } from "./accessPolicy";

const status = v.union(v.literal("pending"), v.literal("approved"), v.literal("denied"), v.literal("revoked"));
const entry = v.object({ _id: v.id("accessRequests"), _creationTime: v.number(), authId: v.string(), email: v.string(), name: v.string(), reason: v.string(), emailVerified: v.optional(v.boolean()), status, updatedAt: v.number(), reviewedBy: v.optional(v.string()) });

export const current = query({
  args: {},
  returns: v.union(v.null(), v.object({ isAdmin: v.boolean(), status: v.union(status, v.literal("unrequested")), userId: v.string(), email: v.string() })),
  handler: async ctx => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) return null;
    return { ...await accessForIdentity(ctx, identity), userId: identity.subject, email: identity.email ?? "" };
  },
});

export const requestAccess = mutation({
  args: { reason: v.string() }, returns: v.null(),
  handler: async (ctx, { reason }) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) throw new Error("Sign in before requesting access.");
    if (reason.length > 500) throw new Error("Please keep the request under 500 characters.");
    const existing = await ctx.db.query("accessRequests").withIndex("by_auth_id", q => q.eq("authId", identity.subject)).unique();
    if (existing || isAccessAdmin(identity)) return null;
    if (!identity.email) throw new Error("An email address is required to request access.");
    await ctx.db.insert("accessRequests", { authId: identity.subject, email: identity.email, name: identity.name ?? "", reason: reason.trim(), emailVerified: identity.emailVerified === true, status: "pending", updatedAt: Date.now() });
    return null;
  },
});

export const listRequests = query({
  args: { status, paginationOpts: paginationOptsValidator },
  returns: paginationResultValidator(entry),
  handler: async (ctx, args) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity || !isAccessAdmin(identity)) throw new Error("Administrator access required.");
    if (args.paginationOpts.numItems < 1 || args.paginationOpts.numItems > 50) throw new Error("Request at most 50 accounts per page.");
    return ctx.db.query("accessRequests").withIndex("by_status", q => q.eq("status", args.status)).order("desc").paginate(args.paginationOpts);
  },
});

export const review = mutation({
  args: { id: v.id("accessRequests"), status: v.union(v.literal("approved"), v.literal("denied"), v.literal("revoked")) },
  returns: v.null(),
  handler: async (ctx, args) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity || !isAccessAdmin(identity)) throw new Error("Administrator access required.");
    const request = await ctx.db.get(args.id);
    if (!request) throw new Error("Access request not found.");
    await ctx.db.patch(args.id, { status: args.status, reviewedBy: identity.subject, updatedAt: Date.now() });
    return null;
  },
});
