const requiredUrls = ["VITE_CONVEX_URL", "VITE_CONVEX_SITE_URL", "VITE_DAISY_API_URL"] as const;

/** Catch broken production endpoints before publishing a blank or unusable app. */
export function validateProductionEnv(env: Record<string, string | undefined>) {
  for (const key of requiredUrls) {
    try {
      const url = new URL(env[key]?.trim() ?? "");
      const hostname = url.hostname.replace(/\.$/, "");
      const local = ["localhost", "0.0.0.0", "[::]", "[::1]"].includes(hostname)
        || hostname.startsWith("127.") || hostname.endsWith(".localhost");
      if (url.protocol !== "https:" || local || url.username || url.password || url.search || url.hash) throw new Error("Invalid endpoint");
    } catch {
      // Report the variable name, never its value or embedded credentials.
      throw new Error(`${key} must be set to a public HTTPS endpoint for production builds.`);
    }
  }
}
