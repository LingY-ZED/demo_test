import sqlite3
from datetime import datetime

DB_PATH = 'd:/backEnd/demo_test/data/intellectual_property.db'

def add_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 创建新案件 A2024006
    case_no = 'A2024006'
    suspect_name = '郑成'
    brand = 'Continental'
    amount = 520000
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    
    cursor.execute("INSERT INTO cases (case_no, suspect_name, brand, amount, created_at) VALUES (?, ?, ?, ?, ?)",
                   (case_no, suspect_name, brand, amount, created_at))
    case_id = cursor.lastrowid
    print(f"创建案件 {case_no}, ID: {case_id}")

    # 2. 添加交易流水，制造“跨案关联”
    # 关联到 Case 1 的上游：上游供应商_钱明
    cursor.execute("INSERT INTO transactions (case_id, transaction_time, payer, payee, amount, payment_method, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 10:00:00', '郑成', '上游供应商_钱明', 85000, '银行转账', '货款-Continental轮胎'))
    
    # 关联到 Case 2 的上游：上游供应商_郑宇
    cursor.execute("INSERT INTO transactions (case_id, transaction_time, payer, payee, amount, payment_method, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 11:30:00', '郑成', '上游供应商_郑宇', 120000, '对公转账', 'Continental品牌授权使用费'))
    
    # 关联到 Case 1 的下游：下游买家_孙敏
    cursor.execute("INSERT INTO transactions (case_id, transaction_time, payer, payee, amount, payment_method, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 14:20:00', '下游买家_孙敏', '郑成', 45000, '微信', '二级代理进货款'))

    # 3. 添加通讯记录
    cursor.execute("INSERT INTO communications (case_id, communication_time, initiator, receiver, content) VALUES (?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 09:15:00', '郑成', '上游供应商_钱明', '老钱，这次Continental那批货标印得深一点，别像上次那样容易磨掉了。'))
    
    cursor.execute("INSERT INTO communications (case_id, communication_time, initiator, receiver, content) VALUES (?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 13:00:00', '下游买家_孙敏', '郑成', '郑老板，能不能多弄点Continental的货？现在这个品牌查得没那么严。'))

    # 4. 添加物流记录
    cursor.execute("INSERT INTO logistics (case_id, shipping_time, tracking_no, sender, sender_address, receiver, receiver_address, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (case_id, '2026-04-18 16:00:00', 'SF9988776655', '上游供应商_钱明', '广州市白云区某工业园', '郑成', '杭州市萧山区汽配城', 'Continental汽车轮胎组件'))

    conn.commit()
    conn.close()
    print("跨案关联测试数据插入成功！")

if __name__ == "__main__":
    add_data()
