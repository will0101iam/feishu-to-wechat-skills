# Feishu to WeChat Publish

<p align="center">
  <a href="README.md">中文</a> | 
  <a href="README-en.md">English</a> | 
  <a href="README-ja.md">日本語</a>
</p>

---

One-click publish Feishu documents to WeChat Official Account draft. Just give it a link, and it automatically does:

```
Feishu Document → Fetch Content → Download Images → Crop Cover → Push to WeChat Draft
```

---

## Prerequisites

### 1. Feishu Open Platform Application

| Credential | Where to Get | Purpose |
|------------|--------------|---------|
| App ID | [Feishu Open Platform](https://open.feishu.cn/app) → Create App → Credentials & Basic Info | Read Feishu documents |
| App Secret | Same page | Get access token |

**App requires permissions and must be published:**
- `docx:document:readonly` (read document content)
- `wiki:wiki:readonly` (read Wiki pages)

**Document must be set to "Accessible within organization"**

### 2. WeChat Official Account

| Credential | Where to Get | Purpose |
|------------|--------------|---------|
| AppID | WeChat Admin → Settings & Tools → Account Settings | Publish to draft |
| AppSecret | Same page → API Permissions → View | Get access_token |

### 3. Computer Environment

| Tool | Installation |
|------|--------------|
| `bun` | `brew install bun` (run TypeScript scripts) |
| `python3` + Pillow | `brew install python3 && pip3 install Pillow` (image processing) |

---

## Installation

### 1. Download

```bash
# Download and extract zip, or
git clone https://github.com/will0101iam/feishu-to-wechat-skills.git
cd feishu-to-wechat-skills
```

### 2. Configure API Credentials

```bash
# Create .env file in project directory
cat > .env << 'EOF'
# Feishu credentials
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret

# WeChat credentials
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret
EOF
```

> **Note**: The `.env` file contains your credentials. Do NOT commit it to GitHub (project automatically ignores `.env`).

---

## Usage

### Simplest (one line)

```bash
cd feishu-to-wechat-skills
./feishu-to-wechat.sh "https://my.feishu.cn/wiki/your_document_link"
```

### Full example

```bash
./feishu-to-wechat.sh \
  "https://my.feishu.cn/wiki/your_document_link" \
  --title "Custom Title" \
  --cover cover.jpg \
  --cover-mode blur \
  --theme grace \
  --color blue \
  --author "Author Name"
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Feishu URL` | Required | Feishu document link, supports wiki/docx |
| `--title` | Auto-extract | Article title |
| `--cover` | Auto-extract first image | Cover image path |
| `--cover-mode` | `blur` | Cover processing: `blur` (blur background + original), `crop` (direct crop), `solid` (solid color) |
| `--theme` | `default` | Theme: `default`, `grace`, `simple`, `modern` |
| `--color` | None | Color scheme: `blue`, `green`, `vermilion`, etc. |
| `--author` | None | Author signature (max 16 chars) |

---

## FAQ

### Q: "Insufficient permissions" or 403 error

- App needs `docx:document:readonly` and `wiki:wiki:readonly` permissions
- App must be **published** (not just saved)
- Document must be set to **organization-accessible**

### Q: "Failed to get access_token"

- Check if `FEISHU_APP_ID` and `FEISHU_APP_SECRET` are correct in `.env`
- Check if Feishu app is **published**

### Q: Cover image blank/not found

- Check if document has images
- Use `--cover /path/to/your/image.jpg` to manually specify

### Q: bun command not found

```bash
brew install bun
```

### Q: python3 Pillow error

```bash
pip3 install Pillow
```

---

## Verify Installation

Run this command. If you see "Document fetched successfully", it works:

```bash
./feishu-to-wechat.sh "https://my.feishu.cn/wiki/any_accessible_document"
```

---

## Technical Details

| Script | Purpose |
|--------|---------|
| `fetch_feishu_doc.py` | Fetch Feishu documents (wiki/docx), download images locally |
| `image-fit.py` | Crop images to 2.35:1 ratio (WeChat cover standard) |
| `feishu-to-wechat.sh` | Orchestration: fetch → cover → publish to WeChat draft |

---

## File Structure

```
feishu-to-wechat-skills/
├── README.md                    # This file
├── SKILL.md                     # Legacy file (for compatibility)
├── .gitignore                   # Git ignore config
└── scripts/
    ├── feishu-to-wechat.sh      # Main entry script
    ├── fetch_feishu_doc.py      # Feishu document fetcher
    ├── image-fit.py             # Cover image cropper
    ├── wechat-api.ts            # WeChat API script
    ├── wechat-extend-config.ts  # WeChat account config
    ├── wechat-image-processor.ts # WeChat image processor
    ├── md-to-wechat.ts          # Markdown to WeChat HTML
    ├── package.json             # Node.js dependencies
    ├── bun.lock
    └── node_modules/            # dependencies
```

> **Note**: This project does NOT include API credentials. Credentials are stored in `.env` file in project root (automatically ignored, not uploaded to GitHub).