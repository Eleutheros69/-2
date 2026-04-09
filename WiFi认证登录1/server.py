from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
import random

app = Flask(__name__)

# 内存存验证码（不用数据库）
code_cache = {}

# --------------------------
# 你改成你自己的 163 邮箱
# --------------------------
EMAIL_HOST = 'smtp.163.com'
EMAIL_PORT = 465
EMAIL_USER = 'woucxzae@163.com'   # 例如：abc123@163.com
EMAIL_PASS = 'RSR6ngt4VsN8wf7k'        # 不是登录密码！是授权码！

# 生成4位验证码
def gen_code():
    return str(random.randint(1000, 9999))

# 发邮件
def send_email(to_email, code):
    try:
        msg = MIMEText(f"您的WiFi认证验证码：{code}", "plain", "utf-8")
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = "WiFi认证上网验证码"

        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print("发邮件失败:", e)
        return False

# 静态页面：认证页、成功页
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/success.html')
def success():
    return app.send_static_file('success.html')

# 获取邮箱验证码（真实发邮件）
@app.route('/api/send_email_code', methods=['POST'])
def api_send_email_code():
    email = request.json.get('email')
    if not email or '@' not in email:
        return jsonify({"ok": False, "msg": "邮箱格式不正确"})

    code = gen_code()
    if send_email(email, code):
        code_cache[email] = code
        return jsonify({"ok": True, "msg": "验证码已发送到您的邮箱"})
    else:
        return jsonify({"ok": False, "msg": "发送失败，请检查邮箱配置"})

# WiFi 认证登录（真正后端安全校验）
@app.route('/api/wifi_login', methods=['POST'])
def api_wifi_login():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    agree = data.get('agree', False)

    # 安全校验
    if not agree:
        return jsonify({"ok": False, "msg": "请同意上网协议"})
    if not email or email not in code_cache:
        return jsonify({"ok": False, "msg": "请先获取验证码"})
    if code_cache[email] != code:
        return jsonify({"ok": False, "msg": "验证码错误"})

    # --------------------------
    # 认证成功！这里以后对接网关
    # --------------------------
    return jsonify({
        "ok": True,
        "msg": "WiFi认证成功",
        "wifi": "测试档5G edmi"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)