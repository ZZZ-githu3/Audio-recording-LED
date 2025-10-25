#include <Arduino.h>
#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>

#define I2S_WS 5
#define I2S_SCK 16
#define I2S_SD 6
#define SAMPLE_RATE 16000
#define LED_PIN 48
#define NUM_PIXELS 1
#define BUFFER_SIZE 1024

Adafruit_NeoPixel pixel(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("🔊 ESP32-S3 + INMP441 bắt đầu...");

  pixel.begin();
  pixel.clear();
  pixel.show();

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_start(I2S_NUM_0);

  Serial.println("✅ Sẵn sàng thu âm...");
}

void loop() {
  int32_t samples[BUFFER_SIZE];
  size_t bytes_read;
  i2s_read(I2S_NUM_0, (char *)samples, sizeof(samples), &bytes_read, portMAX_DELAY);

  int num_samples = bytes_read / 4;
  int16_t pcm[num_samples];
  long sum = 0;

  for (int i = 0; i < num_samples; i++) {
    int16_t s = samples[i] >> 11;
    pcm[i] = s;
    sum += abs(s);
  }

  int avg = sum / num_samples;
  Serial.println(avg);

  // LED báo âm thanh
  if (avg > 100) {
    pixel.setPixelColor(0, pixel.Color(0, 255, 0)); // xanh
    pixel.show();
  } else {
    pixel.clear();
    pixel.show();
  }

  // Gửi dữ liệu PCM sang máy tính (ghi file .wav)
  Serial.write((uint8_t *)pcm, num_samples * 2);
}
