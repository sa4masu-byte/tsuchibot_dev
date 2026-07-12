# 仕入れ判断エージェント Tsuchibot
## 09_Frontend.md — Phase 1 Frontend Specification

## 1. Goals

Next.js App RouterとTypeScriptを使用し、スマートフォンで毎日の候補確認・修正・結果入力を完結できるUIを作る。情報量は多いが、一覧は簡潔に、根拠は詳細画面で段階的に開示する。

## 2. Route Map

- `/login`
- `/` Dashboard
- `/runs`
- `/runs/[runId]`
- `/products`
- `/products/[productId]`
- `/inventory`
- `/inventory/[positionId]`
- `/hypotheses`
- `/settings`

## 3. Login

共有パスワード入力、エラー、再試行制限を表示する。Session確認中は保護画面を表示し、未認証コンテンツを一瞬表示しない。

## 4. Dashboard

表示項目：最新Run状態、探索開始ボタン、強く推奨/推奨/候補/見送り/調査不能件数、候補仕入れ総額、予想利益、平均売却見込み、今日のベスト、ジモティー候補、EC候補、エラー、学びの概要。

## 5. Run Progress

5〜10秒Polling。Stage名、全体%、処理件数、サイト別状態、エラー数、最終更新時刻を表示する。失敗サイトと全体失敗を明確に分ける。

## 6. Candidate List

MobileではCard表示。必須：画像、商品名、仕入先、仕入価格、予想販売価格、予想利益、90日売却見込み、確度、推奨Badge。SortとFilterはBottom SheetまたはDrawerにする。

## 7. Product Detail

セクション：概要、推奨理由、注意点、利益計算、商品情報、価格履歴、メルカリ比較、AI解析、手動修正、感性Feedback、購入記録。各セクションはAccordion可能。

## 8. Comparable Review

比較商品をCard表示し、画像、価格、状態、配送、売却日、類似度、採用状態を示す。「違う商品として除外」と復元操作を提供し、再計算中状態を表示する。

## 9. Correction UX

実効値、AI値、元サイト値を並べ、修正理由を任意入力する。保存後に再計算または再調査が必要かを明示する。

## 10. Inventory UX

購入、出品、売却、返品等をStep形式で入力する。数量、実金額、送料、手数料を入力し、残数と実利益を表示する。

## 11. Component Structure

```text
features/
  dashboard/
  runs/
  products/
  comparables/
  corrections/
  inventory/
  hypotheses/
  settings/
```

共通Component：Money、ScoreBadge、RecommendationBadge、ReasonList、RiskList、EmptyState、ErrorBanner、LoadingSkeleton、ConfirmDialog。

## 12. Data Fetching

Read-heavy画面はServer Component、操作はClient Component。API型はOpenAPI生成Clientを使用する。Active RunのみPollingし、完了後停止する。

## 13. Mobile Accessibility

44px以上のTap target、十分なContrast、Keyboard focus、Screen reader label、色だけに依存しないBadge、横スクロール必須Tableを避ける。

## 14. Error and Empty States

「候補なし」「調査不能」「一部サイト失敗」を区別する。Retry可能なエラーのみRetry actionを表示する。

## 15. Acceptance Criteria

- 主要フローがスマホ幅で利用可能。
- 一覧は簡潔、詳細で根拠確認可能。
- 修正・除外・購入・売却操作ができる。
- Loading、Error、Empty、Partial failureが明確。
- 特権秘密値を扱わない。
