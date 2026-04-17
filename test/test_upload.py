"""
测试数据导入服务
"""
from services.upload_service import UploadService


def test_transactions():
    """测试资金流水导入"""
    records = UploadService.parse_transactions("data/test_transactions.csv", case_id=1)
    print(f"资金流水: {len(records)} 条")
    for r in records:
        print(f"  {r['payer']} -> {r['payee']}: {r['amount']}元 | {r['remark']}")
    return records


def test_communications():
    """测试通讯记录导入"""
    records = UploadService.parse_communications("data/test_communications.csv", case_id=1)
    print(f"\n通讯记录: {len(records)} 条")
    for r in records:
        print(f"  {r['initiator']} -> {r['receiver']}: {r['content']}")
    return records


def test_logistics():
    """测试物流记录导入"""
    records = UploadService.parse_logistics("data/test_logistics.csv", case_id=1)
    print(f"\n物流记录: {len(records)} 条")
    for r in records:
        print(f"  {r['sender']}({r['sender_address']}) -> {r['receiver']}({r['receiver_address']}): {r['description']}")
    return records


if __name__ == "__main__":
    test_transactions()
    test_communications()
    test_logistics()
    print("\n测试完成!")
