"""
敏感词库
用于检测通讯记录中的可疑关键词
"""
from typing import List, Dict

from .keywords_data import (
    CATEGORY_1_COUNTERFEIT,
    CATEGORY_2_EVASIVE,
    CATEGORY_3_SUSPICIOUS,
    CATEGORY_4_SELLING,
    CATEGORY_5_PRODUCTION,
    CATEGORY_6_AUTHORIZATION,
    BRAND_KEYWORDS,
    CATEGORY_WEIGHTS,
    CATEGORY_NAMES,
)


class KeywordMatch:
    """敏感词匹配结果"""

    def __init__(self, word: str, weight: int, category: str, position: int = 0):
        self.word = word
        self.weight = weight
        self.category = category
        self.position = position

    def to_dict(self) -> Dict:
        return {
            "word": self.word,
            "weight": self.weight,
            "category": self.category,
        }


class KeywordLibrary:
    """敏感词库类"""

    def __init__(self):
        self._build_word_list()

    def _build_word_list(self):
        """构建敏感词列表"""
        self._words = []

        # 类别1
        for word in CATEGORY_1_COUNTERFEIT:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_1"],
                "category": CATEGORY_NAMES["category_1"]
            })

        # 类别2
        for word in CATEGORY_2_EVASIVE:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_2"],
                "category": CATEGORY_NAMES["category_2"]
            })

        # 类别3
        for word in CATEGORY_3_SUSPICIOUS:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_3"],
                "category": CATEGORY_NAMES["category_3"]
            })

        # 类别4
        for word in CATEGORY_4_SELLING:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_4"],
                "category": CATEGORY_NAMES["category_4"]
            })

        # 类别5
        for word in CATEGORY_5_PRODUCTION:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_5"],
                "category": CATEGORY_NAMES["category_5"]
            })

        # 类别6
        for word in CATEGORY_6_AUTHORIZATION:
            self._words.append({
                "word": word,
                "weight": CATEGORY_WEIGHTS["category_6"],
                "category": CATEGORY_NAMES["category_6"]
            })

    def search(self, text: str) -> List[Dict]:
        """
        在文本中搜索敏感词

        Args:
            text: 待搜索的文本

        Returns:
            匹配的敏感词列表
        """
        if not text:
            return []

        matches = []
        text_lower = text.lower()

        for item in self._words:
            word = item["word"]
            if word.lower() in text_lower:
                # 记录匹配位置
                pos = text_lower.find(word.lower())
                matches.append({
                    "word": item["word"],
                    "weight": item["weight"],
                    "category": item["category"],
                    "position": pos
                })

        # 按位置排序
        matches.sort(key=lambda x: x["position"])
        return matches

    def search_brands(self, text: str) -> List[str]:
        """
        在文本中搜索品牌词

        Args:
            text: 待搜索的文本

        Returns:
            匹配的品牌列表
        """
        if not text:
            return []

        found_brands = []
        text_lower = text.lower()

        for brand, variants in BRAND_KEYWORDS.items():
            for variant in variants:
                if variant.lower() in text_lower:
                    found_brands.append(brand)
                    break

        return list(set(found_brands))

    def get_category_count(self, matches: List[Dict]) -> Dict[str, int]:
        """统计各类别命中数量"""
        counts = {}
        for item in matches:
            cat = item["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_total_weight(self, matches: List[Dict]) -> int:
        """计算匹配词的总权重"""
        return sum(item["weight"] for item in matches)

    def get_word_count(self) -> Dict[str, int]:
        """获取各类别词数统计"""
        return {
            CATEGORY_NAMES["category_1"]: len(CATEGORY_1_COUNTERFEIT),
            CATEGORY_NAMES["category_2"]: len(CATEGORY_2_EVASIVE),
            CATEGORY_NAMES["category_3"]: len(CATEGORY_3_SUSPICIOUS),
            CATEGORY_NAMES["category_4"]: len(CATEGORY_4_SELLING),
            CATEGORY_NAMES["category_5"]: len(CATEGORY_5_PRODUCTION),
            CATEGORY_NAMES["category_6"]: len(CATEGORY_6_AUTHORIZATION),
        }


# 全局实例
keyword_library = KeywordLibrary()
