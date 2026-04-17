"""
智能分析API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from services.evidence_analyzer import EvidenceAnalyzer
from services.relation_service import RelationService
from services.case_service import CaseService

router = APIRouter(prefix="/api/analyze", tags=["智能分析"])


class EvidenceAnalyzeRequest(BaseModel):
    evidence_text: str
    evidence_type: str = "communication"


class CaseAnalyzeRequest(BaseModel):
    case_id: int


@router.post("/evidence", response_model=dict)
async def analyze_evidence(request: EvidenceAnalyzeRequest):
    """
    分析单条证据（价格异常、主观明知、关键主体）
    """
    result = EvidenceAnalyzer.analyze_evidence(
        evidence_text=request.evidence_text,
        evidence_type=request.evidence_type
    )
    return result


@router.post("/case/{case_id}", response_model=dict)
async def analyze_case(case_id: int):
    """
    全案分析（生成分析报告）
    """
    # 检查案件是否存在
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    # 执行全案分析
    analysis_result = {
        "case_id": case_id,
        "case_no": case.case_no,
        "chain_analysis": RelationService.analyze_case_chain(case_id),
    }

    return analysis_result


@router.get("/actors/{case_id}", response_model=List[dict])
async def analyze_actors(case_id: int):
    """
    分析关键主体
    """
    # 检查案件是否存在
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    # 获取核心嫌疑人
    core_suspects = RelationService.get_core_suspects(case_id)
    return core_suspects