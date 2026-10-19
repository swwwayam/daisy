
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const workspaceRole = v.union(
  v.literal("owner"),
  v.literal("admin"),
  v.literal("member"),
  v.literal("viewer"),
);

const datasetStatus = v.union(
  v.literal("uploading"),
  v.literal("uploaded"),
  v.literal("processing"),
  v.literal("ready"),
  v.literal("failed"),
  v.literal("deleted"),
);

const runStatus = v.union(
  v.literal("queued"),
  v.literal("running"),
  v.literal("completed"),
  v.literal("partial"),
  v.literal("failed"),
  v.literal("cancelled"),
);

export default defineSchema({
  accessRequests: defineTable({
    authId: v.string(),
    email: v.string(),
    name: v.string(),
    reason: v.string(),
    emailVerified: v.optional(v.boolean()),
    status: v.union(v.literal("pending"), v.literal("approved"), v.literal("denied"), v.literal("revoked")),
    updatedAt: v.number(),
    reviewedBy: v.optional(v.string()),
  }).index("by_auth_id", ["authId"]).index("by_status", ["status"]),

  profiles: defineTable({
    authId: v.string(),
    email: v.optional(v.string()),
    displayName: v.optional(v.string()),
    updatedAt: v.number(),
  }).index("by_auth_id", ["authId"]),

  workspaces: defineTable({
    name: v.string(),
    ownerAuthId: v.string(),
    updatedAt: v.number(),
  }).index("by_owner_auth_id", ["ownerAuthId"]),

  workspaceMembers: defineTable({
    workspaceId: v.id("workspaces"),
    userAuthId: v.string(),
    role: workspaceRole,
  })
    .index("by_workspace_id_and_user_auth_id", ["workspaceId", "userAuthId"])
    .index("by_user_auth_id", ["userAuthId"]),

  projects: defineTable({
    workspaceId: v.id("workspaces"),
    name: v.string(),
    description: v.optional(v.string()),
    createdByAuthId: v.string(),
    updatedAt: v.number(),
  }).index("by_workspace_id", ["workspaceId"]),

  datasets: defineTable({
    projectId: v.id("projects"),
    uploadedByAuthId: v.string(),
    filename: v.string(),
    storageId: v.optional(v.id("_storage")),
    byteSize: v.number(),
    rowCount: v.optional(v.number()),
    columnCount: v.optional(v.number()),
    schemaReport: v.any(),
    datasetFingerprint: v.optional(v.string()),
    status: datasetStatus,
    updatedAt: v.number(),
  })
    .index("by_project_id", ["projectId"])
    .index("by_uploaded_by_auth_id", ["uploadedByAuthId"]),

  pipelineRuns: defineTable({
    projectId: v.id("projects"),
    datasetId: v.id("datasets"),
    createdByAuthId: v.string(),
    status: runStatus,
    currentStage: v.optional(v.string()),
    targetColumn: v.optional(v.string()),
    testSize: v.optional(v.number()),
    randomState: v.number(),
    configuration: v.any(),
    errorMessage: v.optional(v.string()),
    startedAt: v.optional(v.number()),
    completedAt: v.optional(v.number()),
    updatedAt: v.number(),
  })
    .index("by_project_id", ["projectId"])
    .index("by_dataset_id", ["datasetId"])
    .index("by_created_by_auth_id", ["createdByAuthId"]),

  experiments: defineTable({
    projectId: v.id("projects"),
    runId: v.id("pipelineRuns"),
    modelName: v.string(),
    problemType: v.union(v.literal("classification"), v.literal("regression")),
    status: v.union(v.literal("success"), v.literal("failed")),
    isWinner: v.boolean(),
    metrics: v.any(),
    parameters: v.any(),
    trainingTimeSeconds: v.optional(v.number()),
  })
    .index("by_run_id", ["runId"])
    .index("by_project_id", ["projectId"]),

  modelArtifacts: defineTable({
    projectId: v.id("projects"),
    runId: v.id("pipelineRuns"),
    experimentId: v.optional(v.id("experiments")),
    createdByAuthId: v.string(),
    filename: v.string(),
    storageId: v.id("_storage"),
    byteSize: v.number(),
    checksumSha256: v.string(),
    metadata: v.any(),
    expiresAt: v.optional(v.number()),
  })
    .index("by_run_id", ["runId"])
    .index("by_created_by_auth_id", ["createdByAuthId"]),

  usageEvents: defineTable({
    workspaceId: v.id("workspaces"),
    userAuthId: v.string(),
    eventType: v.union(
      v.literal("dataset_upload"),
      v.literal("training_run"),
      v.literal("storage_bytes"),
      v.literal("model_download"),
    ),
    quantity: v.number(),
    metadata: v.any(),
  })
    .index("by_workspace_id", ["workspaceId"])
    .index("by_user_auth_id", ["userAuthId"]),

  daisyResources: defineTable({
    externalId: v.string(),
    ownerAuthId: v.string(),
    kind: v.union(
      v.literal("dataset"),
      v.literal("artifact"),
      v.literal("run"),
      v.literal("preferences"),
      v.literal("experiment"),
    ),
    metadata: v.any(),
    storageId: v.optional(v.id("_storage")),
    metadataStorageId: v.optional(v.id("_storage")),
    metadataJson: v.optional(v.string()),
    blobEncoding: v.optional(v.literal("gzip")),
    contentType: v.optional(v.string()),
    updatedAt: v.number(),
  })
    .index("by_external_id", ["externalId"])
    .index("by_owner_auth_id_and_kind", ["ownerAuthId", "kind"])
    .index("by_owner_auth_id_and_kind_and_updated_at", ["ownerAuthId", "kind", "updatedAt"]),

  resourceCounts: defineTable({ ownerAuthId: v.string(), kind: v.string(), count: v.number() })
    .index("by_owner_auth_id_and_kind", ["ownerAuthId", "kind"]),

  trainingJobs: defineTable({
    ownerAuthId: v.string(),
    idempotencyKey: v.string(),
    signature: v.string(),
    payload: v.any(),
    status: v.union(
      v.literal("queued"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("failed"),
      v.literal("cancelled"),
    ),
    leaseUntil: v.optional(v.number()),
    result: v.optional(v.any()),
    resultStorageId: v.optional(v.id("_storage")),
    error: v.optional(v.string()),
  })
    .index("by_owner_auth_id_and_idempotency_key", ["ownerAuthId", "idempotencyKey"])
    .index("by_status", ["status"])
    .index("by_status_and_lease_until", ["status", "leaseUntil"])
    .index("by_owner_auth_id_and_status", ["ownerAuthId", "status"])
    .index("by_owner_auth_id", ["ownerAuthId"]),

  aiUsage: defineTable({
    ownerAuthId: v.string(),
    tokens: v.number(),
  }).index("by_owner_auth_id", ["ownerAuthId"]),

  finalizations: defineTable({
    sourceExternalId: v.string(),
    ownerAuthId: v.string(),
    experimentExternalId: v.string(),
    report: v.optional(v.any()),
    reportStorageId: v.optional(v.id("_storage")),
  }).index("by_source_external_id_and_owner_auth_id", ["sourceExternalId", "ownerAuthId"]),

  workerHeartbeats: defineTable({
    workerId: v.string(),
    seenAt: v.number(),
    status: v.union(v.literal("idle"), v.literal("running"), v.literal("stopped")),
  }).index("by_worker_id", ["workerId"]).index("by_seen_at", ["seenAt"]),

  predictionUsage: defineTable({
    ownerAuthId: v.string(),
    rows: v.number(),
  }).index("by_owner_auth_id", ["ownerAuthId"]),
});
