"""
数据导入API路由
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import pandas as pd
from datetime import datetime
import tempfile
import os

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
        from models.database import Case

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
                communication_time=record.get("communication_time", datetime.now()),
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


# 需要导入io模块
import io
