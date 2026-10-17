"""JSONC（带注释的 JSON）解析。

MaaFramework 的 pipeline / interface 文件允许写注释，也允许尾随逗号，
标准库 `json.loads` 不能直接解析。这里用一个字符级状态机做清洗：

* 去掉 `//` 行注释与 `/* */` 块注释（字符串内的内容原样保留）；
* 去掉对象/数组末尾多余逗号；
* 清洗时保留换行，保证报错行号与原文件一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsoncError(ValueError):
    """清洗后仍无法解析时抛出，附带文件位置。"""

    def __init__(self, message: str, path: Path | None = None, lineno: int | None = None) -> None:
        location = ""
        if path is not None:
            location = f"{path}"
            if lineno is not None:
                location += f":{lineno}"
            location += ": "
        super().__init__(location + message)


def _strip_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    length = len(text)
    in_string = False
    while i < length:
        char = text[i]
        if in_string:
            out.append(char)
            if char == "\\" and i + 1 < length:
                out.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue

        if char == "/" and i + 1 < length:
            nxt = text[i + 1]
            if nxt == "/":
                while i < length and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                    if text[i] == "\n":
                        out.append("\n")
                    i += 1
                i += 2
                continue

        out.append(char)
        i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    i = 0
    length = len(text)
    in_string = False
    while i < length:
        char = text[i]
        if in_string:
            out.append(char)
            if char == "\\" and i + 1 < length:
                out.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue

        if char == ",":
            # 向前看：跳过空白与换行，若下一个有效字符是 } 或 ] 则丢弃该逗号
            j = i + 1
            while j < length and text[j] in " \t\r\n":
                j += 1
            if j < length and text[j] in "}]":
                out.append(" ")
                i += 1
                continue

        out.append(char)
        i += 1
    return "".join(out)


def loads(text: str, path: Path | None = None) -> Any:
    cleaned = _strip_trailing_commas(_strip_comments(text))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise JsoncError(error.msg, path=path, lineno=error.lineno) from error


def load_jsonc(path: str | Path) -> Any:
    file_path = Path(path)
    return loads(file_path.read_text(encoding="utf-8"), path=file_path)
