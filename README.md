# Tsuchibot

Tsuchibot は、メルカリでの再販売に向く仕入れ候補を探索し、根拠と不確実性を示す意思決定支援エージェントです。購入は自動化せず、利益計算と推奨判定は決定論的なコードで行います。

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

仕様は [`docs/`](docs/) を参照してください。開発上の必須ルールは [`CODEX.md`](CODEX.md) にあります。
