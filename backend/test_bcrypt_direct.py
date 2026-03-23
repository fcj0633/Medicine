import bcrypt

# 测试密码验证
password = "123456"
hashed_password = "$2b$12$cnugdhzPegJ33Ra5fabRfuUYPn.6OAZ9kar5wH9pnr5eKhtiTreOq"

print(f"测试密码: {password}")
print(f"密码长度: {len(password)} 字节")
print(f"哈希值: {hashed_password}")

# 验证密码
try:
    # 处理bcrypt 72字节限制
    plain_password = password[:72].encode('utf-8')
    hashed_password = hashed_password.encode('utf-8')
    
    is_valid = bcrypt.checkpw(plain_password, hashed_password)
    print(f"密码验证结果: {'通过' if is_valid else '失败'}")
    
    # 生成新的哈希值进行对比
    new_hash = bcrypt.hashpw(plain_password, bcrypt.gensalt())
    print(f"新生成的哈希值: {new_hash.decode('utf-8')}")
    print(f"哈希值是否相同: {hashed_password == new_hash}")
    
except Exception as e:
    print(f"验证失败: {e}")