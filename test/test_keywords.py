"""
测试敏感词库
"""
from utils.keywords import keyword_library, CATEGORY_1_COUNTERFEIT, CATEGORY_2_EVASIVE, CATEGORY_3_SUSPICIOUS


def test_basic_search():
    """测试基础搜索"""
    text = "这批高仿原厂标一定要贴好，这批货你别声张，不是原厂的"

    matches = keyword_library.search(text)

    print("=== 敏感词搜索测试 ===")
    print(f"文本: {text}")
    print(f"匹配结果: {len(matches)}个")
    for m in matches:
        print(f"  [{m['category']}] {m['word']} (权重{m['weight']})")

    # 统计
    counts = keyword_library.get_category_count(matches)
    print(f"\n类别统计: {counts}")
    print(f"总权重: {keyword_library.get_total_weight(matches)}")


def test_brand_search():
    """测试品牌搜索"""
    texts = [
        "博世大灯尾款",
        "奥迪A4L轮毂",
        "奔驰轮毂坏了需要更换",
        "需要米其林轮胎",
        "这个产品是杂牌",
    ]

    print("\n=== 品牌搜索测试 ===")
    for text in texts:
        brands = keyword_library.search_brands(text)
        print(f"  {text} -> {brands if brands else '无'}")


def test_keyword_categories():
    """测试各类别敏感词"""
    print("\n=== 敏感词类别 ===")
    print(f"类别1(直接承认假冒): {len(CATEGORY_1_COUNTERFEIT)}个 - {CATEGORY_1_COUNTERFEIT}")
    print(f"类别2(回避性话术): {len(CATEGORY_2_EVASIVE)}个 - {CATEGORY_2_EVASIVE}")
    print(f"类别3(暗示非正品): {len(CATEGORY_3_SUSPICIOUS)}个 - {CATEGORY_3_SUSPICIOUS}")


def test_real_communications():
    """测试真实通讯记录"""
    communications = [
        "这批高仿原厂标一定要贴好",
        "这批货你别声张，不是原厂的",
        "博世刹车片到了",
        "拿货价格再低一点，老规矩",
        "高仿件已发货",
    ]

    print("\n=== 通讯记录敏感词检测 ===")
    for comm in communications:
        matches = keyword_library.search(comm)
        brands = keyword_library.search_brands(comm)
        print(f"\n内容: {comm}")
        if matches:
            for m in matches:
                print(f"  [{m['category']}] {m['word']}")
        else:
            print("  无敏感词")
        if brands:
            print(f"  品牌: {brands}")


if __name__ == "__main__":
    test_basic_search()
    test_brand_search()
    test_keyword_categories()
    test_real_communications()
    print("\n敏感词库测试完成!")
