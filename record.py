"""
ESP32-S3 + INMP441 – Recorder
================================
pip install pyserial

Cách dùng:
    python record_audio.py -p COM3
    python record_audio.py -p COM3 -d 10 -o my_audio.wav

⚠️  ĐÓNG Serial Monitor trước khi chạy!
"""

import serial
import serial.tools.list_ports
import wave
import struct
import argparse
import sys
import time
from datetime import datetime

SAMPLE_RATE = 16000
BAUD_RATE   = 230400   # Khớp Serial.begin(230400) trong main.cpp


# ───────────────────────────────────────────────────────────────
def list_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ Không tìm thấy cổng serial nào.")
        return []
    print("\n📡 Cổng serial:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device:15s}  {p.description}")
    return [p.device for p in ports]


def choose_port():
    ports = list_ports()
    if not ports:
        sys.exit(1)
    if len(ports) == 1:
        print(f"✅ Tự động chọn: {ports[0]}")
        return ports[0]
    try:
        return ports[int(input("\n👉 Nhập số thứ tự: ").strip())]
    except (ValueError, IndexError):
        print("❌ Lựa chọn không hợp lệ.")
        sys.exit(1)


# ───────────────────────────────────────────────────────────────
def wait_for_line(ser: serial.Serial, keyword: str, timeout: float = 5.0) -> bool:
    """Đọc từng dòng text (readline) cho đến khi tìm thấy keyword."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if line:
            print(f"   ESP32: '{line}'")
        if keyword in line:
            return True
    return False


# ───────────────────────────────────────────────────────────────
def record(port: str, duration: float, output: str, baud: int):
    print(f"\n🔌 Mở {port} @ {baud} baud…")
    try:
        ser = serial.Serial(port, baud, timeout=2)
    except serial.SerialException as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Đợi ESP32 boot
    print("⏳ Đợi ESP32 khởi động (2s)…")
    time.sleep(2)
    ser.reset_input_buffer()

    # Đọc "READY" (timeout 3s, không bắt buộc)
    ready_line = ser.readline().decode("utf-8", errors="ignore").strip()
    if ready_line:
        print(f"   ESP32: '{ready_line}'")

    # ── Gửi lệnh bắt đầu ──────────────────────────────────────────────
    print("📤 Gửi 'R' → ESP32 bắt đầu stream PCM…")
    ser.reset_input_buffer()
    ser.write(b'R')      # 1 byte, không \n — dùng Serial.read() bên ESP32
    ser.flush()

    # Đọc "START" ACK — đây là dòng text DUY NHẤT trước khi PCM bytes đến
    if wait_for_line(ser, "START", timeout=5):
        print("✅ Nhận START — bắt đầu thu PCM bytes…")
    else:
        print("⚠️  Không nhận START, vẫn tiếp tục (kiểm tra baud & cổng)")

    # ── Thu raw PCM bytes ──────────────────────────────────────────────
    # Từ đây ESP32 chỉ gửi binary — KHÔNG readline nữa
    ser.timeout = 0.05   # non-blocking
    print(f"🎙️  Ghi {duration}s…  Ctrl+C để dừng sớm\n")

    audio   = bytearray()
    start   = time.time()
    vol_avg = 0.0

    try:
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            n = ser.in_waiting
            if n == 0:
                time.sleep(0.002)
                continue

            chunk = ser.read(n)
            audio.extend(chunk)

            # Volume từ chunk
            pairs = (len(chunk) // 2)
            if pairs > 0:
                vals    = struct.unpack_from(f"<{pairs}h", chunk[:pairs * 2])
                vol_avg = sum(abs(v) for v in vals) / pairs

            # Progress bar
            pct  = min(elapsed / duration * 100, 100)
            bar  = "█" * int(pct // 4) + "░" * (25 - int(pct // 4))
            left = max(0.0, duration - elapsed)
            print(f"\r  [{bar}] {pct:5.1f}%  còn {left:.1f}s  "
                  f"bytes={len(audio):,}  vol={vol_avg:5.0f}  ",
                  end="", flush=True)

    except KeyboardInterrupt:
        print("\n⚡ Dừng sớm.")

    # ── Dừng stream ────────────────────────────────────────────────────
    ser.write(b'S')
    ser.flush()
    time.sleep(0.3)

    # Vét nốt bytes còn trong buffer
    ser.timeout = 0.5
    leftover = ser.read(ser.in_waiting or 1)
    if leftover:
        audio.extend(leftover)

    ser.close()

    total = len(audio)
    print(f"\n🔌 Đóng cổng.  Nhận: {total:,} bytes  "
          f"({total // 2:,} samples  /  {total / 2 / SAMPLE_RATE:.2f}s)")

    # ── Kiểm tra data ──────────────────────────────────────────────────
    if total == 0:
        print("\n❌ Không nhận được byte nào!")
        print("   Nguyên nhân phổ biến:")
        print("   • Serial Monitor chưa đóng → ĐÓNG đi rồi thử lại")
        print("   • Baud sai → kiểm tra Serial.begin() trong main.cpp")
        print("   • Cổng COM sai")
        return

    if total / 2 / SAMPLE_RATE < duration * 0.5:
        print(f"\n⚠️  Chỉ nhận được {total/2/SAMPLE_RATE:.1f}s / {duration}s yêu cầu")
        print("   → Baud có thể không đủ bandwidth, thử giảm SAMPLE_RATE hoặc tăng baud")

    # Căn chỉnh byte chẵn
    if len(audio) % 2:
        audio = audio[:-1]

    # Kiểm tra peak
    n_s  = len(audio) // 2
    vals = struct.unpack(f"<{n_s}h", bytes(audio))
    peak = max(abs(v) for v in vals)
    avg  = sum(abs(v) for v in vals) / n_s

    print(f"   Peak: {peak:,}  |  Avg vol: {avg:.0f}")
    if peak < 20:
        print("\n⚠️  Peak ≈ 0 → I2S không đọc được audio")
        print("   → Thử đổi channel trong main.cpp:")
        print("     I2S_CHANNEL_FMT_ONLY_LEFT  ↔  I2S_CHANNEL_FMT_ONLY_RIGHT")
        print("   → Kiểm tra wiring SCK/WS/SD")
    elif peak < 300:
        print("⚠️  Tín hiệu yếu — micro bị che hoặc channel sai")

    # ── Lưu WAV ────────────────────────────────────────────────────────
    with wave.open(output, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(audio))

    dur_s = len(audio) / 2 / SAMPLE_RATE
    kb    = len(audio) / 1024
    print(f"\n💾 Lưu: {output}")
    print(f"   {dur_s:.2f}s  |  {kb:.1f} KB  |  "
          f"{SAMPLE_RATE} Hz / 16-bit / Mono")
    if peak > 300:
        print("✅ Tín hiệu OK — mở file bằng Audacity để kiểm tra")


# ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Ghi âm ESP32 INMP441 → WAV")
    ap.add_argument("-p", "--port",     help="Cổng serial (COM3, /dev/ttyUSB0…)")
    ap.add_argument("-d", "--duration", type=float, default=5.0,
                    help="Thời gian ghi giây (mặc định 5)")
    ap.add_argument("-o", "--output",   help="Tên file .wav output")
    ap.add_argument("-b", "--baud",     type=int, default=BAUD_RATE,
                    help=f"Baud rate (mặc định {BAUD_RATE})")
    args = ap.parse_args()

    port = args.port or choose_port()
    out  = args.output or f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    if not out.endswith(".wav"):
        out += ".wav"

    record(port, args.duration, out, args.baud)


if __name__ == "__main__":
    main()