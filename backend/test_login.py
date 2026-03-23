import requests
import json

# 后端API地址
API_URL = 'http://localhost:8000/api/auth/login'

# 测试账号
test_accounts = [
    {'username': 'laowang', 'password': '123456', 'name': '王大爷'},
    {'username': 'laozhang', 'password': '123456', 'name': '张奶奶'},
    {'username': 'xiaoming', 'password': '123456', 'name': '小明'}
]

print("测试登录API...")
print("-" * 60)

for account in test_accounts:
    print(f"测试账号: {account['name']} ({account['username']})")
    print(f"密码: {account['password']}")
    
    try:
        # 发送登录请求
        response = requests.post(
            API_URL,
            json={'username': account['username'], 'password': account['password']},
            headers={'Content-Type': 'application/json'}
        )
        
        # 打印响应
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ 登录成功！")
        else:
            print("❌ 登录失败！")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print("-" * 60)