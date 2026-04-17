"""
数据导出API路由
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import csv
import io

from services.ledger_service import LedgerService

router = APIRouter(prefix="/api/export", tags=["数据导出"])


@router.get("/csv")
async def export_csv(
    type: str = Query(..., description="导出类型: transactions/persons/evidence"),
    case_id: Optional[int] = Query(None, description="案件ID"),
    case_no: Optional[str] = Query(None, description="案件编号")
):
    """
    导出CSV文件

    Args:
        type: 导出类型
        case_id: 案件ID
        case_no: 案件编号
    """
    if type == "transactions":
        data = LedgerService.get_transaction_ledger(case_no=case_no, limit=10000)
        headers = ["ID", "案件ID", "案件编号", "交易时间", "打款方", "收款方", "金额", "支付方式", "备注"]
        rows = [[
            d.get("id"), d.get("case_id"), d.get("case_no"),
            d.get("transaction_time"), d.get("payer"), d.get("payee"),
            d.get("amount"), d.get("payment_method"), d.get("remark")
        ] for d in data]

    elif type == "persons":
        data = LedgerService.get_person_ledger(limit=10000)
        headers = ["ID", "姓名", "角色", "是否有授权", "主观明知评分", "非法经营数额", "关联案件数"]
        rows = [[
            d.get("id"), d.get("name"), d.get("role"),
            d.get("is_authorized"), d.get("subjective_knowledge_score"),
            d.get("illegal_business_amount"), d.get("linked_cases")
        ] for d in data]

    elif type == "evidence":
        if not case_id:
            raise HTTPException(status_code=400, detail="需要提供case_id")
        inventory = LedgerService.get_evidence_inventory(case_id)
        data = inventory.get("evidence_list", [])
        headers = ["类型", "ID", "时间", "相关方", "内容/描述", "命中关键词", "评分", "涉嫌罪名"]
        rows = [[
            d.get("type"), d.get("id"), d.get("time"),
            f"{d.get('initiator', '')}->{d.get('receiver', '')}" if d.get("type") == "通讯记录" else f"{d.get('sender', '')}->{d.get('receiver', '')}",
            d.get("content", "") or d.get("description", ""),
            ",".join(d.get("hit_keywords", [])),
            d.get("score", 0),
            d.get("crime_type", "")
        ] for d in data]

    else:
        raise HTTPException(status_code=400, detail="不支持的导出类型")

    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={type}_{case_no or case_id}.csv"}
    )