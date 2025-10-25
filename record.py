import serial
import wave
import struct

PORT = "COM3"       # chỉnh lại đúng cổng ESP32-S3
BAUD = 115200
RATE = 16000        # tần số mẫu
CHANNELS = 1
WIDTH = 2           # 16-bit

ser = serial.Serial(PORT, BAUD, timeout=1)
wav = wave.open("output.wav", "wb")
wav.setnchannels(CHANNELS)
wav.setsampwidth(WIDTH)
wav.setframerate(RATE)

print("🎙️ Đang ghi âm... nhấn Ctrl+C để dừng.")

try:
    while True:
        data = ser.read(1024)
        if data:
            wav.writeframes(data)
except KeyboardInterrupt:
    print("\n🛑 Dừng ghi âm.")
finally:
    wav.close()
    ser.close()
    print("💾 File đã lưu: output.wav")
