"""
可疑线索检测服务
遍历通讯记录，命中敏感词生成线索
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from models.database import Case, SuspiciousClue, Communication
from services.score_service import ScoreService
from services.role_detector import RoleDetector
from services.evidence_analyzer import EvidenceAnalyzer
from utils.keywords import keyword_library


class SuspicionDetector:
    """可疑线索检测服务"""

    # 严重程度等级
    SEVERITY_CRIMINAL = "刑事犯罪"      # 8-10分
    SEVERITY_TORT = "民事侵权"          # 5-7分
    SEVERITY_ADMINISTRATIVE = "行政违法"  # 0-4分

    @classmethod
    def detect_from_communication(
        cls,
        case_id: int,
        communications: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        从通讯记录检测可疑线索

        Args:
            case_id: 案件ID
            communications: 通讯记录列表（如果为None，从数据库读取）

        Returns:
            可疑线索列表
        """
        if communications is None:
            # 从数据库读取
            comms = Communication.select().where(Communication.case == case_id)
            communications = [
                {
                    "id": c.id,
                    "communication_time": c.communication_time,
                    "initiator": c.initiator,
                    "receiver": c.receiver,
                    "content": c.content,
                }
                for c in comms
            ]

        clues = []
        for comm in communications:
            content = comm.get("content", "")
            if not content:
                continue

            # 搜索敏感词
            matches = keyword_library.search(content)
            if not matches:
                continue

            # 计算主观明知评分
            score_result = ScoreService.analyze_text(content)

            # 判断严重程度
            severity = cls._get_severity_level(score_result["score"])

            # 获取涉嫌罪名
            crime_type = ScoreService.get_crime_type(matches)

            # 创建主观明知线索记录
            clue = cls.create_suspicious_clue(
                case_id=case_id,
                clue_type="主观明知",
                evidence_text=content,
                hit_keywords=[m["word"] for m in matches],
                score=score_result["score"],
                crime_type=crime_type,
                severity_level=severity,
            )
            clues.append(clue)

            # 从通讯内容中检测价格异常（与证据解析保持一致）
            price_result = EvidenceAnalyzer.analyze_price_anomaly(content)
            if price_result["has_anomaly"]:
                price_clue = cls.create_suspicious_clue(
                    case_id=case_id,
                    clue_type="价格异常",
                    evidence_text=(
                        f"聊天提及价格：{price_result['quoted_price']:.0f}元，"
                        f"参考价：{price_result['reference_price']:.0f}元"
                    ),
                    hit_keywords=[m["word"] for m in matches],
                    score=3,
                    crime_type=crime_type,
                    severity_level="行政违法",
                )
                clues.append(price_clue)

        return clues

    @classmethod
    def detect_price_anomaly(
        cls,
        case_id: int,
        transactions: Optional[List[Dict[str, Any]]] = None,
        reference_prices: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        检测价格异常

        Args:
            case_id: 案件ID
            transactions: 交易记录列表
            reference_prices: 参考价格字典 {"品牌_产品": 参考价}

        Returns:
            价格异常线索列表
        """
        if transactions is None:
            from models.database import Transaction
            trans = Transaction.select().where(Transaction.case == case_id)
            transactions = [
                {
                    "id": t.id,
                    "transaction_time": t.transaction_time,
                    "payer": t.payer,
                    "payee": t.payee,
                    "amount": t.amount,
                    "remark": t.remark,
                }
                for t in trans
            ]

        # 价格异常阈值：低于正常价 50%
        PRICE_ANOMALY_RATIO = 0.5

        clues = []
        for trans in transactions:
            remark = trans.get("remark", "") or ""
            amount = float(trans.get("amount", 0))

            if amount <= 0:
                continue

            # 从备注中提取品牌/产品
            matches = keyword_library.search(remark)
            brands = keyword_library.search_brands(remark)

            # 确定参考价格
            is_anomaly = False
            anomaly_ratio = None
            ref_price = None

            if reference_prices:
                brand = brands[0] if brands else None
                if brand and brand in reference_prices:
                    ref_price = reference_prices[brand]
                    anomaly_ratio = amount / ref_price if ref_price > 0 else 1
                    is_anomaly = anomaly_ratio < PRICE_ANOMALY_RATIO
            else:
                # 无参考价时用通用启发式：正品约为售价 2.5 倍
                ref_price = amount * 2.5
                anomaly_ratio = amount / ref_price  # ≈ 0.4
                is_anomaly = bool(brands or matches) and anomaly_ratio < PRICE_ANOMALY_RATIO

            if is_anomaly:
                remark_suffix = f"，备注：{remark}" if remark else ""
                clue = cls.create_suspicious_clue(
                    case_id=case_id,
                    clue_type="价格异常",
                    evidence_text=f"交易金额：{amount}元，参考价：{ref_price:.0f}元{remark_suffix}",
                    hit_keywords=list(set([m["word"] for m in matches] + brands)),
                    score=3,
                    crime_type="待定",
                    severity_level="行政违法",
                )
                clues.append(clue)

        return clues

    @classmethod
    def detect_role_anomaly(
        cls,
        case_id: int,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        检测角色异常

        Args:
            case_id: 案件ID
            transactions: 资金流水列表
            logistics: 物流列表
            communications: 通讯列表

        Returns:
            角色异常线索列表
        """
        # 提取所有涉及的人员
        persons = set()
        for t in transactions:
            if t.get("payer"):
                persons.add(t.get("payer"))
            if t.get("payee"):
                persons.add(t.get("payee"))
        for l in logistics:
            if l.get("sender"):
                persons.add(l.get("sender"))
            if l.get("receiver"):
                persons.add(l.get("receiver"))

        clues = []
        for person in persons:
            role_result = RoleDetector.detect_role(
                transactions, logistics, communications, person
            )

            # 检查是否存在行为不一致
            if not role_result["is_consistent"]:
                clue = cls.create_suspicious_clue(
                    case_id=case_id,
                    clue_type="角色异常",
                    evidence_text=f"人员{person}的角色判断存在矛盾",
                    hit_keywords=[],
                    score=2,
                    crime_type=role_result.get("crime_type", "待定"),
                    severity_level="行政违法",
                )
                clues.append(clue)

        return clues

    @classmethod
    def detect_all(cls, case_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        全量检测

        Args:
            case_id: 案件ID

        Returns:
            所有检测结果
        """
        from models.database import Transaction, Logistics, Communication

        # 获取所有数据
        trans = Transaction.select().where(Transaction.case == case_id)
        transactions = [
            {
                "id": t.id,
                "transaction_time": t.transaction_time,
                "payer": t.payer,
                "payee": t.payee,
                "amount": t.amount,
                "remark": t.remark,
            }
            for t in trans
        ]

        logis = Logistics.select().where(Logistics.case == case_id)
        logistics = [
            {
                "id": l.id,
                "shipping_time": l.shipping_time,
                "sender": l.sender,
                "sender_address": l.sender_address,
                "receiver": l.receiver,
                "receiver_address": l.receiver_address,
                "description": l.description,
            }
            for l in logis
        ]

        comms = Communication.select().where(Communication.case == case_id)
        communications = [
            {
                "id": c.id,
                "communication_time": c.communication_time,
                "initiator": c.initiator,
                "receiver": c.receiver,
                "content": c.content,
            }
            for c in comms
        ]

        # 执行各类检测
        all_comm_clues = cls.detect_from_communication(case_id, communications)
        # 分离通讯中的价格异常线索
        comm_suspicion = [c for c in all_comm_clues if c.get("clue_type") != "价格异常"]
        comm_price = [c for c in all_comm_clues if c.get("clue_type") == "价格异常"]
        txn_price_clues = cls.detect_price_anomaly(case_id, transactions)
        role_clues = cls.detect_role_anomaly(case_id, transactions, logistics, communications)

        return {
            "suspicion_clues": comm_suspicion,
            "price_clues": comm_price + txn_price_clues,
            "role_clues": role_clues,
        }

    @classmethod
    def create_suspicious_clue(
        cls,
        case_id: int,
        clue_type: str,
        evidence_text: str,
        hit_keywords: List[str],
        score: int,
        crime_type: str,
        severity_level: str
    ) -> Dict[str, Any]:
        """
        创建可疑线索记录

        Args:
            case_id: 案件ID
            clue_type: 线索类型
            evidence_text: 证据原文
            hit_keywords: 命中关键词列表
            score: 评分
            crime_type: 涉嫌罪名
            severity_level: 严重程度

        Returns:
            创建的线索字典
        """
        # 去重：同案件、同类型、同证据文本视为重复
        existing = SuspiciousClue.get_or_none(
            (SuspiciousClue.case_id == case_id)
            & (SuspiciousClue.clue_type == clue_type)
            & (SuspiciousClue.evidence_text == evidence_text)
        )
        if existing:
            return {
                "id": existing.id,
                "case_id": existing.case_id,
                "clue_type": existing.clue_type,
                "evidence_text": existing.evidence_text,
                "hit_keywords": hit_keywords,
                "score": existing.score,
                "crime_type": existing.crime_type,
                "severity_level": existing.severity_level,
            }

        clue = SuspiciousClue.create(
            case_id=case_id,
            clue_type=clue_type,
            evidence_text=evidence_text,
            hit_keywords=",".join(hit_keywords) if hit_keywords else None,
            score=score,
            crime_type=crime_type,
            severity_level=severity_level,
        )

        return {
            "id": clue.id,
            "case_id": clue.case_id,
            "clue_type": clue.clue_type,
            "evidence_text": clue.evidence_text,
            "hit_keywords": hit_keywords,
            "score": clue.score,
            "crime_type": clue.crime_type,
            "severity_level": clue.severity_level,
        }

    @classmethod
    def get_clue_by_id(cls, clue_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取线索详情

        Args:
            clue_id: 线索ID

        Returns:
            线索详情或None
        """
        try:
            clue = SuspiciousClue.get_by_id(clue_id)
            hit_keywords = clue.hit_keywords.split(",") if clue.hit_keywords else []
            return {
                "id": clue.id,
                "case_id": clue.case_id,
                "clue_type": clue.clue_type,
                "evidence_text": clue.evidence_text,
                "hit_keywords": hit_keywords,
                "score": clue.score,
                "crime_type": clue.crime_type,
                "severity_level": clue.severity_level,
            }
        except SuspiciousClue.DoesNotExist:
            return None

    @classmethod
    def _get_severity_level(cls, score: int) -> str:
        """根据评分获取严重程度"""
        if score >= 8:
            return cls.SEVERITY_CRIMINAL
        elif score >= 5:
            return cls.SEVERITY_TORT
        else:
            return cls.SEVERITY_ADMINISTRATIVE