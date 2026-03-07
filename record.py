import serial
import wave

PORT = "COM3"
BAUD = 921600       # tăng baud
RATE = 16000
CHANNELS = 1
WIDTH = 2

ser = serial.Serial(PORT, BAUD, timeout=0.1)

wav = wave.open("output.wav", "wb")
wav.setnchannels(CHANNELS)
wav.setsampwidth(WIDTH)
wav.setframerate(RATE)

print("🎙️ Đang ghi âm... nhấn Ctrl+C để dừng.")

try:
    while True:
        data = ser.read(4096)
        wav.writeframes(data)

except KeyboardInterrupt:
    print("\n🛑 Dừng ghi âm.")

finally:
    wav.close()
    ser.close()
    print("💾 File đã lưu: output.wav")