"""显示层脱敏规则（plan/04 §6，骨架期已实现）。

默认脱敏由 storage 层 settings 开关控制；导出文件同样受开关约束。
合成数据统一使用 19900000000 段假号（脱敏审查白名单登记）。
"""

import re

_PHONE_RE = re.compile(r"1[3-9]\d{9}")


def mask_phone(phone: str) -> str:
    """``19900000003`` → ``199****0003``（留前 3 后 4）；非 11 位号码原样返回。"""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) != 11:
        return phone or ""
    return digits[:3] + "****" + digits[7:]


def mask_email(email: str) -> str:
    """``zhangsan3@example.com`` → ``z******3@example.com``（保留本地部分首尾字符与域名）。"""
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    if not local:
        return email
    tail = local[-1] if len(local) > 1 else ""
    return f"{local[0]}******{tail}@{domain}"


def is_probable_phone(text: str) -> bool:
    """手机号形态判定（供解析规则与脱敏扫描复用）。"""
    return bool(_PHONE_RE.fullmatch(re.sub(r"[\s-]", "", text or "")))
