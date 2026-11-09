#include "test_logic.h"
#include <assert.h>
#include <stdio.h>
#include <initializer_list>
using namespace module_test;

int main() {
  // Thành phần lệch DC không được tính vào dòng điện RMS.
  assert(rmsAmps(2048 * 2000u, uint64_t(2048) * 2048 * 2000, 2000) == 0);
  for (float input : {0.24f, 0.48f}) {
    uint32_t sum = 0; uint64_t squares = 0;
    const double amplitude = input * BURDEN_OHM / CT_RATIO * 4095 / ADC_REFERENCE_V * sqrt(2.0);
    for (unsigned i = 0; i < SAMPLE_HZ; ++i) {
      uint16_t raw = lround(2048 + amplitude * sin(2 * 3.141592653589793 * 50 * i / SAMPLE_HZ));
      sum += raw; squares += uint64_t(raw) * raw;
    }
    assert(fabs(rmsAmps(sum, squares, SAMPLE_HZ) - input) < 0.002);
  }
  for (unsigned mode = 0; mode < 4; ++mode) {
    FlashDetector d(2048); Coincidence c;
    unsigned flashes = 0; bool alarm = false;
    for (unsigned tick = 1; tick <= SAMPLE_HZ * 20; ++tick) {
      const bool bright = mode >= 2 && tick % 400 < 20;
      const bool flash = d.sample(bright ? 2600 : 2048, tick);
      flashes += flash;
      alarm |= c.update(mode % 2 ? 0.48f : 0.24f, flash, tick * 1000u / SAMPLE_HZ);
    }
    assert(flashes == (mode >= 2 ? 100u : 0u));
    assert(alarm == (mode == 3));
  }
  FlashDetector continuous(2048);
  for (unsigned tick = 0; tick < SAMPLE_HZ; ++tick) assert(!continuous.sample(2600, tick));
  assert(!continuous.sample(2048, SAMPLE_HZ)); // Ánh sáng kéo dài không được tính là chớp 10 ms
  Coincidence late;
  assert(!late.update(0.48, false, 0));
  assert(!late.update(0.24, true, 300)); // Ngoài khoảng thời gian kết hợp hai sự kiện
  puts("PASS: RMS offset, 0.24/0.48 A, four cases, 100 flashes/20s, continuous light, timing window");
}
