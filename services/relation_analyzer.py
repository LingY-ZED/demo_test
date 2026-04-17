"""
上下游关系分析服务
分析资金流向、物流源头、通讯联络构建关系网络
"""
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict


class RelationAnalyzer:
    """上下游关系分析服务"""

    @classmethod
    def analyze_money_flow(
        cls,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析资金流向

        Args:
            transactions: 资金流水列表

        Returns:
            资金流向分析结果
        """
        # 边的列表 (付款方, 收款方, 金额)
        edges = []
        # 每个节点的入度和出度
        node_in_degree = defaultdict(float)
        node_out_degree = defaultdict(float)
        # 每个节点的交易对手
        node_counterparties = defaultdict(set)

        for t in transactions:
            payer = t.get("payer", "").strip()
            payee = t.get("payee", "").strip()
            amount = float(t.get("amount", 0))

            if payer and payee:
                edges.append({
                    "from": payer,
                    "to": payee,
                    "amount": amount,
                    "time": t.get("transaction_time"),
                    "remark": t.get("remark"),
                })
                node_out_degree[payer] += amount
                node_in_degree[payee] += amount
                node_counterparties[payer].add(payee)
                node_counterparties[payee].add(payer)

        # 找出核心节点（入度+出度最高）
        all_nodes = set(node_in_degree.keys()) | set(node_out_degree.keys())
        node_scores = {}
        for node in all_nodes:
            node_scores[node] = node_in_degree[node] + node_out_degree[node]

        # 按交易金额排序的核心节点
        core_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)

        # 上游（只有出度，无入度或入度很小）
        upstream = [n for n in all_nodes if node_in_degree[n] < node_out_degree[n] * 0.1]

        # 下游（只有入度，无出度或出度很小）
        downstream = [n for n in all_nodes if node_out_degree[n] < node_in_degree[n] * 0.1]

        # 核心节点
        core = [n for n in all_nodes if n not in upstream and n not in downstream]

        return {
            "edges": edges,
            "nodes": list(all_nodes),
            "upstream": upstream,           # 上游供货商
            "downstream": downstream,       # 下游买家
            "core": core,                   # 核心嫌疑人
            "node_details": {
                n: {
                    "in_amount": node_in_degree[n],
                    "out_amount": node_out_degree[n],
                    "counterparties": list(node_counterparties[n]),
                }
                for n in all_nodes
            },
            "top_core": core_nodes[:5],
        }

    @classmethod
    def trace_shipping_sources(
        cls,
        logistics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        追溯物流发货源头

        Args:
            logistics: 物流记录列表

        Returns:
            物流源头分析结果
        """
        # 按发件地址分组
        address_groups = defaultdict(list)
        # 按发件人分组
        sender_groups = defaultdict(list)

        for l in logistics:
            sender = l.get("sender", "").strip()
            sender_address = l.get("sender_address", "").strip()
            receiver = l.get("receiver", "").strip()
            description = l.get("description", "")

            if sender_address:
                address_groups[sender_address].append({
                    "sender": sender,
                    "receiver": receiver,
                    "description": description,
                    "tracking_no": l.get("tracking_no"),
                    "time": l.get("shipping_time"),
                })

            sender_groups[sender].append({
                "sender_address": sender_address,
                "receiver": receiver,
                "description": description,
                "tracking_no": l.get("tracking_no"),
                "time": l.get("shipping_time"),
            })

        # 找出隐蔽源头（同一地址发货给多个不同收件人）
        hidden_sources = []
        for address, records in address_groups.items():
            receivers = set(r["receiver"] for r in records)
            if len(receivers) >= 2:  # 发给多个不同收件人
                hidden_sources.append({
                    "address": address,
                    "sender": records[0]["sender"],
                    "shipment_count": len(records),
                    "receiver_count": len(receivers),
                    "receivers": list(receivers),
                    "descriptions": list(set(r["description"] for r in records if r["description"])),
                })

        # 按发货次数排序
        hidden_sources.sort(key=lambda x: x["shipment_count"], reverse=True)

        # 多地点发货的发件人（可能是中间商）
        multi_address_senders = [
            sender for sender, records in sender_groups.items()
            if len(set(r["sender_address"] for r in records if r["sender_address"])) > 1
        ]

        return {
            "hidden_sources": hidden_sources,
            "total_sources": len(address_groups),
            "multi_address_senders": multi_address_senders,
            "sender_details": {
                sender: {
                    "shipment_count": len(records),
                    "addresses": list(set(r["sender_address"] for r in records if r["sender_address"])),
                }
                for sender, records in sender_groups.items()
            },
        }

    @classmethod
    def analyze_communication_frequency(
        cls,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析通讯联络频率，特别是转账前的联络

        Args:
            transactions: 资金流水列表
            communications: 通讯记录列表

        Returns:
            通讯分析结果
        """
        # 构建交易-通讯关联
        pre_transfer_links = []
        all_comm_freq = defaultdict(int)

        for trans in transactions:
            trans_time = trans.get("transaction_time")
            payer = trans.get("payer", "").strip()
            payee = trans.get("payee", "").strip()
            amount = trans.get("amount", 0)

            # 查找转账前10分钟内的通讯
            for comm in communications:
                comm_time = comm.get("communication_time")
                initiator = comm.get("initiator", "").strip()
                receiver = comm.get("receiver", "").strip()

                # 检查是否涉及交易双方
                is_related = (
                    (initiator == payer and receiver == payee) or
                    (initiator == payee and receiver == payer)
                )

                if is_related and comm_time and trans_time:
                    time_diff = (trans_time - comm_time).total_seconds() / 60
                    if 0 < time_diff <= 10:
                        pre_transfer_links.append({
                            "transaction": {
                                "payer": payer,
                                "payee": payee,
                                "amount": amount,
                                "time": trans_time,
                            },
                            "communication": {
                                "initiator": initiator,
                                "receiver": receiver,
                                "content": comm.get("content"),
                                "time": comm_time,
                            },
                            "time_diff_minutes": round(time_diff, 1),
                        })

        # 通讯频率统计
        for comm in communications:
            initiator = comm.get("initiator", "").strip()
            receiver = comm.get("receiver", "").strip()
            if initiator:
                all_comm_freq[initiator] += 1
            if receiver:
                all_comm_freq[receiver] += 1

        # 高频联络人员
        high_freq_persons = sorted(
            all_comm_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return {
            "pre_transfer_links": pre_transfer_links,
            "pre_transfer_count": len(pre_transfer_links),
            "communication_frequency": dict(all_comm_freq),
            "high_frequency_persons": high_freq_persons[:10],
        }

    @classmethod
    def build_relation_graph(
        cls,
        transactions: List[Dict[str, Any]],
        logistics: List[Dict[str, Any]],
        communications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        构建整体关系图谱

        Args:
            transactions: 资金流水列表
            logistics: 物流记录列表
            communications: 通讯记录列表

        Returns:
            关系图谱
        """
        # 1. 资金流向分析
        money_flow = cls.analyze_money_flow(transactions)

        # 2. 物流源头追溯
        logistics_sources = cls.trace_shipping_sources(logistics)

        # 3. 通讯联络分析
        comm_analysis = cls.analyze_communication_frequency(transactions, communications)

        # 4. 汇总节点信息
        all_persons = set()
        for t in transactions:
            if t.get("payer"):
                all_persons.add(t.get("payer"))
            if t.get("payee"):
                all_persons.add(t.get("payee"))

        # 构建节点详情
        nodes = []
        for person in all_persons:
            node = {
                "id": person,
                "name": person,
                "money_in": money_flow["node_details"].get(person, {}).get("in_amount", 0),
                "money_out": money_flow["node_details"].get(person, {}).get("out_amount", 0),
                "is_upstream": person in money_flow["upstream"],
                "is_downstream": person in money_flow["downstream"],
                "is_core": person in money_flow["core"],
                "comm_frequency": comm_analysis["communication_frequency"].get(person, 0),
            }
            nodes.append(node)

        # 5. 构建边（关系）
        edges = []

        # 资金流边
        for edge in money_flow["edges"]:
            edges.append({
                "source": edge["from"],
                "target": edge["to"],
                "type": "money",
                "amount": edge["amount"],
                "time": str(edge["time"]) if edge["time"] else None,
            })

        # 物流边
        for l in logistics:
            sender = l.get("sender", "").strip()
            receiver = l.get("receiver", "").strip()
            if sender and receiver:
                edges.append({
                    "source": sender,
                    "target": receiver,
                    "type": "logistics",
                    "description": l.get("description"),
                    "time": str(l.get("shipping_time")) if l.get("shipping_time") else None,
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": {
                "total_persons": len(all_persons),
                "total_transactions": len(transactions),
                "total_logistics": len(logistics),
                "total_communications": len(communications),
                "pre_transfer_count": comm_analysis["pre_transfer_count"],
                "hidden_source_count": len(logistics_sources["hidden_sources"]),
            },
            "upstream": money_flow["upstream"],
            "downstream": money_flow["downstream"],
            "core": money_flow["core"],
            "hidden_sources": logistics_sources["hidden_sources"],
            "pre_transfer_links": comm_analysis["pre_transfer_links"],
        }

    @classmethod
    def find_cross_case_connections(
        cls,
        cases_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        跨案关联分析

        找出同一人员/账户在不同案件中的关联

        Args:
            cases_data: 多个案件的数据列表
                [{"case_id": 1, "persons": [...], "transactions": [...]}, ...]

        Returns:
            跨案关联列表
        """
        # 人员->案件映射
        person_cases = defaultdict(list)

        for case_data in cases_data:
            case_id = case_data.get("case_id")
            persons = case_data.get("persons", [])
            transactions = case_data.get("transactions", [])

            # 从人员列表
            for person in persons:
                person_cases[person].append(case_id)

            # 从交易中提取
            for t in transactions:
                if t.get("payer"):
                    person_cases[t.get("payer")].append(case_id)
                if t.get("payee"):
                    person_cases[t.get("payee")].append(case_id)

        # 找出涉及多个案件的人员
        cross_case_persons = {
            person: cases
            for person, cases in person_cases.items()
            if len(set(cases)) > 1  # 去重后>1说明涉及多个案件
        }

        # 构建关联
        connections = []
        for person, case_ids in cross_case_persons.items():
            connections.append({
                "person": person,
                "case_ids": list(set(case_ids)),
                "case_count": len(set(case_ids)),
            })

        return connections
