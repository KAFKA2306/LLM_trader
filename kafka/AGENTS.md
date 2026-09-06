# KAFKA extension rules

この directory 配下だけを KAFKA 固有実装の authority とする。

## Branch rule

- 通常の機能追加・修正は必ず `kafka` branch で行う。
- ユーザーが単に「更新する」「直す」「機能追加する」と言った場合も `kafka` を対象にする。
- `master` を変更してよいのは、ユーザーが明示的に upstream 同期を求めた場合だけ。
- GitHub の default branch は `kafka` を推奨する。
- upstream 同期前に `KAFKA_DOWNSTREAM.md` を確認する。
- GitHub の "Sync fork" は使わず、`kafka/update_from_upstream.sh` を使う。

## Markdown ownership

- `*.md` を一括で downstream 所有にしない。
- upstream の root `AGENTS.md`, `README.md`, `CHANGELOG.md`, その他 docs は upstream 所有として同期する。
- KAFKA 固有 Markdown は `KAFKA_DOWNSTREAM.md` と `kafka/**` に限定する。
- root `AGENTS.md` に KAFKA 固有ルールを恒久追記しない。upstream 更新との conflict を避けるため。

## Implementation rule

- upstream 管理ファイルを直接変更しない。
- `master` を downstream 開発 branch にしない。
- 新機能は adapter / wrapper / config / dependency injection で実装する。
- upstream core の変更が必要なら、恒久 patch より upstream への汎用変更を優先する。
- silent fallback を追加しない。依存 API や schema が変わった場合は fail loudly / UNVERIFIED とする。
- upstream 更新後は KAFKA 固有 test を実行して互換性を確認する。
- DB schema を直接複製しない。upstream の canonical persistence API を利用する。
- 取引実行より先に paper/testnet で検証する。
- risk guard は LLM から独立した deterministic layer とする。
- conflict は自動解決しない。merge を abort して UNVERIFIED とする。
