"""
数据导入API路由
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import pandas as pd
from datetime import datetime
import tempfile
import os
import io
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from services.upload_service import UploadService, TableFormatError
from services.clean_service import CleanService
from services.case_service import CaseService
from services.suspicion_detector import SuspicionDetector
from models.database import Case

router = APIRouter(prefix="/api/upload", tags=["数据导入"])


@router.post("/transactions")
async def upload_transactions(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None),
):
    """
    上传资金流水Excel/CSV

    Args:
        file: 上传的文件
        case_id: 案件ID
        case_no: 案件编号（如果case_id未提供）

    Returns:
        导入结果
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="仅支持Excel或CSV文件")

    # 获取案件
    case = None
    if case_id:
        case = Case.get_or_none(Case.id == case_id)
    elif case_no:
        case = Case.get_or_none(Case.case_no == case_no)

    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    try:
        # 保存上传文件到临时文件后交给 UploadService 解析
        contents = await file.read()
        suffix = os.path.splitext(file.filename)[1] or ".csv"
        temp_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(contents)
            temp_path = temp_file.name

        # 解析数据
        records = UploadService.parse_transactions(temp_path, case.id)

        # 清洗数据
        cleaned_records = CleanService.clean_transactions(records)

        # 保存到数据库
        from models.database import Transaction

        saved_count = 0
        for record in cleaned_records:
            Transaction.create(
                case=case,
                transaction_time=record.get("transaction_time", datetime.now()),
                payer=record.get("payer", ""),
                payee=record.get("payee", ""),
                amount=record.get("amount", 0),
                payment_method=record.get("payment_method"),
                remark=record.get("remark"),
            )
            saved_count += 1

        recalculated_amount = CaseService.recalculate_case_amount(case.id)
        inferred_fields = CaseService.auto_update_inferred_fields(case.id)
        person_sync = CaseService.sync_case_persons_to_db(case.id)

        # 自动检测可疑线索
        clue_results = SuspicionDetector.detect_all(case.id)
        total_clues = (
            len(clue_results["suspicion_clues"])
            + len(clue_results["price_clues"])
            + len(clue_results["role_clues"])
        )

        return {
            "success": True,
            "message": f"成功导入{saved_count}条资金流水",
            "case_id": case.id,
            "case_no": case.case_no,
            "case_amount": float(recalculated_amount or 0),
            "case_suspect_name": (
                inferred_fields.get("suspect_name") if inferred_fields else None
            ),
            "case_brand": inferred_fields.get("brand") if inferred_fields else None,
            "person_sync": person_sync,
            "total_records": len(records),
            "saved_records": saved_count,
            "clues_generated": total_clues,
        }
    except TableFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if "temp_path" in locals() and temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.post("/communications")
