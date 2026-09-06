# downstream / upstream 同期方針

## 一行ルール

**普段は `master` を編集する。upstream は自動で入り、`*.md` は絶対に上書きされない。**

## Branch

- `master`: KAFKA版の正本、default branch
- `upstream`: `qrak/LLM_trader:master` の exact mirror
- `kafka`: 旧branch名との互換用エイリアス

## 自動同期

`.github/workflows/upstream-sync.yml` が定期的に upstream を取得し、非 Markdown の upstream 内容を `master` に反映する。

同期方式は merge conflict 解決ではなく **snapshot overlay** とする。

1. upstream の最新treeを基準にする。
2. upstream の全 `*.md` を捨てる。
3. 現在の KAFKA 所有ファイルを上書きで戻す。
4. 差分があれば自動commitして push する。
5. `upstream` branch は upstream exact head に更新する。
6. `kafka` branch は `master` と同じheadへ追従させる。

これにより Markdown の競合は構造上発生しない。

## KAFKA 所有

- すべての `*.md`
- `kafka/**`
- `.github/workflows/kafka-*.yml`
- `.github/workflows/upstream-sync.yml`

それ以外の非 Markdown は upstream 所有。

## 禁止

- GitHub の `Sync fork` を使わない。
- `upstream` branch を直接編集しない。
- upstream 所有の非 Markdown ファイルに恒久 patch を置かない。
- upstream Markdown を正本として扱わない。
