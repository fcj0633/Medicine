import pymysql

# 数据库连接信息
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = '274226'
DB_NAME = 'medication_reminder'

# 连接数据库
conn = pymysql.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    db=DB_NAME,
    charset='utf8mb4'
)
cursor = conn.cursor()

# 查询用户数据
print("查询用户数据...")
cursor.execute("SELECT id, username, hashed_password, display_name, role FROM users")
users = cursor.fetchall()

print("\n用户列表:")
print("-" * 80)
print(f"{'ID':<5} {'用户名':<10} {'显示姓名':<10} {'角色':<10} {'密码哈希':<60}")
print("-" * 80)

for user in users:
    user_id, username, hashed_password, display_name, role = user
    print(f"{user_id:<5} {username:<10} {display_name:<10} {role:<10} {hashed_password[:60]}...")

# 关闭连接
cursor.close()
conn.close()

print("\n查询完成！")