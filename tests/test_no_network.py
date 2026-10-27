"""纯本地零网络：AST 扫网络相关的 import 与调用。

判据取 **AST 节点**而不是子串——注释/docstring 里提到 `urllib` 不应误红
（`references/methodology-binding.md` 假门族 ⑱）。
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "bpreflight"

FORBIDDEN_MODULES = (
    "socket",
    "ssl",
    "http",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
)

FORBIDDEN_CALLS = ("urlopen", "socket", "create_connection")


def _iter_sources():
    files = sorted(ROOT.rglob("*.py"))
    assert files, "no sources found — an empty scan is not a pass"
    return files


def test_no_network_imports():
    scanned = 0
    for path in _iter_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scanned += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in FORBIDDEN_MODULES, "{} imports {}".format(
                        path.relative_to(ROOT), alias.name
                    )
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                assert top not in FORBIDDEN_MODULES, "{} imports from {}".format(
                    path.relative_to(ROOT), node.module
                )
    assert scanned >= 1


def test_no_network_calls():
    for path in _iter_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in FORBIDDEN_CALLS:
                raise AssertionError(
                    "{} calls {}".format(path.relative_to(ROOT), name)
                )


def test_third_party_imports_are_absent():
    """运行期零第三方依赖：`src/` 只准 import 标准库与自身包。

    用 `sys.stdlib_module_names`（3.10+）不可用（requires-python >= 3.8），
    改为白名单式断言：凡不是 `bpreflight.*` 的顶层 import 必须出现在标准库名单里。
    """
    stdlib = _stdlib_names()
    scanned = 0
    for path in _iter_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scanned += 1
        for node in ast.walk(tree):
            tops = []
            if isinstance(node, ast.Import):
                tops = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # 相对 import，属本包
                    continue
                tops = [(node.module or "").split(".")[0]]
            for top in tops:
                if top == "bpreflight" or not top:
                    continue
                assert top in stdlib, "{} imports non-stdlib module {!r}".format(
                    path.relative_to(ROOT), top
                )
    assert scanned >= 1


def _stdlib_names():
    """3.8 兼容的标准库顶层模块名单（取自本机 sys 模块 + 常见清单）。"""
    import sys

    names = set(sys.builtin_module_names)
    names.update(
        """
        abc aifc argparse array ast asynchat asyncio asyncore atexit audioop base64
        bdb binascii bisect builtins bz2 calendar cgi cgitb chunk cmath cmd code
        codecs codeop collections colorsys compileall concurrent configparser
        contextlib contextvars copy copyreg crypt csv ctypes curses dataclasses
        datetime dbm decimal difflib dis distutils doctest email encodings ensurepip
        enum errno faulthandler fcntl filecmp fileinput fnmatch formatter fractions
        ftplib functools gc getopt getpass gettext glob grp gzip hashlib heapq hmac
        html http imaplib imghdr importlib inspect io ipaddress itertools json keyword
        lib2to3 linecache locale logging lzma mailbox mailcap marshal math mimetypes
        mmap modulefinder msilib msvcrt multiprocessing netrc nis nntplib numbers
        operator optparse os ossaudiodev parser pathlib pdb pickle pickletools pipes
        pkgutil platform plistlib poplib posix posixpath pprint profile pstats pty pwd
        py_compile pyclbr pydoc queue quopri random re readline reprlib resource
        rlcompleter runpy sched secrets select selectors shelve shlex shutil signal
        site smtpd smtplib sndhdr socket socketserver spwd sqlite3 sre_compile
        sre_constants sre_parse ssl stat statistics string stringprep struct subprocess
        sunau symtable sys sysconfig syslog tabnanny tarfile telnetlib tempfile termios
        test textwrap threading time timeit tkinter token tokenize trace traceback
        tracemalloc tty turtle turtledemo types typing unicodedata unittest urllib
        uu uuid venv warnings wave weakref webbrowser winreg winsound wsgiref xdrlib
        xml xmlrpc zipapp zipfile zipimport zlib zoneinfo
        """.split()
    )
    return names
