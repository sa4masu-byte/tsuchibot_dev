"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import {
  InventorySummary,
  inventoryProgress,
  inventoryStatusLabel,
} from "@/lib/inventory-types";
import { yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

export default function InventoryPage() {
  const session = useRequiredSession();
  const [items, setItems] = useState<InventorySummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (session !== "authenticated") return;
    void apiFetch<InventorySummary[]>("/inventory")
      .then(setItems)
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "在庫を取得できませんでした"),
      );
  }, [session]);

  if (session === "checking") {
    return <div className="center-shell"><p>在庫を読み込んでいます…</p></div>;
  }
  if (session === "unavailable") {
    return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  }

  const totalCost = items.reduce((sum, item) => sum + item.actual_charged_amount_jpy, 0);
  const totalProfit = items.reduce((sum, item) => sum + item.realised_profit_jpy, 0);
  const remaining = items.reduce((sum, item) => sum + item.remaining_quantity, 0);

  return (
    <div className="page-shell">
      <header className="page-heading inventory-heading">
        <div><p className="eyebrow">Inventory & learning</p><h1>仕入れ後の記録</h1></div>
        <p>購入、出品、売却、失敗を順番に残し、予測と実績の差を学習材料にします。外部サイトへの購入・出品操作は行いません。</p>
      </header>
      {error && <p className="error-message" role="alert">{error}</p>}
      <section className="metric-grid inventory-metrics" aria-label="在庫集計">
        <article className="metric-card"><span>保有残数</span><strong>{remaining}</strong><small>{items.length}仕入れ記録</small></article>
        <article className="metric-card"><span>実仕入れ額</span><strong>{yen(totalCost)}</strong><small>クーポン反映後</small></article>
        <article className="metric-card"><span>実利益</span><strong>{yen(totalProfit)}</strong><small>売却済み分</small></article>
      </section>
      {items.length === 0 && !error ? (
        <div className="empty-state inventory-empty"><p>購入記録はまだありません。</p><Link className="text-link" href="/products">候補から購入判断を記録する</Link></div>
      ) : (
        <section className="inventory-list" aria-label="在庫一覧">
          {items.map((item) => (
            <Link className="inventory-card" href={`/inventory/${item.id}`} key={item.id}>
              <div className="inventory-card-main">
                <span className={`status-badge ${item.status}`}>{inventoryStatusLabel[item.status] ?? item.status}</span>
                <p className="source-label">{item.source_type ?? "source unknown"} · {item.purchase_date}</p>
                <h2>{item.name}</h2>
                <div className="inventory-progress" aria-label={`処理済み ${inventoryProgress(item)}%`}><span style={{ width: `${inventoryProgress(item)}%` }} /></div>
                <small>購入 {item.purchased_quantity} · 売却 {item.sold_quantity} · 失敗 {item.failed_quantity} · 残り {item.remaining_quantity}</small>
              </div>
              <dl>
                <div><dt>実仕入れ</dt><dd>{yen(item.actual_charged_amount_jpy)}</dd></div>
                <div><dt>実利益</dt><dd className={item.realised_profit_jpy < 0 ? "negative-value" : ""}>{yen(item.realised_profit_jpy)}</dd></div>
              </dl>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
