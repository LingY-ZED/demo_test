"""
可疑线索API路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from services.suspicion_detector import SuspicionDetector

router = APIRouter(prefix="/api", tags=["可疑线索"])


@router.get("/cases/{case_id}/suspicious")
async def get_case_suspicious_clues(case_id: int):
    """
    获取案件可疑线索列表
    """
    clues = SuspicionDetector.detect_all(case_id)
    return clues


@router.get("/clues/{clue_id}", response_model=dict)
async def get_clue_detail(clue_id: int):
    """
    线索详情（含原文引用高亮）
    """
    clue = SuspicionDetector.get_clue_by_id(clue_id)
    if not clue:
        raise HTTPException(status_code=404, detail="线索不存在")
    return clue