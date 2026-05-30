"""
BlindVest — النسخة النهائية (مستقرة 100%، بدون حظر وبدون أعطال Playsound)
"""

import cv2, time, threading, queue, os, base64, requests, hashlib
import numpy as np
import tempfile
from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit
import edge_tts
import asyncio

# === دعم اللغة العربية في الكاميرا ===
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

try:
    ar_font = ImageFont.truetype("arial.ttf", 18)
except:
    ar_font = ImageFont.load_default()

def put_arabic_text(img, text, position, color):
    img_pil = Image.fromarray(img)
    draw = ImageDraw.Draw(img_pil)
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    draw.text(position, bidi_text, font=ar_font, fill=(color[0], color[1], color[2]))
    return np.array(img_pil)

# استدعاء مكتبة بي جيم الاحترافية وتشغيل محرك الصوت
import pygame
pygame.mixer.init()

ESP_IP = "http://172.20.10.4"
CONF_THRESH = 0.40

app = Flask(__name__)
app.secret_key = "blindvest_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

VALID_DEVICES = {
    "BLIND-001": "1234"
}

state = {
    "emergency": False,
    "gps": {"lat": 0.0, "lng": 0.0, "valid": False},
    "detections": []
}

connected_clients = 0

@socketio.on('connect')
def handle_connect():
    global connected_clients
    connected_clients += 1

@socketio.on('disconnect')
def handle_disconnect():
    global connected_clients
    connected_clients -= 1

# ====================== صوت الذكاء الاصطناعي المستقر ======================
speak_queue = queue.Queue()
audio_cache = {}

def speaker_worker():
    while True:
        text = speak_queue.get()
        if text is None: break
        try:
            if text not in audio_cache:
                file_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
                filename = os.path.join(tempfile.gettempdir(), f"bv_{file_hash}.mp3")

                async def save_audio():
                    # ar-SA-HamedNeural صوت سعودي (يمكنك تغييره إلى ar-EG-SalmaNeural)
                    comm = edge_tts.Communicate(text, "ar-SA-HamedNeural")
                    await comm.save(filename)

                asyncio.run(save_audio())
                audio_cache[text] = filename

            # تشغيل الصوت بنظام pygame الخالي من الأعطال
            pygame.mixer.music.load(audio_cache[text])
            pygame.mixer.music.play()

            # انتظار حتى ينتهي المقطع الصوتي قبل الانتقال للذي يليه
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)

        except Exception as e:
            print(f"[صوت خطأ] {e}")
        speak_queue.task_done()

threading.Thread(target=speaker_worker, daemon=True).start()

def speak(text):
    if speak_queue.qsize() < 2:
        speak_queue.put(text)

# ====================== إرسال أوامر المحركات (بدون تجميد الكاميرا) ======================
latest_motor_cmd = "OFF"

def motor_worker():
    while True:
        try:
            requests.get(f"{ESP_IP}/motor?cmd={latest_motor_cmd}", timeout=0.2)
        except:
            pass
        time.sleep(0.05)

threading.Thread(target=motor_worker, daemon=True).start()

# ====================== تحليلات الألوان و YOLO ======================
try:
    import torch
    if torch.cuda.is_available():
        print(f"✅ CUDA متوفر! YOLO سيستخدم كرت الشاشة: {torch.cuda.get_device_name(0)}")
    else:
        print("⚠️ تحذير: PyTorch لا يرى كرت الشاشة (CUDA غير مفعل)! سيعمل النظام على المعالج (CPU) مما يسبب بطء شديد.")
        print("👉 لحل المشكلة واستخدام كرت RTX 4060، اكتب هذا الأمر في التيرمنال:")
        print("pip uninstall torch torchvision torchaudio -y")
        print("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')
    if torch.cuda.is_available():
        model.to('cuda')
    print("✅ YOLO loaded")
except Exception as e:
    model = None
    print(f"⚠️ YOLO: {e}")

def detect_traffic_light_color(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])

    lower_green = np.array([40, 40, 40])
    upper_green = np.array([90, 255, 255])

    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_green = cv2.inRange(hsv, lower_green, upper_green)

    red_pixels = cv2.countNonZero(mask_red)
    green_pixels = cv2.countNonZero(mask_green)

    if red_pixels > green_pixels and red_pixels > 20: return "red"
    elif green_pixels > red_pixels and green_pixels > 20: return "green"
    return "unknown"

AR = {
    'person':'شخص','car':'سيارة','truck':'شاحنة','bus':'حافلة',
    'chair':'كرسي','cat':'قطة','dog':'كلب','bottle':'زجاجة',
    'cell phone':'هاتف','book':'كتاب','tv':'تلفاز','bicycle':'دراجة',
    'motorcycle':'دراجة نارية', 'traffic light':'إشارة مرور',
    'red_traffic_light':'إشارة مرور حمراء (قف)',
    'green_traffic_light':'إشارة مرور خضراء (انطلق)',
    'stop sign':'إشارة توقف','bench':'مقعد','dining table':'طاولة',
    'laptop':'حاسوب','cup':'كوب','door':'باب','stairs':'درج',
    'refrigerator':'ثلاجة','oven':'فرن','sink':'حوض','bed':'سرير',
}

