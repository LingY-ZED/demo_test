import pandas as pd
import os

file_path = r'd:\backEnd\demo_test\data\10个案例模拟数据\模拟数据-表格.xlsx'
if os.path.exists(file_path):
    # 读取所有 sheet
    xl = pd.ExcelFile(file_path)
    for sheet_name in xl.sheet_names:
        print(f"--- Sheet: {sheet_name} ---")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print(df.head(10))
else:
    print("文件不存在")
