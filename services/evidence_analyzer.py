"""
证据解析服务
分析单条证据，提取关键信息
"""
from typing import Dict, List, Any, Optional, Tuple
import re

from services.score_service import ScoreService
from utils.keywords import keyword_library


class EvidenceAnalyzer:
    """证据解析服务"""

    # 手机号脱敏正则
    PHONE_PATTERN = re.compile(r'(\d{3})\d{4}(\d{4})')
    # 身份证号脱敏正则
    ID_PATTERN = re.compile(r'(\d{6})\d{8}(\d{4})')
    # 银行卡号脱敏正则
    BANK_PATTERN = re.compile(r'(\d{4})\d+(\d{4})')

    @staticmethod
    def _extract_text_for_analysis(text: str) -> str:
        """如果是 CSV 格式，只提取内容列的值；否则原样返回"""
        if not text or not text.strip():
            return text
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return text
        first_line = lines[0].lower()
        # 聊天内容的列名变体（不包含 "mediatype"，它是消息类型代码而非内容）
        if not any(col in first_line for col in ("聊天内容", "内容", "content", "message")):
            return text
        # 找到内容列的索引
        headers = [h.strip() for h in lines[0].split(",")]
        content_idx = None
        for idx, h in enumerate(headers):
            if h in ("聊天内容", "内容", "content", "message"):
                content_idx = idx
                break
        if content_idx is None:
            return text
        # 只提取内容列的值
        extracted = []
        for line in lines[1:]:
            parts = line.split(",")
            if content_idx < len(parts):
                val = parts[content_idx].strip().strip('"').strip("'")
                if val and not val.startswith("{") and not val.startswith("<"):
                    extracted.append(val)
        return "\n".join(extracted) if extracted else text

    @classmethod
    def analyze_evidence(
        cls,
        evidence_text: str,
        evidence_type: str = "communication"
    ) -> Dict[str, Any]:
        """
        分析单条证据

        Args:
            evidence_text: 证据原文
            evidence_type: 证据类型（communication/transaction/logistics）

        Returns:
            分析结果
        """
        # 从 CSV 原文中只提取内容列，避免时间戳/URL 等元数据的误匹配
        analysis_text = cls._extract_text_for_analysis(evidence_text)

        result = {
            "original_text": evidence_text,
            "masked_text": cls.mask_sensitive_info(evidence_text),
            "price_anomaly": None,
            "subjective_knowledge": None,
            "key_actors": [],
        }

        # 先做主观明知分析，获取关键词命中情况
        score_result = ScoreService.analyze_text(analysis_text)
        has_keywords = len(score_result.get("matches", [])) > 0

        # 价格异常判定（传入关键词上下文，避免无涉假背景时误判）
        price_result = cls.analyze_price_anomaly(
            evidence_text,
            has_counterfeit_keywords=has_keywords
        )
        if price_result["has_anomaly"]:
            result["price_anomaly"] = price_result

        # 主观明知分析结果
        if score_result["score"] > 0:
            result["subjective_knowledge"] = {
                "score": score_result["score"],
                "level": score_result["level"],
                "hit_keywords": score_result["hit_words"],
                "categories": score_result["category_counts"],
                "crime_type": ScoreService.get_crime_type(score_result["matches"]),
            }

        return result

    @classmethod
    def analyze_price_anomaly(
        cls,
        text: str,
        reference_price: Optional[float] = None,
        has_counterfeit_keywords: bool = False
    ) -> Dict[str, Any]:
        """
        分析价格异常

        Args:
            text: 文本内容
            reference_price: 参考价（如果为None，仅在有关键词上下文时使用启发式估算）
            has_counterfeit_keywords: 文本中是否已命中涉假敏感词

        Returns:
            价格异常分析结果
        """
        # 提取价格
        prices = cls.extract_prices(text)

        if not prices:
            return {"has_anomaly": False}

        actual_price = prices[0]  # 取第一个提取到的价格

        if reference_price is not None:
            # 有明确参考价：使用参考价判断
            ratio = actual_price / reference_price if reference_price > 0 else 1
            is_anomaly = ratio < 0.5
        elif has_counterfeit_keywords:
            # 无参考价但有关键词上下文：使用启发式估算（正品约为售价 2.5 倍）
            reference_price = actual_price * 2.5
            ratio = actual_price / reference_price  # ≈ 0.4
            is_anomaly = ratio < 0.5
        else:
            # 既无参考价也无涉假上下文：不足以判断价格异常
            return {
                "has_anomaly": False,
                "quoted_price": actual_price,
                "reference_price": None,
                "ratio": None,
                "anomaly_level": None,
                "note": "缺少参考价格或涉假关键词上下文，无法判定价格异常",
            }

        return {
            "has_anomaly": is_anomaly,
            "quoted_price": actual_price,
            "reference_price": reference_price,
            "ratio": ratio,
            "anomaly_level": "严重" if ratio < 0.3 else ("中等" if ratio < 0.5 else "轻微"),
        }

    # 年份范围（排除被误提取为价格的年份数字）
    _YEAR_MIN = 1900
    _YEAR_MAX = 2100
    # 合理价格范围（元）
    _PRICE_MIN = 10
    _PRICE_MAX = 100_000_000

    @classmethod
    def extract_prices(cls, text: str) -> List[float]:
        """
        从文本中提取价格（金额）

        支持格式：元/块/万/千/亿，¥前缀，转账/打款/付款/汇款上下文
        只提取明确含货币语义的数字，避免误匹配数量（如"50套"）
        """
        prices = []
        seen = set()

        # 每条规则必须包含显式的货币单位或上下文，避免误匹配
        # 使用 [^\\S\\n] 代替 \\s 防止跨行匹配（如 "2021\\n元" 误提取年份）
        patterns = [
            # ¥ 前缀
            r'¥[^\S\n]*(\d+(?:\.\d{1,2})?)',
            # 转账/打款/付款/汇款 + 金额
            r'(?:转账|打款|付款|汇款)[^\S\n]*(\d+(?:\.\d{1,2})?)',
            # 价格是/为/： + 金额
            r'价格[是为：:][^\S\n]*(\d+(?:\.\d{1,2})?)',
            # 金额 + 万/千/百 单位
            r'(\d+(?:\.\d{1,2})?)[^\S\n]*[万千百]',
            # 金额 + 元/块 货币后缀
            r'(\d+(?:\.\d{1,2})?)[^\S\n]*[元块]',
        ]

        for pattern in patterns:
            for m in re.finditer(pattern, text):
                try:
                    price = float(m.group(1))
                except (ValueError, IndexError):
                    continue

                # 过滤年份数字（如 2021年 被错误提取）
                if cls._YEAR_MIN <= price <= cls._YEAR_MAX:
                    ctx_end = min(m.end() + 1, len(text))
                    after = text[m.end():ctx_end]
                    if after and after[0] in '年月日/-':
                        continue

                # 过滤不合理价格范围
                if price < cls._PRICE_MIN or price > cls._PRICE_MAX:
                    continue

                # 检测单位：万→×10000, 千→×1000
                ctx_end = min(m.end(), len(text))
                suffix = text[m.end():ctx_end + 2].strip()
                if '亿' in suffix:
                    price *= 100000000
                elif '万' in suffix:
                    price *= 10000
                elif '千' in suffix:
                    price *= 1000

                key = round(price, 2)
                if key not in seen:
                    seen.add(key)
                    prices.append(price)

        return sorted(prices, reverse=True)

    @classmethod
    def extract_subjective_knowledge_evidence(
        cls,
        text: str
    ) -> Dict[str, Any]:
        """
        提取主观明知证据

        Args:
            text: 证据原文

        Returns:
            主观明知证据
        """
        analysis_text = cls._extract_text_for_analysis(text)
        matches = keyword_library.search(analysis_text)
        score_result = ScoreService.analyze_text(analysis_text)

        # 按类别分组命中关键词
        category_hits = {}
        for m in matches:
            cat = m["category"]
            if cat not in category_hits:
                category_hits[cat] = []
            category_hits[cat].append({
                "word": m["word"],
                "weight": m["weight"],
            })

        return {
            "original_text": text,
            "masked_text": cls.mask_sensitive_info(text),
            "hit_count": len(matches),
            "score": score_result["score"],
            "level": score_result["level"],
            "category_hits": category_hits,
            "crime_type": ScoreService.get_crime_type(matches),
        }

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """
        手机号脱敏

        Args:
            phone: 手机号

        Returns:
            脱敏后的手机号
        """
        return cls.PHONE_PATTERN.sub(r'\1****\2', phone)

    @classmethod
    def mask_id_number(cls, id_number: str) -> str:
        """
        身份证号脱敏

        Args:
            id_number: 身份证号

        Returns:
            脱敏后的身份证号
        """
        return cls.ID_PATTERN.sub(r'\1********\2', id_number)

    @classmethod
    def mask_bank_card(cls, card_number: str) -> str:
        """
        银行卡号脱敏

        Args:
            card_number: 银行卡号

        Returns:
            脱敏后的银行卡号
        """
        return cls.BANK_PATTERN.sub(r'\1****\2', card_number)

    @classmethod
    def mask_sensitive_info(cls, text: str) -> str:
        """
        脱敏所有敏感信息

        Args:
            text: 原始文本

        Returns:
            脱敏后的文本
        """
        # 脱敏手机号
        text = cls.PHONE_PATTERN.sub(r'\1****\2', text)
        # 脱敏身份证号
        text = cls.ID_PATTERN.sub(r'\1********\2', text)
        # 脱敏银行卡号
        text = cls.BANK_PATTERN.sub(r'\1****\2', text)
        return text

    @classmethod
    def highlight_keywords(
        cls,
        text: str,
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        高亮文本中的关键词

        Args:
            text: 原始文本
            keywords: 关键词列表（如果为None，自动从文本中提取）

        Returns:
            高亮后的文本（HTML格式）
        """
        if keywords is None:
            analysis_text = cls._extract_text_for_analysis(text)
            matches = keyword_library.search(analysis_text)
            keywords = [m["word"] for m in matches]

        result = text
        for kw in keywords:
            # 使用HTML标签高亮
            result = result.replace(
                kw,
                f'<mark class="keyword">{kw}</mark>'
            )

        return result
