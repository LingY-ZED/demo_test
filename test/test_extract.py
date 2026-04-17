"""
测试自动化抽取服务
"""
from services.extract_service import ExtractService
from services.upload_service import UploadService
from services.clean_service import CleanService


def test_extract_from_files():
    """测试从文件自动抽取"""
    result = ExtractService.extract_from_files(
        transaction_file="data/test_transactions.csv",
        communication_file="data/test_communications.csv",
        logistics_file="data/test_logistics.csv",
        case_id=1
    )

    print("=== 自动化抽取结果 ===\n")

    # 人员档案
    print(f"人员档案: {len(result['persons'])}人")
    for p in result["persons"]:
        print(f"  {p['name']}: 涉案金额 {p['illegal_business_amount']}元")

    # 隐蔽源头
    print(f"\n隐蔽发货源头: {len(result['hidden_sources'])}个")
    for s in result["hidden_sources"]:
        print(f"  {s['address']}: 发货{s['shipment_count']}次, 发件人{s['senders']}")

    # 转账前联络
    print(f"\n转账前联络: {len(result['pre_transfer_links'])}条")
    for link in result["pre_transfer_links"]:
        print(f"  {link['payer']}->{link['payee']}: {link['amount']}元 (转账前{link['time_diff_minutes']}分钟)")

    # 统计信息
    stats = result["statistics"]
    print(f"\n统计信息:")
    print(f"  总交易笔数: {stats['total_transactions']}")
    print(f"  总交易金额: {stats['total_amount']}元")
    print(f"  涉及人员: {stats['person_count']}人")
    print(f"  通讯记录: {stats['communication_count']}条")
    print(f"  物流记录: {stats['logistics_count']}条")
    print(f"  隐蔽源头: {stats['hidden_source_count']}个")


def test_person_role_inference():
    """测试人员角色推断"""
    transactions = UploadService.parse_transactions("data/test_transactions.csv", case_id=1)
    logistics = UploadService.parse_logistics("data/test_logistics.csv", case_id=1)
    transactions = CleanService.clean_transactions(transactions)
    logistics = CleanService.clean_logistics(logistics)

    persons = ["王五", "老张汽配", "赵六", "钱七", "普通车主A"]

    print("\n=== 人员角色推断 ===")
    for name in persons:
        role = ExtractService.get_person_role_by_behavior(name, transactions, logistics)
        print(f"  {name}: {role}")


def test_address_network():
    """测试地址关系网络"""
    logistics = UploadService.parse_logistics("data/test_logistics.csv", case_id=1)
    logistics = CleanService.clean_logistics(logistics)

    network = ExtractService.extract_address_network(logistics)

    print("\n=== 地址关系网络 ===")
    for address, receivers in network.items():
        print(f"  {address} -> {receivers}")


if __name__ == "__main__":
    test_extract_from_files()
    test_person_role_inference()
    test_address_network()
    print("\n抽取测试完成!")
