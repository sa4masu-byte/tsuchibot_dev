"use client";

import Link from "next/link";
import { useState } from "react";

import { apiFetch } from "@/lib/api";
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
        <p className="eyebrow">今日の仕入れ判断</p>
        <h1>利益の可能性を、<br />根拠から見つける。</h1>
        <p className="lead">2つのジモティー拠点から探索し、候補が足りなければECへ広げます。</p>
        <button className="primary-button" onClick={startRun} disabled={pending}>
          {pending ? "開始しています…" : "今日の探索を始める"}
        </button>
        {message && <p className="status-message" role="status">{message}</p>}
      </section>

      <section className="metric-grid" aria-label="今日の概要">
        <article className="metric-card"><span>強く推奨</span><strong>—</strong><small>探索後に表示</small></article>
        <article className="metric-card"><span>予想利益</span><strong>—</strong><small>保守的な見積り</small></article>
        <article className="metric-card"><span>調査エラー</span><strong>—</strong><small>部分障害を分離</small></article>
      </section>

      <section className="panel">
        <div><p className="eyebrow">Foundation</p><h2>まだ候補はありません</h2></div>
        <p>探索基盤が準備できました。カタログ収集は次の実装段階で追加されます。</p>
        <Link className="text-link" href="/runs">実行履歴を見る →</Link>
      </section>
    </div>
  );
}
