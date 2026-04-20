import sys
import os

# 将项目根目录添加到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import db, Case, Person, Transaction, Communication, Logistics, SuspiciousClue

def clear_all_data():
    try:
        db.connect()
        # 注意删除顺序，先删除子表（有外键依赖的），再删除父表
        # 或者直接使用 Peewee 的 truncate 或 delete
        
        print("正在清理模拟数据...")
        
        # 删除所有表的数据
        # 顺序：SuspiciousClue, Logistics, Communication, Transaction -> Case, Person
        SuspiciousClue.delete().execute()
        Logistics.delete().execute()
        Communication.delete().execute()
        Transaction.delete().execute()
        Case.delete().execute()
        Person.delete().execute()
        
        print("所有模拟数据已成功删除。")
    except Exception as e:
        print(f"清理数据时出错: {e}")
    finally:
        if not db.is_closed():
            db.close()

if __name__ == "__main__":
    clear_all_data()