async def upload_communications(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None),
):
    """
    上传通讯记录Excel/CSV

    Args:
        file: 上传的文件
        case_id: 案件ID
        case_no: 案件编号

    Returns:
        导入结果
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="仅支持Excel或CSV文件")

    # 获取案件
    case = None
    if case_id:
        case = Case.get_or_none(Case.id == case_id)
    elif case_no:
        case = Case.get_or_none(Case.case_no == case_no)

    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    try:
        # 保存上传文件到临时文件后交给 UploadService 解析
        contents = await file.read()
        suffix = os.path.splitext(file.filename)[1] or ".csv"
        temp_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(contents)
            temp_path = temp_file.name

        # 解析数据
        is_wechat = UploadService._detect_wechat_format(temp_path)
        records = UploadService.parse_communications(temp_path, case.id)

        # 微信格式：提取转账记录
        wechat_transactions = UploadService.get_wechat_transactions()

        # 清洗数据
        cleaned_records = CleanService.clean_communications(records)

        # 保存到数据库
        from models.database import Communication, Transaction

        saved_count = 0
        for record in cleaned_records:
            Communication.create(
                case=case,
                communication_time=record.get("communication_time") or datetime.now(),
                initiator=record.get("initiator", ""),
                receiver=record.get("receiver", ""),
                content=record.get("content"),
                media_type=record.get("media_type"),
                is_deleted=record.get("is_deleted", False),
                raw_content=record.get("raw_content"),
            )
            saved_count += 1

        # 保存从微信提取的转账记录
        txn_saved = 0
        for txn in wechat_transactions:
            if txn.get("transaction_time") and txn.get("amount", 0) > 0:
                Transaction.create(
                    case=case,
                    transaction_time=txn.get("transaction_time", datetime.now()),
                    payer=txn.get("payer", ""),
                    payee=txn.get("payee", ""),
                    amount=txn.get("amount", 0),
                    payment_method=txn.get("payment_method"),
                    remark=txn.get("remark"),
                )
                txn_saved += 1

        inferred_fields = CaseService.auto_update_inferred_fields(case.id)
        person_sync = CaseService.sync_case_persons_to_db(case.id)

        # 如有提取的转账，重算案件金额
        recalculated_amount = None
        if txn_saved > 0:
            recalculated_amount = CaseService.recalculate_case_amount(case.id)

        # 自动检测可疑线索
        clue_results = SuspicionDetector.detect_all(case.id)
        total_clues = (
            len(clue_results["suspicion_clues"])
            + len(clue_results["price_clues"])
            + len(clue_results["role_clues"])
        )

        result = {
            "success": True,
            "message": f"成功导入{saved_count}条通讯记录",
            "case_id": case.id,
            "case_no": case.case_no,
            "case_suspect_name": (
                inferred_fields.get("suspect_name") if inferred_fields else None
            ),
            "case_brand": inferred_fields.get("brand") if inferred_fields else None,
            "person_sync": person_sync,
            "total_records": len(records),
            "saved_records": saved_count,
            "clues_generated": total_clues,
        }
        if is_wechat:
            result["format_detected"] = "wechat"
            result["extracted_transactions"] = txn_saved
            if recalculated_amount is not None:
                result["case_amount"] = float(recalculated_amount)
        return result
    except TableFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if "temp_path" in locals() and temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.post("/logistics")
async def upload_logistics(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None),
):
    """
    上传物流记录Excel/CSV

    Args:
        file: 上传的文件
        case_id: 案件ID
        case_no: 案件编号

    Returns:
        导入结果
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="仅支持Excel或CSV文件")

    # 获取案件
    case = None
    if case_id:
        case = Case.get_or_none(Case.id == case_id)
    elif case_no:
        case = Case.get_or_none(Case.case_no == case_no)

    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    try:
        # 保存上传文件到临时文件后交给 UploadService 解析
        contents = await file.read()
        suffix = os.path.splitext(file.filename)[1] or ".csv"
        temp_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(contents)
            temp_path = temp_file.name

        # 解析数据
        records = UploadService.parse_logistics(temp_path, case.id)

        # 清洗数据
        cleaned_records = CleanService.clean_logistics(records)

        # 保存到数据库
        from models.database import Logistics

        saved_count = 0
        for record in cleaned_records:
            Logistics.create(
                case=case,
                shipping_time=record.get("shipping_time", datetime.now()),
                tracking_no=record.get("tracking_no"),
                sender=record.get("sender", ""),
                sender_address=record.get("sender_address"),
                receiver=record.get("receiver", ""),
                receiver_address=record.get("receiver_address"),
                description=record.get("description"),
                weight=record.get("weight"),
            )
            saved_count += 1

        inferred_fields = CaseService.auto_update_inferred_fields(case.id)
        person_sync = CaseService.sync_case_persons_to_db(case.id)

        # 自动检测可疑线索
        clue_results = SuspicionDetector.detect_all(case.id)
        total_clues = (
            len(clue_results["suspicion_clues"])
            + len(clue_results["price_clues"])
            + len(clue_results["role_clues"])
        )

        return {
            "success": True,
            "message": f"成功导入{saved_count}条物流记录",
            "case_id": case.id,
            "case_no": case.case_no,
            "case_suspect_name": (
                inferred_fields.get("suspect_name") if inferred_fields else None
            ),
            "case_brand": inferred_fields.get("brand") if inferred_fields else None,
            "person_sync": person_sync,
            "total_records": len(records),
            "saved_records": saved_count,
            "clues_generated": total_clues,
        }
    except TableFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if "temp_path" in locals() and temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _generate_template_xlsx(headers: list, sample_rows: list, sheet_title: str) -> io.BytesIO:
    """生成标准导入模板 XLSX 文件"""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    header_font = Font(bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")

    # 写入表头
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = header_align

    # 写入示例数据行
    for row_idx, row_data in enumerate(sample_rows, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    # 自适应列宽
    for col_idx, header in enumerate(headers, 1):
        max_width = len(header) * 2  # 中文字符约占 2 个英文字符宽度
        for row_data in sample_rows:
            cell_text = str(row_data[col_idx - 1]) if col_idx - 1 < len(row_data) else ""
            max_width = max(max_width, len(cell_text) * 2)
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_width + 4, 50)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# 模板定义
_TEMPLATE_DEFS = {
    "transactions": {
        "filename": "资金流水导入模板.xlsx",
        "sheet_title": "资金流水",
        "headers": [
            "交易发生时间",
            "打款方 (账号/姓名)",
            "收款方 (账号/姓名)",
            "交易金额 (元)",
            "支付方式",
            "交易备注 / 转账留言",
        ],
        "sample_rows": [
            ["2026-01-01 10:00", "张三", "李四", "50000.00", "银行卡", "货款"],
            ["2026-01-02 14:30", "王五", "赵六", "12000.00", "微信", "订金"],
        ],
    },
    "communications": {
        "filename": "通讯记录导入模板.xlsx",
        "sheet_title": "通讯记录",
        "headers": [
            "联络时间",
            "发起方 (微信号/姓名)",
            "接收方 (微信号/姓名)",
            "聊天内容",
        ],
        "sample_rows": [
            ["2026-01-01 10:00", "张三", "李四", "货收到了吗"],
            ["2026-01-01 10:05", "李四", "张三", "收到了，质量不错"],
        ],
    },
    "logistics": {
        "filename": "物流记录导入模板.xlsx",
        "sheet_title": "物流记录",
        "headers": [
            "发货时间",
            "快递单号",
            "发件人/网点",
            "收件人/地址",
            "寄件物品描述",
            "包裹重量(公斤)",
        ],
        "sample_rows": [
            ["2026-01-01 10:00", "SF123456", "张三 (东莞某工业区)", "李四 (杭州余杭某村)", "汽车配件/大灯", "8.0"],
            ["2026-01-02 14:00", "YT789012", "王五 (广州白云)", "赵六 (长沙)", "机油", "45.0"],
        ],
    },
}


@router.get("/template/transactions")
async def download_transactions_template():
    """下载资金流水导入模板"""
    tpl = _TEMPLATE_DEFS["transactions"]
    xlsx = _generate_template_xlsx(tpl["headers"], tpl["sample_rows"], tpl["sheet_title"])
    return StreamingResponse(
        xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(tpl['filename'])}"},
    )


@router.get("/template/communications")
async def download_communications_template():
    """下载通讯记录导入模板"""
    tpl = _TEMPLATE_DEFS["communications"]
    xlsx = _generate_template_xlsx(tpl["headers"], tpl["sample_rows"], tpl["sheet_title"])
    return StreamingResponse(
        xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(tpl['filename'])}"},
    )


@router.get("/template/logistics")
async def download_logistics_template():
    """下载物流记录导入模板"""
    tpl = _TEMPLATE_DEFS["logistics"]
    xlsx = _generate_template_xlsx(tpl["headers"], tpl["sample_rows"], tpl["sheet_title"])
    return StreamingResponse(
        xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(tpl['filename'])}"},
    )
