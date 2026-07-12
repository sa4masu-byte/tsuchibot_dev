# 仕入れ判断エージェント Tsuchibot
## 08_API.md — Phase 1 REST API Specification

## 1. Principles

FastAPI、JSON、`/api/v1`を使用する。すべてのユーザー向けAPIは共有パスワードSessionを要求する。金額は整数円。エラー形式を統一する。

## 2. Common Error

```json
{"error":{"code":"PRODUCT_NOT_FOUND","message":"Product was not found.","details":{},"request_id":"uuid"}}
```

HTTP status: 400, 401, 403, 404, 409, 422, 429, 500, 503。

## 3. Authentication

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/session`

Login成功時、Secure/HttpOnly/SameSite Cookieを発行する。共有パスワードやSession秘密値を返さない。

## 4. Dashboard

`GET /api/v1/dashboard`

最新Run、推奨区分件数、候補仕入れ総額、予想利益合計、平均90日売却見込み、ベスト候補、サイト別概要、エラーを返す。

## 5. Runs

- `POST /api/v1/runs/dispatch`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/progress`
- `GET /api/v1/runs/{run_id}/errors`

Dispatch mode: incremental、full、retry_failed。retry_failedではtarget_run_id必須。同時実行競合は409。

## 6. Products

`GET /api/v1/products`

Filters: run_id、tier、source、category、status、minimum_profit、minimum_sales_prospect、minimum_confidence、search。Sort: overall score、profit、confidence、sales prospect、price、observed time。Cursor paginationを使用する。

`GET /api/v1/products/{product_id}`

商品、仕入先、画像、価格履歴、AI解析、実効値、修正、最新推薦、理由、リスク、調査、在庫、フィードバックを返す。

## 7. Corrections

- `POST /api/v1/products/{product_id}/corrections`
- `DELETE /api/v1/products/{product_id}/corrections/{correction_id}`

修正可能項目：商品名、カテゴリー、メーカー、ブランド、型番、キャラクター、サイズ、色、状態、新品判定、送料、想定販売価格。修正後は再計算し、必要なら再調査をQueueする。

## 8. Research and Comparables

- `GET /api/v1/products/{product_id}/research`
- `GET /api/v1/products/{product_id}/comparables`
- `POST /api/v1/products/{product_id}/comparables/{id}/exclude`
- `POST /api/v1/products/{product_id}/comparables/{id}/restore`

Comparableには画像、タイトル、価格、状態、配送、売却状態、類似度、採否を含める。除外・復元後に推薦を再計算する。

## 9. Recommendation History

- `GET /api/v1/products/{product_id}/recommendations`
- `GET /api/v1/products/{product_id}/recommendations/{recommendation_id}`

入力Snapshot、計算結果、理由、Rule versionを返す。

## 10. Feedback

- `POST /api/v1/products/{id}/feedback/preference`
- `POST /api/v1/products/{id}/feedback/research-value`

Preference: want、slightly_interested、do_not_want、cannot_judge。Research value: worth_researching、not_worth_researching。

## 11. Inventory

- `POST /api/v1/products/{id}/purchase`
- `GET /api/v1/inventory`
- `POST /api/v1/inventory/{id}/listings`
- `POST /api/v1/inventory/{id}/sales`
- `POST /api/v1/inventory/{id}/negative-outcomes`

購入数量は1〜4。売却数量は残在庫を超えない。実利益はServerが決定論的に計算する。

## 12. Hypotheses and Reflection

- `GET /api/v1/hypotheses`
- `GET /api/v1/hypotheses/{id}`
- `GET /api/v1/runs/{run_id}/reflection`

Phase 1の仮説画面は読み取り中心とする。

## 13. Settings

- `GET /api/v1/settings`
- `PATCH /api/v1/settings/{config_type}`

秘密情報は返さない。更新時はexpected versionで楽観ロックする。

## 14. Internal Worker APIs

必要な場合のみ：

- `POST /api/v1/internal/runs/{id}/progress`
- `POST /api/v1/internal/runs/{id}/errors`
- `POST /api/v1/internal/runs/{id}/complete`

専用Worker tokenまたは署名を要求する。

## 15. Signed Images

`GET /api/v1/products/{product_id}/images/{image_id}/url`

短時間有効な署名URLを返す。

## 16. Idempotency and Audit

Run dispatch、purchase、sale、correction、comparable exclusionは`Idempotency-Key`を受け付ける。すべてのCommandはAudit eventを作成する。

## 17. OpenAPI

Operation IDを安定化し、Request/Response例、Enum、Error schemaを記載する。Frontend向けTypeScript client生成を可能にする。

## 18. Security

GitHub tokenとSupabase service roleはBrowserへ出さない。CommandにはCSRF対策、Login rate limit、Request size limitを適用する。

## 19. Acceptance Criteria

- Sessionで保護される。
- Run開始・進捗・履歴を扱える。
- 商品一覧・詳細・修正・Comparable除外が可能。
- 購入から売却まで記録できる。
- エラー形式とOpenAPIが統一される。
- Browserに特権秘密値を渡さない。
