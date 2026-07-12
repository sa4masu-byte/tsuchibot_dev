"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useRequiredSession } from "@/lib/use-session";

type Run = { id: string; mode: string; status: string; current_stage: string; created_at: string };

export default function RunsPage() {
  const session = useRequiredSession();
  const [runs, setRuns] = useState<Run[]>([]);
  const [message, setMessage] = useState("読み込み中…");

  useEffect(() => {
    if (session !== "authenticated") return;
    apiFetch<Run[]>("/runs")
      .then((data) => { setRuns(data); setMessage(data.length ? "" : "実行履歴はまだありません。"); })
      .catch(() => setMessage("ログイン後に実行履歴を確認できます。"));
  }, [session]);

  if (session === "checking") {
    return <div className="center-shell"><p role="status">Sessionを確認しています…</p></div>;
  }
  if (session === "unavailable") {
    return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;
  }

  return (
    <div className="page-shell narrow">
      <p className="eyebrow">Exploration runs</p><h1>実行履歴</h1>
      {message && <div className="empty-state">{message}</div>}
      <div className="run-list">{runs.map((run) => (
        <article className="run-card" key={run.id}>
          <div><strong>{run.mode}</strong><span>{new Date(run.created_at).toLocaleString("ja-JP")}</span></div>
          <span className={`status-badge ${run.status}`}>{run.status}</span>
          <small>{run.current_stage} · {run.id.slice(0, 8)}</small>
        </article>
      ))}</div>
    </div>
  );
}
