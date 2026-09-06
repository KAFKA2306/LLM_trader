# KAFKA extension rules

この directory 配下だけを KAFKA 固有実装の authority とする。

## Branch rule

- 通常の機能追加・修正は必ず `kafka` branch で行う。
- ユーザーが単に「更新する」「直す」「機能追加する」と言った場合も `kafka` を対象にする。
- `master` を変更してよいのは、ユーザーが明示的に upstream 同期を求めた場合だけ。
- upstream 同期前に `KAFKA_DOWNSTREAM.md` を確認する。

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
