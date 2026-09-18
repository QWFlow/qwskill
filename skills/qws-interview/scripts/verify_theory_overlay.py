#!/usr/bin/env python3
"""Verify that a theory overlay did not change a frozen article body."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path


THEORY_HEADING_RE = re.compile(r"^## 理论注释[ \t]*$", re.MULTILINE)
INLINE_RE = re.compile(r"（\[([^\]\n]+)\]\(#(theory-[A-Za-z0-9_-]+)\)）")
ANCHOR_RE = re.compile(r"<a\s+id=[\"'](theory-[^\"']+)[\"']\s*></a>")


class OverlayError(ValueError):
    """Raised when the final document is not a pure theory overlay."""


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def split_final(text: str) -> tuple[str, str]:
    matches = list(THEORY_HEADING_RE.finditer(text))
    if len(matches) > 1:
        raise OverlayError("发现多个“## 理论注释”章节。")
    if not matches:
        return text, ""
    match = matches[0]
    body = text[: match.start()].rstrip() + "\n"
    return body, text[match.start() :]


def verify_overlay(baseline: str, final: str) -> None:
    final_body, notes = split_final(normalize(final))
    inline_ids = [match.group(2) for match in INLINE_RE.finditer(final_body)]
    anchor_ids = ANCHOR_RE.findall(notes)

    if len(inline_ids) != len(set(inline_ids)):
        raise OverlayError("同一理论锚点在正文里被重复标注。")
    if len(anchor_ids) != len(set(anchor_ids)):
        raise OverlayError("理论注释中存在重复锚点。")
    if inline_ids != anchor_ids:
        missing_notes = sorted(set(inline_ids) - set(anchor_ids))
        unused_notes = sorted(set(anchor_ids) - set(inline_ids))
        raise OverlayError(
            "正文与注释锚点的集合或出现顺序不一致；"
            f"缺少注释={missing_notes}，未使用注释={unused_notes}。"
        )

    restored = INLINE_RE.sub("", final_body)
    expected = normalize(baseline)
    actual = normalize(restored)
    if actual != expected:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile="frozen-baseline",
                tofile="restored-final",
            )
        )
        raise OverlayError("移除理论覆盖后无法还原冻结正文：\n" + diff)


def self_test() -> None:
    baseline = "# 示例\n\n第一个判断。\n\n第二个判断。\n"
    valid = (
        "# 示例\n\n第一个判断。（[理论甲](#theory-1)）\n\n第二个判断。\n\n"
        "## 理论注释\n\n<a id=\"theory-1\"></a>\n### 理论甲\n"
    )
    verify_overlay(baseline, valid)
    invalid = valid.replace("第二个判断。", "第二个判断。新增理论推导。")
    try:
        verify_overlay(baseline, invalid)
    except OverlayError:
        pass
    else:
        raise AssertionError("自测未能拦截正文改动。")
    print("self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--final", dest="final_path", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if args.baseline is None or args.final_path is None:
        parser.error("--baseline 和 --final 必须同时提供。")

    try:
        verify_overlay(
            args.baseline.read_text(encoding="utf-8"),
            args.final_path.read_text(encoding="utf-8"),
        )
    except (OSError, OverlayError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: 理论覆盖未改动冻结正文，锚点一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
