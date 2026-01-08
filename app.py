# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, render_template_string, Response, send_file
import os
from datetime import datetime
import time
import json

app = Flask(__name__)

DATA_FILE = "data.json"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------
# 데이터 로드 / 저장
# ---------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devices": {}, "history": []}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"devices": devices, "history": history}, f, ensure_ascii=False, indent=2)

data = load_data()
devices = data.get("devices", {})
history = data.get("history", [])

clients = []

REASONS = [
    "마트에서 이동 도움",
    "상품 선택 도움",
    "결제 도움",
    "기타"
]

# ---------------------------
def elapsed_time_str(start_time, end_time=None):
    start_time = datetime.fromisoformat(start_time)
    if end_time is None:
        delta = datetime.now() - start_time
    else:
        delta = datetime.fromisoformat(end_time) - start_time

    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}초"
    elif s < 3600:
        return f"{s//60}분 {s%60}초"
    else:
        return f"{s//3600}시간 {(s%3600)//60}분"

# ---------------------------
@app.route("/events")
def sse():
    def gen():
        q = []
        clients.append(q)
        try:
            while True:
                if q:
                    msg = q.pop(0)
                    yield f"data: {msg}\n\n"
                else:
                    time.sleep(0.5)
        except GeneratorExit:
            clients.remove(q)
    return Response(gen(), mimetype="text/event-stream")

# ---------------------------
@app.route("/")
def index():
    view_devices = {}
    for k, v in devices.items():
        view_devices[k] = {
            **v,
            "elapsed": elapsed_time_str(v["time"]),
            "time_str": datetime.fromisoformat(v["time"]).strftime("%Y-%m-%d %H:%M:%S")
        }

    return render_template_string(""" 
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>긴급 요청 모니터</title>
<meta http-equiv="refresh" content="15">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: sans-serif; background:#f4f6f8; margin:0; padding:16px; }
h1 { margin-bottom: 10px; }
.card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.1); position:relative; }
.badge-new { color:white; background:#d32f2f; padding:4px 10px; border-radius:12px; }
.badge-move { color:white; background:#f57c00; padding:4px 10px; border-radius:12px; }
.btn { display:inline-block; padding:8px 12px; border-radius:6px; color:white; text-decoration:none; margin-right:6px; }
.view { background:#1976d2; }
.move { background:#f57c00; }
.clear { background:#d32f2f; }
.history { background:#eceff1; padding:10px; margin-bottom:10px; border-radius:10px; position:relative; }
.history .delete, .history .edit-btn { position:absolute; right:10px; top:10px; background:#d32f2f; color:white; border:none; padding:3px 6px; border-radius:4px; cursor:pointer; margin-left:4px;}
.history .edit-btn { background:#1976d2; right:60px; }
</style>
</head>
<body>

<h1>긴급 요청 모니터</h1>

{% for id, d in devices.items() %}
<div class="card">
<b>{{ id }}</b>
<span class="{{ 'badge-new' if d.status=='NEW' else 'badge-move' }}">{{ d.status }}</span><br>
요청 시간: {{ d.time_str }}<br>
경과 시간: {{ d.elapsed }}<br><br>

<a class="btn view" href="/device/{{ id }}">화면 보기</a>
<a class="btn move" href="/move/{{ id }}">직원 이동</a>
</div>
{% else %}
<p>현재 요청이 없습니다.</p>
{% endfor %}

<hr>
<h1>요청 기록</h1>

{% for h in history %}
<div class="history">
<b>{{ h.device_id }}</b><br>
시작 시간: {{ h.start_time }}<br>
종료 시간: {{ h.end_time }}<br>
소요 시간: {{ h.duration }}<br>
사유: {{ h.reason }}
</div>
{% else %}
<p>요청 기록이 없습니다.</p>
{% endfor %}

</body>
</html>
""", devices=view_devices, history=history)

# ---------------------------
@app.route("/device/<device_id>")
def view_device(device_id):
    return f"""
<html>
<body style="background:black;color:white;text-align:center">
<h2>{device_id} 요청 화면</h2>
<img id="cam" src="/image/{device_id}" width="720"><br>
<script>
setInterval(function(){{
 document.getElementById("cam").src="/image/{device_id}?t="+new Date().getTime();
}}, 200);
</script>
</body>
</html>
"""

# ---------------------------
@app.route("/upload", methods=["POST"])
def upload():
    device_id = request.form.get("device_id")
    file = request.files.get("image")
    if not device_id or not file:
        return "Bad Request", 400
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    file.save(path)
    return "OK", 200

# ---------------------------
@app.route("/image/<device_id>")
def get_image(device_id):
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    if not os.path.exists(path):
        return "No Image", 404
    return send_file(path, mimetype="image/jpeg")

# ---------------------------
@app.route("/emergency", methods=["POST"])
def emergency():
    data = request.get_json(silent=True)
    if not data:
        return "Invalid JSON", 400

    device_id = str(data.get("device_id"))

    devices[device_id] = {
        "status": "NEW",
        "time": datetime.now().isoformat()
    }

    save_data()

    for q in clients:
        q.append(f"NEW_DEVICE:{device_id}")

    return "OK", 200

# ---------------------------
@app.route("/move/<device_id>")
def move_staff(device_id):
    if device_id in devices:
        devices[device_id]["status"] = "MOVING"
        save_data()
    return redirect("/")

# ---------------------------
@app.route("/clear/<device_id>", methods=["POST"])
def clear(device_id):
    d = devices.get(device_id)
    if d:
        reason = request.form.get("reason", "기타")

        end_time = datetime.now().isoformat()

        history.insert(0,{
            "device_id": device_id,
            "start_time": d["time"],
            "end_time": end_time,
            "duration": elapsed_time_str(d["time"], end_time),
            "reason": reason
        })

        devices.pop(device_id, None)
        save_data()

    return redirect("/")

# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
