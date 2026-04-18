import sqlite3
conn = sqlite3.connect('d:/backEnd/demo_test/data/intellectual_property.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=" * 50)
print("数据库中的表及数据量")
print("=" * 50)

for t in tables:
    table_name = t[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name}: {count} 条记录")

print()
print("=" * 50)
print("详细数据预览")
print("=" * 50)

for t in tables:
    table_name = t[0]
    print(f"\n[{table_name}]")
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  {row}")
    else:
        print("  (空)")

conn.close()