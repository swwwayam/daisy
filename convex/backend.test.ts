/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { expect, test } from "vitest";
import schema from "./schema";
import rateLimiter from "@convex-dev/rate-limiter/test";
import { internal } from "./_generated/api";
import type { FunctionArgs, FunctionReference } from "convex/server";

const modules = import.meta.glob("./**/*.ts");
// The private RPC intentionally returns a different JSON shape per operation.
const backend: FunctionReference<"mutation", "internal", FunctionArgs<typeof internal.backend.dispatch>, any> = internal.backend.dispatch;

test("resources retain owner boundaries, private bytes, immutable experiments, and counts", async () => {
  const t = convexTest(schema, modules);
  const metadataStorageId = await t.run(ctx => ctx.storage.store(new Blob([JSON.stringify({ secret: "private" })])));
  await t.mutation(backend, { op: "save", owner: "a", id: "resource", kind: "experiment", metadataStorageId, summary: { created_at: "today" } });
  expect(await t.mutation(backend, { op: "get", owner: "b", id: "resource", kind: "experiment" })).toBeNull();
  expect(await t.mutation(backend, { op: "remove", owner: "b", id: "resource", kind: "experiment" })).toBe(false);
  await expect(t.mutation(backend, { op: "save", owner: "b", id: "resource", kind: "experiment", metadataStorageId })).rejects.toThrow("cannot be reassigned");
  await expect(t.mutation(backend, { op: "save", owner: "a", id: "resource", kind: "experiment", metadataStorageId })).rejects.toThrow("immutable");
  expect(await t.mutation(backend, { op: "count", owner: "a", kind: "experiment" })).toBe(1);
  expect(await t.mutation(backend, { op: "remove", owner: "a", id: "resource", kind: "experiment" })).toBe(true);
  expect(await t.mutation(backend, { op: "count", owner: "a", kind: "experiment" })).toBe(0);
  expect(await t.run(ctx => ctx.storage.get(metadataStorageId))).toBeNull();
});

test("queue preserves idempotency, enforces quota, claims once, and protects cancellation", async () => {
  const t = convexTest(schema, modules);
  const input = { op: "enqueue", owner: "a", key: "one", signature: "same", payload: { dataset_id: "data" } };
  const first = await t.mutation(backend, input);
  expect((await t.mutation(backend, input)).id).toBe(first.id);
  expect((await t.mutation(backend, { ...input, signature: "changed" })).status).toBe(409);
  await t.mutation(backend, { ...input, key: "two" });
  expect((await t.mutation(backend, { ...input, key: "three" })).status).toBe(429);
  const claimed = await t.mutation(backend, { op: "claimJob" });
  expect(claimed.id).toBe(first.id);
  expect((await t.mutation(backend, { op: "claimJob" })).id).not.toBe(first.id);
  expect(await t.mutation(backend, { op: "claimJob" })).toBeNull();
  expect(await t.mutation(backend, { op: "cancelJob", owner: "b", id: first.id })).toBeNull();
  await t.mutation(backend, { op: "cancelJob", owner: "a", id: first.id });
  await t.mutation(backend, { op: "finishJob", owner: "a", id: first.id, status: "completed" });
  expect((await t.mutation(backend, { op: "job", owner: "a", id: first.id })).status).toBe("cancelled");
});

test("metadata-only writes preserve dataset bytes and protect ownership", async () => {
  const t = convexTest(schema, modules);
  const storageId = await t.run(ctx => ctx.storage.store(new Blob(["original data"])));
  const metadataStorageId = await t.run(ctx => ctx.storage.store(new Blob(['{"context":{}}'])));
  await t.mutation(backend, { op: "save", owner: "a", id: "data", kind: "dataset", storageId, metadataStorageId, blobEncoding: "gzip" });
  await expect(t.mutation(backend, { op: "updateMetadata", owner: "b", id: "data", kind: "dataset", metadataJson: "{}" })).rejects.toThrow("cannot be reassigned");
  await t.mutation(backend, { op: "updateMetadata", owner: "a", id: "data", kind: "dataset", metadataJson: '{"context":{"eda":"done"}}' });
  const row = await t.mutation(backend, { op: "get", owner: "a", id: "data", kind: "dataset" });
  expect(JSON.parse(row.metadataJson).context.eda).toBe("done");
  expect(row.metadataUrl).toBeNull();
  expect(row.blobUrl).toBeTruthy();
  expect(row.blobEncoding).toBe("gzip");
  expect(await t.run(async ctx => (await ctx.storage.get(storageId))?.size ?? 0)).toBe(13);
  expect(await t.run(ctx => ctx.storage.get(metadataStorageId))).toBeNull();
  expect(await t.mutation(backend, { op: "count", owner: "a", kind: "dataset" })).toBe(1);
  await expect(t.mutation(backend, { op: "updateMetadata", owner: "a", id: "data", kind: "dataset", metadataJson: "x".repeat(32769) })).rejects.toThrow("exceeds limit");
});

test("holdout finalization cannot change winners or overwrite the first report", async () => {
  const t = convexTest(schema, modules);
  const claim = { source: "dataset", owner: "a" };
  await t.mutation(backend, { op: "claimFinalization", ...claim, experiment: "winner" });
  expect((await t.mutation(backend, { op: "claimFinalization", ...claim, experiment: "different" })).experiment_id).toBe("winner");
  const reportStorageId = await t.run(ctx => ctx.storage.store(new Blob(['{"score":1}'])));
  await expect(t.mutation(backend, { op: "finishFinalization", ...claim, experiment: "different", reportStorageId })).rejects.toThrow("does not match");
  await t.mutation(backend, { op: "finishFinalization", ...claim, experiment: "winner", reportStorageId });
  const reportTwo = await t.run(ctx => ctx.storage.store(new Blob(['{"score":2}'])));
  await t.mutation(backend, { op: "finishFinalization", ...claim, experiment: "winner", reportStorageId: reportTwo });
  expect(await t.run(ctx => ctx.storage.get(reportTwo))).toBeNull();
});

test("rolling usage is durable, isolated and bounded", async () => {
  const t = convexTest(schema, modules);
  rateLimiter.register(t);
  expect(await t.mutation(backend, { op: "reservePrediction", owner: "a", amount: 100000 })).toEqual({ accepted: true });
  expect(await t.mutation(backend, { op: "reservePrediction", owner: "a", amount: 1 })).toEqual({ accepted: false });
  expect(await t.mutation(backend, { op: "reservePrediction", owner: "b", amount: 1 })).toEqual({ accepted: true });
  const ai = await t.mutation(backend, { op: "reserveAi", owner: "a", amount: 200000 });
  expect((await t.mutation(backend, { op: "reserveAi", owner: "a", amount: 1 })).error).toBeTruthy();
  await t.mutation(backend, { op: "settleAi", owner: "b", id: ai.id, amount: 0 });
  expect((await t.mutation(backend, { op: "usage", owner: "a" })).ai.tokens).toBe(200000);
  await t.mutation(backend, { op: "settleAi", owner: "a", id: ai.id, amount: 50 });
  expect((await t.mutation(backend, { op: "usage", owner: "a" })).ai.tokens).toBe(50);
  await expect(t.mutation(backend, { op: "reservePrediction", owner: "a", amount: -1 })).rejects.toThrow("Invalid quantity");
});
