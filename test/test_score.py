"""
测试主观明知评分服务
"""
from services.score_service import ScoreService


def test_basic_scoring():
    """测试基础评分"""
    print("=== 基础评分测试 ===\n")

    test_cases = [
        "这批高仿原厂标一定要贴好",
        "这批货你别声张，不是原厂的",
        "博世刹车片到了，要批发吗",
        "原厂品质，价格便宜",
        "我们这是总代理，厂家直销",
    ]

    for text in test_cases:
        result = ScoreService.analyze_text(text)
        print(f"文本: {text}")
        print(f"  评分: {result['score']}分 ({result['level']})")
        print(f"  命中: {result['hit_words']}")
        print(f"  品牌: {result['brands']}")
        print(f"  涉嫌: {ScoreService.get_crime_type(result['matches'])}")
        print()


def test_category_weights():
    """测试各类别权重计算"""
    print("=== 类别权重测试 ===\n")

    # 类别1: 直接承认假冒类
    text1 = "这是高仿的博世大灯"
    result1 = ScoreService.analyze_text(text1)
    print(f"'{text1}'")
    print(f"  评分: {result1['score']} (类别1: {result1['category_counts'].get('直接承认假冒类', 0)}个)")

    # 类别2: 回避性话术类
    text2 = "这事你知道的，老规矩"
    result2 = ScoreService.analyze_text(text2)
    print(f"'{text2}'")
    print(f"  评分: {result2['score']} (类别2: {result2['category_counts'].get('回避性话术类', 0)}个)")

    # 类别3: 暗示非正品类
    text3 = "原厂品质，但没有授权"
    result3 = ScoreService.analyze_text(text3)
    print(f"'{text3}'")
    print(f"  评分: {result3['score']} (类别3: {result3['category_counts'].get('暗示非正品类', 0)}个)")

    # 组合测试
    text4 = "高仿大灯，原厂品质，老规矩，别声张"
    result4 = ScoreService.analyze_text(text4)
    print(f"\n'{text4}'")
    print(f"  评分: {result4['score']} (等级: {result4['level']})")
    print(f"  各类别: {result4['category_counts']}")


def test_extra_factors():
    """测试额外加分因素"""
    print("\n=== 额外加分因素测试 ===\n")

    text = "高仿博世刹车片"

    # 无额外因素
    result1 = ScoreService.analyze_text(text)
    print(f"'{text}' - 无额外因素: {result1['score']}分")

    # 价格异常（报价/正品 < 0.5）
    result2 = ScoreService.analyze_text(text, {"price_ratio": 0.3})
    print(f"'{text}' - 价格异常(30%): {result2['score']}分 (+3)")

    # 无授权
    result3 = ScoreService.analyze_text(text, {"is_authorized": False})
    print(f"'{text}' - 无授权: {result3['score']}分 (+3)")

    # 无凭证
    result4 = ScoreService.analyze_text(text, {"has_receipt": False})
    print(f"'{text}' - 无凭证: {result4['score']}分 (+2)")

    # 组合
    result5 = ScoreService.analyze_text(text, {
        "price_ratio": 0.3,
        "is_authorized": False,
        "has_receipt": False
    })
    print(f"'{text}' - 全组合: {result5['score']}分 (上限10)")


def test_crime_type():
    """测试罪名推断"""
    print("\n=== 罪名推断测试 ===\n")

    test_cases = [
        ("自己生产贴牌做高仿", "生产/贴牌类多"),
        ("批发零售拿货出货", "销售行为类多"),
        ("高仿一比一复刻", "直接承认假冒类"),
        ("原厂品质优惠价", "暗示非正品类"),
    ]

    from utils.keywords import keyword_library
    for text, desc in test_cases:
        matches = keyword_library.search(text)
        crime = ScoreService.get_crime_type(matches)
        print(f"{text} -> {crime} ({desc})")


def test_amount_threshold():
    """测试数额门槛判断"""
    print("\n=== 数额门槛测试 ===\n")

    test_cases = [
        (50000, 30000, 1, "达到入罪门槛"),
        (250000, 150000, 1, "情节特别严重"),
        (30000, 20000, 2, "假冒两种以上，降低门槛"),
        (20000, 10000, 1, "未达门槛"),
    ]

    for biz, income, trademarks, desc in test_cases:
        result = ScoreService.get_amount_threshold_status(biz, income, trademarks)
        print(f"非法经营{biz}元, 违法所得{income}元, {trademarks}个商标 -> {desc}")
        print(f"  门槛满足: {result['threshold_met']}, 类型: {result['crime_type']}, 建议: {result['suggestion']}")


if __name__ == "__main__":
    test_basic_scoring()
    test_category_weights()
    test_extra_factors()
    test_crime_type()
    test_amount_threshold()
    print("\n评分服务测试完成!")
