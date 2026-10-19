import { httpRouter } from "convex/server";
import { authComponent, createAuth } from "./auth";
import { httpAction } from "./_generated/server";
import { api, internal } from "./_generated/api";

const http = httpRouter();
authComponent.registerRoutes(http, createAuth, { cors: true });

// The Python API forwards the verified user's bearer token here on every
// protected request. Revocation takes effect even for an existing session.
http.route({
  path: "/api/daisy/access", method: "GET",
  handler: httpAction(async ctx => {
    const access = await ctx.runQuery(api.access.current, {});
    return Response.json({ approved: access?.status === "approved" }, {
      status: access ? 200 : 401, headers: { "Cache-Control": "no-store" },
    });
  }),
});

http.route({
  path: "/api/daisy/backend",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    const secret = process.env.DAISY_BACKEND_SECRET;
    if (!secret) return new Response("Backend bridge is not configured", { status: 503 });
    const provided = request.headers.get("Authorization")?.replace(/^Bearer /, "") ?? "";
    // Compare fixed-length hashes without a secret-dependent early exit.
    const hash = async (text: string) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
    const [left, right] = await Promise.all([hash(secret), hash(provided)]);
    let difference = 0;
    for (let i = 0; i < left.length; i++) difference |= left[i] ^ right[i];
    if (difference) return new Response("Unauthorized", { status: 401 });
    try {
      const body: unknown = await request.json();
      if (!body || typeof body !== "object" || !("op" in body) || typeof body.op !== "string") return new Response("Invalid operation", { status: 400 });
      // The generated mutation validates every bridge argument at runtime.
      const result: unknown = await ctx.runMutation(internal.backend.dispatch, body as Parameters<typeof ctx.runMutation<typeof internal.backend.dispatch>>[1]);
      return Response.json(result);
    } catch (error) {
      console.error("DAISY bridge operation failed", error instanceof Error ? error.message : "Unknown error");
      return Response.json({ error: "Convex storage operation failed" }, { status: 400 });
    }
  }),
});

export default http;
