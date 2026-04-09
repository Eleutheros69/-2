from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
import random
import re
from datetime import datetime, timedelta

app = Flask(__name__)

# --------------------------
# 配置区
# --------------------------
EMAIL_HOST = 'smtp.163.com'
EMAIL_PORT = 465
EMAIL_USER = 'woucxzae@163.com'  # 您的发件邮箱
EMAIL_PASS = 'RSR6ngt4VsN8wf7k'  # 您的授权码
ADMIN_NOTIFY_EMAIL = 'woucxzae@163.com'  # 您要接收通知的邮箱（可以和上面一样）

# --------------------------
# 全局存储区
# --------------------------
code_cache = {}          # {email: {'code': '1234', 'expire_time': datetime}}
request_limit = {}       # {ip: {'count': int, 'reset_time': datetime}}
risk_devices = {}        # {ip: {'risk_score': int, 'last_seen': datetime}}

# --------------------------
# 安全工具函数
# --------------------------
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$'
    return re.fullmatch(pattern, email) is not None

def sanitize_input(s):
    if not s:
        return ""
    s = re.sub(r'[\'";\\]', '', s)
    s = re.sub(r'<script.*?>', '', s, flags=re.IGNORECASE)
    return s.strip()

def detect_risk_device(client_ip):
    now = datetime.now()
    user_agent = request.headers.get('User-Agent', '').lower()
    if client_ip not in risk_devices:
        risk_devices[client_ip] = {'risk_score': 0, 'last_seen': now, 'request_count': 0}
    device = risk_devices[client_ip]
    device['request_count'] += 1
    if (now - device['last_seen']).total_seconds() < 10:
        device['risk_score'] += 2
    if device['request_count'] > 20:
        device['risk_score'] += 3
    if any(kw in user_agent for kw in ['scrapy', 'curl', 'wget', 'bot', 'spider', 'proxy']):
        device['risk_score'] += 4
    if (now - device['last_seen']).total_seconds() > 3600:
        device['risk_score'] = max(0, device['risk_score'] - 2)
    device['last_seen'] = now
    return device['risk_score']

def check_request_limit(client_ip):
    now = datetime.now()
    if client_ip not in request_limit:
        request_limit[client_ip] = {'count': 1, 'reset_time': now + timedelta(hours=1)}
        return True
    data = request_limit[client_ip]
    if now > data['reset_time']:
        data['count'] = 1
        data['reset_time'] = now + timedelta(hours=1)
        return True
    if data['count'] < 10:
        data['count'] += 1
        return True
    return False

def is_code_valid(email, input_code):
    if email not in code_cache:
        return False
    data = code_cache[email]
    if datetime.now() > data['expire_time']:
        del code_cache[email]
        return False
    return data['code'] == input_code

# --------------------------
# 邮件发送功能
# --------------------------
def send_email(to_email, code):
    """给用户发验证码邮件"""
    try:
        content = f"""
【连这洗衣机书请工作室】邮箱认证

您的WiFi认证验证码是：{code}

--------------------------
温馨提示：
1. 此验证码仅用于本次WiFi认证，有效期5分钟
2. 请勿将验证码泄露给他人，谨防诈骗
3. 本网络仅限合法用途使用，严禁用于违法违规行为
4. 如您未进行此操作，请忽略本邮件
5. 违规使用网络所产生的一切后果由您自行承担

感谢您的使用！
连这洗衣机书请工作室
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

def send_admin_notify(user_email, client_ip, mac_addr="未知"):
    """给管理员发通知邮件（包含用户信息）"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"""
【WiFi认证系统通知】有用户申请验证码

申请时间：{now}
用户邮箱：{user_email}
客户端IP：{client_ip}
设备MAC：{mac_addr}
风险分数：{detect_risk_device(client_ip)}

请留意认证行为，如有异常请及时处理。
"""
        msg = MIMEText(content, "plain", "utf-8")
        msg['From'] = EMAIL_USER
        msg['To'] = ADMIN_NOTIFY_EMAIL
        msg['Subject'] = f"【WiFi认证通知】{user_email} 申请验证码"
        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, ADMIN_NOTIFY_EMAIL, msg.as_string())
        return True
    except Exception as e:
        print("发送管理员通知失败:", e)
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
    email = request.json.get('email', '')
    client_ip = request.remote_addr
    # 尝试获取MAC地址（局域网内有效）
    mac_addr = "未知"
    try:
        # 仅在局域网内有效，通过ARP表获取
        import os
        if os.name == 'nt':
            result = os.popen(f"arp -a {client_ip}").read()
            if client_ip in result:
                mac_addr = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', result).group()
        else:
            result = os.popen(f"arp -n {client_ip}").read()
            mac_addr = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', result).group()
    except:
        mac_addr = "未知"

    risk_score = detect_risk_device(client_ip)
    if risk_score > 5:
        return jsonify({"ok": False, "msg": "当前设备存在异常访问风险，暂时无法发送验证码"})
    if not email or not is_valid_email(email):
        return jsonify({"ok": False, "msg": "邮箱格式不正确，请检查后重试"})
    email = sanitize_input(email)
    if not check_request_limit(client_ip):
        return jsonify({"ok": False, "msg": "请求过于频繁，请1小时后再试"})

    code = str(random.randint(1000, 9999))
    expire_time = datetime.now() + timedelta(minutes=5)
    code_cache[email] = {'code': code, 'expire_time': expire_time}

    # 1. 给用户发验证码
    user_ok = send_email(email, code)
    # 2. 给管理员发通知（不管用户邮件是否成功，都通知管理员）
    send_admin_notify(email, client_ip, mac_addr)

    if user_ok:
        return jsonify({"ok": True, "msg": "验证码已发送，有效期5分钟"})
    else:
        return jsonify({"ok": False, "msg": "邮件发送失败，请稍后重试"})

@app.route('/api/wifi_login', methods=['POST'])
def api_wifi_login():
    data = request.json
    email = request.json.get('email', '')
    code = request.json.get('code', '')
    agree = data.get('agree', False)
    client_ip = request.remote_addr
    risk_score = detect_risk_device(client_ip)
    if risk_score > 7:
        return jsonify({"ok": False, "msg": "设备风险过高，无法完成认证"})
    if not email or not is_valid_email(email):
        return jsonify({"ok": False, "msg": "邮箱格式不正确"})
    email = sanitize_input(email)
    if not agree:
        return jsonify({"ok": False, "msg": "请同意上网协议与隐私政策"})
    if not code:
        return jsonify({"ok": False, "msg": "请输入验证码"})
    if not is_code_valid(email, code):
        return jsonify({"ok": False, "msg": "验证码无效或已过期，请重新获取"})
    return jsonify({
        "ok": True,
        "msg": "WiFi认证成功，已为您开通高速网络",
        "wifi": "测试档5G edmi",
        "risk_score": risk_score
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)