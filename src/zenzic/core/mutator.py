# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""AST Mutation API and Engine."""

from __future__ import annotations

import copy
from typing import Protocol

from zenzic.core import regex
from zenzic.core.ast import CodeSpanNode, LinkNode, Node, TextNode


_FENCE_OPEN_RE = regex.compile(r"^(?P<fence>[`~]{3,})(?P<info>.*)$")


class Mutation(Protocol):
    """Protocol for AST mutations."""

    def apply(self, node: Node) -> bool:
        """Apply the mutation to the given node in-place.

        Returns True if a mutation occurred, False otherwise.
        """
        ...


def _has_text_content(node: Node) -> bool:
    """Returns True if the node contains any non-whitespace text or code content recursively."""
    if isinstance(node, TextNode):
        stripped = node.text
        for char in ("*", "_", "~", "`"):
            stripped = stripped.replace(char, "")
        return bool(stripped.strip())
    if isinstance(node, CodeSpanNode):
        stripped = node.code
        for char in ("*", "_", "~", "`"):
            stripped = stripped.replace(char, "")
        return bool(stripped.strip())
    return any(_has_text_content(child) for child in node.children)


class EmptyLinkTextMutation:
    """Z108 Auto-Fix: Injects placeholder 'TODO' text into empty links."""

    def apply(self, node: Node) -> bool:
        mutated = False
        if isinstance(node, LinkNode):
            is_empty = not any(_has_text_content(child) for child in node.children)

            if is_empty:
                node.children = [TextNode(text="TODO")]
                mutated = True

        for child in node.children:
            if self.apply(child):
                mutated = True

        return mutated


class UntaggedCodeBlockMutation:
    """Z505 Auto-Fix: Injects 'text' language specifier into untagged fenced code blocks."""

    def apply(self, node: Node) -> bool:
        from zenzic.core.ast import Document
        from zenzic.core.parser import parse, serialize

        if isinstance(node, Document):
            text = serialize(node)
            lines = text.splitlines(keepends=True)
            new_lines = []
            mutated = False
            inside = False
            open_char = ""
            open_count = 0

            for line in lines:
                line_clean = line.rstrip("\r\n")
                m = _FENCE_OPEN_RE.match(line_clean)
                if not inside:
                    if m:
                        fence = m.group("fence")
                        info = m.group("info").strip()
                        has_tag = bool(info)
                        inside = True
                        open_char = fence[0]
                        open_count = len(fence)
                        if not has_tag:
                            rest = line[len(fence) :].lstrip(" \t")
                            line = f"{fence}text{rest}"
                            mutated = True
                else:
                    if m:
                        fence = m.group("fence")
                        info = m.group("info").strip()
                        if fence[0] == open_char and len(fence) >= open_count and not info:
                            inside = False
                            open_char = ""
                            open_count = 0

                new_lines.append(line)

            if mutated:
                new_doc = parse("".join(new_lines))
                node.children = new_doc.children
                return True
            return False

        mutated = False
        for child in node.children:
            if self.apply(child):
                mutated = True
        return mutated


class Mutator:
    """Engine that applies a list of Mutations to an AST."""

    def __init__(self, mutations: list[Mutation]) -> None:
        self.mutations = mutations

    def mutate(self, ast: Node) -> tuple[Node, bool]:
        """Applies all mutations to a deep copy of the AST.

        Returns a tuple of (new_ast, changed).
        """
        new_ast = copy.deepcopy(ast)
        changed = False
        for mutation in self.mutations:
            if mutation.apply(new_ast):
                changed = True
        return new_ast, changed


_DATA_IGNORE_RE = regex.compile(r"\bdata-zenzic-ignore\b\s*(=\s*\"[^\"]*\"\s*|=\s*'[^']*'\s*)?")
_WS_COLLAPSE_RE = regex.compile(r"\s+")


class DeadSuppressionMutation:
    """Z603 Auto-Fix: Strips dead zenzic:ignore comments from source code."""

    def __init__(self, dead_lines: set[int]) -> None:
        self.dead_lines = dead_lines
        self.current_line = 1

    def apply(self, node: Node) -> bool:
        mutated = False
        from zenzic.core.ast import CodeSpanNode, LinkNode, TextNode

        if isinstance(node, TextNode):
            text = node.text
            lines = text.splitlines(keepends=True)
            new_lines = []
            node_line_start = self.current_line

            for i, line in enumerate(lines):
                line_no = node_line_start + i
                if line_no in self.dead_lines:
                    # 1. Check for standard zenzic:ignore comment
                    from zenzic.core.suppressions import _SUPPRESS_RE

                    m = _SUPPRESS_RE.search(line)
                    if m:
                        comment_text = m.group(0)
                        stripped_line = line.replace(comment_text, "")
                        if not stripped_line.strip():
                            line = ""
                            mutated = True
                        else:
                            line = stripped_line
                            if stripped_line.endswith("\n") and not line.endswith("\n"):
                                line = line.rstrip() + "\n"
                            mutated = True

                    # 2. Check for dead data-zenzic-ignore HTML attribute
                    from zenzic.core.validator import _RE_POLY_TAG

                    new_line = ""
                    last_idx = 0
                    for tag_match in _RE_POLY_TAG.finditer(line):
                        attrs_str = tag_match.group("attrs")
                        tag = tag_match.group(1)
                        if "data-zenzic-ignore" in attrs_str:
                            new_attrs = _DATA_IGNORE_RE.sub("", attrs_str)
                            new_attrs = _WS_COLLAPSE_RE.sub(" ", new_attrs).strip()
                            if new_attrs:
                                new_tag = f"<{tag} {new_attrs}>"
                            else:
                                new_tag = f"<{tag}>"
                            new_line += line[last_idx : tag_match.start()] + new_tag
                            last_idx = tag_match.end()
                            mutated = True
                    if mutated:
                        new_line += line[last_idx:]
                        line = new_line

                new_lines.append(line)

            self.current_line += text.count("\n")
            if mutated:
                node.text = "".join(new_lines)

        elif isinstance(node, CodeSpanNode):
            self.current_line += node.code.count("\n")
        elif isinstance(node, LinkNode):
            for child in node.children:
                if self.apply(child):
                    mutated = True
            self.current_line += node.url.count("\n")
        else:
            for child in node.children:
                if self.apply(child):
                    mutated = True

        return mutated


