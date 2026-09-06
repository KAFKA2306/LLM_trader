# KAFKA downstream rule

この fork は 2 つの役割を分ける。

- `master`: `qrak/LLM_trader:master` の mirror。KAFKA 固有変更を入れない。
- `kafka`: KAFKA 固有開発 branch。独自実装は原則 `kafka/**` に置く。
- GitHub の default branch は `kafka` を推奨する。通常作業の入口を downstream 側に固定するため。

## 「更新する」の解釈

ユーザーが単に「この repo を更新する」「機能を追加する」「修正する」と言った場合は、`kafka` branch の KAFKA 固有実装を更新する。

`master` を変更してよいのは、ユーザーが明示的に「upstream を同期する」「qrak の更新を取り込む」と依頼した場合だけ。

## Markdown の同期方針

`*.md` 全体を同期対象外にはしない。

upstream の README、CHANGELOG、AGENTS.md、architecture/documentation も upstream の仕様変更を伝える重要な資産なので、通常どおり同期する。

KAFKA 固有として同期対象外にするのは次だけ。

- `KAFKA_DOWNSTREAM.md`
- `kafka/**`
- `.github/workflows/kafka-*.yml`

root `AGENTS.md` は upstream 所有とし、KAFKA 固有ルールを恒久的に追記しない。KAFKA 固有 authority はこのファイルと `kafka/AGENTS.md` に置く。

## upstream 同期

**GitHub の "Sync fork" ボタンは使わない。**

upstream 更新は `kafka/update_from_upstream.sh` を唯一の標準経路とする。

1. `qrak/LLM_trader:master` を取得する。
2. `KAFKA2306/LLM_trader:master` に KAFKA 固有 commit がないことを確認する。
3. fast-forward のみで mirror `master` を更新する。
4. `kafka` に最新 `master` を取り込む。
5. `kafka-boundary` と KAFKA 固有 test を確認する。

fast-forward できない、または conflict が発生した場合は自動解決しない。処理を止め、状態を `UNVERIFIED` として報告する。

## 禁止

- KAFKA 固有機能を `master` に直接 commit しない。
- upstream core の `src/**`, `config/**`, `start.py`, `tests/**` を downstream patch として常用しない。
- conflict を `ours` / `theirs` で機械的に解決しない。
- upstream の DB schema や persistence を独自に複製しない。
- `*.md` を一括で同期除外しない。
- GitHub の "Sync fork" で `kafka` を upstream に直接同期しない。

詳細は `kafka/README.md` と `kafka/AGENTS.md` を参照する。
