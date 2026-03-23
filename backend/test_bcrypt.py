# 应用bcrypt补丁
import bcrypt as _bcrypt
if not hasattr(_bcrypt, '__about__'):
    class _About:
        __version__ = getattr(_bcrypt, '__version__', '4.0.0')
    _bcrypt.__about__ = _About()

from passlib.context import CryptContext

# 创建密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 测试密码验证
password = "123456"
hashed_password = "$2b$12$cnugdhzPegJ33Ra5fabRfuUYPn.6OAZ9kar5wH9pnr5eKhtiTreOq"

print(f"测试密码: {password}")
print(f"密码长度: {len(password)} 字节")
print(f"哈希值: {hashed_password}")

# 验证密码
try:
    is_valid = pwd_context.verify(password, hashed_password)
    print(f"密码验证结果: {'通过' if is_valid else '失败'}")
    
    # 生成新的哈希值进行对比
    new_hash = pwd_context.hash(password)
    print(f"新生成的哈希值: {new_hash}")
    print(f"哈希值是否相同: {hashed_password == new_hash}")
    
except Exception as e:
    print(f"验证失败: {e}")