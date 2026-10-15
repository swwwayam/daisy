import test from "node:test";
import assert from "node:assert/strict";
import { validateProductionEnv } from "./production-env.ts";

const valid = {
  VITE_CONVEX_URL: "https://test.convex.cloud",
  VITE_CONVEX_SITE_URL: "https://test.convex.site",
  VITE_DAISY_API_URL: "https://api.daisy.example/v1",
};

test("accepts public HTTPS endpoints and API path prefixes", () => {
  assert.doesNotThrow(() => validateProductionEnv(valid));
});

test("rejects loopback aliases and unspecified bind addresses", () => {
  for (const host of ["127.0.0.2", "127.1", "2130706433", "0x7f000001", "localhost.", "preview.localhost", "0.0.0.0", "[::]", "[::1]"]) {
    assert.throws(() => validateProductionEnv({ ...valid, VITE_DAISY_API_URL: `https://${host}` }), /VITE_DAISY_API_URL/);
  }
});

test("requires every production endpoint", () => {
  for (const key of Object.keys(valid)) {
    assert.throws(() => validateProductionEnv({ ...valid, [key]: undefined }), new RegExp(key));
  }
});

test("rejects malformed endpoints without exposing credential values", () => {
  for (const value of ["http://api.daisy.example", "not-a-url", "https://api.daisy.example?token=private", "https://api.daisy.example#route", "https://user:private-password@api.daisy.example"]) {
    assert.throws(() => validateProductionEnv({ ...valid, VITE_DAISY_API_URL: value }), error => {
      assert.match(error.message, /VITE_DAISY_API_URL/);
      assert.doesNotMatch(error.message, /private/);
      return true;
    });
  }
});
