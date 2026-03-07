#include <Arduino.h>
#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>

#define I2S_WS 5
#define I2S_SCK 16
#define I2S_SD 6
#define SAMPLE_RATE 16000
#define LED_PIN 48
#define NUM_PIXELS 1
#define BUFFER_SIZE 512

Adafruit_NeoPixel pixel(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);
int32_t samples[BUFFER_SIZE];
int16_t pcm[BUFFER_SIZE]; 

void setup() {
  Serial.begin(921600);
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
    .communication_format = I2S_COMM_FORMAT_STAND_MSB,
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

  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("❌ I2S install lỗi: %d\n", err);
    return;
  }
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_start(I2S_NUM_0);
  Serial.println("✅ Sẵn sàng thu âm...");
}

void loop() {
  size_t bytes_read = 0;
  i2s_read(I2S_NUM_0, samples, sizeof(samples), &bytes_read, portMAX_DELAY);

  int num_samples = bytes_read / sizeof(int32_t);
  if(num_samples == 0) return; 
  int64_t sum = 0;

  for(int i = 0; i < num_samples; i++) {
    int16_t s = (int16_t)(samples[i] >> 16);
    pcm[i] = s;
    sum += abs(s);
  }

  int avg = (int)(sum / (num_samples * 1000));
  Serial.println(avg);
  delay(1000); 

  // LED báo âm thanh
  if (avg > 1000) {
    pixel.setPixelColor(0, pixel.Color(0, 255, 0)); // xanh
  } 
  else {
    pixel.setPixelColor(0, pixel.Color(0, 0, 0)); 
  }
  pixel.show(); 
}
