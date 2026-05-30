#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <HardwareSerial.h>
#include <TinyGPS++.h>

const char* ssid = "iPhone zaid";
const char* password = "12345678";

const int PIN_RIGHT  = 25;
const int PIN_CENTER = 32;
const int PIN_LEFT   = 12;
const int BTN_PIN    = 33;

const int PWM_FREQ = 5000;
const int PWM_RES  = 8;

TinyGPSPlus gps;
HardwareSerial gpsSerial(2);
float lastLat = 0, lastLng = 0;
bool gpsValid = false;

WebServer server(80);
bool emergency = false;
unsigned long lastBtnMs = 0;

// ====================== HTML Interface ======================
const char* html =  R"rawliteral(
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BlindVest - لوحة التحكم</title>
<link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@600;900&family=Tajawal:wght@400;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root {
  --deep: #030b18; --dark: #060f22; --navy: #09152d;
  --panel: #0c1a35; --cyan: #00e5ff; --red: #ff3d5a; --green: #00e676;
  --text-p: #e8f0fe;
}
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family: 'Tajawal', sans-serif; background: var(--deep); color: var(--text-p); min-height: 100vh; }
.hdr { display:flex; align-items:center; justify-content:space-between; padding:0 22px; height:62px; background:var(--dark); border-bottom:1px solid #132648; }
.logo { font-family:'Exo 2', sans-serif; font-size:22px; font-weight:900; color:#fff; }
.logo span { color: var(--cyan); }
.main { display:grid; grid-template-columns: 1fr 320px; gap:15px; padding:15px; }
@media (max-width: 768px) { .main { grid-template-columns: 1fr; } }
.panel { background:var(--panel); border:1px solid #132648; border-radius:16px; overflow:hidden; margin-bottom: 15px; }
.p-hdr { padding:10px 15px; background:var(--navy); border-bottom:1px solid #132648; font-size:14px; font-weight:bold; }
.mgrid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:20px; }
.mbtn { padding:20px 10px; background:#0f2040; border:1px solid #1e3a5f; border-radius:12px; text-align:center; cursor:pointer; transition: 0.2s; font-weight:bold; }
.mbtn:active, .mbtn.active { border-color:var(--cyan); background:rgba(0,229,255,0.15); transform: scale(0.95); }
.emg-box { display:none; background:var(--red); color:#000; padding:15px; text-align:center; font-weight:900; animation: blink 1s infinite; }
.emg-box.on { display:block; }
@keyframes blink { 50% { opacity: 0.7; } }
.status-val { font-family: 'Share Tech Mono', monospace; color: var(--cyan); }
</style>
</head>
<body>
<header class="hdr">
  <div class="logo">Blind<span>Vest</span></div>
  <div style="font-size:12px; color:var(--cyan)">نظام المساعدة الذكي</div>
</header>
<div class="emg-box" id="emg">
  تنبيه طارئ - المستخدم يحتاج مساعدة!
  <br><button onclick="resolveEmg()" style="margin-top:10px; padding:6px 15px; background:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">تم التعامل</button>
</div>
<div class="main">
  <div class="left">
    <div class="panel">
      <div class="p-hdr">التحكم اليدوي بالموتورات</div>
      <div class="mgrid">
        <div class="mbtn" onmousedown="vibrate('LEFT')" onmouseup="stopVibrate()">يسار</div>
        <div class="mbtn" onmousedown="vibrate('CENTER')" onmouseup="stopVibrate()">وسط</div>
        <div class="mbtn" onmousedown="vibrate('RIGHT')" onmouseup="stopVibrate()">يمين</div>
      </div>
    </div>
  </div>
  <div class="sidebar">
    <div class="panel" style="padding:15px;">
      <div class="p-hdr" style="margin:-15px -15px 15px -15px">حالة النظام</div>
      <div style="margin-bottom:8px;">الحالة العامة: <span id="st-msg" class="status-val">جاري الفحص...</span></div>
      <div>موقع GPS: <span id="st-gps" class="status-val">غير متوفر</span></div>
    </div>
  </div>
</div>
<script>
function vibrate(dir) { fetch(`/motor?cmd=${dir}:255`); }
function stopVibrate() { fetch('/motor?cmd=OFF'); }
function resolveEmg() { fetch('/resolve').then(() => document.getElementById('emg').classList.remove('on')); }
setInterval(() => {
  fetch('/status').then(r => r.json()).then(data => {
    document.getElementById('st-msg').innerHTML = data.emergency ? '<span style="color:#ff3d5a">⚠ طارئ!</span>' : 'آمن';
    if(data.emergency) document.getElementById('emg').classList.add('on');
    fetch('/gps').then(r => r.json()).then(g => {
      if(g.valid) document.getElementById('st-gps').innerText = g.lat.toFixed(4) + "," + g.lng.toFixed(4);
    });
  });
}, 2000);
</script>
</body>
</html>
)rawliteral";

// ====================== Functions ======================
void motorWrite(int pin, int val) {
  ledcWrite(pin, constrain(val, 0, 255));
}

void motorsOff() {
  motorWrite(PIN_LEFT, 0);
  motorWrite(PIN_CENTER, 0);
  motorWrite(PIN_RIGHT, 0);
}

// دالة المطوّرات المُعدّلة (تستوعب أكثر من موتور بكلمة واحدة بدلاً من الأول فقط)
void applyMotorCmd(String cmd) {
  cmd.trim();
  if (cmd == "OFF" || cmd == "") { motorsOff(); return; }
  
  motorsOff(); // تصفير الكل لضمان عدم تعليق موتور قديم
  
  int startIndex = 0;
  while (startIndex < cmd.length()) {
    int spaceIndex = cmd.indexOf(' ', startIndex);
    if (spaceIndex == -1) spaceIndex = cmd.length();
    
    String token = cmd.substring(startIndex, spaceIndex);
    int col = token.indexOf(':');
    if (col > 0) {
      String dir = token.substring(0, col);
      int val = token.substring(col+1).toInt();
      if (dir == "LEFT") motorWrite(PIN_LEFT, val);
      else if (dir == "CENTER") motorWrite(PIN_CENTER, val);
      else if (dir == "RIGHT") motorWrite(PIN_RIGHT, val);
    }
    startIndex = spaceIndex + 1;
  }
}

void handleMotor() {
  if (server.hasArg("cmd")) applyMotorCmd(server.arg("cmd"));
  server.send(200, "text/plain", "OK");
}

void handleGPS() {
  String json = "{\"valid\":" + String(gpsValid) + 
                ",\"lat\":" + String(lastLat,6) + 
                ",\"lng\":" + String(lastLng,6) + "}";
  server.send(200, "application/json", json);
}

void handleEmergency() {
  emergency = true;
  server.send(200, "text/plain", "EMERGENCY_SENT");
}

void handleStatus() {
  String json = "{\"emergency\":" + String(emergency ? "true" : "false") + "}";
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);
  ledcAttach(PIN_RIGHT, PWM_FREQ, PWM_RES);
  ledcAttach(PIN_CENTER, PWM_FREQ, PWM_RES);
  ledcAttach(PIN_LEFT, PWM_FREQ, PWM_RES);
  motorsOff();

  pinMode(BTN_PIN, INPUT_PULLUP);
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi Connected - IP: " + WiFi.localIP().toString());

  server.on("/", [](){ server.send(200, "text/html", html); });
  server.on("/motor", handleMotor);
  server.on("/gps", handleGPS);
  server.on("/emergency", handleEmergency);
  server.on("/status", handleStatus);
  server.on("/resolve", [](){ emergency = false; server.send(200, "text/plain", "OK"); });

  server.begin();
}

void loop() {
  server.handleClient();

  while (gpsSerial.available()) {
    if (gps.encode(gpsSerial.read())) {
      if (gps.location.isValid()) {
        lastLat = gps.location.lat();
        lastLng = gps.location.lng();
        gpsValid = true;
      }
    }
  }

  // زر الطوارئ
  if (digitalRead(BTN_PIN) == LOW && millis() - lastBtnMs > 800) {
    lastBtnMs = millis();
    emergency = true;

    WiFiClient client;
    HTTPClient http;
    
    String serverPath = "http://192.168.1.145:5000/emergency";
    
    if (gpsValid && lastLat != 0 && lastLng != 0) {
      serverPath += "?lat=" + String(lastLat,6) + "&lng=" + String(lastLng,6);
    }

    http.begin(client, serverPath); 
    int httpCode = http.GET();
    
    if (httpCode > 0) {
      Serial.print("✅ طوارئ تم إرسالها بنجاح. الكود: ");
      Serial.println(httpCode);
    } else {
      Serial.print("❌ فشل إرسال الطوارئ، الخطأ: ");
      Serial.println(http.errorToString(httpCode).c_str());
    }
    
    http.end();
  }
}
