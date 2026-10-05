"""合成简历生成器（M1，详设见 plan/05 §2）。

人群模板（应届/社招技术/社招职能）× 格式（pdf:docx:txt ≈ 4:4:2），固定 seed 复现；
程序化植入真值：同一人多版本（~60% 人 2+ 版）、同名不同人（5 组）、字段缺失（10–30%）、
格式噪声（伪空格/全角/分隔符变体/多行，覆盖 ~50% 文件）。
全部虚构：手机号 19900000000 段假号，邮箱 example.com 保留域（脱敏白名单登记）。
真值语义一次定清：truth_fields 是"应被解析出"的字段全集，解析器多解析出的按 FP 计。
"""

DEFAULT_SEED = 20261005


def generate(output_dir: str, seed: int = DEFAULT_SEED, persons: int = 100) -> dict:
    """批量生成简历 + truth.json（M1 实现）。"""
    raise NotImplementedError("M1 实现：人群模板 → 简历文件 + 真值 JSON")
