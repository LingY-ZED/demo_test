"""
角色推断服务
根据info.md中的规则推断人员角色
"""

from typing import Dict, List, Any, Tuple

from utils.keywords import keyword_library
from services.person_classifier import PersonClassifier


class RoleDetector:
    """角色推断服务"""

    # 角色定义
    ROLE_PRODUCER = "生产者"  # 涉嫌假冒注册商标罪
    ROLE_SELLER = "销售者"  # 涉嫌销售假冒注册商标的商品罪
    ROLE_MIDDLEMAN = "中间商"  # 既有收款又有发货
    ROLE_BUYER = "终端买家"  # 只有付款+收货
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
    def _keyword_role_result(cls, text: str) -> Dict[str, Any]:
        """提取文本中的关键词角色结果"""
        matches = keyword_library.search(text or "")
        matched_words = [m["word"] for m in matches]

        lowered_text = (text or "").replace(" ", "")
        if any(
            token in lowered_text for token in ["中间商", "代理商", "赚点差价", "倒手"]
        ):
            return {"role": cls.ROLE_MIDDLEMAN, "confidence": 0.88, "matches": matches}
        if any(
            token in lowered_text
            for token in ["付款收货", "付款再收货", "买家", "客户", "自用"]
        ):
            return {"role": cls.ROLE_BUYER, "confidence": 0.82, "matches": matches}

        cat5_matches = [m for m in matches if m["category"] == "生产/贴牌类"]
        if len(cat5_matches) >= 2:
            return {"role": cls.ROLE_PRODUCER, "confidence": 0.9, "matches": matches}

        cat4_matches = [m for m in matches if m["category"] == "销售行为类"]
        if len(cat4_matches) >= 2:
            return {"role": cls.ROLE_SELLER, "confidence": 0.85, "matches": matches}

        production_words = {
            "贴牌",
            "打标",
            "印logo",
            "自己做的",
            "工厂",
            "代工",
            "开模",
            "复刻",
            "生产",
            "加工",
            "仿制",
            "定做",
            "高仿",
            "一比一",
            "原单",
            "跟单",
        }
        if any(word in production_words for word in matched_words) or any(
            token in lowered_text
            for token in [
                "生产",
                "加工",
                "仿制",
                "定做",
                "高仿",
                "一比一",
                "原单",
                "跟单",
            ]
        ):
            return {"role": cls.ROLE_PRODUCER, "confidence": 0.8, "matches": matches}

        selling_words = {
            "出货",
            "拿货",
            "批发",
            "代理",
            "卖",
            "零售",
            "分销",
            "直销",
            "走量",
            "特价",
            "优惠",
            "总代理",
        }
        if any(word in selling_words for word in matched_words) or any(
            token in lowered_text
            for token in [
                "出货",
                "拿货",
                "批发",
                "代理",
                "零售",
                "分销",
                "直销",
                "走量",
                "特价",
                "优惠",
                "总代理",
            ]
        ):
            return {"role": cls.ROLE_SELLER, "confidence": 0.75, "matches": matches}

        if "中间商" in lowered_text or "代理" in lowered_text:
            return {"role": cls.ROLE_MIDDLEMAN, "confidence": 0.72, "matches": matches}

        return {"role": cls.ROLE_UNKNOWN, "confidence": 0.0, "matches": matches}

    @classmethod
    def detect_role_by_keywords(cls, text: str) -> str:
        """
        根据聊天内容中的关键词推断角色

        Args:
            text: 聊天内容

        Returns:
            角色类型
        """
        return cls._keyword_role_result(text)["role"]

    @classmethod
    def infer_role_by_keywords(cls, text: str) -> Tuple[str, float]:
        """兼容旧接口：返回角色和置信度"""
        result = cls._keyword_role_result(text)
        return result["role"], result.get("confidence", 0.0)

    @classmethod
    def infer_role_by_transactions(
        cls,
        person_name: str,
        transactions: List[Dict[str, Any]],
    ) -> str:
        """兼容旧接口：根据交易推断角色"""
        profile = PersonClassifier.build_activity_profile(
            transactions, [], [], person_name
        )
        result = PersonClassifier.classify_business_role(profile)
        return result["role"]

    @classmethod
    def infer_role_by_logistics(
        cls,
        person_name: str,
        logistics: List[Dict[str, Any]],
    ) -> str:
        """兼容旧接口：根据物流推断角色"""
        profile = PersonClassifier.build_activity_profile(
            [], logistics, [], person_name
        )
        result = PersonClassifier.classify_business_role(profile)
        return result["role"]

    @classmethod
    def detect_role_by_behavior(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        person_name: str,
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
        profile = PersonClassifier.build_activity_profile(
            transactions, logistics, [], person_name
        )
        result = PersonClassifier.classify_business_role(profile)
        return result["role"]

    @classmethod
    def detect_role(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        person_name: str,
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
        profile = PersonClassifier.build_activity_profile(
            transactions, logistics, communications, person_name
        )
        behavior_result = PersonClassifier.classify_business_role(profile)
        behavior_role = behavior_result["role"]

        # 2. 基于通讯记录关键词推断
        keyword_roles = []
        keyword_confidence = 0.0
        for comm in communications:
            if (
                comm.get("initiator") == person_name
                or comm.get("receiver") == person_name
            ):
                content = comm.get("content", "")
                if content:
                    keyword_result = cls._keyword_role_result(content)
                    role = keyword_result.get("role", cls.ROLE_UNKNOWN)
                    if role != cls.ROLE_UNKNOWN:
                        keyword_roles.append(role)
                        keyword_confidence = max(
                            keyword_confidence,
                            float(keyword_result.get("confidence", 0.0)),
                        )

        # 综合判断
        final_role = behavior_role
        if behavior_role == cls.ROLE_UNKNOWN and keyword_roles:
            if cls.ROLE_PRODUCER in keyword_roles:
                final_role = cls.ROLE_PRODUCER
            elif cls.ROLE_SELLER in keyword_roles:
                final_role = cls.ROLE_SELLER
            elif cls.ROLE_MIDDLEMAN in keyword_roles:
                final_role = cls.ROLE_MIDDLEMAN
            else:
                final_role = keyword_roles[0]
        elif behavior_role == cls.ROLE_SELLER and cls.ROLE_PRODUCER in keyword_roles:
            final_role = cls.ROLE_PRODUCER

        # 获取涉嫌罪名
        crime_type = cls.ROLE_CRIME_TYPES.get(final_role, "待定")

        # 一致性判断：关键词角色内部一致 且 行为角色与关键词角色不冲突
        keyword_consistent = len(set(keyword_roles)) <= 1 if keyword_roles else True
        if keyword_consistent and behavior_role != cls.ROLE_UNKNOWN and keyword_roles:
            # 行为角色与关键词角色存在冲突（如行为=销售者但关键词=生产者）
            keyword_set = set(keyword_roles)
            if behavior_role not in keyword_set and len(keyword_set) == 1:
                keyword_consistent = False

        return {
            "person_name": person_name,
            "role": final_role,
            "crime_type": crime_type,
            "behavior_role": behavior_role,
            "keyword_roles": keyword_roles,
            "behavior_reason": behavior_result.get("reason"),
            "behavior_confidence": behavior_result.get("confidence", 0.0),
            "keyword_confidence": keyword_confidence,
            "is_consistent": keyword_consistent,
        }

    @classmethod
    def get_role_evidence(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        person_name: str,
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
                evidence["transactions"].append(
                    {
                        "type": "付款" if t.get("payer") == person_name else "收款",
                        "counterparty": (
                            t.get("payee")
                            if t.get("payer") == person_name
                            else t.get("payer")
                        ),
                        "amount": t.get("amount"),
                        "time": t.get("transaction_time"),
                        "remark": t.get("remark"),
                    }
                )

        # 物流证据
        for l in logistics:
            if l.get("sender") == person_name or l.get("receiver") == person_name:
                evidence["logistics"].append(
                    {
                        "type": "发货" if l.get("sender") == person_name else "收货",
                        "counterparty": (
                            l.get("receiver")
                            if l.get("sender") == person_name
                            else l.get("sender")
                        ),
                        "description": l.get("description"),
                        "time": l.get("shipping_time"),
                    }
                )

        # 通讯证据
        for c in communications:
            if c.get("initiator") == person_name or c.get("receiver") == person_name:
                content = c.get("content", "")
                matches = keyword_library.search(content) if content else []
                evidence["communications"].append(
                    {
                        "type": "发起" if c.get("initiator") == person_name else "接收",
                        "counterparty": (
                            c.get("receiver")
                            if c.get("initiator") == person_name
                            else c.get("initiator")
                        ),
                        "content": content,
                        "hit_keywords": [m["word"] for m in matches],
                        "role_hint": (
                            cls.detect_role_by_keywords(content)
                            if content
                            else cls.ROLE_UNKNOWN
                        ),
                    }
                )

        return evidence
