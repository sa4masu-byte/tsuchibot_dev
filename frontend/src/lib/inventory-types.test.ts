import { describe, expect, it } from "vitest";

import { InventorySummary, inventoryProgress, inventoryStatusLabel } from "./inventory-types";

const position: InventorySummary = {
  id: "position",
  canonical_product_id: "product",
  name: "商品",
  category: null,
  source_type: "jimoty",
  image_url: null,
  status: "partially_sold",
  purchased_quantity: 4,
  sold_quantity: 2,
  failed_quantity: 1,
  remaining_quantity: 1,
  actual_charged_amount_jpy: 1000,
  realised_profit_jpy: 500,
  purchase_date: "2026-08-03",
  created_at: "2026-08-03T00:00:00Z",
  updated_at: "2026-08-03T00:00:00Z",
};

describe("inventory presentation", () => {
  it("calculates resolved inventory progress", () => {
    expect(inventoryProgress(position)).toBe(75);
  });

  it("provides Japanese status labels", () => {
    expect(inventoryStatusLabel.partially_sold).toBe("一部売却");
    expect(inventoryStatusLabel.unsold_90_days).toBe("90日未売却");
  });
});
