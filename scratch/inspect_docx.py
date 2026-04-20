import docx
import os

files = [
    r'd:\backEnd\demo_test\data\10个案例模拟数据\模拟数据_指导案例特征线索.docx',
    r'd:\backEnd\demo_test\data\10个案例模拟数据\模拟数据_案例.docx',
    r'd:\backEnd\demo_test\data\10个案例模拟数据\模拟数据_聊天记录.docx'
]

for file_path in files:
    if os.path.exists(file_path):
        print(f"--- File: {os.path.basename(file_path)} ---")
        doc = docx.Document(file_path)
        for i, para in enumerate(doc.paragraphs[:20]): # 只看前20段
            print(f"{i}: {para.text}")
    else:
        print(f"文件不存在: {file_path}")
