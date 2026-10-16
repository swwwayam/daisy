/** Private bridge for the Python API/worker. Never exposed as public mutations. */
import { v } from "convex/values";
import { internalMutation, type MutationCtx } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";
import { abuseLimiter, aiGlobalTokenLimit } from "./abuseProtection";

const kind = v.union(v.literal("dataset"), v.literal("artifact"), v.literal("run"), v.literal("preferences"), v.literal("experiment"));
const operations = v.union(...["probe", "upload", "discard", "save", "updateMetadata", "get", "page", "count", "remove", "finalization", "claimFinalization", "finishFinalization", "heartbeat", "workerReady", "enqueue", "job", "claimJob", "finishJob", "cancelJob", "reserveAi", "settleAi", "reservePrediction", "usage"].map(x => v.literal(x)));
const jobView = (r: Doc<"trainingJobs">) => ({ id: r._id, owner_id: r.ownerAuthId, idempotency_key: r.idempotencyKey, signature: r.signature, payload: r.payload, status: r.status, created_at: r._creationTime / 1000, lease_until: r.leaseUntil ? r.leaseUntil / 1000 : null, result: r.result ?? null, error: r.error ?? null });
const resourceView = (r: Doc<"daisyResources">) => ({ id: r.externalId, kind: r.kind, updated_at: new Date(r.updatedAt).toISOString(), metadata: r.metadata, metadataStorageId: r.metadataStorageId ?? null });
function required(value: string | undefined, field: string): string {
  if (!value || value.length > 512) throw new Error(`Invalid ${field}`);
  return value;
}
function quantity(value: number | undefined, max: number): number {
  if (value === undefined || !Number.isSafeInteger(value) || value < 0 || value > max) throw new Error("Invalid quantity");
  return value;
}
async function changeCount(ctx: MutationCtx, owner: string, resourceKind: string, delta: number) {
  const row = await ctx.db.query("resourceCounts").withIndex("by_owner_auth_id_and_kind", q => q.eq("ownerAuthId", owner).eq("kind", resourceKind)).unique();
  if (row) await ctx.db.patch(row._id, { count: Math.max(0, row.count + delta) });
  else await ctx.db.insert("resourceCounts", { ownerAuthId: owner, kind: resourceKind, count: Math.max(0, delta) });
}
async function fileUrl(ctx: MutationCtx, id?: Id<"_storage">) { return id ? await ctx.storage.getUrl(id) : null; }

