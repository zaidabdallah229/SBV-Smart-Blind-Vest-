# SBV (Smart Blind Vest)

![Smart Blind Vest](https://img.shields.io/badge/Status-Stable_100%25-brightgreen)
![Python](https://img.shields.io/badge/Python-3.x-blue)
![C++](https://img.shields.io/badge/C++-Arduino-cyan)
![YOLOv8](https://img.shields.io/badge/YOLO-v8n-yellow)

The **Smart Blind Vest (BlindVest)** is a comprehensive IoT and AI-powered project designed to assist visually impaired individuals in navigating safely and independently. The system consists of a Python application (handling Computer Vision and AI) and Arduino/ESP32 code (controlling sensors and vibration motors).

---

## ✨ Key Features

1. **AI Object Detection (YOLOv8):** 
   - Detects surrounding obstacles (cars, people, doors, chairs, etc.).
   - Recognizes the status of traffic lights (green to go, red to stop).
2. **Arabic Voice Guidance:**
   - Informs the user about the type of obstacle and its location (right, left, or center) using the `edge_tts` engine.
3. **Haptic Feedback (Vibration Motors):**
   - 3 vibration motors (Right, Center, Left) connected to an ESP32 board vibrate based on the obstacle's location to provide sensory alerts to the user.
4. **Emergency Button & GPS Tracking:**
   - A built-in emergency button on the vest sends an instant alert to the web dashboard along with the user's current geographical location via a GPS module.
5. **Monitoring Web Dashboard:**
   - An advanced control panel that allows caregivers to monitor the user's status, receive emergency alerts, and track their live location.

---

## 🛠️ Technologies Used

### Artificial Intelligence (Python)
- **Python / Flask / Flask-SocketIO:** For building the web server and establishing real-time communication with the frontend.
- **OpenCV & YOLOv8:** For processing live video feed and accurately detecting objects and traffic lights.
- **Edge TTS & Pygame:** For generating fast, stable, and stutter-free Arabic voice alerts.

### Hardware (Arduino / ESP32)
- **ESP32 Microcontroller:** The brain of the vest, connected to Wi-Fi to communicate with the server.
- **TinyGPS++:** For parsing GPS coordinates (Latitude and Longitude).
- **PWM Motors:** Vibration motors driven by PWM signals to adjust vibration intensity based on proximity.

---

## 📂 Project Structure

The repository is divided into two main parts:

1. **`PythonApp/`**: Contains the AI code (`robocraft.py`), the YOLO model (`yolov8n.pt`), and the web dashboard files (`templates/index.html`).
2. **`Arduino/`**: Contains the hardware control code (`Blind_final.ino`) ready to be flashed onto the ESP32 board.

---

## 🚀 Setup & Installation

### 1️⃣ Python Setup (Server & Camera)
1. Ensure Python is installed on your machine.
2. Install the required dependencies:
   ```bash
   pip install flask flask-socketio opencv-python ultralytics edge-tts pygame arabic_reshaper python-bidi requests
   ```
3. *(Optional)* For better camera performance, enable GPU acceleration (CUDA) for PyTorch.
4. Run the main script:
   ```bash
   cd PythonApp
   python robocraft.py
   ```
5. Open your browser and go to `http://localhost:5000` to access the dashboard (The default device password for `BLIND-001` is `1234`).

### 2️⃣ Arduino Setup (ESP32)
1. Open the **Arduino IDE**.
2. Add the ESP32 board support URL and install it from the Boards Manager.
3. Install the `TinyGPS++` library from the Library Manager.
4. Open the `Arduino/Blind_final.ino` file.
5. Update your Wi-Fi credentials (`ssid` and `password`) and modify the `serverPath` IP address to match the IP of the PC running the Python code.
6. Upload the code to your ESP32 board.

---

## 🤝 Contributing
This project is open to contributors who wish to develop and expand its capabilities to help the visually impaired. Feel free to fork the repository and submit a Pull Request!

---
*This system was developed to serve people with disabilities and provide a safer environment for them.*