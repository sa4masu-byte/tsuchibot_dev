# 仕入れ判断エージェント Tsuchibot
## 10_Roadmap.md — Implementation Roadmap

## 1. Delivery Strategy

一括実装を依頼するが、内部的にはSprint単位で完成条件を満たして進める。各Sprintで動作可能な成果を残し、Document・Migration・Testを同時更新する。

## Sprint 0 — Repository and Decisions

README、CODEX、docs、ADR、開発環境、CI、Issue template。完成条件：Lint/Test skeletonが通る。

## Sprint 1 — Foundation

Python/Next.js構成、Config、Logging、Supabase migration、FastAPI skeleton、GitHub Actions、共有パスワード。完成条件：Login、Health、空Run dispatchが動く。

## Sprint 2 — Jimoty Catalog

2拠点Adapter、商品・Observation・Price history、Duplicate detection、差分実行。完成条件：新着と値下げをDBへ保存できる。

## Sprint 3 — Gemini Analysis

画像保存、Prompt、JSON schema、Validation、上限管理。完成条件：候補商品から構造化商品情報を保存できる。

## Sprint 4 — Mercari Research

段階検索、売却済み/販売中、Comparable ranking、価格統計、送料証拠。完成条件：3件/90日ルールで相場算出できる。

## Sprint 5 — Recommendation

Fee、Shipping fallback、Profit、Margin、Sales prospect、Confidence、Score、4段階分類、Reason component。完成条件：決定論的Testが通る。

## Sprint 6 — Web Review

Dashboard、Run、Candidate、Detail、Comparable除外、Correction。完成条件：スマホから根拠確認・修正可能。

## Sprint 7 — EC Exploration

Amazon、楽天、AliExpress、SHEIN AdapterまたはManual fallback。利益パターン、需要、Saleの順で探索。完成条件：Jimoty不足時に代替探索する。

## Sprint 8 — Inventory and Learning Logs

購入、出品、売却、失敗、実利益、感性Feedback、Hypothesis evidence。完成条件：PredictionとActualを比較できる。

## Sprint 9 — Hardening and Release

Retry、Idempotency、Security、E2E、Parser fixture、Observability、Deploy。完成条件：P0 Acceptance Criteriaを満たす。

## Phase 2

自動日次実行、通知、検索語最適化、売却日数モデル、Learning-to-Rank、画像埋め込み、Hypothesis更新支援。

## Phase 3

複数販売先、在庫Portfolio、季節モデル、価格変動、より高度な探索・活用制御。

## Risk Register

- サイト構造・規約変更
- Mercari送料情報の不足
- 型番OCR誤り
- API/LLM費用
- ECバリエーション価格誤認
- 真贋リスク
- 推奨件数不足

各RiskにOwner、検知指標、FallbackをIssueで管理する。