export const dispatch = internalMutation({
  args: { op: operations, owner: v.optional(v.string()), id: v.optional(v.string()), kind: v.optional(kind),
    summary: v.optional(v.any()), metadataStorageId: v.optional(v.id("_storage")), metadataJson: v.optional(v.string()), storageId: v.optional(v.id("_storage")), blobEncoding: v.optional(v.literal("gzip")),
    cursor: v.optional(v.union(v.string(), v.null())), limit: v.optional(v.number()), source: v.optional(v.string()),
    experiment: v.optional(v.string()), reportStorageId: v.optional(v.id("_storage")), worker: v.optional(v.string()), status: v.optional(v.string()),
    key: v.optional(v.string()), signature: v.optional(v.string()), payload: v.optional(v.any()),
    resultStorageId: v.optional(v.id("_storage")), error: v.optional(v.union(v.string(), v.null())), amount: v.optional(v.number()) },
  returns: v.any(),
  handler: async (ctx, a) => {
    if (a.op === "probe") return true;
    if (a.op === "upload") return await ctx.storage.generateUploadUrl();
    if (a.op === "discard") { if (a.storageId) await ctx.storage.delete(a.storageId); return null; }
    if (a.op === "heartbeat") {
      const worker = required(a.worker, "worker");
      if (!["idle", "running", "stopped"].includes(a.status ?? "")) throw new Error("Invalid worker status");
      const status = a.status as "idle" | "running" | "stopped";
      const row = await ctx.db.query("workerHeartbeats").withIndex("by_worker_id", q => q.eq("workerId", worker)).unique();
      if (row) await ctx.db.patch(row._id, { seenAt: Date.now(), status });
      else await ctx.db.insert("workerHeartbeats", { workerId: worker, seenAt: Date.now(), status });
      return null;
    }
    if (a.op === "workerReady") {
      if (a.worker) {
        const row = await ctx.db.query("workerHeartbeats").withIndex("by_worker_id", q => q.eq("workerId", a.worker!)).unique();
        return !!row && row.seenAt > Date.now() - 90000 && row.status !== "stopped";
      }
      const rows = await ctx.db.query("workerHeartbeats").withIndex("by_seen_at", q => q.gt("seenAt", Date.now() - 90000)).take(100);
      return rows.some(r => r.status !== "stopped");
    }
    if (a.op === "claimJob") {
      const expired = await ctx.db.query("trainingJobs").withIndex("by_status_and_lease_until", q => q.eq("status", "running").lt("leaseUntil", Date.now())).take(100);
      for (const row of expired) await ctx.db.patch(row._id, { status: "failed", error: "Worker lease expired. Submit a new job." });
      const row = await ctx.db.query("trainingJobs").withIndex("by_status", q => q.eq("status", "queued")).first();
      if (!row) return null;
      await ctx.db.patch(row._id, { status: "running", leaseUntil: Date.now() + 660000 });
      return jobView({ ...row, status: "running", leaseUntil: Date.now() + 660000 });
    }
    const owner = required(a.owner, "owner"); // verified by Python; HTTP bridge is server-secret protected
    if (["save", "updateMetadata", "get", "remove"].includes(a.op)) {
      const id = required(a.id, "id");
      if (!a.kind) throw new Error("Missing resource kind");
      const row = await ctx.db.query("daisyResources").withIndex("by_external_id", q => q.eq("externalId", id)).unique();
      const owned = row && row.ownerAuthId === owner && row.kind === a.kind;
      if (a.op === "get") return owned ? { ...resourceView(row), metadataJson: row.metadataJson ?? null, blobEncoding: row.blobEncoding ?? null, metadataUrl: await fileUrl(ctx, row.metadataStorageId), blobUrl: await fileUrl(ctx, row.storageId) } : null;
      if (a.op === "remove") {
        if (!owned) return false;
        if (row.storageId) await ctx.storage.delete(row.storageId);
        if (row.metadataStorageId) await ctx.storage.delete(row.metadataStorageId);
        await ctx.db.delete(row._id); await changeCount(ctx, owner, a.kind, -1); return true;
      }
      if (row && !owned) throw new Error("Resource identity cannot be reassigned");
      if (row && a.kind === "experiment") throw new Error("Experiment records are immutable");
      if (!a.metadataStorageId && a.metadataJson === undefined) throw new Error("Missing metadata");
      if (a.metadataJson !== undefined && new TextEncoder().encode(a.metadataJson).length > 32768) throw new Error("Inline metadata exceeds limit");
      if (a.op === "updateMetadata" && !owned) throw new Error("Resource not found");
      const storageId = a.op === "updateMetadata" ? row!.storageId : a.storageId;
      const blobEncoding = a.op === "updateMetadata" ? row!.blobEncoding : a.blobEncoding;
      const fields = { externalId: id, ownerAuthId: owner, kind: a.kind, metadata: a.summary ?? {}, metadataJson: a.metadataJson, metadataStorageId: a.metadataStorageId, storageId, blobEncoding, updatedAt: Date.now() };
      if (row) {
        await ctx.db.patch(row._id, fields);
        if (row.storageId && row.storageId !== storageId) await ctx.storage.delete(row.storageId);
        if (row.metadataStorageId && row.metadataStorageId !== a.metadataStorageId) await ctx.storage.delete(row.metadataStorageId);
      } else { await ctx.db.insert("daisyResources", fields); await changeCount(ctx, owner, a.kind, 1); }
      return null;
    }
    if (a.op === "page") {
      const limit = quantity(a.limit ?? 50, 100);
      const query = a.kind
        ? ctx.db.query("daisyResources").withIndex("by_owner_auth_id_and_kind_and_updated_at", q => q.eq("ownerAuthId", owner).eq("kind", a.kind!)).order("desc")
        : ctx.db.query("daisyResources").withIndex("by_owner_auth_id_and_kind", q => q.eq("ownerAuthId", owner));
      const result = await query.paginate({ numItems: Math.max(1, limit), cursor: a.cursor ?? null });
      return { page: result.page.map(resourceView), cursor: result.continueCursor, done: result.isDone };
    }
    if (a.op === "count") {
      if (!a.kind) throw new Error("Missing resource kind");
      const row = await ctx.db.query("resourceCounts").withIndex("by_owner_auth_id_and_kind", q => q.eq("ownerAuthId", owner).eq("kind", a.kind!)).unique();
      return row?.count ?? 0;
    }
    if (["finalization", "claimFinalization", "finishFinalization"].includes(a.op)) {
      const source = required(a.source, "source");
      let row = await ctx.db.query("finalizations").withIndex("by_source_external_id_and_owner_auth_id", q => q.eq("sourceExternalId", source).eq("ownerAuthId", owner)).unique();
      if (a.op === "claimFinalization" && !row) {
        const id = await ctx.db.insert("finalizations", { sourceExternalId: source, ownerAuthId: owner, experimentExternalId: required(a.experiment, "experiment") });
        row = await ctx.db.get(id);
      }
      if (a.op === "finishFinalization") {
        if (!row || row.experimentExternalId !== a.experiment) throw new Error("Final evaluation does not match the claimed experiment");
        if (!row.report && !row.reportStorageId) {
          if (!a.reportStorageId) throw new Error("Missing final evaluation report");
          await ctx.db.patch(row._id, { reportStorageId: a.reportStorageId }); row = { ...row, reportStorageId: a.reportStorageId };
        } else if (a.reportStorageId && a.reportStorageId !== row.reportStorageId) await ctx.storage.delete(a.reportStorageId);
      }
      return row ? { experiment_id: row.experimentExternalId, report: row.report ?? null, reportUrl: await fileUrl(ctx, row.reportStorageId) } : null;
    }
    if (a.op === "enqueue") {
      const key = required(a.key, "idempotency key");
      const previous = await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id_and_idempotency_key", q => q.eq("ownerAuthId", owner).eq("idempotencyKey", key)).unique();
      if (previous) return previous.signature === a.signature ? jobView(previous) : { error: "Idempotency key was used for a different request", status: 409 };
      const queued = await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id_and_status", q => q.eq("ownerAuthId", owner).eq("status", "queued")).take(2);
      const running = await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id_and_status", q => q.eq("ownerAuthId", owner).eq("status", "running")).take(2);
      const daily = await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id", q => q.eq("ownerAuthId", owner).gt("_creationTime", Date.now() - 86400000)).take(10);
      const globalQueued = await ctx.db.query("trainingJobs").withIndex("by_status", q => q.eq("status", "queued")).take(100);
      const globalRunning = await ctx.db.query("trainingJobs").withIndex("by_status", q => q.eq("status", "running")).take(100);
      if (queued.length + running.length >= 2 || daily.length >= 10 || globalQueued.length + globalRunning.length >= 100) return { error: "Training quota reached. Wait for active jobs or try again tomorrow.", status: 429 };
      const id = await ctx.db.insert("trainingJobs", { ownerAuthId: owner, idempotencyKey: key, signature: required(a.signature, "signature"), payload: a.payload, status: "queued" });
      return jobView((await ctx.db.get(id))!);
    }
    if (["job", "finishJob", "cancelJob"].includes(a.op)) {
      const id = ctx.db.normalizeId("trainingJobs", required(a.id, "job id"));
      const row = id ? await ctx.db.get(id) : null;
      if (!row || row.ownerAuthId !== owner) return null;
      if (a.op === "finishJob" && row.status !== "running" && a.resultStorageId) await ctx.storage.delete(a.resultStorageId);
      if (a.op === "finishJob" && row.status === "running") {
        if (a.status !== "completed" && a.status !== "failed") throw new Error("Invalid completion status");
        await ctx.db.patch(row._id, { status: a.status, resultStorageId: a.resultStorageId, error: a.error ?? undefined });
      }
      if (a.op === "cancelJob" && (row.status === "running" || row.status === "queued")) await ctx.db.patch(row._id, { status: "cancelled" });
      const current = (await ctx.db.get(row._id))!;
      return { ...jobView(current), resultUrl: await fileUrl(ctx, current.resultStorageId) };
    }
    const since = Date.now() - 86400000;
    const ai = await ctx.db.query("aiUsage").withIndex("by_owner_auth_id", q => q.eq("ownerAuthId", owner).gt("_creationTime", since)).take(101);
    if (a.op === "reserveAi") {
      if (process.env.DAISY_AI_ENABLED === "false") return { error: "AI is temporarily paused by the administrator" };
      const tokens = quantity(a.amount, 200000);
      if (tokens > aiGlobalTokenLimit()) return { error: "Shared daily AI safety budget reached. Try again tomorrow." };
      if (ai.length >= 100 || ai.reduce((sum, r) => sum + r.tokens, 0) + tokens > 200000) return { error: "Daily AI budget reached" };
      const limiter = abuseLimiter();
      const checks = [
        ["aiByOwnerMinute", { key: owner }],
        ["aiGlobalDay", {}],
        ["aiGlobalTokens", { count: tokens }],
      ] as const;
      // Check all buckets before consuming any; the surrounding mutation makes
      // checking and charging atomic even under simultaneous requests.
      for (const [name, options] of checks) {
        const result = await limiter.check(ctx, name, options);
        if (!result.ok) return { error: name === "aiByOwnerMinute" ? "Too many AI requests. Wait a minute." : "Shared daily AI safety budget reached. Try again tomorrow." };
      }
      for (const [name, options] of checks) await limiter.limit(ctx, name, options);
      return { id: await ctx.db.insert("aiUsage", { ownerAuthId: owner, tokens }) };
    }
    if (a.op === "settleAi") {
      const id = ctx.db.normalizeId("aiUsage", required(a.id, "usage id"));
      const row = id ? await ctx.db.get(id) : null;
      if (row?.ownerAuthId === owner) await ctx.db.patch(row._id, { tokens: quantity(a.amount, 200000) });
      return null;
    }
    const inference = await ctx.db.query("predictionUsage").withIndex("by_owner_auth_id", q => q.eq("ownerAuthId", owner).gt("_creationTime", since)).take(101);
    if (a.op === "reservePrediction") {
      const rows = quantity(a.amount, 100000);
      const accepted = inference.length < 100 && inference.reduce((sum, r) => sum + r.rows, 0) + rows <= 100000;
      if (accepted) await ctx.db.insert("predictionUsage", { ownerAuthId: owner, rows });
      return { accepted };
    }
    if (a.op === "usage") {
      const training = await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id", q => q.eq("ownerAuthId", owner).gt("_creationTime", since)).take(10);
      const active = (await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id_and_status", q => q.eq("ownerAuthId", owner).eq("status", "queued")).take(2)).length + (await ctx.db.query("trainingJobs").withIndex("by_owner_auth_id_and_status", q => q.eq("ownerAuthId", owner).eq("status", "running")).take(2)).length;
      const expiry = (rows: { _creationTime: number }[]) => rows.length ? new Date(rows[0]._creationTime + 86400000).toISOString() : null;
      return { ai: { requests: ai.length, tokens: ai.reduce((s, r) => s + r.tokens, 0), next_expiry: expiry(ai) }, inference: { requests: inference.length, scored_rows: inference.reduce((s, r) => s + r.rows, 0), next_expiry: expiry(inference) }, training: { requests: training.length, active_jobs: active, next_expiry: expiry(training) } };
    }
    throw new Error("Unknown operation");
  },
});
