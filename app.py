# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, render_template_string, Response
import requests
from datetime import datetime
import time
import os  # 추가

app = Flask(__name__)

# 데이터 저장소 (주의: Render 무료 서버는 재시작 시 데이터가 초기화됩니다)
devices = {}
history = []
clients = [] 

REASONS = [
    "마트에서 이동 도움",
    "상품 선택 도움",
    "결제 도움",
    "기타"
]

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
                    # Render 환경에서 연결 끊김 방지를 위한 dummy data 전송 가능
                    time.sleep(0.5)
        except GeneratorExit:
            if q in clients:
                clients.remove(q)
    # 캐싱 방지 헤더 추가 (SSE 안정성 확보)
    return Response(gen(), mimetype="text/event-stream", headers={'Cache-Control': 'no-cache', 'Transfer-Encoding': 'chunked'})

@app.route("/")
def index():
    # 기존 UI 코드 그대로 유지
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
form { margin:0; }
select, input[type=text] { margin-top:4px; padding:4px 6px; width:200px; border-radius:4px; border:1px solid #ccc; }
</style>
<script>
function showReasonForm(deviceId) {
    const formDiv = document.getElementById('reason-form-' + deviceId);
    formDiv.style.display = 'block';
}
function toggleOtherInput(sel) {
    const otherInput = sel.parentNode.querySelector('input[name="other_reason"]');
    if(sel.value == '기타') { otherInput.style.display='inline-block'; }
    else { otherInput.style.display='none'; }
}
function showEditForm(idx) {
    const div = document.getElementById('edit-form-' + idx);
    div.style.display = 'block';
}

if (!!window.EventSource) {
    var source = new EventSource("/events");
    source.onmessage = function(e) {
        if (e.data.startsWith("NEW_DEVICE")) {
            location.reload();  
        }
    };
}
</script>
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
<a class="btn clear" href="javascript:void(0)" onclick="showReasonForm('{{ id }}')">종료</a>
<div id="reason-form-{{ id }}" style="display:none; margin-top:8px;">
<form action="/clear/{{ id }}" method="post">
<select name="reason" onchange="toggleOtherInput(this)">
{% for r in reasons %}
<option value="{{ r }}">{{ r }}</option>
{% endfor %}
</select>
<input type="text" name="other_reason" placeholder="직접 입력" style="display:none;">
<input type="submit" value="확인">
</form>
</div>
</div>
{% else %}
<p>현재 요청이 없습니다.</p>
{% endfor %}
<hr>
<h1>요청 기록</h1>
{% for idx, h in enumerate(history) %}
<div class="history">
<b>{{ h.device_id }}</b><br>
시작 시간: {{ h.start_time }}<br>
종료 시간: {{ h.end_time }}<br>
소요 시간: {{ h.duration }}<br>
사유: {{ h.reason }}
<form action="/delete_history/{{ idx }}" method="post" style="display:inline;">
<button class="delete">삭제</button>
</form>
<button class="edit-btn" onclick="showEditForm({{ idx }})">수정</button>
<div id="edit-form-{{ idx }}" style="display:none; margin-top:4px;">
<form action="/edit_reason/{{ idx }}" method="post">
<select name="reason" onchange="toggleOtherInput(this)">
{% for r in reasons %}
<option value="{{ r }}" {% if r==h.reason %}selected{% endif %}>{{ r }}</option>
{% endfor %}
</select>
<input type="text" name="other_reason" value="{% if h.reason not in reasons %}{{ h.reason }}{% endif %}" style="display:{% if h.reason not in reasons %}inline-block{% else %}none{% endif %};">
<input type="submit" value="확인">
</form>
</div>
</div>
{% else %}
<p>요청 기록이 없습니다.</p>
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

# ... [나머지 라우트(/device, /emergency, /move, /clear, /edit_reason, /delete_history)는 기존과 동일함] ...
@app.route("/device/<device_id>")
def view_device(device_id):
    d = devices.get(device_id)
    if not d:
        return "해당 장치를 찾을 수 없습니다.", 404
    return f"""
<html>
<head><meta charset="UTF-8"></head>
<body style="background:black;color:white;text-align:center">
<h2>{device_id} 요청 화면</h2>
<iframe src="{d['stream_url']}" width="720" height="540"></iframe><br><br>
<a href="/" style="color:white">←돌아가기</a>
</body>
</html>
"""

@app.route("/emergency", methods=["POST"])
def emergency():
    data = request.get_json(silent=True)
    if not data: return "Invalid JSON", 400
    device_id = str(data.get("device_id"))
    stream_url = str(data.get("stream_url"))
    devices[device_id] = {
        "stream_url": stream_url,
        "status": "NEW",
        "time": datetime.now()
    }
    for q in clients:
        q.append(f"NEW_DEVICE:{device_id}")
    return "OK", 200

@app.route("/move/<device_id>")
def move_staff(device_id):
    d = devices.get(device_id)
    if not d: return "Not found", 404
    try: requests.get(d["stream_url"] + "/staff_moving", timeout=2)
    except: pass
    d["status"] = "MOVING"
    return redirect("/")

@app.route("/clear/<device_id>", methods=["POST"])
def clear(device_id):
    d = devices.get(device_id)
    if d:
        try: requests.get(d["stream_url"] + "/stop", timeout=1)
        except: pass
        reason = request.form.get("reason")
        other_reason = request.form.get("other_reason")
        if reason == "기타" and other_reason.strip():
            reason = other_reason.strip()
        end_time = datetime.now()
        history.insert(0,{
            "device_id": device_id,
            "start_time": d["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": elapsed_time_str(d["time"], end_time),
            "reason": reason
        })
        devices.pop(device_id, None)
    return redirect("/")

@app.route("/edit_reason/<int:idx>", methods=["POST"])
def edit_reason(idx):
    if 0 <= idx < len(history):
        reason = request.form.get("reason")
        other_reason = request.form.get("other_reason")
        if reason == "기타" and other_reason.strip():
            reason = other_reason.strip()
        history[idx]["reason"] = reason
    return redirect("/")

@app.route("/delete_history/<int:idx>", methods=["POST"])
def delete_history(idx):
    if 0 <= idx < len(history):
        history.pop(idx)
    return redirect("/")

# 렌더 서버 배포를 위한 핵심 수정 부분
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)












