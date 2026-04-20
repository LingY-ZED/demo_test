"""
数据台账服务
人员台账、交易台账、证据清单查询
"""
from typing import Dict, List, Any, Optional
from collections import defaultdict
from decimal import Decimal

from models.database import Case, Person, Transaction, Communication, Logistics, SuspiciousClue
from services.score_service import ScoreService
from services.role_detector import RoleDetector
from utils.keywords import keyword_library


class LedgerService:
    """数据台账服务"""

    @classmethod
    def get_person_ledger(
        cls,
        name: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        人员台账查询
        """
        query = Person.select()

        if name:
            query = query.where(Person.name.contains(name))
        if role:
            query = query.where(Person.role == role)

        query = query.limit(limit).offset(offset)

        ledger = []
        for p in query:
            # 尝试获取关联的案件编号 (全量检查资金、通讯、物流)
            case_no = "未知案件"
            # 1. 检查资金
            trans = Transaction.select().join(Case).where((Transaction.payer == p.name) | (Transaction.payee == p.name)).first()
            if trans:
                case_no = trans.case.case_no
            else:
                # 2. 检查通讯
                comm = Communication.select().join(Case).where((Communication.initiator == p.name) | (Communication.receiver == p.name)).first()
                if comm:
                    case_no = comm.case.case_no
                else:
                    # 3. 检查物流
                    logi = Logistics.select().join(Case).where((Logistics.sender == p.name) | (Logistics.receiver == p.name)).first()
                    if logi:
                        case_no = logi.case.case_no

            ledger.append({
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "case_no": case_no,
                "is_authorized": p.is_authorized,
                "subjective_knowledge_score": p.subjective_knowledge_score,
                "illegal_business_amount": float(p.illegal_business_amount) if p.illegal_business_amount else 0,
                "linked_cases": p.linked_cases,
            })

        return ledger

    @classmethod
    def get_person_detail(
        cls,
        person_name: str
    ) -> Dict[str, Any]:
        """
        人员详情
        """
        # 查找人员记录
        try:
            person = Person.get(Person.name == person_name)
        except Person.DoesNotExist:
            person = None

        # 从所有案件的交易中收集该人员的信息
        transactions = Transaction.select()
        related_transactions = []
        total_amount = Decimal("0")

        for t in transactions:
            if t.payer == person_name or t.payee == person_name:
                related_transactions.append({
                    "case_id": t.case.id,
                    "case_no": t.case.case_no,
                    "type": "付款" if t.payer == person_name else "收款",
                    "counterparty": t.payee if t.payer == person_name else t.payer,
                    "amount": float(t.amount),
                    "time": t.transaction_time.isoformat() if t.transaction_time else None,
                })
                total_amount += t.amount

        # 从通讯记录中收集
        communications = Communication.select()
        related_communications = []
        for c in communications:
            if c.initiator == person_name or c.receiver == person_name:
                related_communications.append({
                    "case_id": c.case.id,
                    "case_no": c.case.case_no,
                    "type": "发起" if c.initiator == person_name else "接收",
                    "counterparty": c.receiver if c.initiator == person_name else c.initiator,
                    "content": c.content,
                    "time": c.communication_time.isoformat() if c.communication_time else None,
                })

        # 从物流记录中收集
        logistics = Logistics.select()
        related_logistics = []
        for l in logistics:
            if l.sender == person_name or l.receiver == person_name:
                related_logistics.append({
                    "case_id": l.case.id,
                    "case_no": l.case.case_no,
                    "type": "发货" if l.sender == person_name else "收货",
                    "counterparty": l.receiver if l.sender == person_name else l.sender,
                    "description": l.description,
                    "time": l.shipping_time.isoformat() if l.shipping_time else None,
                })

        # 计算涉及案件数
        case_ids = set()
        for t in related_transactions:
            case_ids.add(t["case_id"])
        for c in related_communications:
            case_ids.add(c["case_id"])
        for l in related_logistics:
            case_ids.add(l["case_id"])

        return {
            "name": person_name,
            "role": person.role if person else None,
            "is_authorized": person.is_authorized if person else None,
            "subjective_knowledge_score": person.subjective_knowledge_score if person else 0,
            "linked_cases": len(case_ids),
            "total_transaction_amount": float(total_amount),
            "transactions": related_transactions,
            "communications": related_communications,
            "logistics": related_logistics,
            "case_ids": list(case_ids),
        }

    @classmethod
    def get_transaction_ledger(
        cls,
        case_no: Optional[str] = None,
        payer: Optional[str] = None,
        payee: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        交易台账查询
        """
        query = Transaction.select().join(Case)

        if case_no:
            query = query.where(Case.case_no.contains(case_no))
        if payer:
            query = query.where(Transaction.payer.contains(payer))
        if payee:
            query = query.where(Transaction.payee.contains(payee))

        query = query.order_by(Transaction.transaction_time.desc()).limit(limit).offset(offset)

        ledger = []
        for t in query:
            ledger.append({
                "id": t.id,
                "case_id": t.case.id,
                "case_no": t.case.case_no,
                "transaction_time": t.transaction_time.isoformat() if t.transaction_time else None,
                "payer": t.payer,
                "payee": t.payee,
                "amount": float(t.amount) if t.amount else 0,
                "payment_method": t.payment_method,
                "remark": t.remark,
            })

        return ledger

    @classmethod
    def get_high_frequency_persons(
        cls,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        高频交易人员统计
        """
        # 统计每个人员的交易次数
        person_transaction_count = defaultdict(int)
        person_total_amount = defaultdict(float)

        transactions = Transaction.select()
        for t in transactions:
            if t.payer:
                person_transaction_count[t.payer] += 1
                person_total_amount[t.payer] += float(t.amount) if t.amount else 0
            if t.payee:
                person_transaction_count[t.payee] += 1
                person_total_amount[t.payee] += float(t.amount) if t.amount else 0

        # 排序
        sorted_persons = sorted(
            person_transaction_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {
                "name": name,
                "transaction_count": count,
                "total_amount": person_total_amount[name],
            }
            for name, count in sorted_persons[:limit]
        ]

    @classmethod
    def get_evidence_inventory(
        cls,
        case_id: int
    ) -> Dict[str, Any]:
        """
        证据清单汇总
        """
        case = Case.get_by_id(case_id)

        # 收集所有通讯记录中的可疑证据
        communications = Communication.select().where(Communication.case == case_id)
        communication_evidence = []

        for c in communications:
            content = c.content or ""
            matches = keyword_library.search(content)

            if matches:
                score_result = ScoreService.analyze_text(content)
                score = score_result["score"]
                severity = "刑事犯罪" if score >= 8 else "民事侵权" if score >= 5 else "行政违法"
                
                communication_evidence.append({
                    "type": "通讯记录",
                    "id": c.id,
                    "case_no": case.case_no,
                    "time": c.communication_time.isoformat() if c.communication_time else None,
                    "initiator": c.initiator,
                    "receiver": c.receiver,
                    "content": content,
                    "hit_keywords": [m["word"] for m in matches],
                    "score": score,
                    "crime_type": ScoreService.get_crime_type(matches),
                    "severity_level": severity,
                })

        # 收集价格异常证据
        transactions = Transaction.select().where(Transaction.case == case_id)
        price_anomaly_evidence = []

        for t in transactions:
            remark = t.remark or ""
            matches = keyword_library.search(remark)

            if matches:
                price_anomaly_evidence.append({
                    "type": "交易备注",
                    "id": t.id,
                    "case_no": case.case_no,
                    "time": t.transaction_time.isoformat() if t.transaction_time else None,
                    "payer": t.payer,
                    "payee": t.payee,
                    "amount": float(t.amount) if t.amount else 0,
                    "remark": remark,
                    "hit_keywords": [m["word"] for m in matches],
                    "score": 3,  # 交易备注命关键词通常定义为低度可疑
                    "severity_level": "行政违法",
                    "crime_type": "价格异常",
                })

        # 收集物流异常
        logistics = Logistics.select().where(Logistics.case == case_id)
        logistics_evidence = []

        for l in logistics:
            description = l.description or ""
            matches = keyword_library.search(description)

            if matches:
                logistics_evidence.append({
                    "type": "物流物品描述",
                    "id": l.id,
                    "case_no": case.case_no,
                    "time": l.shipping_time.isoformat() if l.shipping_time else None,
                    "sender": l.sender,
                    "receiver": l.receiver,
                    "description": description,
                    "hit_keywords": [m["word"] for m in matches],
                    "score": 3,
                    "severity_level": "行政违法",
                    "crime_type": "物流异常",
                })

        # 汇总
        all_evidence = communication_evidence + price_anomaly_evidence + logistics_evidence

        return {
            "case_id": case_id,
            "case_no": case.case_no,
            "total_evidence_count": len(all_evidence),
            "communication_evidence_count": len(communication_evidence),
            "price_anomaly_evidence_count": len(price_anomaly_evidence),
            "logistics_evidence_count": len(logistics_evidence),
            "evidence_list": all_evidence,
        }

    @classmethod
    def get_case_summary(
        cls,
        case_id: int
    ) -> Dict[str, Any]:
        """
        案件摘要

        Args:
            case_id: 案件ID

        Returns:
            案件摘要信息
        """
        case = Case.get_by_id(case_id)

        transactions = Transaction.select().where(Transaction.case == case_id)
        communications = Communication.select().where(Communication.case == case_id)
        logistics = Logistics.select().where(Logistics.case == case_id)
        clues = SuspiciousClue.select().where(SuspiciousClue.case == case_id)

        # 计算总金额
        total_amount = sum(float(t.amount) for t in transactions)

        # 提取人员
        persons = set()
        for t in transactions:
            if t.payer:
                persons.add(t.payer)
            if t.payee:
                persons.add(t.payee)
        for l in logistics:
            if l.sender:
                persons.add(l.sender)
            if l.receiver:
                persons.add(l.receiver)

        # 高危线索统计
        high_risk_clues = [c for c in clues if c.score >= 8]
        medium_risk_clues = [c for c in clues if 5 <= c.score < 8]

        return {
            "case_id": case_id,
            "case_no": case.case_no,
            "suspect_name": case.suspect_name,
            "brand": case.brand,
            "total_amount": total_amount,
            "transaction_count": len(transactions),
            "communication_count": len(communications),
            "logistics_count": len(logistics),
            "person_count": len(persons),
            "suspicious_clue_count": len(clues),
            "high_risk_clue_count": len(high_risk_clues),
            "medium_risk_clue_count": len(medium_risk_clues),
        }