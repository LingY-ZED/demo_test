"""
关联分析服务
单案上下游产业链分析、跨案关联、累犯标记
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from services.relation_analyzer import RelationAnalyzer
from services.role_detector import RoleDetector
from services.amount_calculator import AmountCalculator
from models.database import Case, Transaction, Communication, Logistics


class RelationService:
    """关联分析服务"""

    # 累犯时间阈值（两年）
    RECIDIVISM_YEARS = 2

    @classmethod
    def analyze_case_chain(
        cls,
        case_id: int
    ) -> Dict[str, Any]:
        """
        单案上下游产业链分析

        Args:
            case_id: 案件ID

        Returns:
            产业链分析结果
        """
        # 获取案件数据
        transactions = cls._get_case_transactions(case_id)
        logistics = cls._get_case_logistics(case_id)
        communications = cls._get_case_communications(case_id)

        # 使用RelationAnalyzer构建关系图谱
        relation_graph = RelationAnalyzer.build_relation_graph(
            transactions, logistics, communications
        )

        # 分析每个角色的涉嫌罪名
        role_analysis = cls._analyze_roles(
            transactions, logistics, communications, relation_graph
        )

        # 计算涉案金额
        amount_summary = cls._calculate_amount_summary(transactions, relation_graph)

        return {
            "case_id": case_id,
            "relation_graph": relation_graph,
            "role_analysis": role_analysis,
            "amount_summary": amount_summary,
            "upstream_count": len(relation_graph.get("upstream", [])),
            "downstream_count": len(relation_graph.get("downstream", [])),
            "core_count": len(relation_graph.get("core", [])),
        }

    @classmethod
    def find_cross_case_connections(cls) -> List[Dict[str, Any]]:
        """
        跨案关联拓扑

        找出同一人员/账户在不同案件中的关联

        Returns:
            跨案关联列表
        """
        # 获取所有案件数据
        cases = Case.select()
        cases_data = []

        for case in cases:
            transactions = cls._get_case_transactions(case.id)
            persons = set()

            for t in transactions:
                if t.get("payer"):
                    persons.add(t.get("payer"))
                if t.get("payee"):
                    persons.add(t.get("payee"))

            cases_data.append({
                "case_id": case.id,
                "case_no": case.case_no,
                "persons": list(persons),
                "transactions": transactions,
            })

        # 使用RelationAnalyzer的跨案分析
        connections = RelationAnalyzer.find_cross_case_connections(cases_data)

        # 补充案件信息
        case_map = {c.id: c for c in cases}
        for conn in connections:
            conn["case_details"] = []
            for case_id in conn["case_ids"]:
                case = case_map.get(case_id)
                if case:
                    conn["case_details"].append({
                        "case_no": case.case_no,
                        "suspect_name": case.suspect_name,
                        "brand": case.brand,
                    })

        return connections

    @classmethod
    def detect_recidivism(
        cls,
        person_name: str,
        check_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        累犯检测

        检测某人在两年内是否有同类违法行为

        Args:
            person_name: 人员姓名
            check_date: 检测日期（默认为当前日期）

        Returns:
            累犯检测结果
        """
        if check_date is None:
            check_date = datetime.now()

        threshold_date = check_date - timedelta(days=365 * cls.RECIDIVISM_YEARS)

        # 查询该人员在阈值日期之后的案件
        query = (
            Transaction.select()
            .join(Case, on=(Transaction.case == Case.id))
            .where(
                (Transaction.payer == person_name) | (Transaction.payee == person_name)
            )
            .where(Case.created_at >= threshold_date)
        )

        related_cases = []
        for t in query:
            case = t.case
            related_cases.append({
                "case_id": case.id,
                "case_no": case.case_no,
                "suspect_name": case.suspect_name,
                "transaction_time": t.transaction_time.isoformat() if t.transaction_time else None,
                "amount": float(t.amount) if t.amount else 0,
            })

        # 判断是否构成累犯（涉及多个案件）
        is_recidivist = len(set(c["case_id"] for c in related_cases)) > 1

        return {
            "person_name": person_name,
            "is_recidivist": is_recidivist,
            "check_date": check_date.isoformat(),
            "threshold_years": cls.RECIDIVISM_YEARS,
            "related_cases": related_cases,
            "case_count": len(set(c["case_id"] for c in related_cases)),
        }

    @classmethod
    def get_upstream_suppliers(
        cls,
        case_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取上游供货商列表

        Args:
            case_id: 案件ID

        Returns:
            上游供货商列表（含证据）
        """
        transactions = cls._get_case_transactions(case_id)
        logistics = cls._get_case_logistics(case_id)

        # 使用RelationAnalyzer分析资金流
        money_flow = RelationAnalyzer.analyze_money_flow(transactions)
        upstream_names = money_flow.get("upstream", [])

        # 获取每个上游的详细信息
        upstream_suppliers = []
        for name in upstream_names:
            supplier = {
                "name": name,
                "total_out_amount": money_flow["node_details"].get(name, {}).get("out_amount", 0),
                "counterparties": money_flow["node_details"].get(name, {}).get("counterparties", []),
                "evidence": cls._collect_upstream_evidence(name, transactions, logistics),
            }
            upstream_suppliers.append(supplier)

        return upstream_suppliers

    @classmethod
    def get_downstream_buyers(
        cls,
        case_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取下游买家列表

        Args:
            case_id: 案件ID

        Returns:
            下游买家列表（含证据）
        """
        transactions = cls._get_case_transactions(case_id)
        logistics = cls._get_case_logistics(case_id)

        # 使用RelationAnalyzer分析资金流
        money_flow = RelationAnalyzer.analyze_money_flow(transactions)
        downstream_names = money_flow.get("downstream", [])

        # 获取每个下游的详细信息
        downstream_buyers = []
        for name in downstream_names:
            buyer = {
                "name": name,
                "total_in_amount": money_flow["node_details"].get(name, {}).get("in_amount", 0),
                "counterparties": money_flow["node_details"].get(name, {}).get("counterparties", []),
                "evidence": cls._collect_downstream_evidence(name, transactions, logistics),
            }
            downstream_buyers.append(buyer)

        return downstream_buyers

    @classmethod
    def get_core_suspects(
        cls,
        case_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取核心嫌疑人列表

        Args:
            case_id: 案件ID

        Returns:
            核心嫌疑人列表（含角色分析）
        """
        transactions = cls._get_case_transactions(case_id)
        logistics = cls._get_case_logistics(case_id)
        communications = cls._get_case_communications(case_id)

        # 使用RelationAnalyzer分析资金流
        money_flow = RelationAnalyzer.analyze_money_flow(transactions)
        core_names = money_flow.get("core", [])

        # 获取每个核心嫌疑人的角色分析
        core_suspects = []
        for name in core_names:
            role_result = RoleDetector.detect_role(
                transactions, logistics, communications, name
            )
            evidence = RoleDetector.get_role_evidence(
                transactions, logistics, communications, name
            )

            suspect = {
                "name": name,
                "role": role_result["role"],
                "crime_type": role_result["crime_type"],
                "behavior_role": role_result["behavior_role"],
                "keyword_roles": role_result["keyword_roles"],
                "evidence": evidence,
            }
            core_suspects.append(suspect)

        return core_suspects

    # ==================== 私有辅助方法 ====================

    @classmethod
    def _get_case_transactions(cls, case_id: int) -> List[Dict[str, Any]]:
        """获取案件的资金流水"""
        trans = Transaction.select().where(Transaction.case == case_id)
        return [
            {
                "id": t.id,
                "transaction_time": t.transaction_time,
                "payer": t.payer,
                "payee": t.payee,
                "amount": t.amount,
                "payment_method": t.payment_method,
                "remark": t.remark,
            }
            for t in trans
        ]

    @classmethod
    def _get_case_logistics(cls, case_id: int) -> List[Dict[str, Any]]:
        """获取案件的物流记录"""
        logis = Logistics.select().where(Logistics.case == case_id)
        return [
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

    @classmethod
    def _get_case_communications(cls, case_id: int) -> List[Dict[str, Any]]:
        """获取案件的通讯记录"""
        comms = Communication.select().where(Communication.case == case_id)
        return [
            {
                "id": c.id,
                "communication_time": c.communication_time,
                "initiator": c.initiator,
                "receiver": c.receiver,
                "content": c.content,
            }
            for c in comms
        ]

    @classmethod
    def _analyze_roles(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        relation_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析各角色的涉嫌罪名"""
        role_summary = {
            "producers": [],
            "sellers": [],
            "middlemen": [],
            "buyers": [],
            "unknown": [],
        }

        # 分析核心人员
        for node in relation_graph.get("nodes", []):
            name = node.get("name")
            if not name:
                continue

            role_result = RoleDetector.detect_role(
                transactions, logistics, communications, name
            )

            role = role_result["role"]
            if role == "生产者":
                role_summary["producers"].append(name)
            elif role == "销售者":
                role_summary["sellers"].append(name)
            elif role == "中间商":
                role_summary["middlemen"].append(name)
            elif role == "终端买家":
                role_summary["buyers"].append(name)
            else:
                role_summary["unknown"].append(name)

        return role_summary

    @classmethod
    def _calculate_amount_summary(
        cls,
        transactions: List[Dict[str, Any]],
        relation_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算涉案金额汇总"""
        total_amount = sum(float(t.get("amount", 0)) for t in transactions)

        # 使用AmountCalculator计算
        amount_calc = AmountCalculator.calculate_illegal_income(total_amount)

        return {
            "total_transaction_amount": total_amount,
            "illegal_business_amount": amount_calc.get("illegal_business_amount", total_amount),
            "illegal_income": amount_calc.get("illegal_income", total_amount * 0.7),
            "cost_ratio": amount_calc.get("cost_ratio", 0.3),
            "threshold_check": AmountCalculator.check_threshold(
                total_amount,
                amount_calc.get("illegal_income", total_amount * 0.7),
                1  # 假设1个商标
            ),
        }

    @classmethod
    def _collect_upstream_evidence(
        cls,
        person_name: str,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """收集上游供货商的证据"""
        evidence = {"transactions": [], "logistics": []}

        for t in transactions:
            if t.get("payer") == person_name:
                evidence["transactions"].append({
                    "type": "付款",
                    "counterparty": t.get("payee"),
                    "amount": float(t.get("amount", 0)),
                    "time": str(t.get("transaction_time")) if t.get("transaction_time") else None,
                })

        for l in logistics:
            if l.get("sender") == person_name:
                evidence["logistics"].append({
                    "type": "发货",
                    "counterparty": l.get("receiver"),
                    "description": l.get("description"),
                    "time": str(l.get("shipping_time")) if l.get("shipping_time") else None,
                })

        return evidence

    @classmethod
    def _collect_downstream_evidence(
        cls,
        person_name: str,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """收集下游买家的证据"""
        evidence = {"transactions": [], "logistics": []}

        for t in transactions:
            if t.get("payee") == person_name:
                evidence["transactions"].append({
                    "type": "收款",
                    "counterparty": t.get("payer"),
                    "amount": float(t.get("amount", 0)),
                    "time": str(t.get("transaction_time")) if t.get("transaction_time") else None,
                })

        for l in logistics:
            if l.get("receiver") == person_name:
                evidence["logistics"].append({
                    "type": "收货",
                    "counterparty": l.get("sender"),
                    "description": l.get("description"),
                    "time": str(l.get("shipping_time")) if l.get("shipping_time") else None,
                })

        return evidence