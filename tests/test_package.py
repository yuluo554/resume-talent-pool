"""包级冒烟：版本与全部模块可导入（骨架期锁定包结构，防 import 期语法/依赖错）。"""

import pathlib
import tomllib


def _pyproject_version() -> str:
    """读 pyproject.toml 的 [project].version（唯一权威版本源）。"""
    root = pathlib.Path(__file__).resolve().parents[1]
    with open(root / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_version():
    import resume_talent_pool

    # 与 pyproject 比对：两侧任一侧忘改都会红（字面量断言只能守住 __init__）
    assert resume_talent_pool.__version__ == _pyproject_version()


def test_all_modules_importable():
    import resume_talent_pool.cli  # noqa: F401
    import resume_talent_pool.pipeline  # noqa: F401
    import resume_talent_pool.core.card  # noqa: F401
    import resume_talent_pool.core.masking  # noqa: F401
    import resume_talent_pool.parsing.router  # noqa: F401
    import resume_talent_pool.normalize.matcher  # noqa: F401
    import resume_talent_pool.normalize.merge  # noqa: F401
    import resume_talent_pool.storage.db  # noqa: F401
    import resume_talent_pool.screening.jd  # noqa: F401
    import resume_talent_pool.privacy.purge  # noqa: F401
    import resume_talent_pool.evaluation.generator  # noqa: F401
    import resume_talent_pool.evaluation.benchmark  # noqa: F401
    import resume_talent_pool.gui.app  # noqa: F401
