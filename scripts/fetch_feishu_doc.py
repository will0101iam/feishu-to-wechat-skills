#!/usr/bin/env python3
"""
fetch_feishu_doc.py — 通过飞书开放 API 读取文档纯文本内容

使用方式:
    python3 fetch_feishu_doc.py "https://xxx.larkoffice.com/docx/xxx"
    python3 fetch_feishu_doc.py "https://xxx.larkoffice.com/wiki/xxx"

环境变量（二选一）:
    FEISHU_APP_ID + FEISHU_APP_SECRET    — 自动获取 tenant_access_token
    FEISHU_TOKEN                          — 直接指定 tenant_access_token

输出: 文档纯文本内容到 stdout，可管道给 render_slides.py

依赖: 纯 Python 标准库，零依赖
"""

import json
import os
import re
import ssl
import sys
import urllib.request
import urllib.error
import urllib.parse

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── 飞书 API 基地址 ──────────────────────────────────────
API_BASE = "https://open.feishu.cn/open-apis"


def _req(method: str, url: str, headers: dict = None, body: dict = None) -> dict:
    """发起 HTTP 请求，返回解析后的 JSON"""
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[错误] HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


def get_tenant_token(app_id: str, app_secret: str) -> str:
    """通过 app_id + app_secret 获取 tenant_access_token"""
    url = f"{API_BASE}/auth/v3/tenant_access_token/internal"
    resp = _req("POST", url, body={
        "app_id": app_id,
        "app_secret": app_secret
    })
    if resp.get("code", -1) != 0:
        print(f"[错误] 获取 token 失败: {resp}", file=sys.stderr)
        sys.exit(1)
    return resp["tenant_access_token"]


def parse_feishu_url(url: str) -> tuple:
    """
    解析飞书文档 URL，返回 (doc_type, token)
    支持: /docx/XXX, /docs/XXX, /wiki/XXX
    """
    # 标准化 URL
    url = url.strip().rstrip("/")

    # /wiki/TOKEN
    m = re.search(r'/wiki/([A-Za-z0-9]+)', url)
    if m:
        return ("wiki", m.group(1))

    # /docx/TOKEN 或 /docs/TOKEN
    m = re.search(r'/(?:docx|docs)/([A-Za-z0-9]+)', url)
    if m:
        return ("docx", m.group(1))

    print(f"[错误] 无法解析 URL: {url}", file=sys.stderr)
    print("支持的格式: /docx/TOKEN, /docs/TOKEN, /wiki/TOKEN", file=sys.stderr)
    sys.exit(1)


def resolve_wiki_to_docx(token: str, headers: dict) -> str:
    """将 wiki token 解析为底层文档的 document_id"""
    url = f"{API_BASE}/wiki/v2/spaces/get_node?token={token}"
    resp = _req("GET", url, headers=headers)
    if resp.get("code", -1) != 0:
        print(f"[错误] 解析 wiki 节点失败: {resp.get('msg', resp)}", file=sys.stderr)
        sys.exit(1)
    node = resp.get("data", {}).get("node", {})
    obj_type = node.get("obj_type", "")
    obj_token = node.get("obj_token", "")
    title = node.get("title", "")

    if obj_type not in ("docx", "doc"):
        print(f"[警告] Wiki 节点类型为 {obj_type}（标题: {title}），"
              f"仅支持 docx/doc 类型", file=sys.stderr)

    print(f"[信息] Wiki 节点: {title} (type={obj_type}, token={obj_token})",
          file=sys.stderr)
    return obj_token


def get_doc_raw_content(document_id: str, headers: dict) -> str:
    """获取文档纯文本内容"""
    url = f"{API_BASE}/docx/v1/documents/{document_id}/raw_content"
    resp = _req("GET", url, headers=headers)
    if resp.get("code", -1) != 0:
        msg = resp.get("msg", "")
        print(f"[错误] 获取文档内容失败 (code={resp.get('code')}): {msg}",
              file=sys.stderr)
        if "forbidden" in msg.lower() or resp.get("code") == 1770032:
            print("\n可能的原因:", file=sys.stderr)
            print("  1. 应用未获得文档权限 → 给应用添加 docx:document:readonly 权限",
                  file=sys.stderr)
            print("  2. 文档未对应用开放 → 文档分享设置中添加应用为协作者",
                  file=sys.stderr)
            print("  3. 应用未发布上线 → 飞书开放平台提交发布并审批",
                  file=sys.stderr)
        sys.exit(1)
    return resp.get("data", {}).get("content", "")


