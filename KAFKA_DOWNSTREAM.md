# KAFKA downstream rule

この fork は 2 つの役割を分ける。

- `master`: `qrak/LLM_trader:master` の mirror。KAFKA 固有変更を入れない。
- `kafka`: KAFKA 固有開発 branch。独自実装は原則 `kafka/**` に置く。

## 「更新する」の解釈

ユーザーが単に「この repo を更新する」「機能を追加する」「修正する」と言った場合は、`kafka` branch の KAFKA 固有実装を更新する。

`master` を変更してよいのは、ユーザーが明示的に「upstream を同期する」「qrak の更新を取り込む」と依頼した場合だけ。

## upstream 同期

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

詳細は `kafka/README.md` と `kafka/AGENTS.md` を参照する。
