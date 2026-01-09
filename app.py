# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, render_template_string, Response, send_file, jsonify
import os
from datetime import datetime
import time

app = Flask(__name__)

devices = {}
history = []
clients = []
device_commands = {}

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
    if s < 60: return f"{s}초"
    elif s < 3600: return f"{s//60}분 {s%60}초"
    else: return f"{s//3600}시간 {(s%3600)//60}분"

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
                    time.sleep(1)
        except GeneratorExit:
            if q in clients: clients.remove(q)
    return Response(gen(), mimetype="text/event-stream")

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>긴급 요청 모니터</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; background:#f4f6f8; margin:0; padding:16px; }
        .card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.1); }
        .badge { color:white; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:bold; }
        .badge-new { background:#d32f2f; }
        .badge-move { background:#f57c00; }
        .btn { display:inline-block; padding:10px 16px; border-radius:6px; color:white; text-decoration:none; border:none; cursor:pointer; font-weight:bold; }
        .view { background:#1976d2; }
        .move { background:#f57c00; }
        .clear { background:#d32f2f; }
        .history { background:#eceff1; padding:12px; margin-bottom:8px; border-radius:8px; position:relative; font-size:14px; }
        .btn-group { display: flex; gap: 8px; margin-top: 15px; }
    </style>
    <script>
        if (!!window.EventSource) {
            var source = new EventSource("/events");
            source.onmessage = function(e) { location.reload(); };
        }
        function toggleReason(id) {
            var el = document.getElementById('form-'+id);
            el.style.display = (el.style.display==='none') ? 'block' : 'none';
        }
    </script>
</head>
<body>
    <h1>🚨 실시간 요청</h1>
    {% for id, d in devices.items() %}
    <div class="card">
        <b>ID: {{ id }}</b> 
        <span class="badge {{ 'badge-new' if d.status=='NEW' else 'badge-move' }}">{{ d.status }}</span><br>
        <small>요청: {{ d.time_str }} | 경과: {{ d.elapsed }}</small>
        <div class="btn-group">
            <a class="btn view" href="/device/{{ id }}">화면</a>
            <a class="btn move" href="/move/{{ id }}">이동</a>
            <button class="btn clear" onclick="toggleReason('{{ id }}')">종료</button>
        </div>
        <div id="form-{{ id }}" style="display:none; margin-top:10px; border-top:1px solid #eee; padding-top:10px;">
            <form action="/clear/{{ id }}" method="post">
                <select name="reason" style="padding:8px; width:60%;">
                    {% for r in reasons %}<option value="{{ r }}">{{ r }}</option>{% endfor %}
                </select>
                <input type="submit" value="확인" class="btn clear">
            </form>
        </div>
    </div>
    {% else %}<p>대기 중인 요청이 없습니다.</p>{% endfor %}
    <hr>
    <h3>최근 기록</h3>
    {% for h in history %}
    <div class="history">
        <b>{{ h.device_id }}</b> | {{ h.reason }}<br>
        <small>{{ h.duration }} 소요 ({{ h.start_time }} 종료)</small>
    </div>
    {% endfor %}
</body>
</html>
""", devices={k: {**v, "elapsed": elapsed_time_str(v["time"]), "time_str": v["time"].strftime("%H:%M:%S")} for k,v in devices.items()}, history=history[:10], reasons=REASONS, enumerate=enumerate)

@app.route("/device/<device_id>")
def view_device(device_id):
    return f"""<html><body style="background:#000;color:#fff;text-align:center;">
    <h3>{device_id}</h3><img id="cam" src="/image/{device_id}" style="width:100%;max-width:600px;">
    <script>setInterval(()=>{{document.getElementById("cam").src="/image/{device_id}?t="+Date.now();}}, 500);</script>
    <br><br><a href="/" style="color:#fff;">[ 돌아가기 ]</a></body></html>"""

@app.route("/upload", methods=["POST"])
def upload():
    device_id = request.form.get("device_id")
    file = request.files.get("image")
    if device_id and file:
        file.save(os.path.join(UPLOAD_DIR, f"{device_id}.jpg"))
        return "OK", 200
    return "Fail", 400

@app.route("/image/<device_id>")
def get_image(device_id):
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    return send_file(path, mimetype="image/jpeg") if os.path.exists(path) else ("No Image", 404)

@app.route("/emergency", methods=["POST"])
def emergency():
    data = request.get_json(silent=True)
    if not data: return "Fail", 400
    did = str(data.get("device_id"))
    devices[did] = {"status": "NEW", "time": datetime.now()}
    device_commands[did] = "NONE"
    for q in clients: q.append("NEW")
    return "OK", 200

@app.route("/command/<device_id>")
def get_command(device_id):
    cmd = device_commands.get(device_id, "NONE")
    if cmd != "NONE": device_commands[device_id] = "NONE" # 1회 전송 후 초기화
    return jsonify({"command": cmd})

@app.route("/move/<device_id>")
def move_staff(device_id):
    if device_id in devices:
        devices[device_id]["status"] = "MOVING"
        device_commands[device_id] = "MOVE"
        for q in clients: q.append("UPDATE")
    return redirect("/")

@app.route("/clear/<device_id>", methods=["POST"])
def clear(device_id):
    d = devices.pop(device_id, None)
    if d:
        reason = request.form.get("reason", "기타")
        history.insert(0, {"device_id": device_id, "start_time": datetime.now().strftime("%H:%M:%S"), "duration": elapsed_time_str(d["time"]), "reason": reason})
        device_commands[device_id] = "STOP"
        for q in clients: q.append("CLEAR")
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))















