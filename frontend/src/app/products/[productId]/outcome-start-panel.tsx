"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { apiFetch } from "@/lib/api";

type Props = {
  productId: string;
  sourcePriceJpy: number | null;
};

function localDateTime(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

export function OutcomeStartPanel({ productId, sourcePriceJpy }: Props) {
  const [decision, setDecision] = useState<"purchased" | "skipped">("purchased");
  const [amount, setAmount] = useState(sourcePriceJpy ?? 0);
  const [shipping, setShipping] = useState(0);
  const [coupon, setCoupon] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [positionId, setPositionId] = useState<string | null>(null);
  const actualCharge = Math.max(0, amount + shipping - coupon);

  async function submitPurchase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const purchased = decision === "purchased";
    setPending(true);
    setMessage("");
    try {
      const response = await apiFetch<{ id?: string; purchased?: boolean }>(
        `/products/${productId}/purchase`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({
            purchased,
            purchased_at: new Date(String(form.get("purchased_at"))).toISOString(),
            quantity: purchased ? Number(form.get("quantity")) : null,
            product_amount_jpy: purchased ? amount : null,
            sourcing_shipping_jpy: purchased ? shipping : null,
            coupon_jpy: purchased ? coupon : null,
            point_reference_jpy: purchased ? Number(form.get("points")) : 0,
            actual_charged_amount_jpy: purchased ? actualCharge : null,
            note: String(form.get("note") || "") || null,
          }),
        },
      );
      setPositionId(response.id ?? null);
      setMessage(purchased ? "購入を記録しました。在庫画面で出品・売却を続けられます。" : "購入しなかった判断を学習履歴へ記録しました。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "購入判断を記録できませんでした");
    } finally {
      setPending(false);
    }
  }

  async function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setMessage("");
    try {
      await Promise.all([
        apiFetch(`/products/${productId}/feedback/preference`, {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ signal: form.get("preference"), note: null }),
        }),
        apiFetch(`/products/${productId}/feedback/research-value`, {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ signal: form.get("research_value"), note: null }),
        }),
      ]);
      setMessage("感性と調査価値のFeedbackを履歴へ追加しました。");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Feedbackを記録できませんでした");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="decision-record-panel">
      <div className="section-heading"><div><p className="eyebrow">Decision & feedback</p><h2>購入判断を記録</h2></div><span>外部サイトの操作は行いません</span></div>
      {message && <p className="status-message" role="status">{message} {positionId && <Link className="text-link" href={`/inventory/${positionId}`}>在庫記録を開く →</Link>}</p>}
      <div className="decision-forms">
        <form onSubmit={submitPurchase}>
          <label><span>判断</span><select value={decision} onChange={(event) => setDecision(event.target.value as "purchased" | "skipped")}><option value="purchased">購入した</option><option value="skipped">購入しなかった</option></select></label>
          <label><span>判断・購入日時</span><input name="purchased_at" type="datetime-local" defaultValue={localDateTime()} required /></label>
          {decision === "purchased" && <>
            <label><span>数量（1〜4）</span><input name="quantity" type="number" min="1" max="4" defaultValue="1" required /></label>
            <label><span>商品金額（円）</span><input type="number" min="0" value={amount} onChange={(event) => setAmount(Number(event.target.value))} required /></label>
            <label><span>仕入れ送料（円）</span><input type="number" min="0" value={shipping} onChange={(event) => setShipping(Number(event.target.value))} required /></label>
            <label><span>確定クーポン（円）</span><input type="number" min="0" max={amount + shipping} value={coupon} onChange={(event) => setCoupon(Number(event.target.value))} required /></label>
            <label><span>ポイント参考値（円）</span><input name="points" type="number" min="0" defaultValue="0" /></label>
            <div className="charged-preview"><span>実請求額</span><strong>{actualCharge.toLocaleString("ja-JP")}円</strong><small>ポイントは利益計算から除外</small></div>
          </>}
          <label className="wide-field"><span>メモ（任意）</span><textarea name="note" rows={2} /></label>
          <button className="primary-button" disabled={pending}>{pending ? "記録中…" : "判断を記録"}</button>
        </form>
        <form onSubmit={submitFeedback} className="feedback-form">
          <h3>感性Feedback</h3>
          <label><span>自分にとっての魅力</span><select name="preference"><option value="want">欲しい</option><option value="slightly_interested">少し気になる</option><option value="do_not_want">欲しくない</option><option value="cannot_judge">判断できない</option></select></label>
          <label><span>調査する価値</span><select name="research_value"><option value="worth_researching">調査する価値あり</option><option value="not_worth_researching">調査する価値なし</option></select></label>
          <button className="secondary-button" disabled={pending}>Feedbackを記録</button>
        </form>
      </div>
    </section>
  );
}
