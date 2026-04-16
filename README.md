# Feishu to WeChat Publish

<p align="center">
  <a href="README.md">中文</a> | 
  <a href="README-en.md">English</a> | 
  <a href="README-ja.md">日本語</a>
</p>

---

一键把飞书文档发布到微信公众号草稿箱。给一个链接，自动完成：

```
飞书文档 → 读取内容 → 下载图片 → 裁切封面图 → 推送到微信公众号草稿箱
```

---

## 一、需要准备的东西

### 1. 飞书开放平台应用

| 凭证 | 获取地址 | 用途 |
|------|----------|------|
| App ID | [飞书开放平台](https://open.feishu.cn/app) → 创建应用 → 凭证与基础信息 | 读取飞书文档 |
| App Secret | 同上页面 | 获取访问令牌 |

**应用需要开通权限并发布上线：**
- `docx:document:readonly`（读取文档内容）
- `wiki:wiki:readonly`（读取 Wiki 页面）

**文档需要设置为「组织内可阅读」**

### 2. 微信公众号

| 凭证 | 获取地址 | 用途 |
|------|----------|------|
| AppID | 微信公众号后台 → 设置与工具 → 公众号设置 | 发布到草稿箱 |
| AppSecret | 同上页面 → 接口权限 → 查看 | 获取 access_token |

### 3. 电脑环境

| 工具 | 安装方式 |
|------|----------|
| `bun` | `brew install bun`（运行 TypeScript 脚本） |
| `python3` + Pillow | `brew install python3 && pip3 install Pillow`（图片处理） |

---

## 二、安装步骤

### 1. 下载项目

```bash
# 下载本项目 zip 包，解压到任意目录
# 或者
git clone https://github.com/will0101iam/feishu-to-wechat-skills.git
cd feishu-to-wechat-skills
```

### 2. 配置 API 凭证

```bash
# 在项目目录下创建 .env 文件
cat > .env << 'EOF'
# 飞书凭证
FEISHU_APP_ID=你的飞书AppID
FEISHU_APP_SECRET=你的飞书AppSecret

# 微信公众号凭证
WECHAT_APP_ID=你的微信AppID
WECHAT_APP_SECRET=你的微信AppSecret
EOF
```

> **注意**：`.env` 文件会包含你的凭证，请勿上传到 GitHub（项目已自动忽略 `.env` 文件）。

---

## 三、使用方法

### 最简单的用法（一行命令）

```bash
# 进入项目目录
cd feishu-to-wechat-skills

# 运行脚本
./feishu-to-wechat.sh "https://my.feishu.cn/wiki/你的文档链接"
```

### 完整参数示例

```bash
./feishu-to-wechat.sh \
  "https://my.feishu.cn/wiki/你的文档链接" \
  --title "自定义标题" \
  --cover cover.jpg \
  --cover-mode blur \
  --theme grace \
  --color blue \
  --author "作者名"
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `飞书URL` | 必填 | 飞书文档链接，支持 wiki/docx |
| `--title` | 自动提取 | 文章标题 |
| `--cover` | 自动提取文档第一张图 | 封面图路径 |
| `--cover-mode` | `blur` | 封面图处理模式：`blur`（模糊背景+原图）、`crop`（直接裁切）、`solid`（纯色背景） |
| `--theme` | `default` | 排版主题：`default`、`grace`、`simple`、`modern` |
| `--color` | 无 | 配色：`blue`、`green`、`vermilion` 等 |
| `--author` | 无 | 作者署名（最多16字） |

---

## 四、常见问题

### Q: 提示「应用权限不足」或 403 错误

- 应用需要开通 `docx:document:readonly` 和 `wiki:wiki:readonly` 权限
- 应用需要**发布上线**（不是仅保存）
- 文档需要设为**组织内可阅读**

### Q: 提示「获取 access_token 失败」

- 检查 `.env` 里的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
- 飞书应用是否已经**发布上线**

### Q: 封面图是空白/找不到封面图

- 检查文档里是否有图片
- 可以用 `--cover /path/to/your/image.jpg` 手动指定封面图

### Q: bun 命令找不到

```bash
brew install bun
```

### Q: python3 报 Pillow 错误

```bash
pip3 install Pillow
```

---

## 五、如何确认安装成功？

运行以下命令，如果显示「文档读取完成」就说明正常：

```bash
./feishu-to-wechat.sh "https://my.feishu.cn/wiki/任意一个你能访问的文档链接"
```

---

## 六、技术细节

本项目包含三个模块：

| 脚本 | 职责 |
|------|------|
| `fetch_feishu_doc.py` | 读取飞书文档（wiki/docx），下载图片到本地 |
| `image-fit.py` | 把图片裁切成 2.35:1 比例（微信公众号封面标准比例） |
| `feishu-to-wechat.sh` | 编排脚本：读取→封面→发布到微信公众号草稿箱 |

---

## 七、文件结构

```
feishu-to-wechat-skills/
├── README.md                    # 本说明文件
├── SKILL.md                      # 保留文件（兼容旧版）
├── .gitignore                    # Git 忽略配置
└── scripts/
    ├── feishu-to-wechat.sh       # 一键发布脚本（入口）
    ├── fetch_feishu_doc.py       # 飞书文档读取脚本
    ├── image-fit.py              # 封面图裁切脚本
    ├── wechat-api.ts            # 微信公众号 API 脚本
    ├── wechat-extend-config.ts  # 微信账号配置
    ├── wechat-image-processor.ts # 微信图片处理
    ├── md-to-wechat.ts           # Markdown 转微信 HTML
    ├── package.json              # Node.js 依赖
    ├── bun.lock
    └── node_modules/             # 依赖包
```

> **注意**：本项目不包含 API 凭证。凭证配置在项目根目录的 `.env` 文件中（已自动忽略，不会上传到 GitHub）。