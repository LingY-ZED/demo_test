"""
交易 × 通讯交叉比对服务
从时间和金额两个维度比对资金流水与聊天记录，发现异常交易
"""
import re
from typing import Dict, List, Any, Optional
from datetime import timedelta

from models.database import Transaction, Communication, SuspiciousClue
from services.evidence_analyzer import EvidenceAnalyzer


# 中文数字 → 阿拉伯数字
_CHINESE_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_CHINESE_UNITS = {"百": 100, "千": 1000, "万": 10000, "亿": 100000000}

# 匹配中文金额模式
# A: 数字 + 大单位(万/千/百/亿) [+ 可选 元/块]  如 "三万" "五万块"
# B: 数字 + 货币后缀(元/块/块钱/元钱)             如 "一百元" "五十块"
_CHINESE_AMOUNT_RE = re.compile(
    r"([一二两三四五六七八九十百千万亿]+\s*[万亿千百])\s*(?:元|块|块钱|元钱)?"
    r"|"
    r"([一二两三四五六七八九十百千万亿]+)\s*(?:元|块|块钱|元钱)"
)


def _parse_chinese_number(text: str) -> Optional[float]:
    """将中文数字字符串转为阿拉伯数字（如 '三万' → 30000, '十二万' → 120000）"""
    if not text:
        return None
    text = text.strip()
    if not all(ch in _CHINESE_DIGITS or ch in _CHINESE_UNITS for ch in text):
        return None

    total = 0       # 万/亿 级别累计
    section = 0     # 万以下的当前段
    current = 0     # 当前累积的小数字（如"十二"→12）

    for ch in text:
        if ch in _CHINESE_DIGITS:
            d = _CHINESE_DIGITS[ch]
            if d == 10:  # 十：前有数字则乘，否则就是 10
                current = (current or 1) * 10
            else:
                current += d
        elif ch in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[ch]
            current = (current or 1) * unit
            if unit >= 10000:  # 万/亿：段结算
                total += current
                current = 0
            else:              # 百/千：仍在段内
                section += current
                current = 0
        else:
            return None

    total += section + current
    return float(total) if total > 0 else None


def extract_all_amounts(text: str) -> List[float]:
    """从文本中提取所有金额（正则 + 中文数字）"""
    amounts = EvidenceAnalyzer.extract_prices(text) or []

    # 中文数字金额提取
    for m in _CHINESE_AMOUNT_RE.finditer(text):
        # group(1): 大单位模式 (数字+万/千/百/亿), group(2): 货币后缀模式 (数字+元/块)
        num_part = m.group(1) or m.group(2)
        if num_part:
            num = _parse_chinese_number(num_part)
            if num and num > 0:
                amounts.append(num)

    # 去重排序
    seen = set()
    result = []
    for a in sorted(amounts, reverse=True):
        key = round(a, 2)
        if key not in seen:
            seen.add(key)
            result.append(a)
    return result


