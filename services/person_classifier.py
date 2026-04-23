"""
人员判定公共工具
统一资金流、物流、通讯三类信号的基础提取与角色判定
"""

from typing import Dict, List, Any


class PersonClassifier:
    """人员判定公共工具"""

    CHAIN_UPSTREAM = "上游供货商"
    CHAIN_DOWNSTREAM = "下游买家"
    CHAIN_CORE = "核心节点"
    CHAIN_UNKNOWN = "待定"

    ROLE_PRODUCER = "生产者"
    ROLE_SELLER = "销售者"
    ROLE_MIDDLEMAN = "中间商"
    ROLE_BUYER = "终端买家"
    ROLE_UNKNOWN = "待定"

    @classmethod
    def build_activity_profile(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        person_name: str,
    ) -> Dict[str, Any]:
        """汇总某个人的资金、物流和通讯行为信号"""
        profile = {
            "person_name": person_name,
            "money_in_count": 0,
            "money_out_count": 0,
            "money_in_amount": 0.0,
            "money_out_amount": 0.0,
            "logistics_in_count": 0,
            "logistics_out_count": 0,
            "communication_count": 0,
            "transaction_counterparties": set(),
            "logistics_counterparties": set(),
            "communication_counterparties": set(),
        }

        for transaction in transactions:
            payer = str(transaction.get("payer", "")).strip()
            payee = str(transaction.get("payee", "")).strip()
            amount = float(transaction.get("amount", 0) or 0)

            if payer == person_name:
                profile["money_out_count"] += 1
                profile["money_out_amount"] += amount
                if payee:
                    profile["transaction_counterparties"].add(payee)

            if payee == person_name:
                profile["money_in_count"] += 1
                profile["money_in_amount"] += amount
                if payer:
                    profile["transaction_counterparties"].add(payer)

        for logistic in logistics:
            sender = str(logistic.get("sender", "")).strip()
            receiver = str(logistic.get("receiver", "")).strip()

            if sender == person_name:
                profile["logistics_out_count"] += 1
                if receiver:
                    profile["logistics_counterparties"].add(receiver)

            if receiver == person_name:
                profile["logistics_in_count"] += 1
                if sender:
                    profile["logistics_counterparties"].add(sender)

        for communication in communications:
            initiator = str(communication.get("initiator", "")).strip()
            receiver = str(communication.get("receiver", "")).strip()

            if initiator == person_name or receiver == person_name:
                profile["communication_count"] += 1
                counterpart = receiver if initiator == person_name else initiator
                if counterpart:
                    profile["communication_counterparties"].add(counterpart)

        profile["total_money_amount"] = (
            profile["money_in_amount"] + profile["money_out_amount"]
        )
        profile["total_logistics_count"] = (
            profile["logistics_in_count"] + profile["logistics_out_count"]
        )
        profile["has_money_in"] = profile["money_in_count"] > 0
        profile["has_money_out"] = profile["money_out_count"] > 0
        profile["has_logistics_in"] = profile["logistics_in_count"] > 0
        profile["has_logistics_out"] = profile["logistics_out_count"] > 0
        profile["money_balance"] = (
            profile["money_in_amount"] - profile["money_out_amount"]
        )

        return profile

    @classmethod
    def classify_chain_position(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        """根据行为信号判断上下游位置"""
        money_in = float(profile.get("money_in_amount", 0) or 0)
        money_out = float(profile.get("money_out_amount", 0) or 0)
        logistics_in = int(profile.get("logistics_in_count", 0) or 0)
        logistics_out = int(profile.get("logistics_out_count", 0) or 0)
        communication_count = int(profile.get("communication_count", 0) or 0)

        if (
            money_in <= 0
            and money_out <= 0
            and logistics_in <= 0
            and logistics_out <= 0
        ):
            return {
                "position": cls.CHAIN_UNKNOWN,
                "confidence": 0.0,
                "reason": "缺少可用于判定的资金流和物流信号",
            }

        if money_in > 0 and money_out > 0:
            if logistics_in > 0 and logistics_out > 0:
                return {
                    "position": cls.CHAIN_CORE,
                    "confidence": 0.92,
                    "reason": "同时存在明显的收付资金和收发物流",
                }

            money_gap_ratio = abs(money_in - money_out) / max(money_in + money_out, 1.0)
            if money_gap_ratio <= 0.25:
                return {
                    "position": cls.CHAIN_CORE,
                    "confidence": 0.82,
                    "reason": "资金收付较为双向且接近",
                }

            if money_in > money_out and logistics_out >= logistics_in:
                return {
                    "position": cls.CHAIN_UPSTREAM,
                    "confidence": 0.78,
                    "reason": "收款和发货更明显，偏上游供货",
                }

            if money_out > money_in and logistics_in >= logistics_out:
                return {
                    "position": cls.CHAIN_DOWNSTREAM,
                    "confidence": 0.78,
                    "reason": "付款和收货更明显，偏下游购买",
                }

            return {
                "position": cls.CHAIN_CORE,
                "confidence": 0.72,
                "reason": "资金和物流方向均呈双向特征",
            }

        if money_in > 0 or logistics_out > 0:
            return {
                "position": cls.CHAIN_UPSTREAM,
                "confidence": 0.72,
                "reason": "以收款或发货为主，偏上游",
            }

        if money_out > 0 or logistics_in > 0:
            return {
                "position": cls.CHAIN_DOWNSTREAM,
                "confidence": 0.72,
                "reason": "以付款或收货为主，偏下游",
            }

        if communication_count > 0:
            return {
                "position": cls.CHAIN_UNKNOWN,
                "confidence": 0.2,
                "reason": "仅有通讯信号，缺少资金或物流证据",
            }

        return {
            "position": cls.CHAIN_UNKNOWN,
            "confidence": 0.0,
            "reason": "证据不足",
        }

    @classmethod
    def classify_business_role(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        """根据行为信号判断业务角色"""
        money_in = float(profile.get("money_in_amount", 0) or 0)
        money_out = float(profile.get("money_out_amount", 0) or 0)
        logistics_in = int(profile.get("logistics_in_count", 0) or 0)
        logistics_out = int(profile.get("logistics_out_count", 0) or 0)

        if (
            money_in <= 0
            and money_out <= 0
            and logistics_in <= 0
            and logistics_out <= 0
        ):
            return {
                "role": cls.ROLE_UNKNOWN,
                "confidence": 0.0,
                "reason": "缺少可用于判定的行为信号",
            }

        if money_in > 0 and money_out > 0 and logistics_in > 0 and logistics_out > 0:
            return {
                "role": cls.ROLE_MIDDLEMAN,
                "confidence": 0.92,
                "reason": "同时存在明显收付资金与收发物流",
            }

        if money_in > 0 and money_out == 0 and logistics_out > 0:
            return {
                "role": cls.ROLE_SELLER,
                "confidence": 0.86,
                "reason": "以收款和发货为主",
            }

        if money_out > 0 and money_in == 0 and logistics_in > 0:
            return {
                "role": cls.ROLE_BUYER,
                "confidence": 0.86,
                "reason": "以付款和收货为主",
            }

        if money_in > 0 and money_out > 0:
            money_gap_ratio = abs(money_in - money_out) / max(money_in + money_out, 1.0)
            if money_gap_ratio <= 0.25:
                return {
                    "role": cls.ROLE_MIDDLEMAN,
                    "confidence": 0.78,
                    "reason": "资金收付双向且金额接近",
                }
            if money_in > money_out:
                return {
                    "role": cls.ROLE_SELLER,
                    "confidence": 0.72,
                    "reason": "收款强于付款",
                }
            return {
                "role": cls.ROLE_BUYER,
                "confidence": 0.72,
                "reason": "付款强于收款",
            }

        if money_in > 0 or logistics_out > 0:
            return {
                "role": cls.ROLE_SELLER,
                "confidence": 0.7,
                "reason": "存在收款或发货证据",
            }

        if money_out > 0 or logistics_in > 0:
            return {
                "role": cls.ROLE_BUYER,
                "confidence": 0.7,
                "reason": "存在付款或收货证据",
            }

        return {
            "role": cls.ROLE_UNKNOWN,
            "confidence": 0.0,
            "reason": "无法判定",
        }
