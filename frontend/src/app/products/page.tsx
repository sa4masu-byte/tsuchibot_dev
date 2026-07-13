"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { Candidate, tierLabel, yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

export default function ProductsPage() {
  const session = useRequiredSession();
  const [products, setProducts] = useState<Candidate[]>([]);
  const [tier, setTier] = useState("");
  const [sort, setSort] = useState("overall_sourcing_score");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session !== "authenticated") return;
    const params = new URLSearchParams({ sort });
    if (tier) params.set("tier", tier);
    if (query) params.set("search", query);
    apiFetch<Candidate[]>(`/products?${params}`)
      .then((items) => { setProducts(items); setError(""); })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "候補を取得できませんでした"))
      .finally(() => setLoading(false));
  }, [session, tier, sort, query]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setQuery(search.trim());
  }

  if (session === "checking") return <div className="center-shell"><p>Sessionを確認しています…</p></div>;
  if (session === "unavailable") return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;

  return (
    <div className="page-shell">
      <header className="page-heading">
        <div><p className="eyebrow">Review queue</p><h1>候補を確認する</h1></div>
        <p>価格、売れ行き、信頼度を並べて、根拠の確認が必要な商品からレビューします。</p>
      </header>
      <form className="filter-bar" onSubmit={submit}>
        <label><span>商品を検索</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="商品名・型番" /></label>
        <label><span>判定</span><select value={tier} onChange={(event) => setTier(event.target.value)}><option value="">すべて</option><option value="strongly_recommended">強く推奨</option><option value="recommended">推奨</option><option value="candidate">候補</option><option value="reject">見送り</option></select></label>
        <label><span>並び順</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="overall_sourcing_score">総合スコア</option><option value="expected_profit_jpy">予想利益</option><option value="confidence_score">信頼度</option><option value="sales_prospect_score">売れ行き</option><option value="created_at">更新日時</option></select></label>
        <button className="secondary-button" type="submit">検索</button>
      </form>
      {error && <p className="error-message" role="alert">{error}</p>}
      {loading ? <p className="empty-state">候補を読み込んでいます…</p> : products.length === 0 ? <p className="empty-state">条件に合う候補はありません。</p> : (
        <section className="candidate-grid" aria-label="候補一覧">
          {products.map((product) => (
            <Link className="candidate-card" href={`/products/${product.product_id}`} key={product.product_id}>
              <div className="candidate-top"><span className={`tier-badge ${product.recommendation_tier}`}>{tierLabel(product.recommendation_tier)}</span><span className="score-orb">{product.overall_sourcing_score ?? "—"}</span></div>
              <div><p className="source-label">{product.source_type}</p><h2>{product.name}</h2></div>
              <dl className="candidate-numbers"><div><dt>仕入</dt><dd>{yen(product.sourcing_cost_jpy)}</dd></div><div><dt>相場</dt><dd>{yen(product.estimated_sale_price_jpy)}</dd></div><div><dt>予想利益</dt><dd>{yen(product.expected_profit_jpy)}</dd></div></dl>
              <div className="score-row"><span>売れ行き <strong>{product.sales_prospect_score}</strong></span><span>信頼度 <strong>{product.confidence_score}</strong></span></div>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
