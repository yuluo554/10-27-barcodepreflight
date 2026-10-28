"""文件身份摘要：**行尾归一**之后再算 sha256。

为什么需要这一层（M6 实测，发布阻塞级）：同一个 blob 在不同检出下字节不同——
Windows（Git for Windows 默认 `core.autocrlf=true`）检出为 CRLF，Linux/macOS 为 LF；
`git archive` 也会按 `core.autocrlf` 转换。若直接对原始字节做 sha256，**同一份内嵌字典
会得到两个摘要**，而本项目的运行期校验是"摘要不符即 exit 3"：

  · `git archive` 导出树 → 打成 wheel → 装上后 `dictionary.load()` 抛 `DictionaryError`
    （实测：清单 `1ea02f4e…`，CRLF 文件 `84359ef1…`）；
  · 同一台 Windows 机器上 `git clone` 后直接跑（README 的"不装也能跑"那条）同样 exit 3。

口径（`data/README.md` §8.11）：**摘要面 = 把 `\\r\\n` 归一成 `\\n` 之后的字节流**。
只做行尾归一——**不做** Unicode 归一、不重排 JSON、不修剪空白；摘要仍然对内容敏感，
仍然能抓出"字典换了版本"这种事实变化。归一放在**读文件这一层**（此处），
而不是改数据文件：数据文件必须是官方快照的忠实副本。
"""

import hashlib
import io

CRLF = b"\r\n"
LF = b"\n"


def normalize_newlines(raw):
    """把 CRLF 归一成 LF（幂等；纯 LF 输入原样返回）。"""
    return raw.replace(CRLF, LF)


def sha256_of_bytes(raw):
    """对**行尾归一后**的字节算 sha256（十六进制小写）。"""
    return hashlib.sha256(normalize_newlines(raw)).hexdigest()


def read_normalized(path):
    """按二进制读文件并归一行尾；返回 `(normalized_bytes, digest)`。"""
    with io.open(path, "rb") as handle:
        raw = handle.read()
    normalized = normalize_newlines(raw)
    return normalized, hashlib.sha256(normalized).hexdigest()
