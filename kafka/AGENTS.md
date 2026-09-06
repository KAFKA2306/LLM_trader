# KAFKA 固有実装ルール

このディレクトリは downstream 独自コードの所有領域。

- 通常作業のbranchは `master`。
- `kafka` branch は旧名互換であり、正本ではない。
- `upstream` branch は自動同期専用。
- 全 `*.md` は upstream 同期対象外。
- 新機能は adapter / wrapper / config / dependency injection を優先する。
- upstream core を直接改変して恒久patchを抱えない。
- DB schema は複製せず canonical persistence API を使う。
- silent fallback を作らない。
- upstream API / schema 変更で互換性が壊れたら fail loudly / UNVERIFIED。
- risk guard は LLM から独立した deterministic layer とする。
- paper/testnet を実売買より先に検証する。
