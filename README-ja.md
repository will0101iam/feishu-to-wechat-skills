# Feishu to WeChat Publish

<p align="center">
  <a href="README.md">中文</a> | 
  <a href="README-en.md">English</a> | 
  <a href="README-ja.md">日本語</a>
</p>

---

FeishuドキュメントをWeChat公式アカウントの下書きに一括公開。リンクを与えるだけで自動実行：

```
Feishuドキュメント → コンテンツ取得 → 画像ダウンロード → カバー切り抜き → WeChat下書きにプッシュ
```

---

## 準備するもの

### 1. Feishuオープンプラットフォームアプリ

| 認証情報 | 取得場所 | 用途 |
|----------|----------|------|
| App ID | [Feishuオープンプラットフォーム](https://open.feishu.cn/app) → アプリ作成 → 認証情報と基本情報 | Feishuドキュメントの読み取り |
| App Secret | 同上ページ | アクセストークン取得 |

**アプリの権限設定と公開が必要：**
- `docx:document:readonly`（ドキュメント内容の読み取り）
- `wiki:wiki:readonly`（Wikiページの読み取り）

**ドキュメントは「組織内で閲覧可能」に設定する必要があります**

### 2. WeChat公式アカウント

| 認証情報 | 取得場所 | 用途 |
|----------|----------|------|
| AppID | WeChat管理画面 → 設定とツール → アカウント設定 | 下書きへの公開 |
| AppSecret | 同上ページ → API権限 → 確認 | access_token取得 |

### 3. 動作環境

| ツール | インストール方法 |
|--------|------------------|
| `bun` | `brew install bun`（TypeScriptスクリプト実行） |
| `python3` + Pillow | `brew install python3 && pip3 install Pillow`（画像処理） |

---

## インストール

### 1. ダウンロード

```bash
# ZIPをダウンロードして展開、または
git clone https://github.com/will0101iam/feishu-to-wechat-skills.git
```

### 2. インストール

```bash
# feishu-to-wechatにリネーム
mv feishu-to-wechat-skills ~/.config/opencode/skills/feishu-to-wechat
```

### 3. API認証情報設定

```bash
mkdir -p ~/.baoyu-skills/
cat >> ~/.baoyu-skills/.env << 'EOF'
# Feishu認証情報
FEISHU_APP_ID=あなたのFeishuAppID
FEISHU_APP_SECRET=あなたのFeishuAppSecret

# WeChat認証情報
WECHAT_APP_ID=あなたのWeChatAppID
WECHAT_APP_SECRET=あなたのWeChatAppSecret
EOF
```

> **認証情報はGitHubにアップロードされません**。`.env`ファイルはあなたのローカルにあります。

---

## 使用方法

### 最も簡単な使い方（1行）

```bash
bash ~/.config/opencode/skills/feishu-to-wechat/scripts/feishu-to-wechat.sh \
  "https://my.feishu.cn/wiki/あなたのドキュメントリンク"
```

### 完全な例

```bash
bash ~/.config/opencode/skills/feishu-to-wechat/scripts/feishu-to-wechat.sh \
  "https://my.feishu.cn/wiki/あなたのドキュメントリンク" \
  --title "カスタムタイトル" \
  --cover cover.jpg \
  --cover-mode blur \
  --theme grace \
  --color blue \
  --author "著者名"
```

### パラメータ

| パラメータ | デフォルト | 説明 |
|------------|------------|------|
| `Feishu URL` | 必須 | Feishuドキュメントリンク（wiki/docx対応） |
| `--title` | 自動取得 | 記事タイトル |
| `--cover` | 最初の画像を自動取得 | カバー画像パス |
| `--cover-mode` | `blur` | カバー処理: `blur`（ぼかし背景+元画像）、`crop`（直接切り抜き）、`solid`（単色背景） |
| `--theme` | `default` | テーマ: `default`、`grace`、`simple`、`modern` |
| `--color` | なし | 配色: `blue`、`green`、`vermilion` など |
| `--author` | なし | 著者名（最大16文字） |

---

## よくある質問

### Q: 「権限不足」または403エラー

- アプリに `docx:document:readonly` と `wiki:wiki:readonly` 権限が必要
- アプリを**公開**する必要があります（保存だけでは不可）
- ドキュメントは**組織内で閲覧可能**に設定

### Q: 「access_token取得失敗」

- `~/.baoyu-skills/.env` の `FEISHU_APP_ID` と `FEISHU_APP_SECRET` が正しいか確認
- Feishuアプリが**公開済み**か確認

### Q: カバー画像が空/見つからない

- ドキュメントに画像があるか確認
- `--cover /path/to/your/image.jpg` で手動指定 가능

### Q: bunコマンドが見つからない

```bash
brew install bun
```

### Q: python3 Pillowエラー

```bash
pip3 install Pillow
```

---

## インストール確認

以下のコマンドを実行し、「ドキュメント取得完了」と表示されれば正常動作：

```bash
bash ~/.config/opencode/skills/feishu-to-wechat/scripts/feishu-to-wechat.sh \
  "https://my.feishu.cn/wiki/アクセス可能なドキュメント"
```

---

## 技術詳細

| スクリプト | 機能 |
|------------|------|
| `fetch_feishu_doc.py` | Feishuドキュメント取得（wiki/docx）、画像ダウンロード |
| `image-fit.py` | 画像を2.35:1比率に切り抜き（WeChatカバー標準） |
| `feishu-to-wechat.sh` | オーケストレーション: 取得→カバー→WeChat下書き公開 |

---

## ファイル構成

```
feishu-to-wechat/
├── SKILL.md                    # skill定義ファイル
└── scripts/
    ├── feishu-to-wechat.sh     # メインエントリスクリプト
    ├── fetch_feishu_doc.py      # Feishuドキュメント取得
    ├── image-fit.py             # カバー画像切り抜き
    ├── wechat-api.ts            # WeChat APIスクリプト
    ├── wechat-extend-config.ts  # WeChatアカウント設定
    ├── wechat-image-processor.ts # WeChat画像処理
    ├── md-to-wechat.ts          # MarkdownからWeChat HTMLへ
    ├── package.json             # Node.js依存関係
    ├── bun.lock
    └── node_modules/            # 依存パッケージ
```

> **注意**: このプロジェクトにはAPI認証情報が含まれていません。認証情報は `~/.baoyu-skills/.env` に保存されます（ローカルファイル、GitHubにはアップロードされません）。