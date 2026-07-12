# 仕入れ判断エージェント Tsuchibot
## 07_Scraping.md — Phase 1 Source Collection Specification

## 1. Scope

対象は、ジモティースポット2拠点、メルカリ、Amazon、楽天市場、AliExpress、SHEINである。各サイト固有処理はAdapterに閉じ込め、ドメイン層へHTML、CSSセレクタ、Playwrightオブジェクトを漏らさない。

## 2. Common Adapter Contract

```python
class SourceCatalogProvider(Protocol):
    async def collect(self, config: SourceConfig, context: RunContext) -> SourceCollectionResult: ...

class MarketplaceResearchProvider(Protocol):
    async def search(self, query: MarketplaceSearchQuery, limits: ResearchLimits, context: RunContext) -> MarketplaceSearchResult: ...
```

Adapterは正規化済み商品、取得メトリクス、エラーを返す。利益・確度・推奨区分は計算しない。

## 3. Normalized Source Product

必須・推奨項目：source_type、source_location_id、source_item_id、canonical_url、title、displayed_price_jpy、category、availability、listing_timestamp、image_urls、raw_metadata、parser_version。

## 4. Collection Policy

- 通常実行は差分取得。
- 同一商品IDは同じ商品として扱う。
- 価格変更と在庫変更は新しいObservationとして保存する。
- 一つのサイト失敗で全体を停止しない。
- リクエスト上限、タイムアウト、リトライ、キャッシュをサイト別設定にする。
- Parser versionをすべてのObservationへ保存する。

## 5. Jimoty Spot

### 5.1 Target

設定された2拠点を独立して処理する。

### 5.2 New and Changed Products

新着判定はsource_item_id未登録を基本とし、掲載日時を補助情報とする。既知商品でも価格または在庫が変わった場合は再評価対象とする。

### 5.3 Required Extraction

商品ID、詳細URL、タイトル、価格、画像、掲載日時、カテゴリー、在庫状態を取得する。取得できない値はnullとする。

### 5.4 Implementation Preference

安定したHTTP取得とHTML解析を優先し、必要な場合だけPlaywrightを使う。ページネーションは上限を設定し、同一ページまたは同一IDが繰り返された時点で停止する。

## 6. Mercari Research

### 6.1 Search Stages

1. 型番完全一致
2. メーカー＋型番
3. シリーズ＋商品種別
4. メーカー＋商品種別
5. 類似商品検索

### 6.2 Data Scope

売却済み最大50件、販売中最大50件、直近90日を基本とする。検索結果が複数クエリで重複した場合、listing IDで統合する。

### 6.3 Required Fields

listing ID、URL、タイトル、価格、売却済み/販売中、売却日、状態、送料負担、配送方法、画像、セット・ジャンク・専用出品等のフラグ。

### 6.4 Shipping Evidence

送料込み・着払い、配送方法、サイズ情報、明示送料を抽出する。最終送料の補完計算はResearch/Recommendation層で行う。

### 6.5 Special Listings

まとめ売りは単価換算できる場合のみ候補。ジャンク・部品は対象商品も同条件の場合のみ候補。専用出品は信頼度を下げる。

## 7. Amazon

取得項目：ASIN等の商品ID、タイトル、URL、価格、送料、確実なクーポン、ポイント参考値、在庫、販売者、配送予定日、レビュー、画像。ポイントは利益計算に含めない。

## 8. Rakuten

取得項目：商品コード、店舗ID、価格、送料、クーポン、ポイント、店舗評価、レビュー、配送日、在庫、画像。同一商品はJAN・型番・タイトル・画像でグループ化し、実質価格・評価・配送日から上位3店舗を保存する。

## 9. AliExpress

取得項目：商品ID、バリエーション、円表示価格、元通貨、送料、クーポン、商品評価、レビュー数、店舗評価、配送予定、画像、ブランド・キャラクター表示。バリエーション別価格を必須とし、最安表示だけを採用しない。配送7日超は通常推奨対象外。

## 10. SHEIN

新品衣類・小物を中心とし、商品ID、サイズ/色バリエーション、価格、送料、クーポン、配送予定、評価、レビュー、素材、画像、在庫を取得する。

## 11. Browser Automation

ブラウザ自動化は、クライアント描画や操作が必須な場合に限定する。失敗時のみ診断スクリーンショットを保存し、機密情報は含めない。並列タブ数を制限する。

## 12. HTTP, Rate Limit and Retry

- 408、429、一部5xxのみ指数バックオフで再試行。
- 401/403、CAPTCHA、セレクタ崩壊は同一実行内で無限再試行しない。
- サイト別rate limiterを必須とする。
- キャッシュは価格変更検知を妨げないTTLにする。

## 13. Error Categories

network、timeout、blocked、authentication、parsing、validation、rate_limit、unavailable、policy、unknown。

## 14. Fixtures and Tests

各Adapterに、正常一覧、商品詳細、売却済み、販売中、値下げ、在庫切れ、HTML崩れのfixtureを用意する。通常CIでは実サイトへアクセスしない。

## 15. Manual Fallback

サイト制約で自動取得できない場合、URL、タイトル、価格、画像、送料、評価、配送日を手入力して同じ正規化モデルへ投入できるようにする。

## 16. Acceptance Criteria

- 2拠点を独立取得できる。
- 新着と価格変更を区別できる。
- Mercari売却済み・販売中を統一形式にできる。
- ECの送料、配送、レビュー、バリエーション価格を保持できる。
- Adapter内に利益計算がない。
- Rate limit、parser version、fixtureが存在する。
