"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { ECSessionDetail, eligibilityLabel } from "@/lib/ec-types";
import { yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

export default function ECSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const session = useRequiredSession();
  const [data, setData] = useState<ECSessionDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (session !== "authenticated") return;
    apiFetch<ECSessionDetail>(`/ec/sessions/${sessionId}`)
      .then(setData)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "EC探索を取得できませんでした"));
  }, [session, sessionId]);

  if (session === "checking" || (!data && !error)) return <div className="center-shell"><p>EC探索を読み込んでいます…</p></div>;
  if (session === "unavailable") return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  if (!data) return <div className="center-shell"><p className="error-message">{error}</p></div>;

  return (
    <div className="page-shell">
      <Link className="back-link" href="/ec">← EC探索履歴</Link>
      <header className="detail-header"><div><p className="eyebrow">EC evidence</p><h1>代替探索の結果</h1><p className="lead">{data.session.trigger_reason} · {new Date(data.session.observed_at).toLocaleString("ja-JP")}</p></div><div className="verdict-card"><strong>{data.offers.length}</strong><small>取得オファー</small></div></header>
      <section className="review-section"><div className="section-heading"><div><p className="eyebrow">Attempts</p><h2>検索順序</h2></div><span>{data.attempts.length}試行</span></div><div className="attempt-grid">{data.attempts.map((attempt) => <article key={`${attempt.source}-${attempt.query_order}`}><span>{attempt.source}</span><strong>{attempt.keyword}</strong><small>{attempt.strategy} · {attempt.status} · {attempt.collected_count}件</small></article>)}</div></section>
      <section className="review-section"><div className="section-heading"><div><p className="eyebrow">Offers</p><h2>取得商品とPolicy判定</h2></div></div><div className="ec-offer-list">{data.offers.map((offer) => <article className={`ec-offer-card ${offer.eligibility}`} key={offer.id}><div><span className="source-label">{offer.source}</span><h3>{offer.title}</h3><a href={offer.canonical_url} target="_blank" rel="noreferrer">商品ページを確認 ↗</a></div><dl><div><dt>表示価格</dt><dd>{yen(offer.displayed_price_jpy)}</dd></div><div><dt>仕入原価</dt><dd>{yen(offer.sourcing_cost_jpy)}</dd></div><div><dt>配送</dt><dd>{offer.delivery_days == null ? "未確認" : `${offer.delivery_days}日`}</dd></div></dl><div><span className={`tier-badge ${offer.eligibility}`}>{eligibilityLabel(offer.eligibility)}</span><small>{offer.reason_codes.join(" · ")}</small></div></article>)}</div></section>
    </div>
  );
}
