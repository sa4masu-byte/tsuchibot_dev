"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { ProductDetail, tierLabel, yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

const correctionFields = [
  ["display_name", "商品名"],
  ["category", "カテゴリ"],
  ["manufacturer", "メーカー"],
  ["brand", "ブランド"],
  ["model_number", "型番"],
  ["condition", "状態"],
  ["estimated_sale_price_jpy", "適正販売価格（円）"],
  ["estimated_shipping_jpy", "送料見積り（円）"],
] as const;

export default function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const session = useRequiredSession();
  const [data, setData] = useState<ProductDetail | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [field, setField] = useState("display_name");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    return apiFetch<ProductDetail>(`/products/${productId}`)
      .then((detail) => { setData(detail); setError(""); })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "商品を取得できませんでした"));
  }, [productId]);

  useEffect(() => {
    if (session === "authenticated") void load();
  }, [session, load]);

  async function submitCorrection(event: FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    setPending(true);
    setMessage("");
    try {
      const isMoney = field.endsWith("_jpy");
      const updated = await apiFetch<ProductDetail>(`/products/${productId}/corrections`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          field_name: field,
          corrected_value: isMoney ? Number(value) : value.trim(),
          reason: reason.trim() || null,
        }),
      });
      setData(updated);
      setValue("");
      setReason("");
      setMessage("補正を保存し、判定を再計算しました。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "補正を保存できませんでした");
    } finally {
      setPending(false);
    }
  }

  async function decideComparable(comparableId: string, exclude: boolean) {
    const action = exclude ? "exclude" : "restore";
    setPending(true);
    setMessage("");
    try {
      const updated = await apiFetch<ProductDetail>(
        `/products/${productId}/comparables/${comparableId}/${action}`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ reason: exclude ? "レビュー画面から除外" : "レビュー画面から復元" }),
        },
      );
      setData(updated);
      setMessage(exclude ? "比較対象を除外し、再計算しました。" : "比較対象を復元し、再計算しました。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "比較対象を更新できませんでした");
    } finally {
      setPending(false);
    }
  }

  if (session === "checking" || (!data && !error)) return <div className="center-shell"><p>商品を読み込んでいます…</p></div>;
  if (session === "unavailable") return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  if (error || !data) return <div className="center-shell"><div><p className="error-message" role="alert">{error}</p><Link className="text-link" href="/products">候補一覧へ戻る</Link></div></div>;

  const recommendation = data.recommendation;
  const name = String(data.product.display_name ?? data.source.source_title ?? "名称未確認");

  return (
    <div className="page-shell detail-shell">
      <Link className="back-link" href="/products">← 候補一覧</Link>
      <header className="detail-header">
        <div><p className="source-label">{data.source.source_type} · {data.source.source_category ?? "カテゴリ未確認"}</p><h1>{name}</h1><a className="text-link" href={data.source.source_url} target="_blank" rel="noreferrer">元の商品ページを確認 ↗</a></div>
        {recommendation && <div className="verdict-card"><span className={`tier-badge ${recommendation.recommendation_tier}`}>{tierLabel(recommendation.recommendation_tier)}</span><strong>{recommendation.overall_sourcing_score ?? "—"}</strong><small>総合スコア</small></div>}
      </header>

      {message && <p className="status-message" role="status">{message}</p>}

      <section className="detail-grid" aria-label="価格とスコア">
        <article className="metric-card"><span>現在価格</span><strong>{yen(data.source.current_price_jpy)}</strong><small>取得元の表示価格</small></article>
        <article className="metric-card"><span>適正販売価格</span><strong>{yen(recommendation?.estimated_sale_price_jpy)}</strong><small>比較対象の中央値</small></article>
        <article className="metric-card"><span>予想利益</span><strong>{yen(recommendation?.expected_profit_jpy)}</strong><small>手数料・送料控除後</small></article>
        <article className="metric-card"><span>売れ行き / 信頼度</span><strong>{recommendation ? `${recommendation.sales_prospect_score} / ${recommendation.confidence_score}` : "—"}</strong><small>各100点</small></article>
      </section>

      <div className="review-columns">
        <div>
          <section className="review-section">
            <div className="section-heading"><div><p className="eyebrow">Evidence</p><h2>判定の根拠</h2></div><span>{data.reasons.length}件</span></div>
            <div className="reason-list">{data.reasons.map((item) => <article className={`reason-item ${item.component_type}`} key={`${item.code}-${item.label}`}><span>{item.component_type}</span><strong>{item.label}</strong><small>{item.source}</small></article>)}</div>
          </section>

          <section className="review-section">
            <div className="section-heading"><div><p className="eyebrow">Comparables</p><h2>相場の比較対象</h2></div><span>{data.research ? `${data.research.included_count}件採用` : "調査なし"}</span></div>
            {data.comparables.length === 0 ? <p className="empty-state">比較対象はまだありません。</p> : <div className="comparable-list">{data.comparables.map((item) => (
              <article className={`comparable-card ${item.current_decision === "exclude" ? "excluded" : ""}`} key={item.id}>
                <div><span className="source-label">{item.status === "sold" ? "売却済み" : "出品中"} · 類似度 {Math.round(item.total_similarity * 100)}</span><h3>{item.title}</h3><a href={item.canonical_url} target="_blank" rel="noreferrer">メルカリで確認 ↗</a></div>
                <div className="comparable-price"><strong>{yen(item.displayed_price_jpy)}</strong><small>{item.condition ?? "状態未確認"}</small></div>
                <button className="ghost-button" type="button" disabled={pending} onClick={() => decideComparable(item.id, item.current_decision !== "exclude")}>{item.current_decision === "exclude" ? "比較へ戻す" : "比較から除外"}</button>
              </article>
            ))}</div>}
          </section>
        </div>

        <aside className="correction-panel">
          <p className="eyebrow">Manual correction</p><h2>確認結果を反映</h2><p>型番や価格を手で確認した場合、補正後に判定を再計算します。</p>
          <form onSubmit={submitCorrection}>
            <label><span>補正項目</span><select value={field} onChange={(event) => setField(event.target.value)}>{correctionFields.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label><span>確認した値</span><input type={field.endsWith("_jpy") ? "number" : "text"} min="0" value={value} onChange={(event) => setValue(event.target.value)} required /></label>
            <label><span>根拠メモ（任意）</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} /></label>
            <button className="primary-button" disabled={pending}>{pending ? "再計算中…" : "保存して再計算"}</button>
          </form>
          {data.corrections.length > 0 && <details><summary>有効な補正 {data.corrections.length}件</summary><ul>{data.corrections.map((item) => <li key={item.id}><strong>{item.field_name}</strong><span>{String(item.corrected_value)}</span></li>)}</ul></details>}
        </aside>
      </div>
    </div>
  );
}
