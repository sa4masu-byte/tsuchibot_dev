import { afterEach, describe, expect, it } from "vitest";

import {
  backendUrl,
  downstreamHeaders,
  isAllowedMutation,
  upstreamHeaders,
} from "./api-proxy";

afterEach(() => {
  delete process.env.TSUCHIBOT_BACKEND_URL;
});

describe("LAN API proxy boundary", () => {
  it("accepts same-origin mutations and rejects cross-origin or unverifiable mutations", () => {
    const url = "http://192.168.1.25:3000/api/v1/auth/login";
    expect(isAllowedMutation(new Request(url, {
      method: "POST",
      headers: { Origin: "http://192.168.1.25:3000" },
    }))).toBe(true);
    expect(isAllowedMutation(new Request(url, {
      method: "POST",
      headers: { "Sec-Fetch-Site": "same-origin" },
    }))).toBe(true);
    expect(isAllowedMutation(new Request(url, {
      method: "POST",
      headers: { Origin: "http://evil.test" },
    }))).toBe(false);
    expect(isAllowedMutation(new Request(url, {
      method: "POST",
      headers: { Origin: "http://192.168.1.25:3000", "Sec-Fetch-Site": "cross-site" },
    }))).toBe(false);
    expect(isAllowedMutation(new Request(url, { method: "POST" }))).toBe(false);
  });

  it("forwards only intended request headers and preserves cookie response", () => {
    const request = new Request("http://192.168.1.25:3000/api/v1/runs", {
      headers: {
        Cookie: "tsuchibot_session=signed",
        "Idempotency-Key": "example-key",
        Authorization: "Bearer should-not-forward",
        Origin: "http://192.168.1.25:3000",
      },
    });
    const headers = upstreamHeaders(request);
    expect(headers.get("cookie")).toBe("tsuchibot_session=signed");
    expect(headers.get("idempotency-key")).toBe("example-key");
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("origin")).toBe(false);

    const downstream = downstreamHeaders(new Response(null, {
      headers: { "Set-Cookie": "tsuchibot_session=signed; Path=/; HttpOnly" },
    }));
    expect(downstream.get("set-cookie")).toContain("HttpOnly");
    expect(downstream.get("cache-control")).toBe("no-store");
  });

  it("pins the target to the configured backend and rejects path traversal", () => {
    const request = new Request("http://192.168.1.25:3000/api/v1/runs?limit=25");
    expect(backendUrl(request, ["runs"]).href).toBe("http://127.0.0.1:8000/api/v1/runs?limit=25");
    expect(() => backendUrl(request, ["..", "admin"])).toThrow("Invalid API path");
    expect(() => backendUrl(request, ["runs/evil"])).toThrow("Invalid API path");
    process.env.TSUCHIBOT_BACKEND_URL = "file:///etc/passwd";
    expect(() => backendUrl(request, ["runs"])).toThrow("Invalid backend URL protocol");
  });
});
