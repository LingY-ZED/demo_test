"""
数据台账API路由
"""
from fastapi import APIRouter, Query
from typing import Optional, List

from services.ledger_service import LedgerService

router = APIRouter(prefix="/api/ledger", tags=["数据台账"])


@router.get("/persons", response_model=List[dict])
async def get_person_ledger(
    name: Optional[str] = Query(None, description="姓名模糊匹配"),
    role: Optional[str] = Query(None, description="角色筛选"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    人员台账列表
    """
    return LedgerService.get_person_ledger(
        name=name,
        role=role,
        limit=limit,
        offset=offset
    )


@router.get("/persons/{name}", response_model=dict)
async def get_person_detail(name: str):
    """
    人员详情
    """
    return LedgerService.get_person_detail(name)


@router.get("/transactions", response_model=List[dict])
async def get_transaction_ledger(
    case_no: Optional[str] = Query(None, description="案件编号筛选"),
    payer: Optional[str] = Query(None, description="打款方筛选"),
    payee: Optional[str] = Query(None, description="收款方筛选"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    交易台账列表
    """
    return LedgerService.get_transaction_ledger(
        case_no=case_no,
        payer=payer,
        payee=payee,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )


@router.get("/high-frequency", response_model=List[dict])
async def get_high_frequency_persons(
    limit: int = Query(10, ge=1, le=100)
):
    """
    高频交易人员统计
    """
    return LedgerService.get_high_frequency_persons(limit=limit)


@router.get("/evidence-inventory/{case_id}", response_model=dict)
async def get_evidence_inventory(case_id: int):
    """
    证据清单汇总
    """
    return LedgerService.get_evidence_inventory(case_id)


@router.get("/case-summary/{case_id}", response_model=dict)
async def get_case_summary(case_id: int):
    """
    案件摘要
    """
    return LedgerService.get_case_summary(case_id)