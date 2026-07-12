"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      router.push("/");
    } catch {
      setError("パスワードを確認してください。");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="center-shell">
      <form className="login-card" onSubmit={submit}>
        <span className="brand-mark large">土</span>
        <p className="eyebrow">Private workspace</p>
        <h1>おかえりなさい</h1>
        <p>共有パスワードを入力してください。</p>
        <label htmlFor="password">パスワード</label>
        <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="error-message" role="alert">{error}</p>}
        <button className="primary-button" disabled={pending}>{pending ? "確認中…" : "ログイン"}</button>
      </form>
    </div>
  );
}