def camera_thread():
    global latest_motor_cmd
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    last_spoken = {}  # مؤقت زمني لعدم إزعاج الكفيف

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1); continue

        if connected_clients <= 0:
            latest_motor_cmd = "OFF"
            time.sleep(0.5)
            continue

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        now = time.time()

        detections = []
        active_dirs = {"left": 0, "center": 0, "right": 0}

        if model:
            results = model(frame, verbose=False, conf=CONF_THRESH, imgsz=480)[0]
            for box in results.boxes:
                cls_name = model.names[int(box.cls[0])]
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if cls_name == 'traffic light':
                    if (y2 > y1) and (x2 > x1):
                        roi = frame[y1:y2, x1:x2]
                        color = detect_traffic_light_color(roi)
                        if color == "red": cls_name = "red_traffic_light"
                        elif color == "green": cls_name = "green_traffic_light"

                cx = (x1 + x2) / 2
                direction = "center"
                if cx < w / 3: direction = "left"
                elif cx > 2 * w / 3: direction = "right"

                ar_name = AR.get(cls_name, cls_name)
                dist_label = "قريب" if (x2-x1)*(y2-y1)/(w*h) > 0.1 else "بعيد"

                box_color = (0, 0, 255) if cls_name == "red_traffic_light" else \
                            (0, 255, 0) if cls_name == "green_traffic_light" else (0,255,255)

                cv2.rectangle(frame, (x1,y1), (x2,y2), box_color, 2)
                frame = put_arabic_text(frame, f"{ar_name} | {dist_label}", (x1, max(0, y1-25)), box_color)

                phrase = f"{ar_name} على {'اليسار' if direction=='left' else 'اليمين' if direction=='right' else 'أمامك'}"

                # إرسال الصوت فقط إذا لم يتم نطقه خلال آخر 3 ونصف ثانية! (يمنع الثرثرة)
                if now - last_spoken.get(phrase, 0) > 3.5:
                    speak(phrase)
                    last_spoken[phrase] = now

                detections.append({"label": ar_name, "direction": direction, "dist": dist_label})
                active_dirs[direction] = 180

        state["detections"] = detections

        cmd_parts = []
        if active_dirs["left"] > 0:   cmd_parts.append("LEFT:180")
        if active_dirs["center"] > 0: cmd_parts.append("CENTER:160")
        if active_dirs["right"] > 0:  cmd_parts.append("RIGHT:180")
        
        latest_motor_cmd = " ".join(cmd_parts) if cmd_parts else "OFF"

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(buf).decode()
        socketio.emit('video_frame', {
            'frame': b64,
            'detections': detections,
            'gps': state['gps'],
            'emergency': state['emergency']
        })

threading.Thread(target=camera_thread, daemon=True).start()

# ====================== GPS ======================
def gps_thread():
    while True:
        try:
            r = requests.get(f"{ESP_IP}/gps", timeout=1.5)
            if r.status_code == 200:
                d = r.json()
                state["gps"]["lat"] = d.get("lat", 0)
                state["gps"]["lng"] = d.get("lng", 0)
                state["gps"]["valid"] = d.get("valid", False)
        except: pass
        time.sleep(3)

threading.Thread(target=gps_thread, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    device = data.get('device')
    password = data.get('password')
    if VALID_DEVICES.get(device) == password:
        session['logged_in'] = True
        session['device'] = device
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/status', methods=['GET'])
def status():
    if session.get('logged_in'):
        return jsonify({"logged_in": True, "device": session.get('device')})
    return jsonify({"logged_in": False})

@app.route('/emergency', methods=['GET'])
def handle_esp_emergency():
    state['emergency'] = True
    socketio.emit('emergency_alert', {}, broadcast=True)
    print("🚨 طوارئ وصلت من الفيست!")
    return jsonify({"status": "ok"})

@socketio.on('manual_motor')
def handle_motor(data):
    motor = data.get('motor', '')
    on = data.get('on', False)
    intensity = 220 if on else 0
    if motor == 'all':
        cmd = f"LEFT:{intensity} CENTER:{intensity} RIGHT:{intensity}" if on else "OFF"
    elif motor in ('left','center','right'):
        cmd = f"{motor.upper()}:{intensity}" if on else "OFF"
    else:
        cmd = "OFF"
    try:
        requests.get(f"{ESP_IP}/motor?cmd={cmd}", timeout=0.3)
    except: pass

@socketio.on('resolve_emergency')
def handle_resolve():
    state['emergency'] = False

if __name__ == '__main__':
    print("🚀 BlindVest Server يعمل على http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
