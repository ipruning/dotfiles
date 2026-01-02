#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "autocorrect-py>=2.14.0",
# ]
# ///

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import autocorrect_py

# 用于判断「这段是不是中文语境」有汉字或常见中文标点，就认为是中文语境。
_CJK_PUNCT = set("，。！？：；「」『』《》【】（）")


def _contains_han(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if (
            0x3400 <= o <= 0x4DBF  # CJK Unified Ideographs Extension A
            or 0x4E00 <= o <= 0x9FFF  # CJK Unified Ideographs
            or 0xF900 <= o <= 0xFAFF  # CJK Compatibility Ideographs
            or 0x20000
            <= o
            <= 0x2EBEF  # CJK Unified Ideographs Extension B..F（粗略覆盖）
        ):
            return True
    return False


def _has_cjk_context(text: str) -> bool:
    return _contains_han(text) or any(ch in _CJK_PUNCT for ch in text)


# 代码块保护：Markdown fenced code blocks（``` 或 ~~~）
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def _split_fenced_code_blocks(text: str) -> list[tuple[str, str]]:
    """
    把文档拆成若干段：
      - ("code", "...")：fenced code block（含开始/结束 fence 行）
      - ("text", "...")：普通文本
    """
    lines = text.splitlines(keepends=True)
    segments: list[tuple[str, str]] = []

    buf: list[str] = []
    mode: str = "text"
    close_re: re.Pattern[str] | None = None

    def flush(kind: str) -> None:
        nonlocal buf
        if buf:
            segments.append((kind, "".join(buf)))
            buf = []

    for line in lines:
        if mode == "text":
            m = _FENCE_OPEN_RE.match(line)
            if m:
                flush("text")
                fence_seq = m.group(1)
                fence_char = fence_seq[0]
                fence_len = len(fence_seq)
                close_re = re.compile(
                    rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$"
                )
                mode = "code"
                buf.append(line)
            else:
                buf.append(line)
        else:
            # code mode：原样保留
            buf.append(line)
            stripped = line.rstrip("\r\n")
            if close_re is not None and close_re.match(stripped):
                flush("code")
                mode = "text"
                close_re = None

    flush("code" if mode == "code" else "text")
    return segments


# Markdown 里反斜杠转义判断
def _is_escaped(s: str, idx: int) -> bool:
    bs = 0
    j = idx - 1
    while j >= 0 and s[j] == "\\":
        bs += 1
        j -= 1
    return (bs % 2) == 1


# 保护 span 用的占位符：使用 Unicode 私用区字符，避免被 autocorrect 改写
class _PlaceholderGen:
    def __init__(self, text: str) -> None:
        self._used = set(text)
        self._cp = 0xE000  # Private Use Area start

    def __call__(self) -> str:
        while self._cp <= 0xF8FF:
            ch = chr(self._cp)
            self._cp += 1
            if ch not in self._used:
                self._used.add(ch)
                return ch
        raise RuntimeError(
            "Too many protected spans; ran out of private-use placeholders."
        )


def _replace_spans(
    s: str, spans: list[tuple[int, int]], gen: _PlaceholderGen, mapping: dict[str, str]
) -> str:
    if not spans:
        return s
    spans = sorted(spans, key=lambda x: x[0])

    out: list[str] = []
    last = 0
    for a, b in spans:
        if a < last:
            # overlapping span：保守起见，跳过
            continue
        out.append(s[last:a])
        ph = gen()
        mapping[ph] = s[a:b]
        out.append(ph)
        last = b
    out.append(s[last:])
    return "".join(out)


# 保护：inline code spans（`...`，以及多个 backticks）
def _find_inline_code_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            tick_run = line[i:j]
            k = line.find(tick_run, j)
            if k != -1:
                spans.append((i, k + len(tick_run)))
                i = k + len(tick_run)
                continue
        i += 1
    return spans


# 保护：Markdown inline links / images：[...] (...) / ![...] (...)
# 目标是“不破坏语法”，所以整段 link/image 都原样保留
def _find_markdown_link_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)

    while i < n:
        start: int | None = None
        if line[i] == "[":
            start = i
        elif line[i] == "!" and i + 1 < n and line[i + 1] == "[":
            start = i
            i += 1  # 移到 '['，便于找 ']'
        if start is None:
            i += 1
            continue

        # 找到不被转义的 ']'
        j = i + 1
        while True:
            j = line.find("]", j)
            if j == -1:
                break
            if not _is_escaped(line, j):
                break
            j += 1
        if j == -1:
            i += 1
            continue

        k = j + 1
        while k < n and line[k] in " \t":
            k += 1
        if k >= n or line[k] != "(":
            i = j + 1
            continue

        # 解析 (...)，支持括号嵌套（URL 里偶尔会有括号）
        depth = 0
        p = k
        while p < n:
            ch = line[p]
            if ch == "(" and not _is_escaped(line, p):
                depth += 1
            elif ch == ")" and not _is_escaped(line, p):
                depth -= 1
                if depth == 0:
                    spans.append((start, p + 1))
                    i = p + 1
                    break
            p += 1
        else:
            i = j + 1

    return spans


