export type ECSession = {
  id: string;
  run_id: string;
  trigger_reason: string;
  useful_jimoty_candidates: number;
  keyword_count: number;
  policy_version: string;
  status: string;
  observed_at: string;
  offer_count: number;
  eligible_count: number;
  confirmation_required_count: number;
  rejected_count: number;
};

export type ECOffer = {
  id: string;
  source: string;
  source_item_id: string;
  canonical_url: string;
  title: string;
  displayed_price_jpy: number;
  sourcing_shipping_jpy: number;
  definite_coupon_jpy: number;
  points_reference_jpy: number;
  delivery_days: number | null;
  product_rating: number | null;
  review_count: number | null;
  seller_rating: number | null;
  selected_variant: string | null;
  eligibility: string;
  sourcing_cost_jpy: number;
  reason_codes: string[];
};

export type ECSessionDetail = {
  session: ECSession;
  attempts: Array<{
    source: string;
    query_order: number;
    keyword: string;
    strategy: string;
    status: string;
    collected_count: number;
  }>;
  offers: ECOffer[];
};

export function eligibilityLabel(value: string): string {
  return {
    eligible: "評価へ進める",
    confirmation_required: "要確認",
    rejected: "対象外",
  }[value] ?? value;
}
