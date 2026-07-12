# ADR-0001: Modular Monolith

## Status
Accepted

## Decision
Phase 1はモジュラーモノリスを採用する。Domain境界は明確にするが、Microserviceへ分割しない。

## Rationale
小規模運用でDeployment・Transaction・Debugを単純化しながら、将来の分離可能性を維持する。
