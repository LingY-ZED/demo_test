"""
主观明知评分服务
根据info.md中的评分公式计算主观明知评分
"""
from typing import Dict, List, Any, Tuple

from utils.keywords import keyword_library


class ScoreService:
    """主观明知评分服务"""

    # 评分上限
    MAX_CATEGORY_1_SCORE = 10  # 直接承认假冒类上限
    MAX_CATEGORY_2_SCORE = 8   # 回避性话术类上限
    MAX_CATEGORY_3_SCORE = 4   # 暗示非正品类上限

    # 额外加分项
    PRICE_DISCOUNT_THRESHOLD = 0.5  # 价格低于正品50%以上
    PRICE_DISCOUNT_SCORE = 3        # 价格异常加分

    UNAUTHORIZED_SCORE = 3    # 无授权证明
    NO_RECEIPT_SCORE = 2      # 无正规进货凭证

    # 评分等级阈值
    HIGHLY_SUSPICIOUS_THRESHOLD = 8   # 高度可疑
    MODERATELY_SUSPICIOUS_THRESHOLD = 5  # 中度可疑

    # 评分等级
    LEVEL_HIGHLY = "高度可疑"
    LEVEL_MODERATELY = "中度可疑"
    LEVEL_LOW = "低度可疑"

    @classmethod
    def calculate_score(cls, matches: List[Dict], extra_factors: Dict = None) -> int:
        """
        计算主观明知评分

        Args:
            matches: 敏感词匹配结果列表
            extra_factors: 额外加分因素
                - price_ratio: 实际报价/正品价格 (小于0.5则触发价格异常)
                - is_authorized: 是否有授权证明
                - has_receipt: 是否有正规进货凭证

        Returns:
            评分 (0-10)
        """
        if extra_factors is None:
            extra_factors = {}

        score = 0

        # 1. 类别1加权 (×5，上限10分)
        cat1_matches = [m for m in matches if m["category"] == "直接承认假冒类"]
        cat1_score = len(cat1_matches) * 5
        score += min(cat1_score, cls.MAX_CATEGORY_1_SCORE)

        # 2. 类别2加权 (×4，上限8分)
        cat2_matches = [m for m in matches if m["category"] == "回避性话术类"]
        cat2_score = len(cat2_matches) * 4
        score += min(cat2_score, cls.MAX_CATEGORY_2_SCORE)

        # 3. 类别3加权 (×2，上限4分)
        cat3_matches = [m for m in matches if m["category"] == "暗示非正品类"]
        cat3_score = len(cat3_matches) * 2
        score += min(cat3_score, cls.MAX_CATEGORY_3_SCORE)

        # 4. 类别4-6加权 (各×1)
        other_matches = [
            m for m in matches if m["category"] in
            ["销售行为类", "生产/贴牌类", "授权状态类"]
        ]
        score += len(other_matches)

        # 5. 价格异常加分
        price_ratio = extra_factors.get("price_ratio")
        if price_ratio is not None and price_ratio < cls.PRICE_DISCOUNT_THRESHOLD:
            score += cls.PRICE_DISCOUNT_SCORE

        # 6. 无授权证明
        is_authorized = extra_factors.get("is_authorized")
        if is_authorized is False:
            score += cls.UNAUTHORIZED_SCORE

        # 7. 无正规进货凭证
        has_receipt = extra_factors.get("has_receipt")
        if has_receipt is False:
            score += cls.NO_RECEIPT_SCORE

        # 上限10分
        return min(score, 10)

    @classmethod
    def get_suspicion_level(cls, score: int) -> str:
        """
        根据评分获取可疑程度等级

        Args:
            score: 主观明知评分

        Returns:
            可疑程度等级描述
        """
        if score >= cls.HIGHLY_SUSPICIOUS_THRESHOLD:
            return cls.LEVEL_HIGHLY
        elif score >= cls.MODERATELY_SUSPICIOUS_THRESHOLD:
            return cls.LEVEL_MODERATELY
        else:
            return cls.LEVEL_LOW

    @classmethod
    def analyze_text(cls, text: str, extra_factors: Dict = None) -> Dict[str, Any]:
        """
        分析文本并返回完整评分结果

        Args:
            text: 待分析的文本（聊天内容）
            extra_factors: 额外加分因素

        Returns:
            分析结果字典
        """
        # 搜索敏感词
        matches = keyword_library.search(text)

        # 计算评分
        score = cls.calculate_score(matches, extra_factors)

        # 获取等级
        level = cls.get_suspicion_level(score)

        # 各类别统计
        category_counts = keyword_library.get_category_count(matches)

        # 命中的关键词
        hit_words = [m["word"] for m in matches]

        # 检测到的品牌
        brands = keyword_library.search_brands(text)

        return {
            "text": text,
            "score": score,
            "level": level,
            "matches": matches,
            "hit_words": hit_words,
            "category_counts": category_counts,
            "brands": brands,
            "total_weight": keyword_library.get_total_weight(matches),
        }

    @classmethod
    def should_investigate(cls, score: int) -> bool:
        """
        判断是否需要进一步调查

        Args:
            score: 主观明知评分

        Returns:
            True 如果评分>=5
        """
        return score >= cls.MODERATELY_SUSPICIOUS_THRESHOLD

    @classmethod
    def get_crime_type(cls, matches: List[Dict]) -> str:
        """
        根据命中关键词推断涉嫌罪名

        Args:
            matches: 敏感词匹配结果列表

        Returns:
            涉嫌罪名
        """
        # 类别5（生产/贴牌类）命中多 -> 假冒注册商标罪
        cat5_matches = [m for m in matches if m["category"] == "生产/贴牌类"]
        if len(cat5_matches) >= 2:
            return "涉嫌假冒注册商标罪"

        # 类别4（销售行为类）命中多 -> 销售假冒注册商标的商品罪
        cat4_matches = [m for m in matches if m["category"] == "销售行为类"]
        if len(cat4_matches) >= 2:
            return "涉嫌销售假冒注册商标的商品罪"

        # 有假冒相关词
        counterfeit_words = ["高仿", "复刻", "假冒", "山寨", "盗版"]
        hit_counterfeit = any(m["word"] in counterfeit_words for m in matches)
        if hit_counterfeit:
            if len(cat5_matches) >= 1:
                return "涉嫌假冒注册商标罪"
            else:
                return "涉嫌销售假冒注册商标的商品罪"

        # 初步判断
        if matches:
            return "涉嫌销售假冒注册商标的商品罪"

        return "待定"

    @classmethod
    def get_amount_threshold_status(
        cls,
        illegal_business_amount: float,
        illegal_income_amount: float = None,
        trademark_count: int = 1
    ) -> Dict[str, Any]:
        """
        判断数额是否达到刑事门槛

        根据info.md:
        - 假冒注册商标罪：违法所得≥3万 或 非法经营≥5万
        - 假冒两种以上商标：门槛降低（违法所得≥2万 或 非法经营≥3万）

        Args:
            illegal_business_amount: 非法经营数额
            illegal_income_amount: 违法所得数额（可选）
            trademark_count: 涉及的注册商标数量

        Returns:
            门槛状态字典
        """
        result = {
            "threshold_met": False,
            "crime_type": "待定",
            "suggestion": "",
        }

        # 单种商标门槛
        if illegal_income_amount is not None:
            if illegal_income_amount >= 30000:
                result["threshold_met"] = True
                result["crime_type"] = "假冒注册商标罪"
                result["suggestion"] = "违法所得已达刑事门槛"
            elif illegal_income_amount >= 150000:
                result["suggestion"] = "违法所得已达情节特别严重标准"

        if illegal_business_amount >= 50000:
            result["threshold_met"] = True
            result["crime_type"] = "假冒注册商标罪"
            result["suggestion"] = "非法经营数额已达刑事门槛"
        elif illegal_business_amount >= 250000:
            result["suggestion"] = "非法经营数额已达情节特别严重标准"

        # 假冒两种以上商标，门槛降低
        if trademark_count >= 2:
            if result["threshold_met"]:
                result["suggestion"] = f"假冒{trademark_count}种以上商标，门槛已降低"
            else:
                if illegal_income_amount is not None and illegal_income_amount >= 20000:
                    result["threshold_met"] = True
                    result["crime_type"] = "假冒注册商标罪（多商标）"
                    result["suggestion"] = "假冒两种以上商标，门槛已降低"
                elif illegal_business_amount >= 30000:
                    result["threshold_met"] = True
                    result["crime_type"] = "假冒注册商标罪（多商标）"
                    result["suggestion"] = "假冒两种以上商标，门槛已降低"

        return result
