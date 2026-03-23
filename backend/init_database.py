import pymysql
import os

# 数据库连接信息
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = '274226'
DB_NAME = 'medication_reminder'

# 读取SQL脚本
sql_file = os.path.join(os.path.dirname(__file__), '..', 'database', 'init.sql')
with open(sql_file, 'r', encoding='utf-8') as f:
    sql_commands = f.read()

# 连接到MySQL服务器
print("正在连接到MySQL服务器...")
conn = pymysql.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    charset='utf8mb4'
)
cursor = conn.cursor()

# 执行SQL脚本
print("正在执行数据库初始化脚本...")
try:
    # 分割SQL命令并执行
    commands = sql_commands.split(';')
    for command in commands:
        command = command.strip()
        if command:
            cursor.execute(command)
    conn.commit()
    print("数据库初始化成功！")
    print("\n演示账号：")
    print("- 老人端：laowang / 123456（王大爷）")
    print("- 老人端：laozhang / 123456（张奶奶）")
    print("- 家属端：xiaoming / 123456（小明）")
except Exception as e:
    print(f"数据库初始化失败：{e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()