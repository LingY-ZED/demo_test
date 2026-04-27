"""
数据清洗服务
自动提取人物档案、隐蔽发货源头，重复数据去重
"""
from datetime import datetime
from typing import Dict, List, Set, Any
from collections import defaultdict

from models import Person, Transaction, Logistics, db
from services.upload_service import UploadService


class CleanService:
    """数据清洗服务"""

    @classmethod
    def clean_transactions(cls, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗资金流水数据
        - 去除重复记录
        - 标准化日期格式
        - 提取人物信息
        """
        seen = set()
        cleaned = []

        for record in records:
            # 去重依据：时间+金额+双方
            key = (
                record.get("transaction_time"),
                record.get("payer"),
                record.get("payee"),
                record.get("amount"),
            )
            if key not in seen:
                seen.add(key)
                # 标准化日期
                if isinstance(record.get("transaction_time"), str):
                    record["transaction_time"] = UploadService._parse_datetime(
                        record["transaction_time"]
                    )
                cleaned.append(record)

        return cleaned

    @classmethod
    def clean_communications(cls, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗通讯记录数据
        - 去除重复记录
        - 标准化日期
        """
        seen = set()
        cleaned = []

        for record in records:
            key = (
                record.get("communication_time"),
                record.get("initiator"),
                record.get("receiver"),
                record.get("content"),
            )
            if key not in seen:
                seen.add(key)
                if isinstance(record.get("communication_time"), str):
                    record["communication_time"] = UploadService._parse_datetime(
                        record["communication_time"]
                    )
                cleaned.append(record)

        return cleaned

    @classmethod
    def clean_logistics(cls, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗物流记录数据
        - 去除重复记录（快递单号）
        - 标准化日期
        """
        seen = set()
        cleaned = []

        for record in records:
            tracking_no = record.get("tracking_no")
            # 按快递单号去重
            if tracking_no and tracking_no not in seen:
                seen.add(tracking_no)
                if isinstance(record.get("shipping_time"), str):
                    record["shipping_time"] = UploadService._parse_datetime(
                        record["shipping_time"]
                    )
                cleaned.append(record)
            elif not tracking_no:
                # 没有单号的记录也保留
                if isinstance(record.get("shipping_time"), str):
                    record["shipping_time"] = UploadService._parse_datetime(
                        record["shipping_time"]
                    )
                cleaned.append(record)

        return cleaned

    @classmethod
    def extract_persons_from_transactions(
        cls, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        从资金流水中提取人物档案
        自动抓取打款方和收款方
        """
        persons_map = {}

        for record in records:
            payer = record.get("payer", "").strip()
            payee = record.get("payee", "").strip()

            # 提取打款方
            if payer and payer not in persons_map:
                persons_map[payer] = {
                    "name": payer,
                    "role": None,  # 待定
                    "is_authorized": None,
                    "subjective_knowledge_score": 0,
                    "illegal_business_amount": 0,
                    "linked_cases": 0,
                }

            # 提取收款方
            if payee and payee not in persons_map:
                persons_map[payee] = {
                    "name": payee,
                    "role": None,
                    "is_authorized": None,
                    "subjective_knowledge_score": 0,
                    "illegal_business_amount": 0,
                    "linked_cases": 0,
                }

            # 累加收款方的涉案金额
            if payee and payee in persons_map:
                persons_map[payee]["illegal_business_amount"] += float(
                    record.get("amount", 0)
                )

        return list(persons_map.values())

    @classmethod
    def extract_hidden_shipping_sources(
        cls, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        从物流记录中提取"隐蔽发货源头"
        找出多个包裹共同的发送地址
        """
        # 按发件地址分组统计
        address_count = defaultdict(list)

        for record in records:
            sender = record.get("sender", "").strip()
            sender_address = record.get("sender_address", "").strip()

            if sender_address:
                address_count[sender_address].append(
                    {
                        "sender": sender,
                        "tracking_no": record.get("tracking_no"),
                        "description": record.get("description"),
                    }
                )

        # 筛选出发货次数>=2的地址（隐蔽源头）
        hidden_sources = []
        for address, shipments in address_count.items():
            if len(shipments) >= 2:
                hidden_sources.append(
                    {
                        "address": address,
                        "shipment_count": len(shipments),
                        "senders": list(set([s["sender"] for s in shipments])),
                        "shipments": shipments,
                    }
                )

        return hidden_sources

    @classmethod
    def analyze_pre_transfer_communications(
        cls,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        window_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        分析转账前的联络行为
        比对通讯记录时间，看是否在转账前有联系

        Args:
            transactions: 交易记录
            communications: 通讯记录
            window_minutes: 联络窗口（分钟），默认30分钟
        """
        results = []

        for trans in transactions:
            trans_time = trans.get("transaction_time")
            payer = trans.get("payer", "").strip()
            payee = trans.get("payee", "").strip()

            # 查找转账前10分钟内的通讯记录
            for comm in communications:
                comm_time = comm.get("communication_time")
                initiator = comm.get("initiator", "").strip()
                receiver = comm.get("receiver", "").strip()

                # 检查是否涉及交易双方
                is_relevant = (
                    (initiator == payer and receiver == payee)
                    or (initiator == payee and receiver == payer)
                )

                if is_relevant and comm_time:
                    time_diff = (trans_time - comm_time).total_seconds() / 60
                    if 0 < time_diff <= window_minutes:
                        results.append(
                            {
                                "transaction_time": trans_time,
                                "payer": payer,
                                "payee": payee,
                                "amount": trans.get("amount"),
                                "communication_time": comm_time,
                                "initiator": initiator,
                                "receiver": receiver,
                                "content": comm.get("content"),
                                "time_diff_minutes": round(time_diff, 1),
                            }
                        )

        return results

    @classmethod
    def save_persons_to_db(cls, persons_data: List[Dict[str, Any]]) -> int:
        """
        将人物数据保存到数据库
        返回保存数量
        """
        count = 0
        with db.atomic():
            for person_data in persons_data:
                person, created = Person.get_or_create(
                    name=person_data["name"],
                    defaults={
                        "role": person_data.get("role"),
                        "is_authorized": person_data.get("is_authorized"),
                        "subjective_knowledge_score": person_data.get(
                            "subjective_knowledge_score", 0
                        ),
                        "illegal_business_amount": person_data.get(
                            "illegal_business_amount", 0
                        ),
                        "linked_cases": person_data.get("linked_cases", 0),
                    },
                )
                if not created:
                    # 更新已有记录
                    for key, value in person_data.items():
                        if key != "name" and hasattr(person, key):
                            setattr(person, key, value)
                    person.save()
                count += 1
        return count
