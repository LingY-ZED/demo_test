"""
测试数额计算服务
"""
from services.amount_calculator import AmountCalculator


def test_illegal_business_amount():
    """测试非法经营数额计算"""
    print("=== 非法经营数额计算测试 ===\n")

    test_cases = [
        # (交易数量, 单价, 预期数额)
        (100, 200, 20000),
        (50, 150, 7500),
        (200, 80, 16000),
    ]

    for qty, price, expected in test_cases:
        result = AmountCalculator.calculate_illegal_business_amount(qty, price)
        status = "✓" if result == expected else "✗"
        print(f"{status} 数量:{qty} × 单价:{price} = {result}元 (预期:{expected}元)")


def test_illegal_gain_amount():
    """测试违法所得数额计算"""
    print("\n=== 违法所得数额计算测试 ===\n")

    # 非法经营数额 = 20000，成本率30%
    biz_amount = 20000
    expected_gain = 14000  # 20000 * 0.7

    gain = AmountCalculator.calculate_illegal_gain_amount(biz_amount)
    status = "✓" if gain == expected_gain else "✗"
    print(f"{status} 非法经营:{biz_amount}元 -> 违法所得:{gain}元 (成本率30%, 预期:{expected_gain}元)")


def test_criminal_threshold():
    """测试刑事门槛比对"""
    print("\n=== 刑事门槛比对测试 ===\n")

    test_cases = [
        # (非法经营, 违法所得, 商标数, 描述)
        (50000, 30000, 1, "达到入罪门槛"),
        (250000, 150000, 1, "情节特别严重"),
        (30000, 20000, 2, "假冒两种以上"),
        (20000, 10000, 1, "未达门槛"),
        (50000, 35000, 1, "服务商标"),
    ]

    for biz, gain, trademarks, desc in test_cases:
        result = AmountCalculator.check_criminal_threshold(biz, gain, trademarks)
        print(f"  {desc}:")
        print(f"    非法经营:{biz}元, 违法所得:{gain}元, 商标:{trademarks}个")
        print(f"    结果: {result}")
        print()


def test_trademark_threshold():
    """测试假冒商标门槛"""
    print("\n=== 假冒商标门槛测试 ===\n")

    test_cases = [
        (1, 50000, True, "假冒一种商标"),
        (2, 30000, True, "假冒两种以上商标"),
        (1, 40000, False, "未达门槛"),
        (3, 20000, True, "假冒多种，低门槛"),
    ]

    for trademarks, biz, expected_met, desc in test_cases:
        result = AmountCalculator.check_criminal_threshold(biz, 0, trademarks)
        status = "✓" if result['threshold_met'] == expected_met else "✗"
        print(f"{status} {desc}: 商标{trademarks}个, 经营额{biz}元 -> {result['threshold_met']}")


def test_price_anomaly_detection():
    """测试价格异常判定"""
    print("\n=== 价格异常判定测试 ===\n")

    # 正品参考价100元
    reference_price = 100

    test_cases = [
        # (报价, 描述, 是否异常)
        (30, "低于正品70%", True),
        (50, "低于正品50%", True),
        (60, "高于正品50%", False),
        (100, "等于正品价", False),
        (40, "低于正品60%", True),
    ]

    for quote, desc, expected in test_cases:
        result = AmountCalculator.is_price_anomaly(quote, reference_price)
        status = "✓" if result == expected else "✗"
        ratio = quote / reference_price * 100 if reference_price else 0
        print(f"{status} 报价:{quote}元 (正品{reference_price}元的{ratio:.0f}%) {desc} -> 异常:{result}")


def test_amount_level():
    """测试数额级别判断"""
    print("\n=== 数额级别判断测试 ===\n")

    test_cases = [
        (5000, "轻微"),
        (30000, "较大"),
        (150000, "巨大"),
        (250000, "特别巨大"),
    ]

    for amount, expected_level in test_cases:
        level = AmountCalculator.get_amount_level(amount)
        print(f"  {amount}元 -> {level}")


def test_accumulated_amount():
    """测试累加计算"""
    print("\n=== 累加计算测试 ===\n")

    transactions = [
        {"amount": 5000},
        {"amount": 3000},
        {"amount": 2000},
    ]

    total = AmountCalculator.calculate_total_amount(transactions)
    print(f"  多笔交易累加: 5000+3000+2000 = {total}元")


if __name__ == "__main__":
    test_illegal_business_amount()
    test_illegal_gain_amount()
    test_criminal_threshold()
    test_trademark_threshold()
    test_price_anomaly_detection()
    test_amount_level()
    test_accumulated_amount()
    print("\n数额计算测试完成!")