# 保护：HTML tags（含 autolink，例如 <https://...>）
_HTML_TAG_RE = re.compile(r"<[A-Za-z!/][^>\n]*>")

# 保护：裸 URL / email
_URL_RE = re.compile(r"\bhttps?://[^\s<>()]+")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _protect_line(
    line: str,
    gen: _PlaceholderGen,
    mapping: dict[str, str],
    *,
    protect_links: bool,
    protect_html: bool,
    protect_urls: bool,
    protect_emails: bool,
) -> str:
    # 1) inline code 优先保护
    line = _replace_spans(line, _find_inline_code_spans(line), gen, mapping)

    # 2) 再保护 markdown links（避免后续把 title 里的 " 改掉导致语法坏）
    if protect_links:
        line = _replace_spans(line, _find_markdown_link_spans(line), gen, mapping)

    # 3) HTML tags
    if protect_html:
        spans = [(m.start(), m.end()) for m in _HTML_TAG_RE.finditer(line)]
        line = _replace_spans(line, spans, gen, mapping)

    # 4) 裸 URL / email
    if protect_urls:
        spans = [(m.start(), m.end()) for m in _URL_RE.finditer(line)]
        line = _replace_spans(line, spans, gen, mapping)

    if protect_emails:
        spans = [(m.start(), m.end()) for m in _EMAIL_RE.finditer(line)]
        line = _replace_spans(line, spans, gen, mapping)

    return line


def _restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    table = {ord(k): v for k, v in mapping.items()}
    return text.translate(table)


# 引号转换：双引号（“” -> 「」）
def _convert_curly_double_quotes(text: str) -> str:
    return text.replace("\u201c", "\u300c").replace("\u201d", "\u300d")


