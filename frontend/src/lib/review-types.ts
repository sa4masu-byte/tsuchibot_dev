export type Candidate = {
  product_id: string;
  source_product_id: string;
  name: string;
  source_type: string;
  image_url: string | null;
  sourcing_cost_jpy: number | null;
  estimated_sale_price_jpy: number | null;
  expected_profit_jpy: number | null;
  sales_prospect_score: number;
  confidence_score: number;
  overall_sourcing_score: number | null;
  recommendation_tier: string;
  created_at: string;
};

export type DashboardData = {
  latest_run: {
    id: string;
    status: string;
    current_stage: string;
    created_at: string;
  } | null;
  tier_counts: Record<string, number>;
  total_candidate_cost_jpy: number;
  total_expected_profit_jpy: number;
  average_sales_prospect: number | null;
  open_error_count: number;
  best_candidate: Candidate | null;
};

export type Comparable = {
  id: string;
  title: string;
  canonical_url: string;
  image_url: string | null;
  status: string;
  displayed_price_jpy: number;
  condition: string | null;
  shipping_method: string | null;
  estimated_shipping_jpy: number | null;
  sold_at: string | null;
  listed_at: string | null;
  total_similarity: number;
  current_decision: string;
  decision_reason: string | null;
  included_in_price: boolean;
};

export type ProductDetail = {
  product: Record<string, unknown> & { id: string; display_name?: string };
  source: {
    source_product_id: string;
    source_type: string;
    source_url: string;
    source_title: string | null;
    source_category: string | null;
    current_price_jpy: number | null;
    image_url: string | null;
  };
  recommendation: (Record<string, unknown> & {
    recommendation_tier: string;
    expected_profit_jpy: number | null;
    estimated_sale_price_jpy: number | null;
    estimated_shipping_jpy: number | null;
    sales_prospect_score: number;
    confidence_score: number;
    overall_sourcing_score: number | null;
  }) | null;
  reasons: Array<{
    code: string;
    label: string;
    component_type: string;
    value: unknown;
    score_delta: number | null;
    source: string;
  }>;
  research: {
    included_count: number;
    median_price_jpy: number | null;
    sufficient_evidence: boolean;
    evidence_period_start: string;
    evidence_period_end: string;
  } | null;
  comparables: Comparable[];
  corrections: Array<{
    id: string;
    field_name: string;
    corrected_value: unknown;
    reason: string | null;
    created_at: string;
  }>;
};

export function yen(value: number | null | undefined): string {
  return value == null ? "未確認" : `${value.toLocaleString("ja-JP")}円`;
}

export function tierLabel(tier: string): string {
  return {
    strongly_recommended: "強く推奨",
    recommended: "推奨",
    candidate: "候補",
    reject: "見送り",
  }[tier] ?? tier;
}
