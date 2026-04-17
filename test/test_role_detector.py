"""
测试角色推断服务
"""
from services.role_detector import RoleDetector


def test_keyword_based_role():
    """测试基于关键词的角色推断"""
    print("=== 关键词角色推断测试 ===\n")

    test_cases = [
        # 文本, 预期角色
        ("这批高仿件我来做，贴牌生产", "生产者"),
        ("我们要生产一批博世的大灯", "生产者"),
        ("厂家直销，总代理拿货", "销售者"),
        ("批发零售，价格优惠", "销售者"),
        ("出货给下家，拿货价格再低些", "销售者"),
        ("我是中间商，赚点差价", "中间商"),
        ("付款收货，好评", "终端买家"),
    ]

    for text, expected in test_cases:
        role, confidence = RoleDetector.infer_role_by_keywords(text)
        status = "✓" if role == expected else "✗"
        print(f"{status} 文本: {text[:20]}...")
        print(f"   推断: {role} (置信度:{confidence}), 预期: {expected}")
        print()


def test_producer_keywords():
    """测试生产/贴牌类关键词"""
    print("\n=== 生产者关键词测试 ===")

    producer_keywords = [
        "贴牌", "打标", "代工", "仿制", "开模", "定做",
        "高仿", "一比一", "复刻", "原单", "跟单"
    ]

    for kw in producer_keywords:
        role, confidence = RoleDetector.infer_role_by_keywords(f"这批货需要{kw}")
        print(f"  '{kw}' -> {role} ({confidence})")


def test_seller_keywords():
    """测试销售行为类关键词"""
    print("\n=== 销售者关键词测试 ===")

    seller_keywords = [
        "出货", "拿货", "批发", "代理", "零售", "分销",
        "走量", "特价", "优惠", "直销"
    ]

    for kw in seller_keywords:
        role, confidence = RoleDetector.infer_role_by_keywords(f"大量{kw}")
        print(f"  '{kw}' -> {role} ({confidence})")


def test_transaction_role():
    """测试基于交易行为的角色推断"""
    print("\n=== 交易行为角色推断测试 ===")

    # 模拟交易数据
    transactions = [
        {"payer": "张三", "payee": "李四", "amount": 5000},
        {"payer": "李四", "payee": "王五", "amount": 4500},
        {"payer": "赵六", "payee": "李四", "amount": 3000},
    ]

    role = RoleDetector.infer_role_by_transactions("李四", transactions)
    print(f"  李四的交易角色: {role}")

    role = RoleDetector.infer_role_by_transactions("张三", transactions)
    print(f"  张三的交易角色: {role}")


def test_logistics_role():
    """测试基于物流行为的角色推断"""
    print("\n=== 物流行为角色推断测试 ===")

    # 模拟物流数据（发件人多，收件人少 -> 可能是上游发货商）
    logistics = [
        {"sender": "老张", "receiver": "多个买家", "sender_address": "广州某地址"},
    ]

    role = RoleDetector.infer_role_by_logistics("老张", logistics)
    print(f"  老张的物流角色: {role}")


def test_combined_role():
    """测试综合角色推断"""
    print("\n=== 综合角色推断测试 ===")

    # 生产者特征
    text1 = "我们自己开模生产，贴牌加工"
    role1, conf1 = RoleDetector.infer_role_by_keywords(text1)
    print(f"  文本1: '{text1[:15]}...' -> {role1} ({conf1})")

    # 销售者特征
    text2 = "批发零售，大量出货，价格优惠"
    role2, conf2 = RoleDetector.infer_role_by_keywords(text2)
    print(f"  文本2: '{text2[:15]}...' -> {role2} ({conf2})")

    # 中间商特征
    text3 = "从这边拿货再发过去，赚点差价"
    role3, conf3 = RoleDetector.infer_role_by_keywords(text3)
    print(f"  文本3: '{text3[:15]}...' -> {role3} ({conf3})")


if __name__ == "__main__":
    test_keyword_based_role()
    test_producer_keywords()
    test_seller_keywords()
    test_transaction_role()
    test_logistics_role()
    test_combined_role()
    print("\n角色推断测试完成!")