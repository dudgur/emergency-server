# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, render_template_string, Response, send_file, jsonify
import os
from datetime import datetime
import time

app = Flask(__name__)

# 데이터 저장소
devices = {}
history = []
clients = []
device_commands = {}  # 기기에 내릴 명령 저장 (MOVE, STOP 등)

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

# ================== 실시간 알림 (SSE) ==================
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
            if q in clients:
                clients.remove(q)
    return Response(gen(), mimetype="text/event-stream")

# ================== 메인 관리 화면 ==================
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
h1 { margin-bottom: 10px; }
.card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.1); position:relative; }
.badge-new { color:white; background:#d32f2f; padding:4px 10px; border-radius:12px; font-size:0.8em; }
.badge-move { color:white; background:#f57c00; padding:4px 10px; border-radius:12px; font-size:0.8em; }
.btn { display:inline-block; padding:8px 12px; border-radius:6px; color:white; text-decoration:none; margin-right:6px; border:none; cursor:pointer; font-size:14px; }
.view { background:#1976d2; }
.move { background:#f57c00; }
.clear { background:#d32f2f; }
.history { background:#eceff1; padding:10px; margin-bottom:10px; border-radius:10px; position:relative; }
.history .delete { position:absolute; right:10px; top:10px; background:#d32f2f; color:white; border:none; padding:3px 6px; border-radius:4px; cursor:pointer; }
form { margin:0; display:inline; }
select, input[type=text] { margin-top:4px; padding:6px; width:180px; border-radius:4px; border:1px solid #ccc; }
.btn-group { display: flex; gap: 5px; margin-top: 10px; flex-wrap: wrap; }
</style>
<script>
function showReasonForm(deviceId) {
    const formDiv = document.getElementById('reason-form-' + deviceId);
    formDiv.style.display = (formDiv.style.display === 'none') ? 'block' : 'none';
}
function toggleOtherInput(sel) {
    const otherInput = sel.parentNode.querySelector('input[name="other_reason"]');
    if(sel.value == '기타') { otherInput.style.display='inline-block'; }
    else { otherInput.style.display='none'; }
}

// 실시간 자동 새로고침 (새 요청 올 때만)
if (!!window.EventSource) {
    var source = new EventSource("/events");
    source.onmessage = function(e) {
        if (e.data.startsWith("NEW_DEVICE") || e.data.startsWith("UPDATE")) {
            location.reload();
        }
    };
}
</script>
</head>
<body>

<h1>🚨 긴급 요청 모니터</h1>

{% for id, d in devices.items() %}
<div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <b>기기 ID: {{ id }}</b>
        <span class="{{ 'badge-new' if d.status=='NEW' else 'badge-move' }}">{{ d.status }}</span>
    </div>
    <p style="margin: 8px 0; font-size: 0.9em; color: #555;">
        요청 시간: {{ d.time_str }}<br>
        경과 시간: <span style="color:#d32f2f; font-weight:bold;">{{ d.elapsed }}</span>
    </p>

    <div class="btn-group">
        <a class="btn view" href="/device/{{ id }}">화면 보기</a>
        <a class="btn move" href="/move/{{ id }}">직원 이동</a>
        <button class="btn clear" onclick="showReasonForm('{{ id }}')">종료</button>
    </div>

    <div id="reason-form-{{ id }}" style="display:none; margin-top:12px; padding:10px; background:#f9f9f9; border-radius:8px;">
        <form action="/clear/{{ id }}" method="post">
            <select name="reason" onchange="toggleOtherInput(this)">
                {% for r in reasons %}
                <option value="{{ r }}">{{ r }}</option>
                {% endfor %}
            </select><br>
            <input type="text" name="other_reason" placeholder="직접 입력" style="display:none;"><br>
            <input type="submit" value="종료 확인" class="btn clear" style="margin-top:8px; width:100%;">
        </form>
    </div>
</div>
{% else %}
<div class="card" style="text-align:center; color:#888;">현재 활성화된 요청이 없습니다.</div>
{% endfor %}

<hr style="border:0; border-top:1px solid #ccc; margin:20px 0;">

<h1>📋 최근 요청 기록</h1>
{% for idx, h in enumerate(history) %}
<div class="history">
    <b>{{ h.device_id }}</b> ({{ h.duration }} 소요)<br>
    <small>{{ h.start_time }} ~ {{ h.end_time }}</small><br>
    사유: <b>{{ h.reason }}</b>
    <form action="/delete_history/{{ idx }}" method="post">
        <button class="delete">삭제</button>
    </form>
</div>
{% else %}
<p style="color:#888;">기록이 없습니다.</p>
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
reasons=REASONS,
enumerate=enumerate
)

# ================== 기기 통신 및 기능 API ==================

@app.route("/device/<device_id>")
def view_device(device_id):
    return f"""
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="background:black;color:white;text-align:center;margin:0;padding:20px;">
    <h3>{device_id} 실시간 화면</h3>
    <img id="cam" src="/image/{device_id}" style="max-width:100%; border:2px solid #333;"><br><br>
    <a href="/" style="color:white; text-decoration:none; background:#444; padding:10px 20px; border-radius:5px;">← 돌아가기</a>
    <script>
    setInterval(function(){{
        document.getElementById("cam").src = "/image/{device_id}?t=" + new Date().getTime();
    }}, 300);
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
    return "OK", 200

@app.route("/image/<device_id>")
def get_image(device_id):
    path = os.path.join(UPLOAD_DIR, f"{device_id}.jpg")
    if not os.path.exists(path):
        return "No Image", 404
    return send_file(path, mimetype="image/jpeg")

@app.route("/emergency", methods=["POST"])
def emergency():
    data = request.get_json(silent=True)
    if not data: return "Invalid JSON", 400
    device_id = str(data.get("device_id"))
    devices[device_id] = {"status": "NEW", "time": datetime.now()}
    device_commands[device_id] = "NONE"
    for q in clients:
        q.append(f"NEW_DEVICE:{device_id}")
    return "OK", 200

@app.route("/command/<device_id>")
def get_command(device_id):
    cmd = device_commands.get(device_id, "NONE")
    device_commands[device_id] = "NONE"  # 명령 확인 후 초기화
    return jsonify({"command": cmd})

@app.route("/move/<device_id>")
def move_staff(device_id):
    if device_id in devices:
        devices[device_id]["status"] = "MOVING"
        device_commands[device_id] = "MOVE"  # 기기에 MOVE 명령 전달
        for q in clients: q.append("UPDATE")
    return redirect("/")

@app.route("/clear/<device_id>", methods=["POST"])
def clear(device_id):
    d = devices.get(device_id)
    if d:
        reason = request.form.get("reason")
        other = request.form.get("other_reason")
        if reason == "기타" and other: reason = other
        
        end_time = datetime.now()
        history.insert(0, {
            "device_id": device_id,
            "start_time": d["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": elapsed_time_str(d["time"], end_time),
            "reason": reason
        })
        device_commands[device_id] = "STOP"  # 기기에 STOP 명령 전달
        devices.pop(device_id, None)
        for q in clients: q.append("UPDATE")
    return redirect("/")

@app.route("/delete_history/<int:idx>", methods=["POST"])
def delete_history(idx):
    if 0 <= idx < len(history):
        history.pop(idx)
    return redirect("/")

if __name__ == "__main__":
    # Render 배포용 포트 설정
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)













