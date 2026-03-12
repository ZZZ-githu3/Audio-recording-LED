/*
  ESP32-S3 + INMP441 – PCM Recorder
  ====================================
  Baud: 230400 (đủ bandwidth cho 16kHz PCM)

  Protocol:
    - Mặc định: in avg dạng text → xem Serial Monitor bình thường
    - Python gửi 'R' → ESP32 stream raw PCM 16-bit bytes
    - Python gửi 'S' → ESP32 dừng, về chế độ text

  Wiring INMP441:
    VDD → 3.3V  |  GND → GND
    WS  → GPIO5  |  SCK → GPIO16  |  SD → GPIO6
    L/R → GND  (LEFT channel)
*/

#include <Arduino.h>
#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>

#define I2S_WS      5
#define I2S_SCK     16
#define I2S_SD      6
#define SAMPLE_RATE 16000
#define LED_PIN     48
#define NUM_PIXELS  1
#define BUFFER_SIZE 256    // Nhỏ hơn để flush nhanh hơn

Adafruit_NeoPixel pixel(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);
int32_t raw[BUFFER_SIZE];
int16_t pcm[BUFFER_SIZE];
bool streaming = false;

void setLED(uint8_t r, uint8_t g, uint8_t b) {
  pixel.setPixelColor(0, pixel.Color(r, g, b));
  pixel.show();
}

void setup() {
  Serial.begin(230400);
  delay(500);

  pixel.begin();
  pixel.clear();
  pixel.show();

  i2s_config_t cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_RIGHT,  // L/R → GND = LEFT
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = BUFFER_SIZE,
    .use_apll             = false,
    .tx_desc_auto_clear   = false,
    .fixed_mclk           = 0
  };

  i2s_pin_config_t pins = {
    .bck_io_num   = I2S_SCK,
    .ws_io_num    = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);

  setLED(0, 0, 80);
  Serial.println("READY");
}

void loop() {
  // Nhận lệnh từ Python (byte đơn 'R' hoặc 'S')
  if (Serial.available()) {
    char c = (char)Serial.read();
    if (c == 'R') {
      i2s_zero_dma_buffer(I2S_NUM_0);
      streaming = true;
      setLED(255, 0, 0);       // Đỏ = đang ghi
      Serial.println("START"); // ACK — dòng text duy nhất trước khi stream
    } else if (c == 'S') {
      streaming = false;
      setLED(0, 0, 80);
      Serial.println("STOP");
    }
  }

  size_t bytes_read = 0;
  i2s_read(I2S_NUM_0, raw, sizeof(raw), &bytes_read, portMAX_DELAY);

  int n = bytes_read / sizeof(int32_t);
  if (n == 0) return;

  int64_t sum = 0;
  for (int i = 0; i < n; i++) {
    int16_t s = (int16_t)(raw[i] >> 16);
    pcm[i] = s;
    sum += abs(s);
  }

  if (streaming) {
    // Gửi thẳng raw PCM bytes — không println gì thêm
    Serial.write((uint8_t*)pcm, n * sizeof(int16_t));
  } else {
    // Chế độ monitor: in avg text bình thường
    int avg = (int)(sum / n);
    Serial.println(avg);
    if      (avg > 100 && avg <= 1000)   setLED(0, 255, 0);
    else if (avg > 1000)                 setLED(255, 200, 0);
    else if (avg > 0 && avg <= 100)     setLED(0, 0, 80);
    else                                setLED(0, 0, 0);
  }
}