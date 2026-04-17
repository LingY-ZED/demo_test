"""
报告生成API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import os
import uuid
from datetime import datetime

from config.settings import settings
from services.case_service import CaseService
from services.relation_service import RelationService
from services.ledger_service import LedgerService

router = APIRouter(prefix="/api/report", tags=["报告生成"])


@router.post("/generate")
async def generate_report(case_id: int):
    """
    生成Word分析报告

    Args:
        case_id: 案件ID

    Returns:
        报告下载地址
    """
    # 检查案件是否存在
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    # 获取分析数据
    case_detail = CaseService.get_case_detail(case_id)
    chain_analysis = RelationService.analyze_case_chain(case_id)
    evidence_inventory = LedgerService.get_evidence_inventory(case_id)

    # 生成报告内容
    report_content = _generate_report_content(
        case_detail, chain_analysis, evidence_inventory
    )

    # 保存报告
    filename = f"report_{case.case_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    report_dir = getattr(settings, 'report_dir', 'data/reports')
    os.makedirs(report_dir, exist_ok=True)
    filepath = os.path.join(report_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_content)

    return {
        "success": True,
        "report_id": filename,
        "download_url": f"/api/report/download/{filename}",
        "message": "报告生成成功"
    }


@router.get("/download/{filename}")
async def download_report(filename: str):
    """
    获取报告下载地址
    """
    report_dir = getattr(settings, 'report_dir', 'data/reports')
    filepath = os.path.join(report_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="报告不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=filename
    )


@router.get("/{case_id}")
async def get_report_status(case_id: int):
    """
    获取报告信息
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")

    # 简单返回案件摘要信息
    summary = LedgerService.get_case_summary(case_id)
    return {
        "case_id": case_id,
        "case_no": case.case_no,
        "report_available": True,
        "summary": summary
    }


def _generate_report_content(case_detail, chain_analysis, evidence_inventory) -> str:
    """
    生成报告文本内容
    """
    case = case_detail.get("case", {})
    stats = case_detail.get("statistics", {})

    lines = [
        "=" * 60,
        "火眼智擎—汽配领域知产保护分析报告",
        "=" * 60,
        "",
        f"案件编号: {case.get('case_no', 'N/A')}",
        f"嫌疑人姓名: {case.get('suspect_name', 'N/A')}",
        f"涉案品牌: {case.get('brand', 'N/A')}",
        f"涉案金额: {case.get('amount', 0)}元",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "-" * 60,
        "一、案件概况",
        "-" * 60,
        f"  交易记录: {stats.get('transaction_count', 0)}条",
        f"  通讯记录: {stats.get('communication_count', 0)}条",
        f"  物流记录: {stats.get('logistics_count', 0)}条",
        f"  涉案人员: {stats.get('person_count', 0)}人",
        f"  可疑线索: {stats.get('suspicious_clue_count', 0)}条",
        "",
        "-" * 60,
        "二、可疑线索",
        "-" * 60,
    ]

    # 添加可疑线索
    suspicious_clues = case_detail.get("suspicious_clues", [])
    if suspicious_clues:
        for i, clue in enumerate(suspicious_clues[:10], 1):
            lines.append(f"  {i}. [{clue.get('clue_type', '未知')}] {clue.get('evidence_text', '')[:50]}...")
            lines.append(f"     评分: {clue.get('score', 0)}分 | 涉嫌罪名: {clue.get('crime_type', '待定')}")
    else:
        lines.append("  暂无可疑线索")

    lines.extend([
        "",
        "-" * 60,
        "三、上下游关系",
        "-" * 60,
        f"  上游供货商: {len(chain_analysis.get('upstream_count', []))}个",
        f"  下游买家: {len(chain_analysis.get('downstream_count', []))}个",
        f"  核心嫌疑人: {len(chain_analysis.get('core_count', []))}个",
    ])

    # 添加核心嫌疑人信息
    core_suspects = chain_analysis.get("role_analysis", {})
    if core_suspects.get("producers"):
        lines.append(f"  生产者: {', '.join(core_suspects['producers'])}")
    if core_suspects.get("sellers"):
        lines.append(f"  销售者: {', '.join(core_suspects['sellers'])}")

    lines.extend([
        "",
        "-" * 60,
        "四、证据清单",
        "-" * 60,
        f"  通讯证据: {evidence_inventory.get('communication_evidence_count', 0)}条",
        f"  价格异常证据: {evidence_inventory.get('price_anomaly_evidence_count', 0)}条",
        f"  物流异常证据: {evidence_inventory.get('logistics_evidence_count', 0)}条",
        "",
        "=" * 60,
        "报告生成完毕",
        "=" * 60,
    ])

    return "\n".join(lines)