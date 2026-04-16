---
name: feishu-to-wechat
description: |
  飞书文档一键发布微信公众号。给一个飞书文档链接，自动读取内容、处理封面图、推送到微信公众号草稿箱。
  串联三个能力：fetch_feishu_doc（读飞书文档）+ image-fit（封面图处理）+ baoyu-post-to-wechat（微信发布）。
  当用户提到以下任何情况时使用此 Skill：
  - "飞书发公众号"、"飞书转微信"、"飞书文档发微信"
  - "feishu to wechat"、"把飞书文档推到公众号"
  - "飞书文档发布微信公众号"、"飞书一键发微信"
  - 任何飞书文档 URL + 想要发布到微信公众号的意图
  即使用户没有明确说"微信"，只要意图是把飞书文档发布到公众号草稿箱，也应该触发。
---

# 飞书文档 → 微信公众号

## Language

**Match user's language**: Respond in the same language the user uses.

## Purpose

飞书文档一键发布微信公众号草稿箱：

```
飞书文档 URL → fetch_feishu_doc.py → Markdown
                                        ↓
                              封面图 → image-fit.py → 2.35:1 封面
                                        ↓
                              baoyu-post-to-wechat → 草稿箱
```

## Script Directory

**Agent Execution**: Determine this SKILL.md directory as `{baseDir}`.

| 脚本 | 行数 | 职责 |
|------|------|------|
| `fetch_feishu_doc.py` | 416 | 飞书文档 URL → Markdown（支持 wiki/docx） |
| `image-fit.py` | 240 | 任意图片 → 2.35:1 (900×383) 微信封面图 |
| `feishu-to-wechat.sh` | 194 | 一键编排脚本（读取→封面→发布） |

外部依赖（read-only，不包含在本 skill 内）：

| 脚本 | 位置 | 职责 |
|------|------|------|
| `wechat-api.ts` | `baoyu-post-to-wechat` skill | 微信公众号草稿箱 API |

## When to Use

- 用户给了飞书文档链接，想发布到微信公众号
- "飞书发公众号"、"飞书转微信"、"飞书文档发微信"
- "把这篇飞书文章推到公众号草稿箱"
- "帮我发布到微信公众号"
- 任何飞书 URL + 发布微信公众号的意图

## Prerequisites

| 依赖 | 用途 | 必须？ |
|------|------|--------|
| `FEISHU_APP_ID` + `FEISHU_APP_SECRET` | 飞书 Open API 凭证 | ✅ |
| `WECHAT_APP_ID` + `WECHAT_APP_SECRET` | 微信公众号 API 凭证 | ✅ |
| `bun` 或 `npx` | 运行 wechat-api.ts | ✅ |
| `baoyu-post-to-wechat` skill 已部署 | 微信发布 API | ✅ |
| `python3` + `Pillow` | 封面图处理 | ✅ |

飞书应用需要的权限：`docx:document:readonly` + `wiki:wiki:readonly`

## Complete Workflow

### 方式一：一键脚本（推荐）

```bash
FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx \
WECHAT_APP_ID=xxx WECHAT_APP_SECRET=xxx \
  bash {baseDir}/scripts/feishu-to-wechat.sh "https://my.feishu.cn/wiki/xxx"
```

完整参数：

```bash
bash {baseDir}/scripts/feishu-to-wechat.sh "FEISHU_URL" \
  --title "自定义标题" \
  --cover cover.jpg \
  --cover-mode blur \
  --theme grace \
  --color blue \
  --author "作者名" \
  --method api
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FEISHU_URL` | 必填 | 飞书文档链接 |
| `--title` | 自动提取 | 文章标题（默认从文档第一个标题提取） |
| `--cover` | 自动提取 | 封面图路径（默认从文档中第一张图片提取） |
| `--cover-mode` | `blur` | 封面图处理模式：`blur`/`solid`/`gradient`/`crop` |
| `--theme` | `default` | 文章排版主题 |
| `--color` | 无 | 配色方案 |
| `--author` | 无 | 作者署名 |
| `--method` | `api` | 发布方式：`api`（草稿箱）或 `browser`（浏览器） |

一键脚本自动完成：
1. 读取飞书文档 → Markdown
2. 提取标题和摘要
3. 提取/处理封面图（自动裁切为 2.35:1）
4. 推送到微信公众号草稿箱

### 方式二：分步执行

#### Step 1: 读取飞书文档

```bash
FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx \
  python3 {baseDir}/scripts/fetch_feishu_doc.py "FEISHU_URL" > article.md
```

支持的 URL 格式：
- `https://*.feishu.cn/wiki/xxx`
- `https://*.feishu.cn/docx/xxx`
- `https://*.larkoffice.com/wiki/xxx`

fetch_feishu_doc.py 能力：
- 自动获取 tenant_access_token
- wiki URL 自动解析节点 → docx token
- 完整提取所有 block 类型：标题(H1-H6)、正文、列表、代码块、引用块、QuoteContainer(type=34)、Callout(type=25)、图片(type=14/27)、分割线、Todo
- **已修复的飞书 API 坑**：
  - type=12 引用块数据在 `bullet` key 而非 `quote` key
  - type=14 有时伪装代码块（数据在 `code` 字段而非 `image`）
  - type=11 代码块有 children 子块模式
  - type=34/25 容器子块去重

#### Step 2: 处理封面图

```bash
python3 {baseDir}/scripts/image-fit.py input.jpg --mode blur -o cover.jpg
```

image-fit.py 能力：
- 输入：任意尺寸图片
- 输出：900×383 (2.35:1) 微信公众号封面图
- 4 种模式：

| 模式 | 效果 |
|------|------|
| `blur` | 高斯模糊背景 + 居中原图（默认） |
| `solid` | 纯色背景 + 居中原图 |
| `gradient` | 渐变背景 + 居中原图 |
| `crop` | 直接裁切为目标比例 |

参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `input` | 必填 | 输入图片路径 |
| `--mode` | `blur` | 处理模式 |
| `-o` | `output.jpg` | 输出路径 |
| `--bg-color` | `#ffffff` | solid 模式背景色 |
| `--quality` | `95` | JPEG 质量 |

#### Step 3: 发布到微信公众号

使用 `baoyu-post-to-wechat` skill 发布 Markdown 到草稿箱。这是外部依赖，已预装。

## Troubleshooting

| 问题 | 解决 |
|------|------|
| 飞书文档 403 | 应用需开通权限并发布上线，文档设为"组织内可阅读" |
| 找不到 wechat-api.ts | 确保 baoyu-post-to-wechat skill 已部署 |
| 封面图比例不对 | 使用 `--cover-mode crop` 直接裁切 |
| 引用块内容为空 | 已修复（通用 `_get_elements` 扫描所有 key） |
| 代码块消失 | 已修复（type=14 伪装代码块 + type=11 children 子块模式） |
| python3 没有 Pillow | 使用 `python3.11`（sandbox 中 Pillow 仅在 3.11 可用） |
