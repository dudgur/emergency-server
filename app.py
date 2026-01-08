# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, render_template_string, Response, send_file, jsonify
import os
from datetime import datetime
import time

app = Flask(__name__)

devices = {}
history = []
clients = []
device_commands = {}  # 👈 기기에 내릴 명령 저장

REASONS = [
    "마트에서 이동 도움",
    "상품 선택 도움",
    "결제 도움",
    "기타"
]

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def elapsed_time_str(start_time, end_time=None):
    if end_time is None:
        delta = datetime.now() - start_time
    else:
        delta = end_time - start_time
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}초"
    elif s < 3600:
        return f"{s//60}분 {s%60}초"
    else:
        return f"{s//3600}시간 {(s%3600)//60}분"

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>긴급 요청 모니터</title>
<meta http-equiv="refresh" content="10">
<style>
body { font-family: sans-serif; background:#f4f6f8; padding:16px; }
.card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.1); }
.btn { display:inline-block; padding:8px 12px; border-radius:6px; color:white; text-decoration:none; margin-right:6px; }
.move { background:#f57c00; }
.clear { background:#d32f2f; }
.view { background:#1976d2; }
</style>
</head>
<body>

<h1>긴급 요청 모니터</h1>

{% for id, d in devices.items() %}
<div class="card">
<b>{{ id }}</b> ({{ d.status }})<br>
요청 시간: {{ d.time_str }}<br>
경과 시간: {{ d.elapsed }}<br><br>

<a class="btn view" href="/device/{{ id }}">화면 보기</a>
<a class="btn move" href="/move/{{ id }}">직원 이동</a>

<form action="/clear/{{ id }}" method="post" style="display:inline;">
<select name="reason">
{% for r in reasons %}
<option value="{{ r }}">{{ r }}</option>
{% endfor %}
</select>
<input class="btn clear" type="submit" value="종료">
</form>
</div>
{% else %}
<p>현재 요청 없음</p>
{% endfor %}

<hr>
<h2>요청 기록</h2>
{% for h in history %}
<div class="card">
<b>{{ h.device_id }}</b><br>
{{ h.start_time }} → {{ h.end_time }}<br>
소요: {{ h.duration }}<br>
사유: {{ h.reason }}
</div>
{% endfor %}

</body>
</html>
""",
devices={k: {
    **v,
    "elapsed": elapsed_time_str(v["time"]),
    "time_str": v["time"].strftime("%Y-%m-%d %H:%M:%S")
} for k,v in devices.items()},
history=history,
reasons=REASONS
)

@app.route("/device/<device_id>")
def view_device(device_id):
    return f"""
<html>
<body style="background:black;color:white;text-align:center">
<h2>{device_id}</h2>
<img id="cam" src="/image/{device_id}" width="720">
<script>
setInterval(function(){{
  document.getElementById("cam").src="/image/{device_id}?t="+new Date().getTime();
}},300);
</script>
</body>
</html>
"""

@app.route("/upload", methods=["POST"])
def upload():
    device_id = request.form.get("device_id")
    file = request.files.get("image")
    if not device_id or not file:
        return "Bad Request", 400
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    file.save(path)
    return "OK"

@app.route("/image/<device_id>")
def get_image(device_id):
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    if not os.path.exists(path):
        return "No Image", 404
    return send_file(path, mimetype="image/jpeg")

@app.route("/emergency", methods=["POST"])
def emergency():
    data = request.get_json()
    device_id = str(data.get("device_id"))

    devices[device_id] = {
        "status": "NEW",
        "time": datetime.now()
    }
    device_commands[device_id] = "NONE"
    return "OK"

# 🔥 기기가 명령 물어보는 API
@app.route("/command/<device_id>")
def get_command(device_id):
    cmd = device_commands.get(device_id, "NONE")
    device_commands[device_id] = "NONE"  # 읽으면 초기화
    return jsonify({"command": cmd})

@app.route("/move/<device_id>")
def move_staff(device_id):
    if device_id in devices:
        devices[device_id]["status"] = "MOVING"
        device_commands[device_id] = "MOVE"   # 👈 기기로 보낼 명령
    return redirect("/")

@app.route("/clear/<device_id>", methods=["POST"])
def clear(device_id):
    d = devices.get(device_id)
    if d:
        reason = request.form.get("reason")
        end_time = datetime.now()

        history.insert(0,{
            "device_id": device_id,
            "start_time": d["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": elapsed_time_str(d["time"], end_time),
            "reason": reason
        })

        device_commands[device_id] = "STOP"  # 👈 기기로 종료 명령
        devices.pop(device_id, None)

    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
