"""
案件服务
提供案件的创建、查询、管理功能
"""

from typing import Dict, List, Any, Optional, Set
from decimal import Decimal
from datetime import datetime
from collections import Counter

from models.database import (
    Case,
    Person,
    Transaction,
    Communication,
    Logistics,
    SuspiciousClue,
    db,
)
from services.role_detector import RoleDetector
from services.score_service import ScoreService
from utils.keywords_data import BRAND_KEYWORDS


class CaseService:
    """案件服务"""

    DEFAULT_SUSPECT_NAME = "待推导"

    @classmethod
    def create_case(
        cls,
        case_no: str,
        suspect_name: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> Case:
        """
        创建案件

        Args:
            case_no: 案件编号
            suspect_name: 嫌疑人姓名（可选，默认待推导）
            brand: 涉案品牌

        Returns:
            创建的案件对象
        """
        case = Case.create(
            case_no=case_no,
            suspect_name=suspect_name or cls.DEFAULT_SUSPECT_NAME,
            brand=brand,
            amount=Decimal("0"),
            created_at=datetime.now(),
        )
        return case

    @classmethod
    def infer_suspect_name(cls, case_id: int) -> Optional[str]:
        """
        根据当前案件数据推导嫌疑人。

        规则：
        1. 优先基于交易记录推导，收款方权重高于打款方；
        2. 若无交易记录，回退到通讯与物流中的高频主体。
        """
        score_map: Dict[str, Decimal] = {}

        transactions = Transaction.select().where(Transaction.case == case_id)
        has_transactions = False
        for t in transactions:
            has_transactions = True
            amount = t.amount or Decimal("0")
            if t.payer:
                score_map[t.payer] = (
                    score_map.get(t.payer, Decimal("0"))
                    + amount * Decimal("0.8")
                    + Decimal("1")
                )
            if t.payee:
                score_map[t.payee] = (
                    score_map.get(t.payee, Decimal("0"))
                    + amount * Decimal("1.2")
                    + Decimal("1")
                )

        if has_transactions and score_map:
            return max(score_map.items(), key=lambda item: item[1])[0]

        freq = Counter()
        logistics = Logistics.select().where(Logistics.case == case_id)
        for l in logistics:
            if l.sender:
                freq[l.sender] += 1
            if l.receiver:
                freq[l.receiver] += 1

        communications = Communication.select().where(Communication.case == case_id)
        for c in communications:
            if c.initiator:
                freq[c.initiator] += 1
            if c.receiver:
                freq[c.receiver] += 1

        if not freq:
            return None
        return freq.most_common(1)[0][0]

    @classmethod
    def infer_brand(cls, case_id: int) -> Optional[str]:
        """
        根据案件文本证据推导涉案品牌。

        数据来源：交易备注、物流描述、通讯内容。
        """
        text_parts: List[str] = []

        transactions = Transaction.select().where(Transaction.case == case_id)
        for t in transactions:
            if t.remark:
                text_parts.append(t.remark)

        logistics = Logistics.select().where(Logistics.case == case_id)
        for l in logistics:
            if l.description:
                text_parts.append(l.description)

        communications = Communication.select().where(Communication.case == case_id)
        for c in communications:
            if c.content:
                text_parts.append(c.content)

        if not text_parts:
            return None

        full_text = "\n".join(text_parts)
        full_text_lower = full_text.lower()
        brand_hits: Counter = Counter()

        for canonical_brand, aliases in BRAND_KEYWORDS.items():
            for alias in aliases:
                if not alias:
                    continue
                alias_lower = alias.lower()
                brand_hits[canonical_brand] += full_text_lower.count(alias_lower)

        if not brand_hits:
            return None

        brand, hit_count = brand_hits.most_common(1)[0]
        if hit_count <= 0:
            return None
        return brand

    @classmethod
    def auto_update_inferred_fields(cls, case_id: int) -> Optional[Dict[str, Any]]:
        """
        自动推导并回写案件的嫌疑人和品牌字段。

        Returns:
            更新结果字典；若案件不存在返回None
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        inferred_suspect_name = cls.infer_suspect_name(case_id)
        inferred_brand = cls.infer_brand(case_id)

        updated_fields = []
        if inferred_suspect_name and case.suspect_name != inferred_suspect_name:
            case.suspect_name = inferred_suspect_name
            updated_fields.append(Case.suspect_name)

        if inferred_brand and case.brand != inferred_brand:
            case.brand = inferred_brand
            updated_fields.append(Case.brand)

        if updated_fields:
            case.save(only=updated_fields)

        return {
            "case_id": case.id,
            "suspect_name": case.suspect_name,
            "brand": case.brand,
        }

    @classmethod
    def recalculate_case_amount(cls, case_id: int) -> Optional[Decimal]:
        """
        根据资金流水重新计算案件涉案金额。

        Args:
            case_id: 案件ID

        Returns:
            重新计算后的金额；若案件不存在则返回None
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        transactions = Transaction.select().where(Transaction.case == case_id)
        total_amount = sum((t.amount or Decimal("0")) for t in transactions)
        case.amount = total_amount
        case.save(only=[Case.amount])
        return total_amount

    @classmethod
    def _collect_case_person_names(cls, case_id: int) -> Set[str]:
        """收集案件涉及的全部人员姓名（资金/物流/通讯并集）。"""
        names: Set[str] = set()

        transactions = Transaction.select().where(Transaction.case == case_id)
        for t in transactions:
            if t.payer:
                names.add(t.payer.strip())
            if t.payee:
                names.add(t.payee.strip())

        logistics = Logistics.select().where(Logistics.case == case_id)
        for l in logistics:
            if l.sender:
                names.add(l.sender.strip())
            if l.receiver:
                names.add(l.receiver.strip())

        communications = Communication.select().where(Communication.case == case_id)
        for c in communications:
            if c.initiator:
                names.add(c.initiator.strip())
            if c.receiver:
                names.add(c.receiver.strip())

        return {name for name in names if name}

    @classmethod
    def _calculate_person_metrics(cls, person_name: str) -> Dict[str, Any]:
        """计算人员在全库范围内的基础指标。"""
        incoming_amount = Decimal("0")

        incoming_transactions = Transaction.select().where(
            Transaction.payee == person_name
        )
        for t in incoming_transactions:
            incoming_amount += t.amount or Decimal("0")

        linked_case_ids = set()

        trans_query = Transaction.select(Transaction.case).where(
            (Transaction.payer == person_name) | (Transaction.payee == person_name)
        )
        for row in trans_query:
            if row.case_id:
                linked_case_ids.add(row.case_id)

        logistics_query = Logistics.select(Logistics.case).where(
            (Logistics.sender == person_name) | (Logistics.receiver == person_name)
        )
        for row in logistics_query:
            if row.case_id:
                linked_case_ids.add(row.case_id)

        comm_query = Communication.select().where(
            (Communication.initiator == person_name)
            | (Communication.receiver == person_name)
        )
        communications_data: List[Dict[str, Any]] = []
        for row in comm_query:
            if row.case_id:
                linked_case_ids.add(row.case_id)
            communications_data.append(
                {
                    "communication_time": row.communication_time,
                    "initiator": row.initiator,
                    "receiver": row.receiver,
                    "content": row.content,
                }
            )

        transactions_data = [
            {
                "transaction_time": t.transaction_time,
                "payer": t.payer,
                "payee": t.payee,
                "amount": t.amount,
                "remark": t.remark,
            }
            for t in Transaction.select().where(
                (Transaction.payer == person_name) | (Transaction.payee == person_name)
            )
        ]

        logistics_data = [
            {
                "shipping_time": l.shipping_time,
                "sender": l.sender,
                "receiver": l.receiver,
                "description": l.description,
            }
            for l in Logistics.select().where(
                (Logistics.sender == person_name) | (Logistics.receiver == person_name)
            )
        ]

        role_result = RoleDetector.detect_role(
            transactions_data,
            logistics_data,
            communications_data,
            person_name,
        )

        comm_text = "\n".join(
            [str(c.get("content") or "").strip() for c in communications_data]
        ).strip()
        subjective_score = (
            ScoreService.analyze_text(comm_text).get("score", 0) if comm_text else 0
        )

        return {
            "role": role_result.get("role", "待定"),
            "subjective_knowledge_score": subjective_score,
            "illegal_business_amount": incoming_amount,
            "linked_cases": len(linked_case_ids),
        }

    @classmethod
    def sync_case_persons_to_db(cls, case_id: int) -> Optional[Dict[str, Any]]:
        """
        将案件涉及人员同步到 persons 表。

        当前策略：全局人物档按姓名聚合，导入后执行幂等 upsert。
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        person_names = sorted(cls._collect_case_person_names(case_id))
        created_count = 0
        updated_count = 0

        with db.atomic():
            for name in person_names:
                metrics = cls._calculate_person_metrics(name)
                person, created = Person.get_or_create(
                    name=name,
                    defaults={
                        "role": metrics["role"],
                        "subjective_knowledge_score": metrics[
                            "subjective_knowledge_score"
                        ],
                        "illegal_business_amount": metrics["illegal_business_amount"],
                        "linked_cases": metrics["linked_cases"],
                    },
                )

                if created:
                    created_count += 1
                    continue

                person.role = metrics["role"]
                person.subjective_knowledge_score = metrics[
                    "subjective_knowledge_score"
                ]
                person.illegal_business_amount = metrics["illegal_business_amount"]
                person.linked_cases = metrics["linked_cases"]
                person.save(
                    only=[
                        Person.role,
                        Person.subjective_knowledge_score,
                        Person.illegal_business_amount,
                        Person.linked_cases,
                    ]
                )
                updated_count += 1

        return {
            "case_id": case_id,
            "case_person_count": len(person_names),
            "created": created_count,
            "updated": updated_count,
        }

    @classmethod
    def get_case_by_id(cls, case_id: int) -> Optional[Case]:
        """
        根据ID查询案件

        Args:
            case_id: 案件ID

        Returns:
            案件对象或None
        """
        try:
            return Case.get_by_id(case_id)
        except Case.DoesNotExist:
            return None

    @classmethod
    def get_case_by_no(cls, case_no: str) -> Optional[Case]:
        """
        根据案件编号查询案件

        Args:
            case_no: 案件编号

        Returns:
            案件对象或None
        """
        try:
            return Case.get(Case.case_no == case_no)
        except Case.DoesNotExist:
            return None

    @classmethod
    def list_cases(
        cls,
        case_no: Optional[str] = None,
        suspect_name: Optional[str] = None,
        brand: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        查询案件列表

        Args:
            case_no: 案件编号（模糊匹配）
            suspect_name: 嫌疑人姓名（模糊匹配）
            brand: 涉案品牌（模糊匹配）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            案件列表
        """
        query = Case.select()

        if case_no:
            query = query.where(Case.case_no.contains(case_no))
        if suspect_name:
            query = query.where(Case.suspect_name.contains(suspect_name))
        if brand:
            query = query.where(Case.brand.contains(brand))

        query = query.order_by(Case.created_at.desc()).limit(limit).offset(offset)

        cases = []
        for case in query:
            cases.append(cls._case_to_dict(case))
        return cases

    @classmethod
    def get_case_detail(cls, case_id: int) -> Optional[Dict[str, Any]]:
        """
        获取案件详情，包含关联数据

        Args:
            case_id: 案件ID

        Returns:
            案件详情字典或None
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        return {
            "case": cls._case_to_dict(case),
            "transactions": cls.get_case_transactions(case_id),
            "communications": cls.get_case_communications(case_id),
            "logistics": cls.get_case_logistics(case_id),
            "persons": cls.get_case_persons(case_id),
            "suspicious_clues": cls.get_case_suspicious_clues(case_id),
            "statistics": cls.get_case_statistics(case_id),
        }

    @classmethod
    def get_case_transactions(cls, case_id: int) -> List[Dict[str, Any]]:
        """
        获取案件的资金流水

        Args:
            case_id: 案件ID

        Returns:
            资金流水列表
        """
        transactions = Transaction.select().where(Transaction.case == case_id)
        return [cls._transaction_to_dict(t) for t in transactions]

    @classmethod
    def get_case_communications(cls, case_id: int) -> List[Dict[str, Any]]:
        """
        获取案件的通讯记录

        Args:
            case_id: 案件ID

        Returns:
            通讯记录列表
        """
        communications = Communication.select().where(Communication.case == case_id)
        return [cls._communication_to_dict(c) for c in communications]

    @classmethod
    def get_case_logistics(cls, case_id: int) -> List[Dict[str, Any]]:
        """
        获取案件的物流记录

        Args:
            case_id: 案件ID

        Returns:
            物流记录列表
        """
        logistics = Logistics.select().where(Logistics.case == case_id)
        return [cls._logistics_to_dict(l) for l in logistics]

    @classmethod
    def get_case_persons(cls, case_id: int) -> List[Dict[str, Any]]:
        """
        获取案件涉及的人员

        Args:
            case_id: 案件ID

        Returns:
            人员列表
        """
        # 从资金流水中提取人员
        transactions = Transaction.select().where(Transaction.case == case_id)
        persons_set = set()
        for t in transactions:
            if t.payer:
                persons_set.add(t.payer)
            if t.payee:
                persons_set.add(t.payee)

        # 从物流中提取人员
        logistics = Logistics.select().where(Logistics.case == case_id)
        for l in logistics:
            if l.sender:
                persons_set.add(l.sender)
            if l.receiver:
                persons_set.add(l.receiver)

        # 从通讯中提取人员
        communications = Communication.select().where(Communication.case == case_id)
        for c in communications:
            if c.initiator:
                persons_set.add(c.initiator)
            if c.receiver:
                persons_set.add(c.receiver)

        return [{"name": name} for name in persons_set]

    @classmethod
    def get_case_suspicious_clues(cls, case_id: int) -> List[Dict[str, Any]]:
        """
        获取案件的可疑线索

        Args:
            case_id: 案件ID

        Returns:
            可疑线索列表
        """
        clues = SuspiciousClue.select().where(SuspiciousClue.case == case_id)
        return [cls._clue_to_dict(c) for c in clues]

    @classmethod
    def get_case_statistics(cls, case_id: int) -> Dict[str, Any]:
        """
        获取案件统计数据

        Args:
            case_id: 案件ID

        Returns:
            统计数据
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return {}

        transactions = Transaction.select().where(Transaction.case == case_id)
        communications = Communication.select().where(Communication.case == case_id)
        logistics = Logistics.select().where(Logistics.case == case_id)
        clues = SuspiciousClue.select().where(SuspiciousClue.case == case_id)

        # 计算总交易金额
        total_transaction_amount = sum(t.amount for t in transactions)

        # 提取人员数
        persons_set = set()
        for t in transactions:
            if t.payer:
                persons_set.add(t.payer)
            if t.payee:
                persons_set.add(t.payee)
        for l in logistics:
            if l.sender:
                persons_set.add(l.sender)
            if l.receiver:
                persons_set.add(l.receiver)

        return {
            "transaction_count": len(transactions),
            "communication_count": len(communications),
            "logistics_count": len(logistics),
            "suspicious_clue_count": len(clues),
            "person_count": len(persons_set),
            "total_transaction_amount": float(total_transaction_amount),
        }

    @classmethod
    def update_case(
        cls,
        case_id: int,
        suspect_name: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> Optional[Case]:
        """
        更新案件信息

        Args:
            case_id: 案件ID
            suspect_name: 嫌疑人姓名
            brand: 涉案品牌

        Returns:
            更新后的案件对象或None
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        # suspect_name/brand 为推导字段，不允许通过该接口手工修改

        case.save()
        return case

    @classmethod
    def delete_case(cls, case_id: int) -> bool:
        """
        删除案件（级联删除关联数据）

        Args:
            case_id: 案件ID

        Returns:
            是否删除成功
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return False

        # 外键设置了CASCADE，会自动删除关联数据
        case.delete_instance()
        return True

    # ==================== 私有转换方法 ====================

    @classmethod
    def _case_to_dict(cls, case: Case) -> Dict[str, Any]:
        """案件对象转字典"""
        return {
            "id": case.id,
            "case_no": case.case_no,
            "suspect_name": case.suspect_name,
            "brand": case.brand,
            "amount": float(case.amount) if case.amount else 0,
            "created_at": case.created_at.isoformat() if case.created_at else None,
        }

    @classmethod
    def _transaction_to_dict(cls, t: Transaction) -> Dict[str, Any]:
        """资金流水对象转字典"""
        return {
            "id": t.id,
            "case_id": t.case.id if t.case else None,
            "transaction_time": (
                t.transaction_time.isoformat() if t.transaction_time else None
            ),
            "payer": t.payer,
            "payee": t.payee,
            "amount": float(t.amount) if t.amount else 0,
            "payment_method": t.payment_method,
            "remark": t.remark,
        }

    @classmethod
    def _communication_to_dict(cls, c: Communication) -> Dict[str, Any]:
        """通讯记录对象转字典"""
        return {
            "id": c.id,
            "case_id": c.case.id if c.case else None,
            "communication_time": (
                c.communication_time.isoformat() if c.communication_time else None
            ),
            "initiator": c.initiator,
            "receiver": c.receiver,
            "content": c.content,
        }

    @classmethod
    def _logistics_to_dict(cls, l: Logistics) -> Dict[str, Any]:
        """物流记录对象转字典"""
        return {
            "id": l.id,
            "case_id": l.case.id if l.case else None,
            "shipping_time": l.shipping_time.isoformat() if l.shipping_time else None,
            "tracking_no": l.tracking_no,
            "sender": l.sender,
            "sender_address": l.sender_address,
            "receiver": l.receiver,
            "receiver_address": l.receiver_address,
            "description": l.description,
            "weight": float(l.weight) if l.weight else None,
        }

    @classmethod
    def _clue_to_dict(cls, c: SuspiciousClue) -> Dict[str, Any]:
        """可疑线索对象转字典"""
        return {
            "id": c.id,
            "case_id": c.case.id if c.case else None,
            "clue_type": c.clue_type,
            "evidence_text": c.evidence_text,
            "hit_keywords": c.hit_keywords,
            "score": c.score,
            "crime_type": c.crime_type,
            "severity_level": c.severity_level,
        }
