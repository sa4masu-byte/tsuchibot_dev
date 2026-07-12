# ADR-0005: GitHub Actions Exploration Worker

## Status
Accepted

## Decision
Phase 1の探索処理はworkflow_dispatchで起動する。

## Rationale
1日1回の手動実行に十分で、常時Server費用を抑えられる。