_BARE_URL_MUTATOR_RE = regex.compile(r"https?://[^\s<>`\"'\[\]\(\)]+")


class BareUrlMutation:
    """Z515 Auto-Fix: Injects angle brackets around bare URLs in prose."""

    def apply(self, node: Node) -> bool:
        from zenzic.core.ast import CodeSpanNode, LinkNode, TextNode

        mutated = False
        if isinstance(node, TextNode):
            text = node.text
            if "http://" in text or "https://" in text:
                url_matches = list(_BARE_URL_MUTATOR_RE.finditer(text))
                if url_matches:
                    new_text = ""
                    last_idx = 0
                    for match in url_matches:
                        start, end = match.span()
                        raw_url = match.group(0)
                        if start > 0 and text[start - 1] in ("<", "[", "("):
                            continue
                        if end < len(text) and text[end] in (">", "]", ")"):
                            continue
                        url = raw_url.rstrip(".,;:!?")
                        trailing_punct = raw_url[len(url) :]
                        new_text += text[last_idx:start] + f"<{url}>{trailing_punct}"
                        last_idx = end
                        mutated = True
                    if mutated:
                        new_text += text[last_idx:]
                        node.text = new_text

        elif isinstance(node, LinkNode | CodeSpanNode):
            return False
        else:
            for child in node.children:
                if self.apply(child):
                    mutated = True

        return mutated


class HeadingPunctuationMutation:
    """Z517 Auto-Fix: Strips trailing punctuation (., :, ;) from headings."""

    def apply(self, node: Node) -> bool:
        from zenzic.core.ast import Heading, TextNode

        mutated = False
        if isinstance(node, Heading):
            for child in reversed(node.children):
                if isinstance(child, TextNode):
                    content = child.text
                    has_newline = content.endswith("\n")
                    clean = content.rstrip("\r\n")
                    if clean and clean[-1] in {".", ":", ";"}:
                        clean = clean[:-1]
                        child.text = clean + ("\n" if has_newline else "")
                        mutated = True
                        break
                    elif clean:
                        break

        for child in node.children:
            if self.apply(child):
                mutated = True

        return mutated


_LIST_MARKER_MUTATION_RE = regex.compile(r"^(\*|-|\+|\d+\.|\d+\))\s+")
_CONJUNCTION_MUTATION_RE = regex.compile(r"^(and|or|but|nor|so|yet)\s+", regex.IGNORECASE)


class MalformedListMutation:
    """Z520 Auto-Fix: Transforms fake/malformed paragraph lists into valid Markdown bullet lists."""

    def apply(self, node: Node) -> bool:
        from zenzic.core.ast import Paragraph
        from zenzic.core.parser import parse, serialize

        if isinstance(node, Paragraph):
            text = serialize(node)
            lines = text.splitlines(keepends=True)
            if len(lines) < 3:
                return False

            mutated = False
            new_lines = []
            i = 0
            n = len(lines)
            while i < n:
                run = []
                open_parens = 0
                j = i
                while j < n:
                    raw_line = lines[j]
                    clean = raw_line.rstrip("\r\n").strip()
                    if not clean:
                        break
                    if (
                        _LIST_MARKER_MUTATION_RE.match(clean)
                        or clean.startswith("#")
                        or clean.startswith("|")
                        or clean.startswith("```")
                        or clean.startswith("~~~")
                    ):
                        break

                    open_parens += clean.count("(") - clean.count(")")
                    if open_parens > 0 or clean.startswith("(") or clean.endswith(")"):
                        break

                    if clean.endswith(";") or clean.endswith(","):
                        if clean.endswith(",") and _CONJUNCTION_MUTATION_RE.match(clean):
                            break
                        run.append(j)
                        j += 1
                    elif (
                        len(run) >= 2
                        and clean.endswith(".")
                        and not _CONJUNCTION_MUTATION_RE.match(clean)
                    ):
                        run.append(j)
                        j += 1
                        break
                    else:
                        break

                punct_count = sum(
                    1
                    for idx in run
                    if lines[idx].rstrip("\r\n").strip().endswith(";")
                    or lines[idx].rstrip("\r\n").strip().endswith(",")
                )
                if len(run) >= 3 and punct_count >= 3:
                    mutated = True
                    for k in range(i, j):
                        line_content = lines[k]
                        l_stripped = line_content.lstrip(" \t")
                        indent = line_content[: len(line_content) - len(l_stripped)]
                        new_lines.append(f"{indent}- {l_stripped}")
                    i = j
                else:
                    new_lines.append(lines[i])
                    i += 1

            if mutated:
                new_text = "".join(new_lines)
                new_doc = parse(new_text)
                node.children = new_doc.children
                return True

        mutated = False
        for child in node.children:
            if self.apply(child):
                mutated = True

        return mutated
