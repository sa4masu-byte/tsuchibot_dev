import type { Metadata } from "next";
import Link from "next/link";

import "./styles.css";

export const metadata: Metadata = {
  title: "Tsuchibot",
  description: "根拠が見える仕入れ判断エージェント",
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
            <Link href="/runs">実行履歴</Link>
            <Link href="/login">ログイン</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
