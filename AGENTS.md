# KAFKA2306/LLM_trader 運用規約

このファイルを、この fork におけるエージェント運用の正本とする。

## 1. 正準ブランチ

- `master`: 通常開発の正本。GitHub の現在の default branch も `master`。
- `upstream`: `qrak/LLM_trader:master` の完全ミラー。自動同期専用で、直接編集しない。
- `kafka`: 旧運用との互換用エイリアス。新規作業の正本にはしない。

したがって、ユーザーが単に「更新して」「修正して」「機能追加して」と依頼した場合は `master` を更新する。

## 2. upstream 同期

upstream 同期は GitHub Actions の `upstream-sync` が自律実行する。

- `qrak/LLM_trader:master` を取得する。
- `upstream` branch をその exact head に更新する。
- upstream の非 Markdown ファイルを `master` に反映する。
- KAFKA 所有領域は保持する。
- `kafka` branch は `master` の互換エイリアスとして追従させる。

GitHub の `Sync fork` ボタンは使わない。

## 3. Markdown 所有権

**すべての `*.md` は KAFKA 側の所有物とし、upstream 同期対象外とする。**

upstream の Markdown は信頼できる正本として扱わない。必要な情報はコード、テスト、設定、実行結果から検証し、日本語 Markdown としてこちらで再構成する。

upstream が Markdown を追加・変更・削除しても、自動同期では取り込まない。

## 4. 独自コードの所有領域

KAFKA 独自コードは原則として次に置く。

- `kafka/**`
- `.github/workflows/kafka-*.yml`
- `.github/workflows/upstream-sync.yml`
- すべての `*.md`

それ以外の非 Markdown ファイルは upstream 所有とし、自動同期で upstream の内容を優先する。

upstream core の変更が必要な場合は、直接 patch を抱えるより adapter / wrapper / config / dependency injection を優先する。

## 5. データと安全性

- DB schema を独自に複製せず、実コード上の canonical persistence API を使う。
- silent fallback を追加しない。
- API / schema 不整合は fail loudly または `UNVERIFIED` とする。
- risk guard は LLM から独立した deterministic layer とする。
- 実売買より paper/testnet 検証を先に行う。

## 6. 信頼順位

実装判断では次の順で信頼する。

1. 実行中コード
2. テスト
3. 設定・schema
4. CI / 実行ログ
5. KAFKA が検証して書いた Markdown
6. upstream の Markdown は参考資料に留める
