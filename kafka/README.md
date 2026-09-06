# KAFKA extension layer

KAFKA 固有コードの隔離領域です。

## 現在の構成

- 開発正本: `master`
- upstream mirror: `upstream`
- 旧branch互換: `kafka`
- 独自コード: `kafka/**`
- Markdown: 全てKAFKA所有、upstream同期対象外

upstream 同期は GitHub Actions が自律実行するため、通常は手動操作不要です。

手動で同じ同期を実行したい場合だけ次を使います。

```bash
bash kafka/update_from_upstream.sh
```

同期は upstream の非 Markdown snapshot を取り込み、KAFKA所有ファイルをoverlayで戻す方式です。Gitの競合解決を日常運用に持ち込みません。
