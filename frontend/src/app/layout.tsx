import type { Metadata } from "next";
import Link from "next/link";

import "./styles.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: "Tsuchibot",
  description: "適正価格と仕入れ判断の根拠を確認するレビューシステム",
  openGraph: {
    title: "Tsuchibot",
    description: "適正価格と仕入れ判断の根拠を、ひとつずつ確認する。",
    images: [{ url: "/og.png", width: 1731, height: 909 }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Tsuchibot ホーム">
            <span className="brand-mark">土</span>
            <span>Tsuchibot</span>
          </Link>
          <nav aria-label="メインナビゲーション">
            <Link href="/products">候補</Link>
            <Link href="/ec">EC探索</Link>
            <Link href="/runs">実行履歴</Link>
            <Link href="/login">ログイン</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
