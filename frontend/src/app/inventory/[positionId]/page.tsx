"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { apiFetch } from "@/lib/api";
import {
  Hypothesis,
  InventoryDetail,
  inventoryStatusLabel,
} from "@/lib/inventory-types";
import { yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

function localDateTime(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function iso(value: FormDataEntryValue | null): string {
  return new Date(String(value)).toISOString();
}

export default function InventoryDetailPage() {
  const { positionId } = useParams<{ positionId: string }>();
  const session = useRequiredSession();
  const [data, setData] = useState<InventoryDetail | null>(null);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  const load = useCallback(() => {
    return Promise.all([
        apiFetch<InventoryDetail>(`/inventory/${positionId}`),
        apiFetch<Hypothesis[]>("/hypotheses"),
      ])
      .then(([detail, hypothesisList]) => {
        setData(detail);
        setHypotheses(hypothesisList);
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "在庫記録を取得できませんでした");
      });
  }, [positionId]);

  useEffect(() => {
    if (session === "authenticated") void load();
  }, [session, load]);

  async function submitEvent(
    event: FormEvent<HTMLFormElement>,
    kind: "listings" | "sales" | "negative-outcomes",
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const body =
      kind === "listings"
        ? {
            listed_at: iso(values.get("occurred_at")),
            marketplace: values.get("marketplace"),
            listing_price_jpy: Number(values.get("amount")),
            listing_url: String(values.get("url") || "") || null,
            quantity: Number(values.get("quantity")),
          }
        : kind === "sales"
          ? {
              sold_at: iso(values.get("occurred_at")),
              sold_price_jpy: Number(values.get("amount")),
              actual_fee_jpy: Number(values.get("fee")),
              actual_shipping_jpy: Number(values.get("shipping")),
              quantity: Number(values.get("quantity")),
            }
          : {
              occurred_at: iso(values.get("occurred_at")),
              outcome_type: values.get("outcome_type"),
              quantity: Number(values.get("quantity")),
              note: String(values.get("note") || "") || null,
            };
    setPending(true);
    setMessage("");
    try {
      const updated = await apiFetch<InventoryDetail>(`/inventory/${positionId}/${kind}`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(body),
      });
      setData(updated);
      form.reset();
      setMessage(kind === "listings" ? "出品を記録しました。" : kind === "sales" ? "売却と実利益を記録しました。" : "失敗・返品を記録しました。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "記録できませんでした");
    } finally {
      setPending(false);
    }
  }

  async function submitEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const hypothesisId = String(values.get("hypothesis_id"));
    setPending(true);
    setMessage("");
    try {
      await apiFetch(`/hypotheses/${hypothesisId}/evidence`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          evidence_type: "inventory_outcome_review",
          direction: values.get("direction"),
          strength: Number(values.get("strength")),
          source_reference_type: "inventory_position",
          source_reference_id: positionId,
          summary: values.get("summary"),
        }),
      });
      form.reset();
      await load();
      setMessage("仮説の証拠を履歴へ追加しました。スコア規則は自動変更していません。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "証拠を追加できませんでした");
    } finally {
      setPending(false);
    }
  }

  if (session === "checking" || (!data && !error)) {
    return <div className="center-shell"><p>在庫記録を読み込んでいます…</p></div>;
  }
  if (session === "unavailable") {
    return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  }
  if (error || !data) {
    return <div className="center-shell"><div><p className="error-message" role="alert">{error}</p><Link className="text-link" href="/inventory">在庫一覧へ戻る</Link></div></div>;
  }

  const defaultTime = localDateTime();
  const maxQuantity = Math.max(1, data.remaining_quantity);
  return (
    <div className="page-shell detail-shell inventory-detail">
      <Link className="back-link" href="/inventory">← 在庫一覧</Link>
      <header className="detail-header">
        <div><p className="source-label">{data.source.type ?? "source unknown"} · {data.purchase_date}</p><h1>{data.product.name}</h1>{data.source.url && <a className="text-link" href={data.source.url} target="_blank" rel="noreferrer">仕入れ元を確認 ↗</a>}</div>
        <div className="inventory-balance"><span className={`status-badge ${data.status}`}>{inventoryStatusLabel[data.status] ?? data.status}</span><strong>{data.remaining_quantity}</strong><small>残り / 購入 {data.purchased_quantity}</small></div>
      </header>
      {message && <p className="status-message" role="status">{message}</p>}

      <section className="comparison-panel" aria-labelledby="comparison-heading">
        <div className="section-heading"><div><p className="eyebrow">Prediction vs actual</p><h2 id="comparison-heading">予測と実績</h2></div><span>購入時点の予測は固定</span></div>
        <div className="comparison-grid">
          <article><span>予想利益（売却数分）</span><strong>{yen(data.comparison.predicted_profit_for_sold_jpy)}</strong></article>
          <article><span>実利益（売却数分）</span><strong>{yen(data.comparison.actual_profit_for_sold_jpy)}</strong></article>
          <article className={data.comparison.profit_difference_jpy != null && data.comparison.profit_difference_jpy < 0 ? "negative" : "positive"}><span>予実差</span><strong>{yen(data.comparison.profit_difference_jpy)}</strong></article>
        </div>
        <dl className="actual-breakdown">
          <div><dt>実仕入れ</dt><dd>{yen(data.actual.purchase_cost_jpy)}</dd></div>
          <div><dt>売上</dt><dd>{yen(data.actual.sale_revenue_jpy)}</dd></div>
          <div><dt>販売手数料</dt><dd>{yen(data.actual.selling_fees_jpy)}</dd></div>
          <div><dt>売却送料</dt><dd>{yen(data.actual.sale_shipping_jpy)}</dd></div>
        </dl>
      </section>

      <section className="outcome-steps" aria-label="仕入れ後の記録">
        <article className="outcome-form-card">
          <div className="step-number">1</div><h2>出品を記録</h2><p>価格は1点あたりで入力します。</p>
          <form onSubmit={(event) => submitEvent(event, "listings")}>
            <label><span>出品日時</span><input name="occurred_at" type="datetime-local" defaultValue={defaultTime} required /></label>
            <label><span>販売先</span><input name="marketplace" defaultValue="mercari" required /></label>
            <label><span>出品価格（円）</span><input name="amount" type="number" min="0" required /></label>
            <label><span>数量</span><input name="quantity" type="number" min="1" max={maxQuantity} defaultValue="1" required /></label>
            <label className="wide-field"><span>出品URL（任意）</span><input name="url" type="url" /></label>
            <button className="secondary-button" disabled={pending || data.remaining_quantity === 0}>出品を記録</button>
          </form>
        </article>
        <article className="outcome-form-card featured">
          <div className="step-number">2</div><h2>売却を記録</h2><p>売却額はこの取引の合計額です。実利益は自動計算します。</p>
          <form onSubmit={(event) => submitEvent(event, "sales")}>
            <label><span>売却日時</span><input name="occurred_at" type="datetime-local" defaultValue={defaultTime} required /></label>
            <label><span>売却額（円）</span><input name="amount" type="number" min="0" required /></label>
            <label><span>実手数料（円）</span><input name="fee" type="number" min="0" required /></label>
            <label><span>実送料（円）</span><input name="shipping" type="number" min="0" required /></label>
            <label><span>数量</span><input name="quantity" type="number" min="1" max={maxQuantity} defaultValue="1" required /></label>
            <button className="primary-button" disabled={pending || data.remaining_quantity === 0}>売却と実利益を記録</button>
          </form>
        </article>
        <article className="outcome-form-card">
          <div className="step-number">3</div><h2>失敗・返品を記録</h2><p>残数に影響する結果を、理由とともに残します。</p>
          <form onSubmit={(event) => submitEvent(event, "negative-outcomes")}>
            <label><span>発生日時</span><input name="occurred_at" type="datetime-local" defaultValue={defaultTime} required /></label>
            <label><span>結果</span><select name="outcome_type" defaultValue="unsold_90_days"><option value="returned">返品</option><option value="cancelled">キャンセル</option><option value="unsold_90_days">90日未売却</option><option value="damaged">破損</option><option value="lost">紛失</option><option value="other">その他</option></select></label>
            <label><span>数量</span><input name="quantity" type="number" min="1" max={maxQuantity} defaultValue="1" required /></label>
            <label className="wide-field"><span>メモ（任意）</span><textarea name="note" rows={2} /></label>
            <button className="secondary-button" disabled={pending || data.remaining_quantity === 0}>結果を記録</button>
          </form>
        </article>
      </section>

      <section className="learning-panel">
        <div><p className="eyebrow">Hypothesis evidence</p><h2>仮説へ証拠を追加</h2><p>実績を既存仮説の支持・反証として残します。これだけで推薦ルールや確信度は変更しません。</p></div>
        {hypotheses.length > 0 ? <form onSubmit={submitEvidence}>
          <label><span>仮説</span><select name="hypothesis_id">{hypotheses.map((item) => <option value={item.id} key={item.id}>{item.pattern_name ?? item.statement}</option>)}</select></label>
          <label><span>方向</span><select name="direction"><option value="supporting">支持</option><option value="contradictory">反証</option><option value="neutral">中立</option></select></label>
          <label><span>強さ</span><select name="strength"><option value="0.25">弱い</option><option value="0.5">中程度</option><option value="0.8">強い</option><option value="1">決定的</option></select></label>
          <label className="wide-field"><span>要約</span><textarea name="summary" rows={3} required /></label>
          <button className="secondary-button" disabled={pending}>証拠を追加</button>
        </form> : <p className="empty-state">仮説がありません。</p>}
      </section>

      <section className="history-panel">
        <div className="section-heading"><div><p className="eyebrow">Append-only history</p><h2>記録履歴</h2></div><span>{data.learning_events.length}件</span></div>
        {data.learning_events.length === 0 ? <p className="empty-state">履歴はまだありません。</p> : <ol>{data.learning_events.map((item) => <li key={item.id}><strong>{inventoryStatusLabel[item.event_type] ?? item.event_type}</strong><time>{new Date(item.created_at).toLocaleString("ja-JP")}</time></li>)}</ol>}
      </section>
    </div>
  );
}
