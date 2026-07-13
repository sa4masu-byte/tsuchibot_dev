import { describe, expect, it } from "vitest";

import { tierLabel, yen } from "./review-types";

describe("review display helpers", () => {
  it("formats known yen without inventing unknown values", () => {
    expect(yen(1234)).toBe("1,234円");
    expect(yen(null)).toBe("未確認");
  });

  it("translates recommendation tiers", () => {
    expect(tierLabel("strongly_recommended")).toBe("強く推奨");
    expect(tierLabel("future_tier")).toBe("future_tier");
  });
});
