"""
关联分析API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List

from services.relation_service import RelationService
from services.case_service import CaseService

router = APIRouter(prefix="/api/relations", tags=["关联分析"])


@router.get("/chain/{case_id}", response_model=dict)
async def get_case_relation_chain(case_id: int):
    """
    单案上下游关系图数据
    """
    # 检查案件是否存在
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    result = RelationService.analyze_case_chain(case_id)
    return result


@router.get("/cross-case", response_model=List[dict])
async def get_cross_case_connections():
    """
    跨案关联拓扑数据
    """
    connections = RelationService.find_cross_case_connections()
    return connections


@router.get("/recidivism/{person_name}", response_model=dict)
async def check_recidivism(person_name: str):
    """
    累犯检测
    """
    result = RelationService.detect_recidivism(person_name)
    return result


@router.get("/upstream/{case_id}", response_model=List[dict])
async def get_upstream_suppliers(case_id: int):
    """
    获取上游供货商列表
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    suppliers = RelationService.get_upstream_suppliers(case_id)
    return suppliers


@router.get("/downstream/{case_id}", response_model=List[dict])
async def get_downstream_buyers(case_id: int):
    """
    获取下游买家列表
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    buyers = RelationService.get_downstream_buyers(case_id)
    return buyers


@router.get("/core-suspects/{case_id}", response_model=List[dict])
async def get_core_suspects(case_id: int):
    """
    获取核心嫌疑人列表
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    suspects = RelationService.get_core_suspects(case_id)
    return suspects