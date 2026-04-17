"""
角色推断服务
根据info.md中的规则推断人员角色
"""
from typing import Dict, List, Any, Tuple

from utils.keywords import keyword_library


class RoleDetector:
    """角色推断服务"""

    # 角色定义
    ROLE_PRODUCER = "生产者"           # 涉嫌假冒注册商标罪
    ROLE_SELLER = "销售者"             # 涉嫌销售假冒注册商标的商品罪
    ROLE_MIDDLEMAN = "中间商"          # 既有收款又有发货
    ROLE_BUYER = "终端买家"            # 只有付款+收货
    ROLE_UNKNOWN = "待定"

    # 角色对应的涉嫌罪名
    ROLE_CRIME_TYPES = {
        ROLE_PRODUCER: "涉嫌假冒注册商标罪",
        ROLE_SELLER: "涉嫌销售假冒注册商标的商品罪",
        ROLE_MIDDLEMAN: "涉嫌销售假冒注册商标的商品罪",
        ROLE_BUYER: "待定",
        ROLE_UNKNOWN: "待定",
    }

    @classmethod
    def detect_role_by_keywords(cls, text: str) -> str:
        """
        根据聊天内容中的关键词推断角色

        Args:
            text: 聊天内容

        Returns:
            角色类型
        """
        matches = keyword_library.search(text)

        # 类别5（生产/贴牌类）命中 >= 2 → 生产者
        cat5_matches = [m for m in matches if m["category"] == "生产/贴牌类"]
        if len(cat5_matches) >= 2:
            return cls.ROLE_PRODUCER

        # 类别4（销售行为类）命中 >= 2 → 销售者
        cat4_matches = [m for m in matches if m["category"] == "销售行为类"]
        if len(cat4_matches) >= 2:
            return cls.ROLE_SELLER

        # 有生产相关词
        production_words = ["贴牌", "打标", "印logo", "自己做的", "工厂"]
        has_production = any(m["word"] in production_words for m in matches)
        if has_production:
            return cls.ROLE_PRODUCER

        # 有销售相关词
        selling_words = ["出货", "拿货", "批发", "代理", "卖"]
        has_selling = any(m["word"] in selling_words for m in matches)
        if has_selling:
            return cls.ROLE_SELLER

        return cls.ROLE_UNKNOWN

    @classmethod
    def detect_role_by_behavior(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        person_name: str
    ) -> str:
        """
        根据资金流水和物流行为模式推断角色

        规则:
        - 同时有"收款+发货" -> 中间商
        - 只有"付款+收货" -> 终端买家
        - 只有"收款"无发货 -> 核心销售商
        - 只有"付款"无收货 -> 下游买家

        Args:
            transactions: 资金流水列表
            logistics: 物流列表
            person_name: 人员姓名

        Returns:
            角色类型
        """
        # 查找该人员的所有交易
        as_payer = [t for t in transactions if t.get("payer") == person_name]
        as_payee = [t for t in transactions if t.get("payee") == person_name]

        # 查找该人员的所有物流
        as_sender = [l for l in logistics if l.get("sender") == person_name]
        as_receiver = [l for l in logistics if l.get("receiver") == person_name]

        has_outgoing_money = len(as_payer) > 0  # 付过钱
        has_incoming_money = len(as_payee) > 0  # 收过钱
        has_outgoing_logistics = len(as_sender) > 0  # 发过货
        has_incoming_logistics = len(as_receiver) > 0  # 收过货

        # 推断角色
        if has_incoming_money and has_outgoing_logistics:
            return cls.ROLE_MIDDLEMAN
        elif has_outgoing_money and has_incoming_logistics:
            return cls.ROLE_BUYER
        elif has_incoming_money and not has_outgoing_logistics:
            return cls.ROLE_SELLER
        elif has_outgoing_money and not has_incoming_logistics:
            return cls.ROLE_BUYER
        else:
            return cls.ROLE_UNKNOWN

    @classmethod
    def detect_role(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        person_name: str
    ) -> Dict[str, Any]:
        """
        综合推断角色

        结合关键词和行为模式

        Args:
            transactions: 资金流水列表
            logistics: 物流列表
            communications: 通讯列表
            person_name: 人员姓名

        Returns:
            角色推断结果
        """
        # 1. 基于行为模式推断
        behavior_role = cls.detect_role_by_behavior(
            transactions, logistics, person_name
        )

        # 2. 基于通讯记录关键词推断
        keyword_roles = []
        for comm in communications:
            if comm.get("initiator") == person_name or comm.get("receiver") == person_name:
                content = comm.get("content", "")
                if content:
                    role = cls.detect_role_by_keywords(content)
                    if role != cls.ROLE_UNKNOWN:
                        keyword_roles.append(role)

        # 综合判断
        if keyword_roles:
            # 如果通讯中有多个角色指向，取最高风险
            if cls.ROLE_PRODUCER in keyword_roles:
                final_role = cls.ROLE_PRODUCER
            elif cls.ROLE_SELLER in keyword_roles:
                final_role = cls.ROLE_SELLER
            else:
                final_role = keyword_roles[0]
        else:
            final_role = behavior_role

        # 获取涉嫌罪名
        crime_type = cls.ROLE_CRIME_TYPES.get(final_role, "待定")

        return {
            "person_name": person_name,
            "role": final_role,
            "crime_type": crime_type,
            "behavior_role": behavior_role,
            "keyword_roles": keyword_roles,
            "is_consistent": len(set(keyword_roles)) <= 1 if keyword_roles else True,
        }

    @classmethod
    def get_role_evidence(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        person_name: str
    ) -> Dict[str, Any]:
        """
        获取角色判断的证据

        Args:
            transactions: 资金流水列表
            logistics: 物流列表
            communications: 通讯列表
            person_name: 人员姓名

        Returns:
            证据字典
        """
        evidence = {
            "transactions": [],
            "logistics": [],
            "communications": [],
        }

        # 资金流水证据
        for t in transactions:
            if t.get("payer") == person_name or t.get("payee") == person_name:
                evidence["transactions"].append({
                    "type": "付款" if t.get("payer") == person_name else "收款",
                    "counterparty": t.get("payee") if t.get("payer") == person_name else t.get("payer"),
                    "amount": t.get("amount"),
                    "time": t.get("transaction_time"),
                    "remark": t.get("remark"),
                })

        # 物流证据
        for l in logistics:
            if l.get("sender") == person_name or l.get("receiver") == person_name:
                evidence["logistics"].append({
                    "type": "发货" if l.get("sender") == person_name else "收货",
                    "counterparty": l.get("receiver") if l.get("sender") == person_name else l.get("sender"),
                    "description": l.get("description"),
                    "time": l.get("shipping_time"),
                })

        # 通讯证据
        for c in communications:
            if c.get("initiator") == person_name or c.get("receiver") == person_name:
                content = c.get("content", "")
                matches = keyword_library.search(content) if content else []
                evidence["communications"].append({
                    "type": "发起" if c.get("initiator") == person_name else "接收",
                    "counterparty": c.get("receiver") if c.get("initiator") == person_name else c.get("initiator"),
                    "content": content,
                    "hit_keywords": [m["word"] for m in matches],
                    "role_hint": cls.detect_role_by_keywords(content) if content else cls.ROLE_UNKNOWN,
                })

        return evidence
