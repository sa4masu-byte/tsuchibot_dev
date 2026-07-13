# Tsuchibot

Tsuchibot は、ジモティの適正価格設定と、別事業のEC小売向け仕入れ判断を、根拠と不確実性つきで支援するエージェントです。購入は自動化せず、利益計算と推奨判定は決定論的なコードで行います。

## ローカル起動

必要環境は Python 3.12–3.14、Node.js 20.9以上、pnpm です。

```bash
cp .env.example .env
make install
make dev-backend
make dev-frontend
```

`pnpm`がPATHにない場合、Frontend用スクリプトは`corepack`、次に`npx`へ自動的にフォールバックします。Backendが既に8000番で正常稼働中の場合、重複起動せずその旨を表示します。

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

初期実装では永続化・GitHub dispatchとも交換可能なポートを使用し、資格情報がないローカル環境では安全なインメモリ実装にフォールバックします。

## 品質確認

```bash
make check
```

## 手動探索バッチ

Supabase接続を設定した後、最初にchecksum管理付きmigrationを適用します。

```bash
make migrate
make migration-status
```

通常の差分探索は次のいずれかで開始できます。

```bash
./scripts/explore.sh
make explore
```

macOSでは、Finderから `run_exploration.command` をダブルクリックしても同じ差分探索を開始できます。

```bash
# 全件再処理
./scripts/explore.sh full

# 指定したRunの失敗項目を再実行
./scripts/explore.sh retry_failed <target-run-id>
```

事前に一度 `make install` を実行してください。バッチは `.venv` がない場合や引数が不正な場合、処理を始めずに理由を表示します。
実サイトの商品を履歴として保存するため、`TSUCHIBOT_DATABASE_URL`とmigration適用済みPostgreSQLが必要です。2拠点は独立処理され、一方が失敗しても他方を継続します。CIやfixture確認では`TSUCHIBOT_SOURCE_MODE=disabled`を指定すると外部通信を行いません。

## Mercariブラウザ調査

通常のWebページ操作を低速・逐次で代行するローカルバッチを使用できます。最初にPlaywright用Chromiumを一度だけインストールします。

```bash
make install-browser
./scripts/research-mercari-browser.sh \
  --source-product-id <source-product-uuid> \
  --run-id <exploration-run-uuid>
```

既定では確認可能なブラウザ画面を開きます。最新のGemini分析に十分な型番候補があればGoogle Lensを省略し、不明または低信頼の場合だけ先頭の商品画像でLens検索を行います。その後、Mercariの5段階検索を販売中・売却済み別に一件ずつ進めます。CAPTCHA、ログイン要求、アクセス制限は回避せず停止し、失敗時だけ`artifacts/browser/`へ診断画像を保存します。

## Mercari手動入力フォールバック

ブラウザ調査が利用できない場合は、`mercari-manual-v1` JSONから同じ正規化・Comparable判定・相場統計フローを実行できます。入力例は `backend/tests/fixtures/mercari/manual_research.json` です。

```bash
./scripts/research-mercari.sh \
  --source-product-id <source-product-uuid> \
  --run-id <exploration-run-uuid> \
  --input backend/tests/fixtures/mercari/manual_research.json
```

既存のCanonical Productを使う場合は`--source-product-id`を`--canonical-product-id`へ置き換えます。処理は段階検索、listing ID重複統合、特殊出品判定、直近90日の売却済み3件ルール、価格・送料統計を履歴として保存します。自動購入は行いません。

`--source-product-id`を指定したMercari調査は、保存後に決定論的な推奨計算まで続けます。保存済みの調査証拠だけを再計算する場合は次を実行します。

```bash
./scripts/recommend.sh \
  --source-product-id <source-product-uuid> \
  --run-id <exploration-run-uuid> \
  --research-session-id <research-session-uuid>
```

手数料、送料fallback、予想利益、2種類の利益率、90日販売見込み、信頼度、総合スコア、4段階分類はコードで計算されます。同一入力と同一スコア版の再実行は同じ履歴を返します。証拠不足時は価格や送料を補完せず、確認事項とリスクを構造化して保存します。

仕様は [`docs/`](docs/) を参照してください。開発上の必須ルールは [`CODEX.md`](CODEX.md) にあります。
