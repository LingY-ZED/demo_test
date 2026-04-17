"""
数据脱敏工具
提供手机号、身份证号、银行卡号等敏感信息的脱敏功能
"""
import re
from typing import Optional


class MaskingTool:
    """数据脱敏工具类"""

    # 正则表达式模式
    PHONE_PATTERN = re.compile(r'(\d{3})\d{4}(\d{4})')
    ID_PATTERN = re.compile(r'(\d{6})\d{8}(\d{4})')
    BANK_PATTERN = re.compile(r'(\d{4})\d+(\d{4})')
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """
        手机号脱敏

        Args:
            phone: 手机号

        Returns:
            脱敏后的手机号，如 138****5678
        """
        if not phone:
            return phone
        return cls.PHONE_PATTERN.sub(r'\1****\2', phone)

    @classmethod
    def mask_id_number(cls, id_number: str) -> str:
        """
        身份证号脱敏

        Args:
            id_number: 身份证号

        Returns:
            脱敏后的身份证号，如 110101**********1234
        """
        if not id_number:
            return id_number
        return cls.ID_PATTERN.sub(r'\1********\2', id_number)

    @classmethod
    def mask_bank_card(cls, card_number: str) -> str:
        """
        银行卡号脱敏

        Args:
            card_number: 银行卡号

        Returns:
            脱敏后的银行卡号，如 6225****1234
        """
        if not card_number:
            return card_number
        # 移除空格和可能的其他分隔符
        clean_number = re.sub(r'[\s-]', '', card_number)
        return cls.BANK_PATTERN.sub(r'\1****\2', clean_number)

    @classmethod
    def mask_email(cls, email: str) -> str:
        """
        邮箱脱敏

        Args:
            email: 邮箱地址

        Returns:
            脱敏后的邮箱，如 t***@example.com
        """
        if not email:
            return email

        def replace_email(m):
            username = m.group(1)
            domain = m.group(2)
            if len(username) <= 2:
                masked_username = username[0] + '*'
            else:
                masked_username = username[0] + '*' * (len(username) - 2) + username[-1]
            return f"{masked_username}@{domain}"

        return cls.EMAIL_PATTERN.sub(replace_email, email)

    @classmethod
    def mask_sensitive_info(cls, text: str) -> str:
        """
        脱敏文本中的所有敏感信息

        Args:
            text: 原始文本

        Returns:
            脱敏后的文本
        """
        if not text:
            return text

        # 按顺序执行脱敏，避免正则冲突
        # 1. 脱敏手机号
        text = cls.PHONE_PATTERN.sub(r'\1****\2', text)
        # 2. 脱敏身份证号
        text = cls.ID_PATTERN.sub(r'\1********\2', text)
        # 3. 脱敏银行卡号
        text = cls.BANK_PATTERN.sub(r'\1****\2', text)

        return text

    @classmethod
    def mask_name(cls, name: str, keep_last: bool = True) -> str:
        """
        姓名脱敏

        Args:
            name: 姓名
            keep_last: 是否保留最后一个字

        Returns:
            脱敏后的姓名，如 张*三 或 **三
        """
        if not name or len(name) < 2:
            return name

        if len(name) == 2:
            return name[0] + '*'
        elif keep_last:
            return name[0] + '*' * (len(name) - 2) + name[-1]
        else:
            return '*' * len(name)

    @classmethod
    def mask_address(cls, address: str, keep_detail: bool = False) -> str:
        """
        地址脱敏

        Args:
            address: 详细地址
            keep_detail: 是否保留详细信息（如街道门牌号）

        Returns:
            脱敏后的地址，只保留省市区
        """
        if not address:
            return address

        # 简单实现：保留前N个字符
        if keep_detail:
            # 保留省市区 + 前10个字符的详细信息
            if len(address) <= 20:
                return address
            return address[:20] + '...'
        else:
            # 只保留前N个字符
            if len(address) <= 10:
                return address
            return address[:10] + '...'

    @classmethod
    def mask_amount(cls, amount: float, precision: int = 0) -> str:
        """
        金额脱敏（用于显示）

        Args:
            amount: 金额
            precision: 精度（保留小数位数）

        Returns:
            脱敏后的金额字符串
        """
        if amount is None:
            return "***"

        # 直接返回格式化后的金额，不做脱敏
        # 金额脱敏主要用于隐私保护场景
        return f"{amount:,.{precision}f}"

    @classmethod
    def batch_mask_phone(cls, phones: list) -> list:
        """
        批量脱敏手机号

        Args:
            phones: 手机号列表

        Returns:
            脱敏后的手机号列表
        """
        return [cls.mask_phone(p) for p in phones]

    @classmethod
    def batch_mask_sensitive_info(cls, texts: list) -> list:
        """
        批量脱敏文本中的敏感信息

        Args:
            texts: 文本列表

        Returns:
            脱敏后的文本列表
        """
        return [cls.mask_sensitive_info(t) for t in texts]