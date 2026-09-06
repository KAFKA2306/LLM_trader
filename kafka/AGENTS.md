# KAFKA extension rules

この directory 配下だけを KAFKA 固有実装の authority とする。

- upstream 管理ファイルを直接変更しない。
- `master` を downstream 開発 branch にしない。
- 新機能は adapter / wrapper / config / dependency injection で実装する。
- upstream core の変更が必要なら、恒久 patch より upstream への汎用変更を優先する。
- silent fallback を追加しない。依存 API や schema が変わった場合は fail loudly / UNVERIFIED とする。
- upstream 更新後は KAFKA 固有 test を実行して互換性を確認する。
- DB schema を直接複製しない。upstream の canonical persistence API を利用する。
- 取引実行より先に paper/testnet で検証する。
- risk guard は LLM から独立した deterministic layer とする。
