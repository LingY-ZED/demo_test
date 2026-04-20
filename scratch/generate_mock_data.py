import sys
import os
import random
from datetime import datetime, timedelta

# 将项目根目录添加到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import db, Case, Person, Transaction, Communication, Logistics, SuspiciousClue

BRANDS = ['奥迪', '大众', '博世', '奔驰', '宝马', '米其林', '福耀', '丰田', '本田', '别克']
SUSPECT_NAMES = ['张伟', '王芳', '李娜', '刘洋', '陈敏', '郑成', '陆建国', '钱明', '孙志平', '周勇']
ROLES = ['核心嫌疑人', '上游供应商', '下游买家', '财务人员', '仓储物流人员']
CONTENTS = [
    "这批货的标印得深一点，别像上次那样容易磨掉。",
    "老板，能不能多弄点这品牌的货？现在查得不严。",
    "只能开配件发票，不开品牌明细，别留把柄。",
    "对外一律说'正品原厂'，别提高仿、假冒的事。",
    "价格能不能再低点？我这走量大。",
    "这批货不是原厂的，你心里有数就行。",
    "货款走微信，别走对公。",
    "我们要大众和奥迪的款，这两款好卖。",
    "上次那批货质量不行，客户投诉了。",
    "一定要保密，现在的监管力度很大。"
]
METHODS = ['银行转账', '对公转账', '微信', '支付宝', '现金']
REMARKS = ['货款', '进货款', '二级代理进货', '品牌授权费', '物流费', '配件采购']

def generate_data(num_cases=10):
    try:
        db.connect()
        print(f"开始生成 {num_cases} 个案例的模拟数据...")
        
        for i in range(1, num_cases + 1):
            # 1. 创建案件
            case_no = f'A2024{str(i).zfill(3)}'
            suspect = random.choice(SUSPECT_NAMES)
            brand = random.choice(BRANDS)
            amount = random.randint(100000, 1000000)
            created_at = datetime.now() - timedelta(days=random.randint(0, 30))
            
            case = Case.create(
                case_no=case_no,
                suspect_name=suspect,
                brand=brand,
                amount=amount,
                created_at=created_at
            )
            print(f"创建案件: {case_no}")
            
            # 2. 创建人员
            # 核心嫌疑人
            Person.create(
                name=suspect,
                role='核心嫌疑人',
                is_authorized=False,
                subjective_knowledge_score=random.randint(5, 10),
                illegal_business_amount=amount,
                linked_cases=random.randint(1, 3)
            )
            
            # 供应商和买家
            supplier = f"上游供应商_{random.choice(['赵', '钱', '孙', '李'])}{random.randint(1, 99)}"
            Person.create(
                name=supplier,
                role='上游供应商',
                is_authorized=False,
                subjective_knowledge_score=random.randint(1, 5),
                illegal_business_amount=amount * 0.8,
                linked_cases=1
            )
            
            buyer = f"下游买家_{random.choice(['周', '吴', '郑', '王'])}{random.randint(1, 99)}"
            Person.create(
                name=buyer,
                role='下游买家',
                is_authorized=None,
                illegal_business_amount=amount * 0.3,
                linked_cases=1
            )
            
            # 3. 创建交易记录
            for _ in range(random.randint(3, 8)):
                Transaction.create(
                    case=case,
                    transaction_time=created_at + timedelta(hours=random.randint(1, 100)),
                    payer=random.choice([suspect, buyer]),
                    payee=random.choice([suspect, supplier]),
                    amount=random.randint(5000, 50000),
                    payment_method=random.choice(METHODS),
                    remark=f"{random.choice(REMARKS)}-{brand}"
                )
            
            # 4. 创建通讯记录
            for _ in range(random.randint(5, 12)):
                content = random.choice(CONTENTS)
                Communication.create(
                    case=case,
                    communication_time=created_at + timedelta(hours=random.randint(1, 100)),
                    initiator=random.choice([suspect, buyer, supplier]),
                    receiver=random.choice([suspect, buyer, supplier]),
                    content=content
                )
                
                # 如果包含敏感内容，生成可疑线索
                if any(word in content for word in ['假冒', '仿冒', '把柄', '原厂', '保密', '不走对公']):
                    SuspiciousClue.create(
                        case=case,
                        clue_type='聊天言论',
                        evidence_text=content,
                        hit_keywords='敏感词',
                        score=random.randint(1, 5),
                        crime_type='销售假冒注册商标商品罪',
                        severity_level='中度可疑'
                    )
            
            # 5. 创建物流记录
            Logistics.create(
                case=case,
                shipping_time=created_at + timedelta(days=random.randint(1, 5)),
                tracking_no=f'SF{random.randint(1000000000, 9999999999)}',
                sender=supplier,
                sender_address="某汽配工业园",
                receiver=suspect,
                receiver_address="某市汽配城",
                description=f"{brand}汽车配件"
            )

        print("数据生成完成！")
    except Exception as e:
        print(f"生成数据时出错: {e}")
    finally:
        if not db.is_closed():
            db.close()

if __name__ == "__main__":
    generate_data(10)
