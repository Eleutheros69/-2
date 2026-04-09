from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
import random
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# --------------------------
# 配置区（您的邮箱信息）
# --------------------------
EMAIL_HOST = 'smtp.163.com'
EMAIL_PORT = 465
EMAIL_USER = 'woucxzae@163.com'
EMAIL_PASS = 'RSR6ngt4VsN8wf7k'

# --------------------------
# 全局存储区
# --------------------------
code_cache = {}          # 存验证码 {email: {'code': '1234', 'expire_time': 时间戳}}
request_limit = {}       # 存发邮件频率限制 {ip: {'count': 10, 'reset_time': 时间戳}}

# --------------------------
# 工具函数
# --------------------------
def gen_code():
    """生成4位随机验证码"""
    return str(random.randint(1000, 9999))

def is_code_valid(email, input_code):
    """检查验证码是否有效（5分钟有效期）"""
    if email not in code_cache:
        return False
    data = code_cache[email]
    # 检查是否过期
    if datetime.now() > data['expire_time']:
        del code_cache[email]  # 过期直接删除
        return False
    # 检查验证码是否正确
    return data['code'] == input_code

def check_request_limit(client_ip):
    """
    检查发邮件频率限制
    规则：同一IP 1小时内最多请求10次
    """
    now = datetime.now()
    if client_ip not in request_limit:
        # 首次请求：初始化计数和过期时间（1小时后重置）
        request_limit[client_ip] = {
            'count': 1,
            'reset_time': now + timedelta(hours=1)
        }
        return True
    
    data = request_limit[client_ip]
    # 如果时间已过，重置计数
    if now > data['reset_time']:
        data['count'] = 1
        data['reset_time'] = now + timedelta(hours=1)
        return True
    
    # 如果未超过限制
    if data['count'] < 10:
        data['count'] += 1
        return True
    
    # 超过限制
    return False

# --------------------------
# 邮件发送功能（已美化）
# --------------------------
def send_email(to_email, code):
    try:
        content = f"""
【淑情工作室】邮箱认证

您的WiFi认证验证码是：{code}

--------------------------
温馨提示：
1. 此验证码仅用于本次WiFi认证，有效期5分钟
2. 请勿将验证码泄露给他人，谨防诈骗
3. 本网络仅限合法用途使用，严禁用于违法违规行为
4. 如您未进行此操作，请忽略本邮件
5. 违规使用网络所产生的一切后果由您自行承担

感谢您的使用！
"""
        msg = MIMEText(content, "plain", "utf-8")
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = "【WiFi认证】您的验证码"

        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print("发邮件失败:", e)
        return False

# --------------------------
# API 接口
# --------------------------
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/success.html')
def success():
    return app.send_static_file('success.html')

@app.route('/api/send_email_code', methods=['POST'])
def api_send_email_code():
    email = request.json.get('email')
    client_ip = request.remote_addr  # 获取客户端IP（用于频率限制）

    # 1. 基础格式检查
    if not email or '@' not in email:
        return jsonify({"ok": False, "msg": "邮箱格式不正确"})

    # 2. 频率限制检查（1小时10次）
    if not check_request_limit(client_ip):
        return jsonify({"ok": False, "msg": "请求过于频繁，请1小时后再试"})

    # 3. 生成验证码并设置5分钟有效期
    code = gen_code()
    expire_time = datetime.now() + timedelta(minutes=5)
    
    # 4. 存储验证码
    code_cache[email] = {
        'code': code,
        'expire_time': expire_time
    }

    # 5. 发送邮件
    if send_email(email, code):
        return jsonify({"ok": True, "msg": "验证码已发送到您的邮箱，有效期5分钟"})
    else:
        return jsonify({"ok": False, "msg": "发送失败，请检查邮箱配置"})

@app.route('/api/wifi_login', methods=['POST'])
def api_wifi_login():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    agree = data.get('agree', False)

    # 1. 协议检查
    if not agree:
        return jsonify({"ok": False, "msg": "请同意上网协议"})

    # 2. 验证码有效性检查（含过期检查）
    if not is_code_valid(email, code):
        return jsonify({"ok": False, "msg": "验证码无效或已过期，请重新获取"})

    # 3. 认证成功
    # 这里可以后续对接AC网关放行MAC地址
    return jsonify({
        "ok": True,
        "msg": "WiFi认证成功，已为您开通网络权限",
        "wifi": "测试档5G edmi"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)