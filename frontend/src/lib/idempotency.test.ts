import { afterEach, describe, expect, it, vi } from "vitest";

import { createIdempotencyKey } from "./idempotency";

afterEach(() => vi.unstubAllGlobals());

describe("createIdempotencyKey", () => {
  it("uses getRandomValues when randomUUID is unavailable", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.fill(0xab);
        return bytes;
      },
    });

    expect(createIdempotencyKey()).toBe("abababab-abab-4bab-abab-abababababab");
  });

  it("still creates distinct keys without the Crypto API", () => {
    vi.stubGlobal("crypto", undefined);

    const first = createIdempotencyKey();
    const second = createIdempotencyKey();
    expect(first).toMatch(/^local-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/);
    expect(second).not.toBe(first);
  });
});
