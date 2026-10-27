"""包内数据定位。

**运行期数据只从包内读**（决策 D15）：`src/bpreflight/data/` 随 wheel 安装，
而仓库根的 `data/` 只放"人读的依据台账"，不进 wheel（`data/README.md` 与代码是两类东西）。

**不要**用 `Path(__file__).parent.parent...` 拼路径——用 `importlib.resources` 的
`files()`（3.9+）不行（`requires-python >= 3.8`），因此这里退化为 `__file__` 同目录，
并在 `tests/test_package_data.py` 里断言"安装后仍能读到"。
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VECTORS_DIR = os.path.join(DATA_DIR, "vectors")
DICT_DIR = os.path.join(DATA_DIR, "gs1-syntax-dictionary")

#: 随包发行的向量文件（按固定序，输出可复现）。
VECTOR_FILES = ("quiet_zone.json", "gen_spec.json")


def data_path(*parts):
    """返回包内数据文件的绝对路径（不检查存在性——调用方负责报错）。"""
    return os.path.join(DATA_DIR, *parts)


def vector_path(name):
    return os.path.join(VECTORS_DIR, name)


def load_vector(name):
    """读包内向量文件。缺文件说明安装不完整（或打包漏了 package-data）。"""
    path = vector_path(name)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
