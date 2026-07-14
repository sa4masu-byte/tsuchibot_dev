"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { ECSession } from "@/lib/ec-types";
import { useRequiredSession } from "@/lib/use-session";

export default function ECExplorationPage() {
  const session = useRequiredSession();
  const [sessions, setSessions] = useState<ECSession[]>([]);
  const [message, setMessage] = useState("読み込んでいます…");

  useEffect(() => {
    if (session !== "authenticated") return;
    apiFetch<ECSession[]>("/ec/sessions")
      .then((items) => { setSessions(items); setMessage(items.length ? "" : "EC探索履歴はまだありません。"); })
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : "EC探索履歴を取得できませんでした"));
  }, [session]);

  if (session === "checking") return <div className="center-shell"><p>Sessionを確認しています…</p></div>;
  if (session === "unavailable") return <div className="center-shell"><p role="alert">APIへ接続できません。</p></div>;

  return (
    <div className="page-shell narrow">
      <header className="page-heading ec-heading"><div><p className="eyebrow">Alternative sources</p><h1>EC探索</h1></div><p>Jimoty候補が不足した時、Amazon、楽天、AliExpress、SHEINの順に試した証拠を確認します。</p></header>
      {message && <p className="empty-state">{message}</p>}
      <section className="ec-session-list">
        {sessions.map((item) => (
          <Link className="ec-session-card" href={`/ec/${item.id}`} key={item.id}>
            <div><span className={`status-badge ${item.status}`}>{item.status}</span><h2>{new Date(item.observed_at).toLocaleString("ja-JP")}</h2><p>{item.trigger_reason} · 検索語 {item.keyword_count}件</p></div>
            <dl><div><dt>候補</dt><dd>{item.offer_count}</dd></div><div><dt>評価へ</dt><dd>{item.eligible_count}</dd></div><div><dt>要確認</dt><dd>{item.confirmation_required_count}</dd></div><div><dt>対象外</dt><dd>{item.rejected_count}</dd></div></dl>
          </Link>
        ))}
      </section>
    </div>
  );
}
