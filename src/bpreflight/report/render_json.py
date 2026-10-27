"""JSON 渲染：确定性优先（sorted keys / 2 空格缩进 / 尾随换行 / UTF-8 原样）。"""

import json


def render_json(report):
    """返回 (text, filename_hint)。filename 只用于 stdout/落盘提示，不参与内容。"""
    payload = report.to_dict()
    text = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
    )
    return text + "\n", "bpreflight.json"
