"""
ESP32-S3 + INMP441 – Python Recorder v3
=========================================
Nhận raw PCM 16-bit từ ESP32 và lưu .wav

Cài đặt:  pip install pyserial
Cách dùng:
    python record_audio.py                     # tự chọn cổng, ghi 5s
    python record_audio.py -p COM3 -d 10
    python record_audio.py -p COM3 --debug     # in hex để kiểm tra data

⚠️  QUAN TRỌNG: Đóng Serial Monitor trước khi chạy script này!
"""

import serial
import serial.tools.list_ports
import wave
import struct
import argparse
import sys
import time
from datetime import datetime

# ── Khớp với main.cpp ───────────────────────
SAMPLE_RATE     = 16000
BAUD_RATE       = 460800
MAGIC_START     = bytes([0xFF, 0xFE, 0xFD, 0xFC])
MAGIC_END       = bytes([0xFC, 0xFD, 0xFE, 0xFF])


# ────────────────────────────────────────────
def list_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("⚠️  Không tìm thấy cổng serial nào.")
        return []
    print("\n📡 Cổng serial khả dụng:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device:20s} {p.description}")
    return [p.device for p in ports]


def choose_port():
    ports = list_ports()
    if not ports:
        sys.exit(1)
    if len(ports) == 1:
        print(f"✅ Tự động chọn: {ports[0]}")
        return ports[0]
    try:
        idx = int(input("\n👉 Nhập số thứ tự cổng: ").strip())
        return ports[idx]
    except (ValueError, IndexError):
        print("❌ Lựa chọn không hợp lệ.")
        sys.exit(1)


# ────────────────────────────────────────────
def wait_for_magic(ser: serial.Serial, magic: bytes, timeout: float = 5.0) -> bool:
    """Đọc bytes cho đến khi tìm thấy magic sequence."""
    buf = bytearray()
    t0  = time.time()
    while time.time() - t0 < timeout:
        b = ser.read(1)
        if not b:
            continue
        buf.append(b[0])
        if len(buf) > len(magic):
            buf.pop(0)
        if bytes(buf) == magic:
            return True
    return False


# ────────────────────────────────────────────
def save_wav(raw_bytes: bytes, filename: str) -> bool:
    n_samples = len(raw_bytes) // 2
    if n_samples == 0:
        print("⚠️  Không có dữ liệu audio.")
        return False

    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw_bytes)

    duration = n_samples / SAMPLE_RATE
    kb       = len(raw_bytes) / 1024
    print(f"\n{'─'*52}")
    print(f"💾 File      : {filename}")
    print(f"⏱️  Thời lượng : {duration:.2f}s  ({n_samples:,} samples)")
    print(f"📦 Kích thước : {kb:.1f} KB")
    print(f"🎵 Định dạng  : {SAMPLE_RATE} Hz | 16-bit | Mono")
    print(f"{'─'*52}")
    return True


