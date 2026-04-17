"""
测试数据清洗服务
"""
from services.upload_service import UploadService
from services.clean_service import CleanService


def test_clean_transactions():
    """测试资金流水清洗"""
    records = UploadService.parse_transactions("data/test_transactions.csv", case_id=1)
    cleaned = CleanService.clean_transactions(records)
    print(f"资金流水: 原始{len(records)}条 -> 清洗后{len(cleaned)}条")
    return cleaned


def test_clean_communications():
    """测试通讯记录清洗"""
    records = UploadService.parse_communications("data/test_communications.csv", case_id=1)
    cleaned = CleanService.clean_communications(records)
    print(f"通讯记录: 原始{len(records)}条 -> 清洗后{len(cleaned)}条")
    return cleaned


def test_clean_logistics():
    """测试物流记录清洗"""
    records = UploadService.parse_logistics("data/test_logistics.csv", case_id=1)
    cleaned = CleanService.clean_logistics(records)
    print(f"物流记录: 原始{len(records)}条 -> 清洗后{len(cleaned)}条")
    return cleaned


def test_extract_persons():
    """测试人物档案提取"""
    records = UploadService.parse_transactions("data/test_transactions.csv", case_id=1)
    persons = CleanService.extract_persons_from_transactions(records)
    print(f"\n人物档案: 共{len(persons)}人")
    for p in persons:
        print(f"  {p['name']}: 涉案金额 {p['illegal_business_amount']}元")
    return persons


def test_hidden_sources():
    """测试隐蔽发货源头"""
    records = UploadService.parse_logistics("data/test_logistics.csv", case_id=1)
    sources = CleanService.extract_hidden_shipping_sources(records)
    print(f"\n隐蔽发货源头: 发现{len(sources)}个")
    for s in sources:
        print(f"  地址: {s['address']}")
        print(f"  发货次数: {s['shipment_count']}")
        print(f"  发件人: {s['senders']}")
    return sources


def test_pre_transfer():
    """测试转账前联络分析"""
    transactions = UploadService.parse_transactions("data/test_transactions.csv", case_id=1)
    communications = UploadService.parse_communications("data/test_communications.csv", case_id=1)

    # 清洗数据
    transactions = CleanService.clean_transactions(transactions)
    communications = CleanService.clean_communications(communications)

    results = CleanService.analyze_pre_transfer_communications(transactions, communications)
    print(f"\n转账前联络: 发现{len(results)}条")
    for r in results:
        print(f"  {r['payer']}->{r['payee']}: {r['amount']}元 (转账前{r['time_diff_minutes']}分钟联络过)")
    return results


if __name__ == "__main__":
    test_clean_transactions()
    test_clean_communications()
    test_clean_logistics()
    test_extract_persons()
    test_hidden_sources()
    test_pre_transfer()
    print("\n清洗测试完成!")
