#pragma once
#include <stdint.h>
#include <math.h>

namespace module_test {
constexpr uint32_t SAMPLE_HZ = 2000;
constexpr uint32_t BLOCK_SAMPLES = SAMPLE_HZ / 50; // 20 ms ở tần số lấy mẫu danh định
constexpr float ADC_REFERENCE_V = 3.3f; // Đo nguồn 3V3 và điều chỉnh nếu cần.
constexpr float CURRENT_GAIN = 1.0f;    // Chỉ hiệu chỉnh theo giá trị RMS chuẩn đo thực tế.
constexpr float CURRENT_THRESHOLD_A = 0.40f;
constexpr float BURDEN_OHM = 150.0f;
constexpr float CT_RATIO = 1000.0f;     // Người dùng đã xác nhận tỷ số; một lượt dây sơ cấp.
constexpr float LIGHT_ON_DELTA_V = 0.050f; // Giá trị khởi đầu; kiểm tra trên mạch thực.
constexpr float LIGHT_OFF_DELTA_V = 0.025f;
constexpr uint32_t COINCIDENCE_MS = 200;
constexpr uint16_t FLAG_ADC_CLIPPED = 1;
constexpr uint16_t FLAG_SAMPLE_TIMING = 2;
constexpr uint16_t FLAG_QUEUE_FULL = 4;

struct Block {
  uint32_t sum = 0;
  uint64_t sum_squares = 0;
  uint32_t count = 0;
  uint16_t light_peak = 0;
  uint16_t flashes = 0;
  uint16_t flags = 0;
  uint32_t end_sample = 0;
};

inline float rmsAmps(uint32_t sum, uint64_t squares, uint32_t count) {
  if (!count) return 0;
  const double mean = double(sum) / count;
  double variance = double(squares) / count - mean * mean;
  if (variance < 0) variance = 0;
  return float(sqrt(variance) * ADC_REFERENCE_V / 4095.0 *
               CT_RATIO / BURDEN_OHM * CURRENT_GAIN);
}

// Bộ kích Schmitt: đếm một lần tại cạnh xuống của xung đạt điều kiện.
// Xung đi qua mốc báo cáo được tính vào giây chứa cạnh xuống của xung.
class FlashDetector {
 public:
  explicit FlashDetector(uint16_t baseline) : baseline_(baseline) {}
  bool sample(uint16_t raw, uint32_t tick) {
    const float on = baseline_ + LIGHT_ON_DELTA_V * 4095 / ADC_REFERENCE_V;
    const float off = baseline_ + LIGHT_OFF_DELTA_V * 4095 / ADC_REFERENCE_V;
    if (!high_ && raw >= on) { high_ = true; rising_ = tick; }
    else if (high_ && raw <= off) {
      high_ = false;
      const uint32_t width = tick - rising_;
      // Chấp nhận xung dài 1..100 ms, các lần đếm chớp cách nhau ít nhất 50 ms.
      if (width >= SAMPLE_HZ / 1000 && width <= SAMPLE_HZ / 10 &&
          (!have_last_ || tick - last_ >= SAMPLE_HZ / 20)) {
        last_ = tick; have_last_ = true; return true;
      }
    }
    return false;
  }
 private:
  uint16_t baseline_;
  uint32_t rising_ = 0, last_ = 0;
  bool high_ = false, have_last_ = false;
};

class Coincidence {
 public:
  bool update(float amps, bool flash, uint32_t now_ms) {
    if (amps > CURRENT_THRESHOLD_A) { current_ms_ = now_ms; have_current_ = true; }
    if (flash) { flash_ms_ = now_ms; have_flash_ = true; }
    return have_current_ && have_flash_ &&
           uint32_t(now_ms - current_ms_) <= COINCIDENCE_MS &&
           uint32_t(now_ms - flash_ms_) <= COINCIDENCE_MS;
  }
 private:
  uint32_t current_ms_ = 0, flash_ms_ = 0;
  bool have_current_ = false, have_flash_ = false;
};
} // Kết thúc không gian tên module_test
