"""
案件服务
提供案件的创建、查询、管理功能
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime

from models.database import Case, Person, Transaction, Communication, Logistics, SuspiciousClue


class CaseService:
    """案件服务"""

    @classmethod
    def create_case(
        cls,
        case_no: str,
        suspect_name: str,
        brand: Optional[str] = None,
        amount: Optional[Decimal] = None
    ) -> Case:
        """
        创建案件

        Args:
            case_no: 案件编号
            suspect_name: 嫌疑人姓名
            brand: 涉案品牌
            amount: 涉案金额

        Returns:
            创建的案件对象
        """
        case = Case.create(
            case_no=case_no,
            suspect_name=suspect_name,
            brand=brand,
            amount=amount or Decimal("0"),
            created_at=datetime.now()
        )
        return case

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
        offset: int = 0
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
        amount: Optional[Decimal] = None
    ) -> Optional[Case]:
        """
        更新案件信息

        Args:
            case_id: 案件ID
            suspect_name: 嫌疑人姓名
            brand: 涉案品牌
            amount: 涉案金额

        Returns:
            更新后的案件对象或None
        """
        case = cls.get_case_by_id(case_id)
        if not case:
            return None

        if suspect_name is not None:
            case.suspect_name = suspect_name
        if brand is not None:
            case.brand = brand
        if amount is not None:
            case.amount = amount

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
            "transaction_time": t.transaction_time.isoformat() if t.transaction_time else None,
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
            "communication_time": c.communication_time.isoformat() if c.communication_time else None,
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