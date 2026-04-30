"""
智能分析API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel

from services.evidence_analyzer import EvidenceAnalyzer
from services.relation_service import RelationService
from services.case_service import CaseService
from services.transaction_cross_validator import TransactionCrossValidator

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


@router.post("/cross-validate/{case_id}")
async def cross_validate_transactions(case_id: int, window_minutes: int = 60):
    """
    交易 × 通讯交叉比对

    从时间和金额两个维度比对资金流水与聊天记录，标记异常交易：
    - 金额不符：聊天提及金额与实际交易金额偏差超过 20%
    - 无沟通大额交易：5 万元以上转账前后 1 小时内无相关聊天
    - 聊天提及无对应交易：聊天讨论了付款但找不到匹配交易

    Args:
        case_id: 案件ID
        window_minutes: 时间窗口（分钟），默认 60
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    anomalies = TransactionCrossValidator.validate(case_id, window_minutes)

    return {
        "case_id": case_id,
        "case_no": case.case_no,
        "anomalies": anomalies,
        "total_anomalies": len(anomalies),
    }