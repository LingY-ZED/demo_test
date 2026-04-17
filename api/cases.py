"""
案件管理API路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from decimal import Decimal

from services.case_service import CaseService

router = APIRouter(prefix="/api/cases", tags=["案件管理"])


class CaseCreate(BaseModel):
    case_no: str
    suspect_name: str
    brand: Optional[str] = None
    amount: Optional[float] = None


class CaseUpdate(BaseModel):
    suspect_name: Optional[str] = None
    brand: Optional[str] = None
    amount: Optional[float] = None


@router.get("", response_model=List[dict])
async def list_cases(
    case_no: Optional[str] = Query(None, description="案件编号模糊匹配"),
    suspect_name: Optional[str] = Query(None, description="嫌疑人姓名模糊匹配"),
    brand: Optional[str] = Query(None, description="涉案品牌模糊匹配"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    案件列表查询
    """
    cases = CaseService.list_cases(
        case_no=case_no,
        suspect_name=suspect_name,
        brand=brand,
        limit=limit,
        offset=offset
    )
    return cases


@router.get("/{case_id}", response_model=dict)
async def get_case(case_id: int):
    """
    案件详情
    """
    detail = CaseService.get_case_detail(case_id)
    if not detail:
        raise HTTPException(status_code=404, detail="案件不存在")
    return detail


@router.post("", response_model=dict)
async def create_case(case_data: CaseCreate):
    """
    创建案件
    """
    # 检查案件编号是否已存在
    existing = CaseService.get_case_by_no(case_data.case_no)
    if existing:
        raise HTTPException(status_code=400, detail="案件编号已存在")

    case = CaseService.create_case(
        case_no=case_data.case_no,
        suspect_name=case_data.suspect_name,
        brand=case_data.brand,
        amount=Decimal(str(case_data.amount)) if case_data.amount else None
    )
    return CaseService._case_to_dict(case)


@router.put("/{case_id}", response_model=dict)
async def update_case(case_id: int, case_data: CaseUpdate):
    """
    更新案件
    """
    case = CaseService.update_case(
        case_id=case_id,
        suspect_name=case_data.suspect_name,
        brand=case_data.brand,
        amount=Decimal(str(case_data.amount)) if case_data.amount else None
    )
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    return CaseService._case_to_dict(case)


@router.delete("/{case_id}")
async def delete_case(case_id: int):
    """
    删除案件
    """
    success = CaseService.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="案件不存在")
    return {"success": True, "message": "案件已删除"}