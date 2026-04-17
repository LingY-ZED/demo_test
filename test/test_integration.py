"""
集成测试：数据导入 → 清洗 → 分析 → 报告 全流程
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.upload_service import UploadService
from services.clean_service import CleanService
from services.extract_service import ExtractService
from services.score_service import ScoreService
from services.suspicion_detector import SuspicionDetector
from services.evidence_analyzer import EvidenceAnalyzer
from services.case_service import CaseService
from services.role_detector import RoleDetector
from utils.report_generator import ReportGenerator
from utils.exporter import Exporter
from utils.masking import MaskingUtil


def test_full_pipeline():
    """测试完整分析流程"""
    print("=" * 60)
    print("集成测试：数据导入 → 清洗 → 分析 → 报告")
    print("=" * 60)

    # 测试数据文件路径
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    test_transactions = os.path.join(data_dir, 'test_transactions.csv')
    test_communications = os.path.join(data_dir, 'test_communications.csv')
    test_logistics = os.path.join(data_dir, 'test_logistics.csv')

    case_id = 999  # 测试用案件ID

    print("\n【步骤1】数据导入")
    print("-" * 40)

    transactions = UploadService.parse_transactions(test_transactions, case_id=case_id)
    print(f"  资金流水导入: {len(transactions)}条")

    communications = UploadService.parse_communications(test_communications, case_id=case_id)
    print(f"  通讯记录导入: {len(communications)}条")

    logistics = UploadService.parse_logistics(test_logistics, case_id=case_id)
    print(f"  物流记录导入: {len(logistics)}条")

    print("\n【步骤2】数据清洗")
    print("-" * 40)

    clean_transactions = CleanService.clean_transactions(transactions)
    print(f"  清洗后资金流水: {len(clean_transactions)}条")

    clean_communications = CleanService.clean_communications(communications)
    print(f"  清洗后通讯记录: {len(clean_communications)}条")

    clean_logistics = CleanService.clean_logistics(logistics)
    print(f"  清洗后物流记录: {len(clean_logistics)}条")

    print("\n【步骤3】自动化抽取")
    print("-" * 40)

    extract_result = ExtractService.extract_from_files(
        transaction_file=test_transactions,
        communication_file=test_communications,
        logistics_file=test_logistics,
        case_id=case_id
    )

    print(f"  人员档案: {len(extract_result['persons'])}人")
    print(f"  隐蔽发货源头: {len(extract_result['hidden_sources'])}个")
    print(f"  转账前联络: {len(extract_result['pre_transfer_links'])}条")

    print("\n【步骤4】可疑线索检测")
    print("-" * 40)

    suspicious_clues = SuspicionDetector.detect_suspicious_clues(case_id, communications)
    print(f"  检测到可疑线索: {len(suspicious_clues)}条")

    for i, clue in enumerate(suspicious_clues[:3], 1):
        print(f"    {i}. [{clue.get('clue_type')}] 评分:{clue.get('score')} | {clue.get('evidence_text')[:30]}...")

    print("\n【步骤5】主观明知评分")
    print("-" * 40)

    for comm in communications[:3]:
        result = ScoreService.analyze_text(comm.get('content', ''))
        print(f"  文本: {comm.get('content')[:25]}...")
        print(f"    评分: {result['score']}分 ({result['level']})")
        print(f"    命中: {result['hit_words']}")

    print("\n【步骤6】角色推断")
    print("-" * 40)

    for person in extract_result['persons'][:3]:
        name = person.get('name', '')
        role, conf = RoleDetector.infer_role_by_keywords(f"{name}相关交易")
        print(f"  {name}: {role} (置信度:{conf})")

    print("\n【步骤7】数据脱敏")
    print("-" * 40)

    test_data = {
        "phone": "13812345678",
        "id_card": "110101199001011234",
        "bank_card": "6225881234567890",
        "name": "张三",
        "address": "北京市朝阳区建国路88号",
        "amount": 50000
    }

    masked = MaskingUtil.mask_sensitive_info(test_data)
    print(f"  手机: {test_data['phone']} -> {masked['phone']}")
    print(f"  身份证: {test_data['id_card']} -> {masked['id_card']}")
    print(f"  银行卡: {test_data['bank_card']} -> {masked['bank_card']}")
    print(f"  姓名: {test_data['name']} -> {masked['name']}")

    print("\n【步骤8】报告生成")
    print("-" * 40)

    case_data = {
        "case": {
            "case_no": "TEST001",
            "suspect_name": "测试嫌疑人",
            "brand": "博世",
            "amount": 50000
        },
        "statistics": {
            "transaction_count": len(transactions),
            "communication_count": len(communications),
            "logistics_count": len(logistics),
            "person_count": len(extract_result['persons']),
            "suspicious_clue_count": len(suspicious_clues)
        },
        "suspicious_clues": suspicious_clues[:5]
    }

    chain_analysis = {
        "upstream": extract_result['persons'][:2],
        "downstream": [],
        "core_suspects": [],
        "role_analysis": {}
    }

    evidence_inventory = {
        "communication_evidence_count": len(suspicious_clues),
        "price_anomaly_evidence_count": 0,
        "logistics_evidence_count": len(extract_result['hidden_sources'])
    }

    report_path = ReportGenerator.generate_simple_report(
        case_no="TEST001",
        suspect_name="测试嫌疑人",
        brand="博世",
        amount=50000,
        clue_count=len(suspicious_clues),
        evidence_count=len(communications)
    )
    print(f"  报告生成: {report_path}")

    print("\n【步骤9】数据导出")
    print("-" * 40)

    csv_path = Exporter.export_transactions(clean_transactions, format='csv', filename='test_transactions_export')
    print(f"  CSV导出: {csv_path}")

    print("\n" + "=" * 60)
    print("集成测试完成!")
    print("=" * 60)


def test_keyword_score_flow():
    """测试敏感词→评分→罪名流程"""
    print("\n" + "=" * 60)
    print("敏感词 → 评分 → 罪名推断 流程测试")
    print("=" * 60)

    test_texts = [
        "这批高仿博世大灯一定要贴好标，老规矩别声张",
        "原厂品质，价格优惠，正品保证",
        "批发零售，拿货出货，利润丰厚",
    ]

    for text in test_texts:
        print(f"\n文本: {text}")

        # 1. 敏感词检测
        matches = ScoreService.search_keywords(text)
        print(f"  命中关键词: {[m['word'] for m in matches]}")

        # 2. 评分
        result = ScoreService.analyze_text(text)
        print(f"  评分: {result['score']}分 ({result['level']})")

        # 3. 罪名推断
        crime = ScoreService.get_crime_type(matches)
        print(f"  涉嫌罪名: {crime}")


if __name__ == "__main__":
    test_full_pipeline()
    test_keyword_score_flow()
    print("\n所有集成测试完成!")