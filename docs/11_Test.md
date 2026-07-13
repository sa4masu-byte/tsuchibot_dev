# 仕入れ判断エージェント Tsuchibot
## 11_Test.md — Phase 1 Test Strategy

## 1. Principles

ドメイン計算を最優先でTestする。通常CIは実サイト・実Geminiへ接続しない。FixtureとFake Adapterで再現可能にする。

## 2. Test Pyramid

- Unit: ドメイン計算、Rule、Value object
- Application: Use case、Partial failure、Rerun
- Contract: Adapter正規化、AI schema
- Integration: PostgreSQL、Migration、FastAPI
- E2E: Loginから売却記録まで
- Manual smoke: 実サイトAdapter

## 3. Required Unit Tests

Fee、Sourcing cost、Profit、Margin、中央値・四分位、Shipping fallback、Sold-rate、Sales prospect、Confidence、Tier、Duplicate、Price change、Manual override、Quantity 1〜4、Inventory残数。

Recommendation tests must also cover fee floor rounding, same/similar/method shipping precedence,
unknown financial inputs, insufficient-comparable downgrade, structured reasons, all four quantity
evaluations, and same-input/scoring-version idempotency.

## 4. Application Tests

通常Run、ジモティー片側失敗、Gemini一部失敗、Mercari調査不能、EC代替探索、Full rerun、Retry failed、Comparable除外後再計算、Correction後再調査。

## 5. Adapter Contract Tests

各Adapterは同じNormalized modelを返すこと。Parser fixtureで商品ID、価格、画像、配送、売却状態、レビュー、配送日、バリエーションを検証する。

## 6. AI Evaluation

Category、メーカー、型番完全一致、型番候補Recall、Character、Condition、Schema valid率、Unknown honesty、User correction率。説明文の流暢さより構造化抽出を重視する。

## 7. API Tests

Auth、Run dispatch、Conflict、Pagination、Product detail、Correction、Comparable exclude/restore、Purchase、Sale、Over-sale、Error schema、Idempotency。

## 8. Frontend E2E

Login、Dashboard、Run開始、Progress、Candidate表示、Detail、修正、Comparable除外、購入、出品、売却、Mobile viewport。

## 9. Migration Tests

空DB適用、既存DB Upgrade、Constraint、Index、View、Backfillを検証する。適用済みMigrationを書き換えない。

## 10. Non-Functional Tests

Secret漏洩、Cookie属性、CSRF、Rate limit、大きな画像、Run overlap、100件一覧、Polling停止、部分障害表示。

## 11. CI Gates

Python lint/type/test、Frontend lint/type/unit、Migration validation、OpenAPI generation、Document link check。Live smokeは手動Workflowに分離する。

## 12. Acceptance Criteria

- P0ドメインRuleが自動Test済み。
- Live外部サービスなしでCI成功。
- Adapter fixture回帰試験がある。
- Mobile E2Eが主要フローを通る。
- 失敗時に全Runが不必要に停止しない。
