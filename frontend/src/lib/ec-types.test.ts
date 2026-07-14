import { describe, expect, it } from "vitest";

import { eligibilityLabel } from "./ec-types";

describe("EC review labels", () => {
  it("shows policy outcomes without calling them recommendations", () => {
    expect(eligibilityLabel("eligible")).toBe("評価へ進める");
    expect(eligibilityLabel("confirmation_required")).toBe("要確認");
    expect(eligibilityLabel("rejected")).toBe("対象外");
  });
});