# 引号转换：单引号（‘’ -> 『』），但要避免把英文缩写/所有格里的 apostrophe（’）误转
def _is_wordish(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _is_punct(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch).startswith("P")


def _looks_like_apostrophe(text: str, i: int) -> bool:
    prev = text[i - 1] if i > 0 else ""
    nxt = text[i + 1] if i + 1 < len(text) else ""

    # don’t, Alex’s, 1980’s：夹在两个“单词字符”之间
    if prev and nxt and _is_wordish(prev) and _is_wordish(nxt):
        return True

    # ’90s：leading apostrophe（常见于年代）
    if (
        nxt
        and nxt.isdigit()
        and (not prev or prev.isspace() or _is_punct(prev) or prev in '‘『「("')
    ):
        return True

    return False


def _convert_curly_single_quotes(text: str) -> str:
    out: list[str] = []
    in_single = False

    for i, ch in enumerate(text):
        if ch == "\u2018":  # ‘
            out.append("\u300e")  # 『
            in_single = True
        elif ch == "\u2019":  # ’
            if in_single and not _looks_like_apostrophe(text, i):
                out.append("\u300f")  # 』
                in_single = False
            else:
                out.append(ch)  # apostrophe / unmatched：原样保留
        else:
            out.append(ch)

    return "".join(out)


# 可选：ASCII 双引号（"）按出现顺序交替配对成「」
def _convert_ascii_double_quotes(text: str) -> str:
    out: list[str] = []
    open_q = True
    for ch in text:
        if ch == '"':
            out.append("\u300c" if open_q else "\u300d")
            open_q = not open_q
        else:
            out.append(ch)
    return "".join(out)


# 按空行分段，段内保持换行
_BLANK_SEP_RE = re.compile(r"(\n[ \t]*\n+)")


@dataclass
class _Options:
    autocorrect: bool
    ascii_double: bool
    all_text: bool
    markdown: bool
    protect_links: bool
    protect_html: bool
    protect_urls: bool
    protect_emails: bool


def _process_text_segment(seg: str, opt: _Options) -> str:
    parts = _BLANK_SEP_RE.split(seg)
    out: list[str] = []

    for part in parts:
        if part == "":
            continue

        # 空行分隔符原样保留
        if _BLANK_SEP_RE.fullmatch(part):
            out.append(part)
            continue

        # 默认：只处理“中文语境”的段落；纯英文段落保持原样
        if not (opt.all_text or _has_cjk_context(part)):
            out.append(part)
            continue

        gen = _PlaceholderGen(part)
        mapping: dict[str, str] = {}

        protected_lines: list[str] = []
        for line in part.splitlines(keepends=True):
            protected_lines.append(
                _protect_line(
                    line,
                    gen,
                    mapping,
                    protect_links=opt.protect_links,
                    protect_html=opt.protect_html,
                    protect_urls=opt.protect_urls,
                    protect_emails=opt.protect_emails,
                )
            )
        protected = "".join(protected_lines)

        if opt.autocorrect:
            protected = autocorrect_py.format(protected)

        protected = _convert_curly_double_quotes(protected)
        protected = _convert_curly_single_quotes(protected)

        if opt.ascii_double:
            protected = _convert_ascii_double_quotes(protected)

        out.append(_restore_placeholders(protected, mapping))

    return "".join(out)


def format_text(text: str, opt: _Options) -> str:
    if not opt.markdown:
        return _process_text_segment(text, opt)

    segments = _split_fenced_code_blocks(text)
    out: list[str] = []
    for kind, seg in segments:
        if kind == "code":
            out.append(seg)
        else:
            out.append(_process_text_segment(seg, opt))
    return "".join(out)


def _read_all_input(files: list[str]) -> str:
    if not files:
        if sys.stdin.isatty():
            raise SystemExit("No input. Pipe text via stdin, or pass file paths.")
        return sys.stdin.read()

    chunks: list[str] = []
    for f in files:
        if f == "-":
            chunks.append(sys.stdin.read())
        else:
            chunks.append(Path(f).read_text(encoding="utf-8"))
    return "".join(chunks)


# autocorrect-disable
def main() -> None:
    p = argparse.ArgumentParser(
        description="Chinese prose formatter: autocorrect spacing + convert quotes to 「」『』 (Markdown-aware)."
    )
    p.add_argument(
        "--no-autocorrect",
        action="store_true",
        help="Skip autocorrect_py.format() (only do quote conversions).",
    )
    p.add_argument(
        "--ascii-double",
        action="store_true",
        help='Also convert ASCII double quotes (") to 「」 by alternating open/close (outside protected spans).',
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Process all paragraphs (including pure English paragraphs). Default: only paragraphs with Chinese context.",
    )
    p.add_argument(
        "--no-markdown",
        action="store_true",
        help="Treat input as plain text (do not protect Markdown fenced code blocks).",
    )

    p.add_argument(
        "--no-protect-links",
        action="store_true",
        help="Do not protect Markdown inline links/images.",
    )
    p.add_argument(
        "--no-protect-html",
        action="store_true",
        help="Do not protect HTML tags / autolinks.",
    )
    p.add_argument(
        "--no-protect-urls", action="store_true", help="Do not protect bare URLs."
    )
    p.add_argument(
        "--no-protect-emails",
        action="store_true",
        help="Do not protect email addresses.",
    )

    p.add_argument(
        "files",
        nargs="*",
        help="Optional files to read (use '-' for stdin). If omitted, read stdin.",
    )
    args = p.parse_args()

    opt = _Options(
        autocorrect=not args.no_autocorrect,
        ascii_double=args.ascii_double,
        all_text=args.all,
        markdown=not args.no_markdown,
        protect_links=not args.no_protect_links,
        protect_html=not args.no_protect_html,
        protect_urls=not args.no_protect_urls,
        protect_emails=not args.no_protect_emails,
    )

    text = _read_all_input(args.files)
    sys.stdout.write(format_text(text, opt))


if __name__ == "__main__":
    main()