def get_doc_blocks(document_id: str, headers: dict) -> list:
    """获取文档所有块（用于更丰富的 Markdown 转换）"""
    blocks = []
    page_token = ""
    while True:
        url = f"{API_BASE}/docx/v1/documents/{document_id}/blocks?page_size=500"
        if page_token:
            url += f"&page_token={page_token}"
        resp = _req("GET", url, headers=headers)
        if resp.get("code", -1) != 0:
            print(f"[错误] 获取文档块失败: {resp.get('msg', resp)}", file=sys.stderr)
            sys.exit(1)
        data = resp.get("data", {})
        items = data.get("items", [])
        blocks.extend(items)
        if not data.get("has_more", False):
            break
        page_token = data.get("page_token", "")
    return blocks


def blocks_to_markdown(blocks: list) -> str:
    """将飞书文档块转换为 Markdown 文本"""
    lines = []
    block_map = {b["block_id"]: b for b in blocks}

    # 收集所有容器块（type=34 QuoteContainer, type=25 Callout）的子块 ID，避免重复处理
    container_children = set()
    for b in blocks:
        if b.get("block_type") in (34, 11):
            for cid in b.get("children", []):
                container_children.add(cid)
        if b.get("block_type") == 24:
            for cid in b.get("children", []):
                container_children.add(cid)

    def _extract_text(elements: list) -> str:
        """从 text elements 提取文字"""
        parts = []
        for el in elements:
            if "text_run" in el:
                tr = el["text_run"]
                content = tr.get("content", "")
                style = tr.get("text_element_style", {})
                if style.get("bold"):
                    content = f"**{content}**"
                if style.get("italic"):
                    content = f"*{content}*"
                if style.get("strikethrough"):
                    content = f"~~{content}~~"
                if style.get("inline_code"):
                    content = f"`{content}`"
                link = style.get("link", {})
                if link.get("url"):
                    url = urllib.parse.unquote(link["url"])
                    content = f"[{content}]({url})"
                parts.append(content)
            elif "mention_doc" in el:
                md = el["mention_doc"]
                url = md.get("url", "")
                parts.append(f"[文档链接]({url})")
            elif "equation" in el:
                parts.append(f"${el['equation'].get('content', '')}$")
        return "".join(parts)

    def _get_elements(block: dict) -> list:
        """
        通用提取 elements —— 飞书 API 返回的数据 key 不固定，
        可能是 text/bullet/ordered/quote/todo/heading1/heading2/... 等，
        这里按优先级尝试所有可能的 key。
        """
        # 优先级：直接匹配 block_type 对应的 key，然后 fallback 扫描
        for key in list(block.keys()):
            if key in ("block_id", "block_type", "parent_id", "children"):
                continue
            val = block[key]
            if isinstance(val, dict) and "elements" in val:
                return val["elements"]
        return []

    for block in blocks:
        bt = block.get("block_type", 0)

        if bt == 1:
            continue

        if block["block_id"] in container_children:
            continue

        if bt == 2:
            # 文本块
            elements = _get_elements(block)
            text = _extract_text(elements)
            if text.strip():
                lines.append(text)
            else:
                lines.append("")

        elif bt in (3, 4, 5, 22, 23):
            level_map = {3: 1, 4: 2, 5: 3, 22: 4, 23: 5}
            level = level_map.get(bt, 3)
            elements = _get_elements(block)
            text = _extract_text(elements)
            prefix = "#" * level
            lines.append(f"{prefix} {text}")

        elif bt == 9:
            # 无序列表
            elements = _get_elements(block)
            text = _extract_text(elements)
            lines.append(f"- {text}")

        elif bt == 10:
            # 有序列表
            elements = _get_elements(block)
            text = _extract_text(elements)
            lines.append(f"1. {text}")

        elif bt == 11:
            # 代码块 — 两种结构:
            # A) elements 直接在 code 字段内
            # B) code 字段只有 style，实际内容在 children 子块中
            code_data = block.get("code", {})
            elements = _get_elements(block)
            text = _extract_text(elements)

            # 如果直接提取为空，尝试从 children 子块中收集代码行
            if not text.strip() and block.get("children"):
                code_lines = []
                for cid in block["children"]:
                    child = block_map.get(cid)
                    if child:
                        child_elems = _get_elements(child)
                        child_text = _extract_text(child_elems)
                        code_lines.append(child_text)
                text = "\n".join(code_lines)

            lang = code_data.get("style", {}).get("language", "")
            lang_map = {
                1: "python", 2: "java", 3: "javascript", 4: "go",
                5: "c", 6: "cpp", 7: "csharp", 8: "ruby",
                9: "swift", 10: "kotlin", 11: "rust", 12: "typescript",
                13: "bash", 14: "sql", 15: "html", 16: "css",
                17: "json", 18: "yaml", 19: "xml", 20: "markdown",
                22: "php"
            }
            lang_str = lang_map.get(lang, "")
            lines.append(f"```{lang_str}")
            lines.append(text)
            lines.append("```")

        elif bt == 12:
            # 引用块 — 飞书 API 的 key 可能是 quote/bullet/text 等，用通用提取
            elements = _get_elements(block)
            text = _extract_text(elements)
            if text.strip():
                lines.append(f"> {text}")

        elif bt == 13:
            elements = _get_elements(block)
            text = _extract_text(elements)
            lines.append(f"1. {text}")

        elif bt in (14, 27):
            # 图片（14=普通图片, 27=高清图片）
            # 注意：飞书有时把代码块存成 type=14，数据在 code 字段中
            img_token = block.get("image", {}).get("token", "")
            if img_token:
                lines.append(f"![image]({img_token})")
            elif block.get("code") and block["code"].get("elements"):
                # 实际上是代码块，伪装成了 type=14
                code_data = block["code"]
                elements = code_data.get("elements", [])
                text = _extract_text(elements)
                lang = code_data.get("style", {}).get("language", "")
                lang_map = {
                    1: "python", 2: "java", 3: "javascript", 4: "go",
                    5: "c", 6: "cpp", 7: "csharp", 8: "ruby",
                    9: "swift", 10: "kotlin", 11: "rust", 12: "typescript",
                    13: "bash", 14: "sql", 15: "html", 16: "css",
                    17: "json", 18: "yaml", 19: "xml", 20: "markdown",
                    22: "php"
                }
                lang_str = lang_map.get(lang, "plaintext")
                lines.append(f"```{lang_str}")
                lines.append(text)
                lines.append("```")

        elif bt == 17:
            # Todo / Checkbox
            elements = _get_elements(block)
            text = _extract_text(elements)
            # done 状态可能在多个 key 下
            done = False
            for key in block:
                val = block[key]
                if isinstance(val, dict) and "style" in val:
                    done = val["style"].get("done", False)
                    break
            check = "x" if done else " "
            lines.append(f"- [{check}] {text}")

        elif bt == 25:
            children_ids = block.get("children", [])
            for cid in children_ids:
                child = block_map.get(cid)
                if child and cid not in container_children:
                    child_elems = _get_elements(child)
                    child_text = _extract_text(child_elems)
                    if child_text.strip():
                        lines.append(child_text)
                    elif child.get("block_type") in (14, 27):
                        img_token = child.get("image", {}).get("token", "")
                        if img_token:
                            lines.append(f"![image]({img_token})")
                    elif child.get("block_type") == 13:
                        lines.append("1. " + (_extract_text(child_elems) if child_elems else ""))

        elif bt == 34:
            # QuoteContainer（引用容器/高亮块）
            # 子块内容需要递归处理
            children_ids = block.get("children", [])
            for cid in children_ids:
                child = block_map.get(cid)
                if child:
                    elements = _get_elements(child)
                    text = _extract_text(elements)
                    if text.strip():
                        lines.append(f"> {text}")

        else:
            # 其他类型 — 尝试提取文字
            elements = _get_elements(block)
            if elements:
                text = _extract_text(elements)
                if text.strip():
                    lines.append(text)

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="通过飞书开放 API 读取文档内容",
        epilog="示例: python3 fetch_feishu_doc.py https://xxx.larkoffice.com/wiki/xxx"
    )
    parser.add_argument("url", help="飞书文档 URL")
    parser.add_argument("--raw", action="store_true",
                        help="输出纯文本（默认输出 Markdown）")
    parser.add_argument("--app-id", default=None,
                        help="App ID (或设 FEISHU_APP_ID 环境变量)")
    parser.add_argument("--app-secret", default=None,
                        help="App Secret (或设 FEISHU_APP_SECRET 环境变量)")
    parser.add_argument("--token", default=None,
                        help="直接指定 tenant_access_token (或设 FEISHU_TOKEN 环境变量)")
    parser.add_argument("--download-images", action="store_true",
                        help="下载图片 token 为本地文件并替换路径")
    args = parser.parse_args()

    # 获取凭证
    token = args.token or os.environ.get("FEISHU_TOKEN", "")
    if not token:
        app_id = args.app_id or os.environ.get("FEISHU_APP_ID", "")
        app_secret = args.app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        if not app_id or not app_secret:
            print("[错误] 请设置环境变量 FEISHU_APP_ID + FEISHU_APP_SECRET，"
                  "或 FEISHU_TOKEN", file=sys.stderr)
            print("\n例:", file=sys.stderr)
            print("  export FEISHU_APP_ID=cli_xxx", file=sys.stderr)
            print("  export FEISHU_APP_SECRET=xxx", file=sys.stderr)
            sys.exit(1)
        print("[信息] 正在获取 tenant_access_token...", file=sys.stderr)
        token = get_tenant_token(app_id, app_secret)
        print("[信息] token 获取成功", file=sys.stderr)

    headers = {"Authorization": f"Bearer {token}"}

    # 解析 URL
    doc_type, doc_token = parse_feishu_url(args.url)
    print(f"[信息] 文档类型: {doc_type}, token: {doc_token}", file=sys.stderr)

    # Wiki → 底层 docx token
    if doc_type == "wiki":
        document_id = resolve_wiki_to_docx(doc_token, headers)
    else:
        document_id = doc_token

    if args.raw:
        # 纯文本模式
        content = get_doc_raw_content(document_id, headers)
        print(content)
    else:
        # Markdown 模式（默认）
        print("[信息] 正在获取文档块...", file=sys.stderr)
        blocks = get_doc_blocks(document_id, headers)
        print(f"[信息] 共 {len(blocks)} 个块", file=sys.stderr)
        md = blocks_to_markdown(blocks)

        if args.download_images:
            import tempfile, re
            work_dir = tempfile.mkdtemp(prefix="feishu_img_")
            downloaded = {}
            for tok in re.findall(r'!\[[^\]]*\]\(([A-Za-z0-9_]+)\)', md):
                if tok in downloaded:
                    continue
                out_path = os.path.join(work_dir, tok)
                url = f"{API_BASE}/drive/v1/medias/{tok}/download"
                try:
                    data_req = urllib.request.Request(url, data=b"", method="GET")
                    data_req.add_header("Authorization", f"Bearer {token}")
                    with urllib.request.urlopen(data_req, context=_SSL_CTX, timeout=30) as r:
                        with open(out_path, "wb") as f:
                            f.write(r.read())
                        downloaded[tok] = out_path
                        print(f"[信息] 下载图片: {tok}", file=sys.stderr)
                except Exception as e:
                    print(f"[警告] 图片下载失败 {tok}: {e}", file=sys.stderr)
            for tok, path in downloaded.items():
                md = md.replace(f"({tok})", f"({path})")
            print(f"[信息] 图片已下载到: {work_dir}", file=sys.stderr)

        print(md)


if __name__ == "__main__":
    main()
