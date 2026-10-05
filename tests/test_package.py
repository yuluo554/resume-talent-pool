"""包级冒烟：版本与全部模块可导入（骨架期锁定包结构，防 import 期语法/依赖错）。"""


def test_version():
    import resume_talent_pool

    assert resume_talent_pool.__version__ == "0.1.0"


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
