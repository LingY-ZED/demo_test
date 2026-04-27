"""
微信聊天记录 CSV 解析器

将微信原始导出 CSV 映射为后端兼容的结构化数据。
"""
import ast
import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple


# 微信 CSV 特征列
WECHAT_SIGNATURE_COLUMNS = {"way", "sender", "senderName", "mediaType", "isDelete"}

# 微信 CSV 日期格式
WECHAT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def detect_wechat_format(headers: List[str]) -> bool:
    """检测是否为微信 CSV 格式"""
    normalized = {h.strip() for h in headers if h}
    return WECHAT_SIGNATURE_COLUMNS.issubset(normalized)


def _parse_datetime(value: str) -> Optional[datetime]:
    """解析微信时间格式"""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), WECHAT_TIME_FORMAT)
    except ValueError:
        return None


def _parse_content_dict(content: str) -> Optional[dict]:
    """尝试将 content 解析为 Python dict（单引号格式）"""
    if not content or not content.strip():
        return None
    content = content.strip()
    if not (content.startswith("{") and content.endswith("}")):
        return None
    try:
        # 微信 CSV 使用单引号 Python dict 格式
        return ast.literal_eval(content)
    except (ValueError, SyntaxError):
        return None


def _extract_voicelength(title_xml: str) -> Optional[int]:
    """从语音 XML 中提取 voicelength（毫秒）"""
    match = re.search(r'voicelength="(\d+)"', title_xml)
    if match:
        return int(match.group(1))
    return None


def _extract_content_for_media(
    media_type: str, content: str
) -> Tuple[str, Optional[str]]:
    """
    根据 mediaType 提取可读内容。

    Returns:
        (extracted_text, raw_content)
        - extracted_text: 用于 stored content 字段
        - raw_content: 非文本消息的原始 JSON 留存
    """
    if media_type == "文本":
        return content.strip() or None, None

    if media_type in ("语音聊天", "其他"):
        return content.strip() or None, None

    parsed = _parse_content_dict(content)
    if parsed is None:
        return content, content

    if media_type == "图片":
        att_type = parsed.get("attType", "pic")
        return f"[图片消息 ({att_type})]", content

    if media_type == "音频":
        title = parsed.get("title", "")
        voicelength = _extract_voicelength(title)
        if voicelength:
            seconds = voicelength // 1000
            return f"[语音消息 {seconds}秒]", content
        return "[语音消息]", content

    if media_type == "转账":
        amount = parsed.get("amount", "").replace("¥", "").replace("￥", "").strip()
        sender = parsed.get("senderName", "")
        receiver = parsed.get("receiverName", "")
        deal_status = parsed.get("dealStatus", "")
        status_text = "已收款" if deal_status == "03" else ("待收款" if deal_status == "02" else "")
        parts = [f"[转账] ¥{amount}"]
        if sender:
            parts.append(f"付款方: {sender}")
        if receiver:
            parts.append(f"收款方: {receiver}")
        if status_text:
            parts.append(f"状态: {status_text}")
        return "，".join(parts), content

    return content, None


def _extract_transaction_from_record(
    record: dict, parsed_content: dict
) -> Optional[dict]:
    """从转账消息提取交易记录"""
    deal_status = parsed_content.get("dealStatus", "")
    if deal_status != "03":
        return None

    amount_str = (
        parsed_content.get("amount", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace(",", "")
        .strip()
    )
    try:
        amount = Decimal(amount_str)
    except Exception:
        amount = Decimal("0")

    if amount <= 0:
        return None

    transaction_time = record.get("communication_time")
    return {
        "transaction_time": transaction_time,
        "payer": parsed_content.get("senderName", ""),
        "payee": parsed_content.get("receiverName", ""),
        "amount": amount,
        "payment_method": "微信转账",
        "remark": f"从聊天记录自动提取 (转账ID: {parsed_content.get('id', '')})",
    }


def parse_wechat_csv(file_path: str) -> Dict[str, Any]:
    """
    解析微信 CSV 文件。

    Returns:
        {
            "communications": [...],
            "transactions": [...],
            "participants": {"account_owner": str, "other_party": str},
        }
    """
    communications: List[Dict[str, Any]] = []
    transactions: List[Dict[str, Any]] = []

    with open(file_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 第一遍扫描：识别双方身份
    account_owner: Optional[str] = None
    other_party: Optional[str] = None

    for row in rows:
        way = row.get("way", "").strip()
        sender_name = row.get("senderName", "").strip()
        if way == "1" and sender_name and not account_owner:
            account_owner = sender_name
        if way == "2" and sender_name and not other_party:
            other_party = sender_name
        if account_owner and other_party:
            break

    # 如果只有一方，使用 sender 账号兜底
    if not account_owner or not other_party:
        for row in rows:
            way = row.get("way", "").strip()
            sender = row.get("sender", "").strip()
            sender_name = row.get("senderName", "").strip()
            name = sender_name or sender
            if way == "1" and not account_owner:
                account_owner = name
            if way == "2" and not other_party:
                other_party = name

    # 第二遍扫描：构建通讯记录
    for row in rows:
        way = row.get("way", "").strip()
        sender_name = row.get("senderName", "").strip()
        sender = row.get("sender", "").strip()
        time_str = row.get("time", "").strip()
        content = row.get("content", "").strip()
        media_type = row.get("mediaType", "").strip()
        is_delete_str = row.get("isDelete", "").strip()

        comm_time = _parse_datetime(time_str)
        name = sender_name or sender
        is_deleted = is_delete_str == "是"

        # 确定发起方/接收方
        if way == "1":
            initiator = account_owner or name
            receiver = other_party or ""
        else:
            initiator = other_party or name
            receiver = account_owner or ""

        # 提取内容
        extracted_text, raw_content = _extract_content_for_media(media_type, content)

        comm_record = {
            "communication_time": comm_time,
            "initiator": initiator,
            "receiver": receiver,
            "content": extracted_text,
            "media_type": media_type,
            "is_deleted": is_deleted,
            "raw_content": raw_content,
        }
        communications.append(comm_record)

        # 转账消息 → 提取交易记录
        if media_type == "转账":
            parsed = _parse_content_dict(content)
            if parsed:
                txn = _extract_transaction_from_record(comm_record, parsed)
                if txn:
                    transactions.append(txn)

    return {
        "communications": communications,
        "transactions": transactions,
        "participants": {
            "account_owner": account_owner or "",
            "other_party": other_party or "",
        },
    }
