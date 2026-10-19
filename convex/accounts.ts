import { mutation, query, type MutationCtx } from "./_generated/server";
import { requireApprovedAccess } from "./accessPolicy";

async function requireIdentity(ctx: MutationCtx) {
  return requireApprovedAccess(ctx);
}

export const ensurePersonalWorkspace = mutation({
  args: {},
  handler: async (ctx) => {
    const identity = await requireIdentity(ctx);
    const authId = identity.tokenIdentifier;
    const now = Date.now();
    const email = typeof identity.email === "string" ? identity.email : undefined;
    const displayName =
      typeof identity.name === "string" && identity.name.trim()
        ? identity.name.trim()
        : email?.split("@")[0] || "DAISY user";

    const profile = await ctx.db
      .query("profiles")
      .withIndex("by_auth_id", (q) => q.eq("authId", authId))
      .unique();
    if (profile) {
      await ctx.db.patch(profile._id, { email, displayName, updatedAt: now });
    } else {
      await ctx.db.insert("profiles", { authId, email, displayName, updatedAt: now });
    }

    let workspace = await ctx.db
      .query("workspaces")
      .withIndex("by_owner_auth_id", (q) => q.eq("ownerAuthId", authId))
      .unique();
    if (!workspace) {
      const workspaceId = await ctx.db.insert("workspaces", {
        name: `${displayName}'s workspace`,
        ownerAuthId: authId,
        updatedAt: now,
      });
      workspace = await ctx.db.get(workspaceId);
    }
    if (!workspace) throw new Error("Unable to create workspace");

    const membership = await ctx.db
      .query("workspaceMembers")
      .withIndex("by_workspace_id_and_user_auth_id", (q) =>
        q.eq("workspaceId", workspace._id).eq("userAuthId", authId),
      )
      .unique();
    if (!membership) {
      await ctx.db.insert("workspaceMembers", {
        workspaceId: workspace._id,
        userAuthId: authId,
        role: "owner",
      });
    }
    return { profileId: profile?._id ?? null, workspaceId: workspace._id };
  },
});

export const currentWorkspace = query({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) return null;
    await requireApprovedAccess(ctx);
    return await ctx.db
      .query("workspaces")
      .withIndex("by_owner_auth_id", (q) => q.eq("ownerAuthId", identity.tokenIdentifier))
      .unique();
  },
});
