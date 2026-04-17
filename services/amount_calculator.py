"""
数额计算服务
用于计算非法经营数额、违法所得数额，以及刑事门槛比对
"""
from typing import Dict, Any, List


class AmountCalculator:
    """数额计算工具类"""

    # 行业默认成本率
    DEFAULT_COST_RATIO = 0.3

    # 假冒注册商标罪门槛
    # 违法所得 ≥ 3万 或 非法经营 ≥ 5万
    CRIMINAL_THRESHOLD_ILLEGAL_INCOME = 30000
    CRIMINAL_THRESHOLD_ILLEGAL_BUSINESS = 50000

    # 情节特别严重
    # 违法所得 ≥ 15万 或 非法经营 ≥ 25万
    SEVERE_THRESHOLD_ILLEGAL_INCOME = 150000
    SEVERE_THRESHOLD_ILLEGAL_BUSINESS = 250000

    # 假冒两种以上注册商标门槛降低
    # 违法所得 ≥ 2万 或 非法经营 ≥ 3万
    TWO_PLUS_THRESHOLD_ILLEGAL_INCOME = 20000
    TWO_PLUS_THRESHOLD_ILLEGAL_BUSINESS = 30000

    @classmethod
    def calculate_illegal_income(cls, total_amount: float) -> Dict[str, Any]:
        """
        计算非法经营数额和违法所得数额

        Args:
            total_amount: 总金额

        Returns:
            包含非法经营数额、违法所得数额、成本比例的字典
        """
        illegal_business_amount = total_amount
        cost_ratio = cls.DEFAULT_COST_RATIO
        illegal_income = illegal_business_amount * (1 - cost_ratio)

        return {
            "illegal_business_amount": illegal_business_amount,
            "illegal_income": illegal_income,
            "cost_ratio": cost_ratio,
            "cost_amount": illegal_business_amount * cost_ratio
        }

    @classmethod
    def calculate_illegal_business_amount(cls, quantity: int, unit_price: float) -> float:
        """
        计算非法经营数额

        Args:
            quantity: 交易数量
            unit_price: 单价

        Returns:
            非法经营数额
        """
        return quantity * unit_price

    @classmethod
    def calculate_illegal_gain_amount(cls, illegal_business_amount: float) -> float:
        """
        计算违法所得数额

        违法所得 = 非法经营数额 × (1 - 成本率)

        Args:
            illegal_business_amount: 非法经营数额

        Returns:
            违法所得数额
        """
        return illegal_business_amount * (1 - cls.DEFAULT_COST_RATIO)

    @classmethod
    def check_threshold(
        cls,
        illegal_business_amount: float,
        illegal_income: float,
        num_trademarks: int = 1
    ) -> Dict[str, Any]:
        """
        检查是否达到刑事立案门槛

        Args:
            illegal_business_amount: 非法经营数额
            illegal_income: 违法所得数额
            num_trademarks: 假冒商标数量

        Returns:
            门槛检查结果
        """
        # 假冒两种以上商标门槛降低
        if num_trademarks >= 2:
            threshold_met = (
                illegal_income >= cls.TWO_PLUS_THRESHOLD_ILLEGAL_INCOME or
                illegal_business_amount >= cls.TWO_PLUS_THRESHOLD_ILLEGAL_BUSINESS
            )
            threshold_level = "two_plus"
        else:
            threshold_met = (
                illegal_income >= cls.CRIMINAL_THRESHOLD_ILLEGAL_INCOME or
                illegal_business_amount >= cls.CRIMINAL_THRESHOLD_ILLEGAL_BUSINESS
            )
            threshold_level = "standard"

        # 检查是否情节特别严重
        is_severe = (
            illegal_income >= cls.SEVERE_THRESHOLD_ILLEGAL_INCOME or
            illegal_business_amount >= cls.SEVERE_THRESHOLD_ILLEGAL_BUSINESS
        )

        return {
            "threshold_met": threshold_met,
            "threshold_level": threshold_level,
            "is_severe": is_severe,
            "crime_type": "假冒注册商标罪" if threshold_met else "未达刑事门槛",
            "suggestion": cls._get_suggestion(threshold_met, is_severe, threshold_level)
        }

    @classmethod
    def check_criminal_threshold(
        cls,
        illegal_business_amount: float,
        illegal_income: float,
        num_trademarks: int = 1
    ) -> Dict[str, Any]:
        """
        检查刑事门槛（别名方法，与check_threshold相同）

        Args:
            illegal_business_amount: 非法经营数额
            illegal_income: 违法所得数额
            num_trademarks: 假冒商标数量

        Returns:
            门槛检查结果
        """
        return cls.check_threshold(illegal_business_amount, illegal_income, num_trademarks)

    @classmethod
    def _get_suggestion(cls, threshold_met: bool, is_severe: bool, threshold_level: str) -> str:
        """根据门槛检查结果给出建议"""
        if is_severe:
            return "情节特别严重，应追究刑事责任，建议立即立案"
        if threshold_met:
            if threshold_level == "two_plus":
                return "假冒两种以上商标，已达刑事立案标准"
            return "已达刑事立案标准，建议立案侦查"
        return "未达刑事立案标准，可作为行政违法处理"

    @classmethod
    def is_price_anomaly(cls, quote: float, reference_price: float) -> bool:
        """
        判断价格是否异常（低于正品50%）

        Args:
            quote: 报价
            reference_price: 正品参考价

        Returns:
            是否异常
        """
        if reference_price <= 0:
            return False
        return quote < reference_price * 0.5

    @classmethod
    def get_amount_level(cls, amount: float) -> str:
        """
        判断数额级别

        Args:
            amount: 金额

        Returns:
            数额级别
        """
        if amount < 10000:
            return "轻微"
        elif amount < 100000:
            return "较大"
        elif amount < 200000:
            return "巨大"
        else:
            return "特别巨大"

    @classmethod
    def calculate_total_amount(cls, transactions: List[Dict[str, Any]]) -> float:
        """
        计算交易总额

        Args:
            transactions: 交易列表

        Returns:
            总金额
        """
        return sum(float(t.get("amount", 0)) for t in transactions)