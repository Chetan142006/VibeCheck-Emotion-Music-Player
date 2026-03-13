import requests
import base64
import cv2
import json

# Capture a dummy frame using OpenCV
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
cap.release()

if ret:
    print(f"[TEST] Captured frame of size {frame.shape}")
    _, buffer = cv2.imencode('.jpg', frame)
    b64_str = base64.b64encode(buffer).decode('utf-8')
    data_uri = f"data:image/jpeg;base64,{b64_str}"

    print("[TEST] Sending to API...")
    try:
        resp = requests.post("http://localhost:5000/api/detect-emotion", json={"image": data_uri})
        print(f"[TEST] Response Code: {resp.status_code}")
        print(f"[TEST] Response Body: {resp.text}")
    except Exception as e:
        print(f"[TEST] Exception: {e}")
else:
    print("[TEST] Failed to capture frame from webcam.")
