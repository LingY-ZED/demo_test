"""
自动化抽取服务
整合数据抽取逻辑，自动从原始数据中提取关键信息
"""

from typing import Dict, List, Any, Tuple

from services.upload_service import UploadService
from services.clean_service import CleanService
from services.person_classifier import PersonClassifier


class ExtractService:
    """自动化抽取服务"""

    @classmethod
    def extract_all(cls, case_id: int) -> Dict[str, Any]:
        """
        自动化抽取主入口
        从已上传的文件中自动提取各类信息

        返回:
            {
                "persons": [...],           # 人员档案列表
                "hidden_sources": [...],    # 隐蔽发货源头
                "pre_transfer_links": [...], # 转账前联络
                "statistics": {...}          # 统计信息
            }
        """
        return {
            "persons": [],
            "hidden_sources": [],
            "pre_transfer_links": [],
            "statistics": {},
        }

    @classmethod
    def extract_from_files(
        cls,
        transaction_file: str,
        communication_file: str,
        logistics_file: str,
        case_id: int,
    ) -> Dict[str, Any]:
        """
        从文件路径自动抽取所有信息

        Args:
            transaction_file: 资金流水文件路径
            communication_file: 通讯记录文件路径
            logistics_file: 物流记录文件路径
            case_id: 案件ID

        Returns:
            抽取结果字典
        """
        # 1. 解析原始数据
        transactions = UploadService.parse_transactions(transaction_file, case_id)
        communications = UploadService.parse_communications(communication_file, case_id)
        logistics = UploadService.parse_logistics(logistics_file, case_id)

        # 2. 清洗数据
        transactions = CleanService.clean_transactions(transactions)
        communications = CleanService.clean_communications(communications)
        logistics = CleanService.clean_logistics(logistics)

        # 3. 自动化抽取
        result = cls._extract(transactions, communications, logistics)

        return result

    @classmethod
    def extract_from_records(
        cls,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        从已解析的记录中抽取信息

        Args:
            transactions: 资金流水记录列表
            communications: 通讯记录列表
            logistics: 物流记录列表

        Returns:
            抽取结果字典
        """
        # 清洗
        transactions = CleanService.clean_transactions(transactions)
        communications = CleanService.clean_communications(communications)
        logistics = CleanService.clean_logistics(logistics)

        # 抽取
        return cls._extract(transactions, communications, logistics)

    @classmethod
    def _extract(
        cls,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        内部抽取逻辑

        包含:
        1. 从资金流水自动抓取"打款方"和"收款方"建立人员信息
        2. 从通讯记录自动比对转账前后的联络行为
        3. 从物流记录自动抓取共同发件地址
        """
        # 1. 提取人物档案（从资金流水）
        persons = CleanService.extract_persons_from_transactions(transactions)

        # 2. 提取隐蔽发货源头（从物流记录）
        hidden_sources = CleanService.extract_hidden_shipping_sources(logistics)

        # 3. 分析转账前联络（资金流水 + 通讯记录）
        pre_transfer_links = CleanService.analyze_pre_transfer_communications(
            transactions, communications
        )

        # 4. 统计信息
        statistics = cls._calculate_statistics(
            transactions, communications, logistics, persons, hidden_sources
        )

        return {
            "persons": persons,
            "hidden_sources": hidden_sources,
            "pre_transfer_links": pre_transfer_links,
            "statistics": statistics,
        }

    @classmethod
    def _calculate_statistics(
        cls,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        persons: List[Dict[str, Any]],
        hidden_sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """计算统计信息"""
        # 总交易金额
        total_amount = sum(float(t.get("amount", 0)) for t in transactions)

        # 涉及人员数
        person_count = len(persons)

        # 通讯记录数
        comm_count = len(communications)

        # 物流记录数
        logistics_count = len(logistics)

        # 隐蔽源头数
        hidden_source_count = len(hidden_sources)

        # 转账前联络数
        pre_transfer_count = 0  # 后续从pre_transfer_links计算

        # 涉案金额排名（前5）
        top_persons = sorted(
            persons, key=lambda x: x.get("illegal_business_amount", 0), reverse=True
        )[:5]

        return {
            "total_transactions": len(transactions),
            "total_amount": total_amount,
            "person_count": person_count,
            "communication_count": comm_count,
            "logistics_count": logistics_count,
            "hidden_source_count": hidden_source_count,
            "top_persons": top_persons,
        }

    @classmethod
    def get_person_role_by_behavior(
        cls,
        person_name: str,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
    ) -> str:
        """
        根据行为推断人员角色

        规则:
        - 同时有"收款+发货" -> 中间商/代理商
        - 只有"付款+收货" -> 终端买家
        - 只有"收款"无发货 -> 核心嫌疑人（收款方）
        - 只有"付款"无收货 -> 下游买家
        """
        profile = PersonClassifier.build_activity_profile(
            transactions, logistics, [], person_name
        )
        result = PersonClassifier.classify_business_role(profile)

        role_map = {
            "生产者": "核心销售商",
            "销售者": "核心销售商",
            "中间商": "中间商/代理商",
            "终端买家": "终端买家",
            "待定": "待定",
        }

        return role_map.get(result["role"], "待定")

    @classmethod
    def extract_address_network(
        cls, logistics: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        提取地址关系网络
        返回: {地址: [发往该地址的所有收件人]}
        """
        address_network = {}

        for record in logistics:
            sender_address = record.get("sender_address", "").strip()
            receiver = record.get("receiver", "").strip()

            if sender_address:
                if sender_address not in address_network:
                    address_network[sender_address] = []
                if receiver and receiver not in address_network[sender_address]:
                    address_network[sender_address].append(receiver)

        return address_network