# ────────────────────────────────────────────
def draw_progress(elapsed, duration, n_bytes, debug_avg):
    pct    = min(elapsed / duration * 100, 100)
    filled = int(pct // 4)
    bar    = "█" * filled + "░" * (25 - filled)
    left   = max(0.0, duration - elapsed)
    n_samp = n_bytes // 2
    print(f"\r  [{bar}] {pct:5.1f}%  còn {left:.1f}s  "
          f"samples={n_samp:,}  vol≈{debug_avg:5.0f}  ",
          end="", flush=True)


# ────────────────────────────────────────────
def record(port: str, duration: float, output: str, baud: int, debug: bool):
    print(f"\n🔌 Mở cổng {port} @ {baud} baud…")
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except serial.SerialException as e:
        print(f"❌ Lỗi mở cổng: {e}")
        sys.exit(1)

    print("⏳ Đợi ESP32 (2s)…")
    time.sleep(2)
    ser.reset_input_buffer()

    # ── Gửi lệnh 'R' để bắt đầu stream ─────
    print("📤 Gửi lệnh ghi âm tới ESP32…")
    ser.write(b'R')
    ser.flush()

    # ── Chờ magic start bytes ────────────────
    print("⏳ Chờ xác nhận từ ESP32…")
    if wait_for_magic(ser, MAGIC_START, timeout=5):
        print("✅ ESP32 bắt đầu stream PCM.")
    else:
        print("⚠️  Không nhận được magic start – vẫn tiếp tục (có thể bị lệch sync).")

    print(f"🎙️  Đang ghi {duration}s…  (Nhấn Ctrl+C để dừng sớm)\n")

    audio_buf  = bytearray()
    start      = time.time()
    last_vol   = 0.0
    chunk_size = 512  # bytes mỗi lần đọc

    try:
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            waiting = ser.in_waiting
            if waiting == 0:
                time.sleep(0.001)
                continue

            chunk = ser.read(min(waiting, chunk_size))
            if not chunk:
                continue

            # Debug mode: in hex
            if debug:
                print(" ".join(f"{b:02X}" for b in chunk[:32]), "…")
                continue

            audio_buf.extend(chunk)

            # Tính volume xấp xỉ từ chunk
            n = (len(chunk) // 2) * 2
            if n >= 2:
                vals   = struct.unpack_from(f"<{n//2}h", chunk[:n])
                last_vol = sum(abs(v) for v in vals) / len(vals)

            draw_progress(elapsed, duration, len(audio_buf), last_vol)

    except KeyboardInterrupt:
        print("\n⚡ Dừng sớm.")

    # ── Gửi lệnh dừng ────────────────────────
    ser.write(b'S')
    ser.flush()
    time.sleep(0.3)

    # Đọc nốt data còn trong buffer
    remaining = ser.read(ser.in_waiting)
    if remaining and not debug:
        # Cắt bỏ end marker nếu có
        idx = remaining.find(MAGIC_END)
        audio_buf.extend(remaining[:idx] if idx != -1 else remaining)

    ser.close()
    print(f"\n🔌 Đã đóng cổng. Tổng nhận: {len(audio_buf):,} bytes")

    if debug:
        print("ℹ️  Chế độ debug: không lưu file.")
        return

    # Căn chỉnh: loại bỏ byte lẻ cuối
    if len(audio_buf) % 2 != 0:
        audio_buf = audio_buf[:-1]

    save_wav(bytes(audio_buf), output)

    # Kiểm tra nhanh chất lượng
    n = len(audio_buf) // 2
    if n > 0:
        vals    = struct.unpack(f"<{n}h", audio_buf)
        peak    = max(abs(v) for v in vals)
        avg_vol = sum(abs(v) for v in vals) / n
        print(f"\n📊 Kiểm tra nhanh:")
        print(f"   Peak amplitude : {peak:,}  (max=32767)")
        print(f"   Average volume : {avg_vol:.1f}")
        if peak < 100:
            print("   ⚠️  Peak rất thấp → kiểm tra lại kết nối INMP441 hoặc channel (L/R pin)")
        elif peak < 500:
            print("   ⚠️  Tín hiệu yếu → micro có thể bị che hoặc channel sai")
        else:
            print("   ✅ Tín hiệu OK")


# ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Ghi âm từ ESP32-S3 + INMP441 → .wav")
    parser.add_argument("-p", "--port",   help="Cổng serial (VD: COM3, /dev/ttyUSB0)")
    parser.add_argument("-d", "--duration", type=float, default=5.0,
                        help="Thời gian ghi (giây). Mặc định: 5")
    parser.add_argument("-o", "--output", help="Tên file .wav output")
    parser.add_argument("-b", "--baud",   type=int, default=BAUD_RATE,
                        help=f"Baud rate (mặc định: {BAUD_RATE})")
    parser.add_argument("--debug", action="store_true",
                        help="In raw hex bytes để kiểm tra data nhận được")
    args = parser.parse_args()

    port = args.port or choose_port()

    if args.output:
        out = args.output if args.output.lower().endswith(".wav") else args.output + ".wav"
    else:
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = f"recording_{ts}.wav"

    record(port, args.duration, out, args.baud, args.debug)


if __name__ == "__main__":
    main()