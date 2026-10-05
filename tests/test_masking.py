"""脱敏规则（plan/04 §6；合成假号段 19900000000 亦用于脱敏审查白名单对照）。"""

from resume_talent_pool.core.masking import is_probable_phone, mask_email, mask_phone


def test_mask_phone_keeps_head_and_tail():
    assert mask_phone("19900000003") == "199****0003"


def test_mask_phone_tolerates_separators():
    assert mask_phone("199 0000 0003") == "199****0003"
    assert mask_phone("199-0000-0003") == "199****0003"


def test_mask_phone_invalid_untouched():
    assert mask_phone("12345") == "12345"
    assert mask_phone("") == ""


def test_mask_email_keeps_first_char_and_domain():
    assert mask_email("zhangsan3@example.com") == "z******3@example.com"


def test_mask_email_single_char_local():
    assert mask_email("a@example.com") == "a******@example.com"


def test_mask_email_invalid_untouched():
    assert mask_email("not-an-email") == "not-an-email"


def test_is_probable_phone():
    assert is_probable_phone("19900000003")
    assert is_probable_phone("199-0000-0003")
    assert not is_probable_phone("12345678901")  # 12x 段不合法
