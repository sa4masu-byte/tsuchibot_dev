export type InventorySummary = {
  id: string;
  canonical_product_id: string;
  name: string;
  category: string | null;
  source_type: string | null;
  image_url: string | null;
  status: string;
  purchased_quantity: number;
  sold_quantity: number;
  failed_quantity: number;
  remaining_quantity: number;
  actual_charged_amount_jpy: number;
  realised_profit_jpy: number;
  purchase_date: string;
  created_at: string;
  updated_at: string;
};

type InventoryEvent = Record<string, unknown> & {
  id: string;
  created_at: string;
};

export type InventoryDetail = InventorySummary & {
  product: {
    id: string;
    name: string;
    category: string | null;
    brand: string | null;
    model_number: string | null;
    image_url: string | null;
  };
  source: { type: string | null; url: string | null };
  prediction: {
    estimated_sale_price_jpy: number | null;
    sourcing_cost_jpy: number | null;
    expected_profit_jpy: number | null;
    recommendation_tier: string;
    confidence_score: number;
  };
  actual: {
    purchase_cost_jpy: number;
    sale_revenue_jpy: number;
    selling_fees_jpy: number;
    sale_shipping_jpy: number;
    realised_profit_jpy: number;
  };
  comparison: {
    predicted_profit_for_sold_jpy: number | null;
    actual_profit_for_sold_jpy: number;
    profit_difference_jpy: number | null;
  };
  purchase_events: InventoryEvent[];
  listing_events: InventoryEvent[];
  sale_events: InventoryEvent[];
  negative_outcomes: InventoryEvent[];
  learning_events: Array<InventoryEvent & { event_type: string }>;
};

export type Hypothesis = {
  id: string;
  statement: string;
  state: string;
  confidence: number | string;
  pattern_name: string | null;
  supporting_count?: number;
  contradictory_count?: number;
};

export const inventoryStatusLabel: Record<string, string> = {
  purchased: "購入済み",
  listed: "出品中",
  partially_sold: "一部売却",
  sold: "売却完了",
  returned: "返品",
  cancelled: "キャンセル",
  unsold_90_days: "90日未売却",
  damaged: "破損",
  lost: "紛失",
  other_failure: "その他失敗",
};

export function inventoryProgress(item: InventorySummary): number {
  if (item.purchased_quantity === 0) return 0;
  return Math.round(
    ((item.sold_quantity + item.failed_quantity) / item.purchased_quantity) * 100,
  );
}
