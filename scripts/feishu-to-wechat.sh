#!/usr/bin/env bash
#
# feishu-to-wechat.sh — 飞书文档一键发布微信公众号草稿箱
#
# 用法:
#   bash feishu-to-wechat.sh "https://my.feishu.cn/wiki/xxx"
#   bash feishu-to-wechat.sh "https://my.feishu.cn/wiki/xxx" --title "标题" --cover cover.jpg
#   bash feishu-to-wechat.sh "https://my.feishu.cn/wiki/xxx" --theme grace --color blue
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -z "${FEISHU_APP_ID:-}" ]; then
    if [ -f "$PROJECT_ROOT/.env" ]; then
        set -a && source "$PROJECT_ROOT/.env" && set +a
    elif [ -f "$HOME/.baoyu-skills/.env" ]; then
        set -a && source "$HOME/.baoyu-skills/.env" && set +a
    fi
fi

# ── 颜色输出 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
err()   { echo -e "${RED}[error]${NC} $*" >&2; }

# ── 定位依赖脚本（同目录优先） ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 飞书文档读取（同目录）
FETCH_PY="$SCRIPT_DIR/fetch_feishu_doc.py"
[ -f "$FETCH_PY" ] || { err "找不到 fetch_feishu_doc.py，应与本脚本在同一目录"; exit 1; }

# 封面图处理（同目录）
IMAGE_FIT="$SCRIPT_DIR/image-fit.py"
[ -f "$IMAGE_FIT" ] || { IMAGE_FIT=""; warn "找不到 image-fit.py，封面图将不做比例处理"; }

# 微信发布（本地内置）
WECHAT_API="$SCRIPT_DIR/wechat-api.ts"
[ ! -f "$WECHAT_API" ] && { err "找不到 wechat-api.ts"; exit 1; }
[ -d "$SCRIPT_DIR/node_modules" ] || { info "安装微信发布依赖..."; (cd "$SCRIPT_DIR" && bun install 2>/dev/null); }

# Bun 运行时
BUN_X=""
command -v bun >/dev/null 2>&1 && BUN_X="bun"
[ -z "$BUN_X" ] && command -v npx >/dev/null 2>&1 && BUN_X="npx -y bun"
[ -z "$BUN_X" ] && { err "需要 bun 或 npx，请安装: brew install oven-sh/bun/bun"; exit 1; }

# ── 参数解析 ──
FEISHU_URL=""
TITLE=""
SUMMARY=""
COVER=""
COVER_MODE="blur"
THEME="default"
COLOR=""
METHOD="api"
AUTHOR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --title)      TITLE="$2"; shift 2 ;;
        --summary)    SUMMARY="$2"; shift 2 ;;
        --cover)      COVER="$2"; shift 2 ;;
        --cover-mode) COVER_MODE="$2"; shift 2 ;;
        --theme)      THEME="$2"; shift 2 ;;
        --color)      COLOR="$2"; shift 2 ;;
        --method)     METHOD="$2"; shift 2 ;;
        --author)     AUTHOR="$2"; shift 2 ;;
        -*)           err "未知参数: $1"; exit 1 ;;
        *)
            if [ -z "$FEISHU_URL" ]; then
                FEISHU_URL="$1"; shift
            else
                err "多余参数: $1"; exit 1
            fi
            ;;
    esac
done

[ -z "$FEISHU_URL" ] && { err "用法: $0 <飞书文档URL> [--title 标题] [--cover 封面图] [--theme 主题]"; exit 1; }

# ── 创建工作目录 ──
WORK_DIR=$(mktemp -d "/tmp/feishu2wechat.XXXXXX")
trap "rm -rf '$WORK_DIR'" EXIT
info "工作目录: $WORK_DIR"

# ── Step 1: 读取飞书文档（自动下载图片） ──
info "正在读取飞书文档..."
python3 "$FETCH_PY" "$FEISHU_URL" --download-images > "$WORK_DIR/article.md" 2>"$WORK_DIR/fetch.log"

LINE_COUNT=$(wc -l < "$WORK_DIR/article.md")
ok "文档读取完成 ($LINE_COUNT 行)"

IMG_DIR=$(grep "图片已下载到:" "$WORK_DIR/fetch.log" 2>/dev/null | sed 's/.*图片已下载到: //' || true)

ARTICLE_PATH="$WORK_DIR/article.md"
if [ -n "$IMG_DIR" ] && [ -d "$IMG_DIR" ]; then
    info "检测到文档图片，已下载到: $IMG_DIR"
    python3 - "$WORK_DIR/article.md" "$IMG_DIR" << 'PYEOF'
import sys, re, os
path, img_dir = sys.argv[1], sys.argv[2]
content = open(path).read()
for f in os.listdir(img_dir):
    if f == 'article.md':
        continue
    token = os.path.splitext(f)[0]
    full_path = os.path.join(img_dir, f)
    # strip extension so path matches what's in markdown
    content = content.replace(f']({token})', f']({os.path.splitext(full_path)[0]})')
