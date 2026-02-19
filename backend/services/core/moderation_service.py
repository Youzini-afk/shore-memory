class ModerationService:
    def __init__(self):
        # 敏感词库 - 仅用于 Steam 审核演示
        # 在实际生产环境中，这里应该连接更强大的在线审核 API 或加载本地大型词库
        self.banned_keywords = [
            "非法内容",
            "仇恨言论",
            "恐怖主义",
            # 可以添加更多演示用的敏感词
        ]

        # 是否启用审核
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def check_text(self, text: str) -> bool:
        """
        检查文本是否包含敏感内容
        返回: True (通过), False (不通过)
        """
        if not self.enabled:
            return True

        if not text:
            return True

        # 简单的关键词匹配
        for keyword in self.banned_keywords:
            if keyword in text:
                print(f"[Moderation] 拦截到敏感词: {keyword}")
                return False

        return True


# 全局单例
moderation_service = ModerationService()
