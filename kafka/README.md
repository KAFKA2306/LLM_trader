https://github.com/qrak/LLM_trader

# KAFKA extension layer

この `kafka` branch は、`KAFKA2306/LLM_trader:master` を upstream mirror として保ったまま、KAFKA 固有の拡張だけを保持するための長期 branch です。

## Authority

- upstream: `qrak/LLM_trader:master`
- mirror: `KAFKA2306/LLM_trader:master`
- downstream extension: `KAFKA2306/LLM_trader:kafka`
- KAFKA 固有コード: `kafka/**`

## Rule

`master` には KAFKA 固有 commit を入れません。

KAFKA 固有の実装は `kafka/**` に置きます。upstream core の `src/**`, `config/**`, `start.py`, `tests/**` などを直接改変しません。

upstream に必要な拡張点がない場合は、downstream patch を恒久保有せず、まず upstream に汎用 hook / adapter point を提案します。

## Update flow

1. upstream `master` の新しい head を確認する。
2. fork `master` が独自 commit を持っていないことを確認する。
3. fork `master` を upstream head へ fast-forward する。
4. `kafka` branch に最新 `master` を取り込む。
5. KAFKA 固有 test を実行する。
6. conflict が発生した場合は自動解決しない。core を直接変更していない限り、通常は conflict を発生させない。

## Why

目的は、upstream の DB、risk、reflection、dashboard、test 改善を継続的に受け取りながら、KAFKA 固有の scheduler、policy、adapter、分析を独立して維持することです。
