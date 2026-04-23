"""
案件管理API路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from services.case_service import CaseService

router = APIRouter(prefix="/api/cases", tags=["案件管理"])


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_no: str


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


@router.get("", response_model=List[dict])
async def list_cases(
    case_no: Optional[str] = Query(None, description="案件编号模糊匹配"),
    suspect_name: Optional[str] = Query(None, description="嫌疑人姓名模糊匹配"),
    brand: Optional[str] = Query(None, description="涉案品牌模糊匹配"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    案件列表查询
    """
    cases = CaseService.list_cases(
        case_no=case_no,
        suspect_name=suspect_name,
        brand=brand,
        limit=limit,
        offset=offset,
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
    )
    return CaseService._case_to_dict(case)


@router.put("/{case_id}", response_model=dict)
async def update_case(case_id: int, case_data: CaseUpdate):
    """
    更新案件
    """
    case = CaseService.update_case(case_id=case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    return CaseService._case_to_dict(case)


@router.post("/{case_id}/infer-fields", response_model=dict)
async def infer_case_fields(case_id: int):
    """
    重新推导案件嫌疑人和涉案品牌
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    infer_result = CaseService.auto_update_inferred_fields(case_id)
    return {
        "success": True,
        "message": "推导完成",
        "case": CaseService._case_to_dict(CaseService.get_case_by_id(case_id)),
        "inference": infer_result,
    }


@router.delete("/{case_id}")
async def delete_case(case_id: int):
    """
    删除案件
    """
    success = CaseService.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="案件不存在")
    return {"success": True, "message": "案件已删除"}
