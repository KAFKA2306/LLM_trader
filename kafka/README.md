https://github.com/KAFKA2306/LLM_trader/tree/kafka

# KAFKA extension layer

この `kafka` branch は、`KAFKA2306/LLM_trader:master` を upstream mirror として保ったまま、KAFKA 固有の拡張だけを保持する長期 branch です。

## Authority

- upstream: `qrak/LLM_trader:master`
- mirror: `KAFKA2306/LLM_trader:master`
- downstream extension: `KAFKA2306/LLM_trader:kafka`
- KAFKA 固有コード: `kafka/**`
- 更新ルール: `KAFKA_DOWNSTREAM.md`

## 迷ったときの唯一のルール

**普通の機能追加・修正は `kafka`。upstream 同期だけ `master`。**

GitHub の default branch も `kafka` を推奨します。repository を開いたときの入口と通常作業先を一致させるためです。

「この repo を更新する」とだけ依頼された場合、`master` ではなく `kafka` を更新します。

## Markdown

`*.md` 全体は同期除外しません。

upstream の README / CHANGELOG / AGENTS.md / docs には仕様変更や運用変更が含まれるため、upstream と一緒に追従します。

KAFKA 固有 Markdown は `KAFKA_DOWNSTREAM.md` と `kafka/**` に限定します。

## Rule

`master` には KAFKA 固有 commit を入れません。

KAFKA 固有の実装は `kafka/**` に置きます。upstream core の `src/**`, `config/**`, `start.py`, `tests/**` などを直接改変しません。

upstream に必要な拡張点がない場合は、downstream patch を恒久保有せず、まず upstream に汎用 hook / adapter point を提案します。

## Update flow

**GitHub の "Sync fork" ボタンは使いません。**

通常は次を実行します。

```bash
bash kafka/update_from_upstream.sh
```

この script は fast-forward できない状態や merge conflict を自動解決せず停止します。

1. upstream `master` の新しい head を取得する。
2. fork `master` に独自 commit がないことを確認する。
3. fork `master` を upstream head へ fast-forward する。
4. `kafka` branch に最新 `master` を取り込む。
5. downstream boundary を検証する。
6. conflict があれば merge を abort して失敗終了する。

## Why

目的は、upstream の DB、risk、reflection、dashboard、test 改善を継続的に受け取りながら、KAFKA 固有の scheduler、policy、adapter、分析を独立して維持することです。
