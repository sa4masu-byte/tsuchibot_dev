# ADR-0006: LLM Extracts, Code Calculates

## Status
Accepted

## Decision
LLMは解釈・抽出・文章化に限定し、金額・Score・Tierは決定論的コードで計算する。

## Rationale
再現性、Testability、説明可能性、誤計算防止を優先する。
