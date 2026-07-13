"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { DashboardData, tierLabel, yen } from "@/lib/review-types";
import { useRequiredSession } from "@/lib/use-session";

type DispatchResponse = {
  run: { id: string; status: string };
  dispatch_accepted: boolean;
  external_run_id: string | null;
};

export default function Dashboard() {
  const session = useRequiredSession();
  const [message, setMessage] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    if (session !== "authenticated") return;
    apiFetch<DashboardData>("/dashboard")
      .then(setData)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "概要を取得できませんでした");
      });
  }, [session]);

  async function startRun() {
    setPending(true);
    setMessage("");
    try {
      const result = await apiFetch<DispatchResponse>("/runs/dispatch", {
        method: "POST",
        body: JSON.stringify({ mode: "incremental" }),
      });
      if (result.external_run_id?.startsWith("local-")) {
        setMessage(
          `ローカル受付のみ完了しました（${result.run.id.slice(0, 8)}）。` +
          "DB・GitHub設定後に実探索が開始されます。",
        );
      } else {
        setMessage(`探索を受け付けました（${result.run.id.slice(0, 8)}）`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "探索を開始できませんでした");
    } finally {
      setPending(false);
    }
  }

  if (session === "checking") {
    return <div className="center-shell"><p role="status">Sessionを確認しています…</p></div>;
  }
  if (session === "unavailable") {
    return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  }

  return (
    <div className="page-shell">
      <section className="hero">
        <p className="eyebrow">Fair price review</p>
        <h1>価格の根拠を、<br />ひとつずつ確かめる。</h1>
        <p className="lead">ジモティーの適正価格設定と、小売事業のEC仕入れ判断を同じ根拠からレビューします。</p>
        <button className="primary-button" onClick={startRun} disabled={pending}>
          {pending ? "開始しています…" : "今日の探索を始める"}
        </button>
        {message && <p className="status-message" role="status">{message}</p>}
      </section>

      <section className="metric-grid" aria-label="今日の概要">
        <article className="metric-card"><span>要レビュー候補</span><strong>{data ? (data.tier_counts.strongly_recommended ?? 0) + (data.tier_counts.recommended ?? 0) + (data.tier_counts.candidate ?? 0) : "—"}</strong><small>根拠を確認できる候補</small></article>
        <article className="metric-card"><span>候補の予想利益</span><strong>{data ? yen(data.total_expected_profit_jpy) : "—"}</strong><small>手数料・送料控除後</small></article>
        <article className="metric-card"><span>未解決エラー</span><strong>{data?.open_error_count ?? "—"}</strong><small>探索を止めず個別に記録</small></article>
      </section>

      <section className="panel">
        <div><p className="eyebrow">Top candidate</p><h2>{data?.best_candidate?.name ?? "候補を探索してください"}</h2></div>
        <p>{data?.best_candidate ? `${tierLabel(data.best_candidate.recommendation_tier)} · 見込み ${data.best_candidate.sales_prospect_score} · 信頼度 ${data.best_candidate.confidence_score}` : "探索後、最も確認価値の高い候補をここに表示します。"}</p>
        <Link className="text-link" href={data?.best_candidate ? `/products/${data.best_candidate.product_id}` : "/products"}>レビューする →</Link>
      </section>
    </div>
  );
}
