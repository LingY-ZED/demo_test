"""
数据导入API路由
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import pandas as pd
from datetime import datetime

from services.upload_service import UploadService
from services.clean_service import CleanService
from models.database import Case

router = APIRouter(prefix="/api/upload", tags=["数据导入"])


@router.post("/transactions")
async def upload_transactions(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None)
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
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
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
        # 读取文件
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # 解析数据
        records = UploadService.parse_transactions(df)

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

        return {
            "success": True,
            "message": f"成功导入{saved_count}条资金流水",
            "case_id": case.id,
            "case_no": case.case_no,
            "total_records": len(records),
            "saved_records": saved_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/communications")
async def upload_communications(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None)
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
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
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
        # 读取文件
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # 解析数据
        records = UploadService.parse_communications(df)

        # 清洗数据
        cleaned_records = CleanService.clean_communications(records)

        # 保存到数据库
        from models.database import Communication
        saved_count = 0
        for record in cleaned_records:
            Communication.create(
                case=case,
                communication_time=record.get("communication_time", datetime.now()),
                initiator=record.get("initiator", ""),
                receiver=record.get("receiver", ""),
                content=record.get("content"),
            )
            saved_count += 1

        return {
            "success": True,
            "message": f"成功导入{saved_count}条通讯记录",
            "case_id": case.id,
            "case_no": case.case_no,
            "total_records": len(records),
            "saved_records": saved_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/logistics")
async def upload_logistics(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    case_no: Optional[str] = Form(None)
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
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
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
        # 读取文件
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # 解析数据
        records = UploadService.parse_logistics(df)

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

        return {
            "success": True,
            "message": f"成功导入{saved_count}条物流记录",
            "case_id": case.id,
            "case_no": case.case_no,
            "total_records": len(records),
            "saved_records": saved_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# 需要导入io模块
import io