open(path, 'w').write(content)
PYEOF
    cp "$WORK_DIR/article.md" "$IMG_DIR/article.md"
    ARTICLE_PATH="$IMG_DIR/article.md"
    for f in "$IMG_DIR"/*; do
        case "$(file -b --mime-type "$f" 2>/dev/null)" in
            image/png)  [ "${f%.png}" != "$f" ] || [ "${f##*.}" == "$f" ] && mv "$f" "$f.png" 2>/dev/null ;;
            image/jpeg) [ "${f%.jpg}" != "$f" ] || [ "${f##*.}" == "$f" ] && mv "$f" "$f.jpg" 2>/dev/null ;;
        esac
    done
fi

# 自动提取标题
if [ -z "$TITLE" ]; then
    TITLE=$(grep -m1 '^# ' "$ARTICLE_PATH" | sed 's/^# //' || true)
    [ -z "$TITLE" ] && TITLE=$(grep -m1 "Wiki 节点:" "$WORK_DIR/fetch.log" 2>/dev/null | sed 's/.*Wiki 节点: //' | sed 's/ (type=.*//' || true)
    [ -z "$TITLE" ] && TITLE="未命名文章"
    info "自动提取标题: $TITLE"
fi

# 自动生成摘要
if [ -z "$SUMMARY" ]; then
    SUMMARY=$(grep -v '^#' "$ARTICLE_PATH" | grep -v '^\[信息\]' | grep -v '^$' | head -3 | tr '\n' ' ' | cut -c1-120)
    [ -z "$SUMMARY" ] && SUMMARY="$TITLE"
    info "自动生成摘要: ${SUMMARY:0:60}..."
fi

# ── Step 2: 处理封面图 ──
COVER_FINAL=""

    if [ -n "$COVER" ] && [ -f "$COVER" ]; then
        info "处理用户提供的封面图..."
        COVER_FINAL="$WORK_DIR/cover_wechat.jpg"
        if [ -n "$IMAGE_FIT" ]; then
            python3 "$IMAGE_FIT" "$COVER" --mode "$COVER_MODE" -o "$COVER_FINAL"
            ok "封面图已处理 (${COVER_MODE}模式, 2.35:1)"
        else
            cp "$COVER" "$COVER_FINAL"
            warn "image-fit 不可用，封面图未做比例处理"
        fi
    else
        FIRST_IMG=$(python3 -c "
import re, sys, os
c = open('$ARTICLE_PATH').read()
m = re.search(r'!\[[^\]]*\]\(([^)]+)\)', c)
if m:
    p = m.group(1)
    # strip extension since actual files have .png/.jpg
    base = os.path.splitext(p)[0]
    for ext in ('.png', '.jpg', '.jpeg'):
        if os.path.exists(base + ext):
            print(base + ext)
            break
        elif os.path.exists(p):
            print(p)
            break
" 2>/dev/null || true)
        if [ -n "$FIRST_IMG" ] && [ -f "$FIRST_IMG" ]; then
            info "使用文档第一张图片作为封面: $FIRST_IMG"
            if [ -n "$IMAGE_FIT" ]; then
                COVER_FINAL="$WORK_DIR/cover_wechat.jpg"
                python3 "$IMAGE_FIT" "$FIRST_IMG" --mode "$COVER_MODE" -o "$COVER_FINAL" && ok "封面图已处理 (${COVER_MODE}模式, 2.35:1)"
            fi
        fi

    if [ -z "$COVER_FINAL" ] || [ ! -f "$COVER_FINAL" ]; then
        warn "未找到封面图，微信公众号文章需要封面图"
        warn "请使用 --cover 参数指定封面图"
    fi
fi

# ── Step 3: 发布到微信公众号 ──
info "正在推送到微信公众号草稿箱..."

TITLE_FILE="$WORK_DIR/wechat_title.txt"
SUMMARY_FILE="$WORK_DIR/wechat_summary.txt"
echo -n "$TITLE" > "$TITLE_FILE"
echo -n "$SUMMARY" > "$SUMMARY_FILE"

CMD_ARGS=("$ARTICLE_PATH" "--theme" "$THEME")
[ -n "$TITLE" ]        && CMD_ARGS+=("--title" "@$TITLE_FILE")
[ -n "$SUMMARY" ]     && CMD_ARGS+=("--summary" "@$SUMMARY_FILE")
[ -n "$COVER_FINAL" ]  && [ -f "$COVER_FINAL" ] && CMD_ARGS+=("--cover" "$COVER_FINAL")
[ -n "$COLOR" ]        && CMD_ARGS+=("--color" "$COLOR")
[ -n "$AUTHOR" ]      && CMD_ARGS+=("--author" "$AUTHOR")

if [ "$METHOD" = "api" ]; then
    $BUN_X "$WECHAT_API" "${CMD_ARGS[@]}" 2>"$WORK_DIR/publish.log"
else
    WECHAT_BROWSER="$(dirname "$WECHAT_API")/wechat-article.ts"
    $BUN_X "$WECHAT_BROWSER" --markdown "$WORK_DIR/article.md" --theme "$THEME" ${COLOR:+--color "$COLOR"} 2>"$WORK_DIR/publish.log"
fi

PUBLISH_EXIT=$?

# ── Step 4: 报告结果 ──
echo ""
if [ $PUBLISH_EXIT -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ 飞书文档已推送到微信公众号草稿箱！${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  来源:  $FEISHU_URL"
    echo "  标题:  $TITLE"
    echo "  摘要:  ${SUMMARY:0:60}..."
    echo "  封面:  ${COVER_FINAL:-未设置} ($COVER_MODE 模式)"
    echo "  主题:  $THEME ${COLOR:+(配色: $COLOR)}"
    echo "  方式:  $METHOD"
    echo ""
    echo "  → 登录 https://mp.weixin.qq.com"
    echo "    进入「内容管理」→「草稿箱」查看和发布"
    echo ""
else
    err "发布失败，退出码: $PUBLISH_EXIT"
    [ -f "$WORK_DIR/publish.log" ] && echo "错误日志:" && cat "$WORK_DIR/publish.log"
    exit 1
fi
