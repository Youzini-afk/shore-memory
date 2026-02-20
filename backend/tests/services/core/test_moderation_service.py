from services.core.moderation_service import ModerationService


def test_moderation_disabled():
    """测试审核服务关闭时"""
    service = ModerationService()
    service.set_enabled(False)
    assert service.check_text("非法内容") is True
    assert service.check_text("正常内容") is True


def test_moderation_enabled_block():
    """测试审核服务开启时拦截敏感词"""
    service = ModerationService()
    service.set_enabled(True)
    # 假设 "非法内容" 在默认禁止列表中
    assert service.check_text("这是一个包含非法内容的句子") is False


def test_moderation_enabled_pass():
    """测试审核服务开启时放行正常词"""
    service = ModerationService()
    service.set_enabled(True)
    assert service.check_text("这是一个非常正常的内容") is True


def test_moderation_empty():
    """测试空文本"""
    service = ModerationService()
    service.set_enabled(True)
    assert service.check_text("") is True
    assert service.check_text(None) is True