class TransactionCrossValidator:
    """交易 × 通讯交叉比对"""

    # 金额不符：偏差比例阈值
    AMOUNT_MISMATCH_RATIO = 0.20
    # 金额不符：最小差额（元），避免小额误报
    AMOUNT_MISMATCH_MIN_DIFF = 500
    # 无沟通大额交易：金额阈值
    NO_COMM_LARGE_AMOUNT = 50000
    # 默认时间窗口（分钟）
    DEFAULT_WINDOW_MINUTES = 60

    @classmethod
    def validate(
        cls, case_id: int, window_minutes: int = DEFAULT_WINDOW_MINUTES
    ) -> List[Dict[str, Any]]:
        """
        执行全量交叉比对，返回异常线索列表

        Args:
            case_id: 案件ID
            window_minutes: 时间窗口（分钟），默认 60

        Returns:
            异常线索列表（已写入 SuspiciousClue 表）
        """
        # 加载数据
        transactions = cls._load_transactions(case_id)
        communications = cls._load_communications(case_id)

        if not transactions:
            return []

        anomalies = []

        for trans in transactions:
            matched_comms = cls._find_matching_communications(
                trans, communications, window_minutes
            )

            # 检测1：金额不符
            amount_anomaly = cls._check_amount_mismatch(trans, matched_comms)
            if amount_anomaly:
                anomalies.append(amount_anomaly)

            # 检测2：无沟通大额交易
            no_comm_anomaly = cls._check_no_communication(trans, matched_comms)
            if no_comm_anomaly:
                anomalies.append(no_comm_anomaly)

        # 检测3：聊天提及无对应交易（全局扫描）
        phantom_anomalies = cls._check_phantom_transactions(
            case_id, transactions, communications, window_minutes
        )
        anomalies.extend(phantom_anomalies)

        # 写入 SuspiciousClue
        saved = []
        for anomaly in anomalies:
            clue = cls._save_anomaly(case_id, anomaly)
            if clue:
                saved.append(clue)

        return saved

    # ---------- 数据加载 ----------

    @classmethod
    def _load_transactions(cls, case_id: int) -> List[Dict[str, Any]]:
        rows = Transaction.select().where(Transaction.case == case_id)
        return [
            {
                "id": t.id,
                "transaction_time": t.transaction_time,
                "payer": t.payer.strip(),
                "payee": t.payee.strip(),
                "amount": float(t.amount),
                "remark": t.remark or "",
            }
            for t in rows
        ]

    @classmethod
    def _load_communications(cls, case_id: int) -> List[Dict[str, Any]]:
        rows = Communication.select().where(Communication.case == case_id)
        return [
            {
                "id": c.id,
                "communication_time": c.communication_time,
                "initiator": c.initiator.strip(),
                "receiver": c.receiver.strip(),
                "content": c.content or "",
            }
            for c in rows
        ]

    # ---------- 匹配逻辑 ----------

    @classmethod
    def _find_matching_communications(
        cls,
        transaction: Dict[str, Any],
        communications: List[Dict[str, Any]],
        window_minutes: int,
    ) -> List[Dict[str, Any]]:
        """查找与某笔交易匹配的聊天记录（双方 + 时间窗口）"""
        payer = transaction["payer"]
        payee = transaction["payee"]
        trans_time = transaction["transaction_time"]

        if not payer or not payee:
            return []

        matched = []
        window = timedelta(minutes=window_minutes)

        for comm in communications:
            comm_time = comm.get("communication_time")
            if comm_time is None:
                continue

            initiator = comm.get("initiator", "")
            receiver = comm.get("receiver", "")

            # 双方精确匹配
            parties_match = (
                (initiator == payer and receiver == payee)
                or (initiator == payee and receiver == payer)
            )
            if not parties_match:
                continue

            # 时间窗口
            if abs(trans_time - comm_time) <= window:
                matched.append(comm)

        return matched

    # ---------- 三个检测器 ----------

    @classmethod
    def _check_amount_mismatch(
        cls,
        transaction: Dict[str, Any],
        matched_comms: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """检测金额不符：聊天金额 vs 实际转账金额"""

        trans_amount = transaction["amount"]
        if trans_amount <= 0:
            return None

        for comm in matched_comms:
            content = comm.get("content", "")
            if not content:
                continue

            chat_prices = extract_all_amounts(content)
            for chat_price in chat_prices:
                if chat_price <= 0:
                    continue
                diff_ratio = abs(trans_amount - chat_price) / max(trans_amount, chat_price)
                diff_abs = abs(trans_amount - chat_price)

                if diff_ratio > cls.AMOUNT_MISMATCH_RATIO and diff_abs > cls.AMOUNT_MISMATCH_MIN_DIFF:
                    direction = "高于" if trans_amount > chat_price else "低于"
                    return {
                        "transaction_id": transaction["id"],
                        "transaction_time": transaction["transaction_time"],
                        "payer": transaction["payer"],
                        "payee": transaction["payee"],
                        "amount": trans_amount,
                        "anomaly_type": "金额不符",
                        "chat_content": content,
                        "chat_time": comm.get("communication_time"),
                        "detail": (
                            f"聊天提及金额约{chat_price:.0f}元，"
                            f"实际转账{trans_amount:.0f}元，"
                            f"{direction}{diff_ratio*100:.0f}%"
                        ),
                        "score": 7,
                        "severity_level": "民事侵权",
                    }
        return None

    @classmethod
    def _check_no_communication(
        cls,
        transaction: Dict[str, Any],
        matched_comms: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """检测无沟通大额交易"""
        if transaction["amount"] < cls.NO_COMM_LARGE_AMOUNT:
            return None
        if matched_comms:
            return None

        return {
            "transaction_id": transaction["id"],
            "transaction_time": transaction["transaction_time"],
            "payer": transaction["payer"],
            "payee": transaction["payee"],
            "amount": transaction["amount"],
            "anomaly_type": "无沟通大额交易",
            "chat_content": "",
            "chat_time": None,
            "detail": (
                f"{transaction['payer']} → {transaction['payee']} "
                f"转账{transaction['amount']:.0f}元，"
                f"前后一小时内无相关聊天记录"
            ),
            "score": 5,
            "severity_level": "民事侵权",
        }

    @classmethod
    def _check_phantom_transactions(
        cls,
        case_id: int,
        transactions: List[Dict[str, Any]],
        communications: List[Dict[str, Any]],
        window_minutes: int,
    ) -> List[Dict[str, Any]]:
        """
        检测聊天提及付款但无对应交易
        扫描所有含金额关键词的聊天，检查时间窗口内是否有匹配交易
        """
        anomalies = []
        window = timedelta(minutes=window_minutes)

        # 构建交易索引：按 (payer, payee) 分组
        trans_index: Dict[tuple, List[Dict]] = {}
        for t in transactions:
            key = (t["payer"], t["payee"])
            trans_index.setdefault(key, []).append(t)

        for comm in communications:
            content = comm.get("content", "")
            if not content:
                continue
            comm_time = comm.get("communication_time")
            if comm_time is None:
                continue

            # 聊天是否包含付款相关金额
            prices = extract_all_amounts(content)
            if not prices:
                continue

            # 检查是否有"转账/打款/付款/汇款"等付款语义
            has_payment_intent = any(
                kw in content for kw in ("转账", "打款", "付款", "汇款", "货款", "订金", "定金", "尾款")
            )
            if not has_payment_intent:
                continue

            initiator = comm.get("initiator", "")
            receiver = comm.get("receiver", "")

            # 检查是否有匹配的交易（双方 + 时间窗口）
            has_match = False
            for (p1, p2), txns in trans_index.items():
                parties_match = (
                    (p1 == initiator and p2 == receiver)
                    or (p1 == receiver and p2 == initiator)
                )
                if not parties_match:
                    continue
                for txn in txns:
                    if abs(txn["transaction_time"] - comm_time) <= window:
                        has_match = True
                        break
                if has_match:
                    break

            if not has_match:
                anomalies.append({
                    "transaction_id": None,
                    "transaction_time": None,
                    "payer": initiator,
                    "payee": receiver,
                    "amount": prices[0] if prices else 0,
                    "anomaly_type": "聊天提及无对应交易",
                    "chat_content": content,
                    "chat_time": comm_time,
                    "detail": (
                        f"{initiator} 与 {receiver} 在聊天中讨论付款"
                        f"（金额约{prices[0]:.0f}元），但时间窗口内无匹配交易记录"
                    ),
                    "score": 5,
                    "severity_level": "民事侵权",
                })

        return anomalies

    # ---------- 持久化 ----------

    @classmethod
    def _save_anomaly(
        cls, case_id: int, anomaly: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        将异常写入 SuspiciousClue 表（去重）
        evidence_text 使用 human-readable 的 detail 字段
        """
        evidence_text = anomaly["detail"]

        existing = SuspiciousClue.get_or_none(
            (SuspiciousClue.case_id == case_id)
            & (SuspiciousClue.clue_type == "交易异常")
            & (SuspiciousClue.evidence_text == evidence_text)
        )
        if existing:
            return None  # 已存在，跳过

        clue = SuspiciousClue.create(
            case_id=case_id,
            clue_type="交易异常",
            evidence_text=evidence_text,
            hit_keywords=anomaly["anomaly_type"],
            score=anomaly["score"],
            crime_type="待定",
            severity_level=anomaly["severity_level"],
        )

        return {
            "id": clue.id,
            "case_id": clue.case_id,
            "clue_type": clue.clue_type,
            "evidence_text": clue.evidence_text,
            "hit_keywords": clue.hit_keywords.split(",") if clue.hit_keywords else [],
            "score": clue.score,
            "crime_type": clue.crime_type,
            "severity_level": clue.severity_level,
        }
