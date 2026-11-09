#include <Arduino.h>
#include <HardwareTimer.h>
#include "test_logic.h"

using namespace module_test;
HardwareSerial rs485(PA10, PA9); // Chân nhận RX, chân truyền TX
HardwareTimer sampleTimer(TIM2);
FlashDetector light(2048);
Coincidence coincidence;

constexpr uint8_t QUEUE_SIZE = 16;
Block queue[QUEUE_SIZE];
volatile uint8_t head = 0, tail = 0;
volatile uint16_t stickyFaults = 0;
Block collecting;
uint32_t tick = 0, lastSampleUs = 0;
bool firstTick = true;

void sampleInputs() {
  const uint32_t now = micros();
  if (!firstTick && uint32_t(now - lastSampleUs) > 750)
    collecting.flags |= FLAG_SAMPLE_TIMING;
  firstTick = false;
  lastSampleUs = now;
  const uint16_t current = analogRead(PA0);
  const uint16_t optical = analogRead(PA1);
  ++tick;
  collecting.sum += current;
  collecting.sum_squares += uint64_t(current) * current;
  ++collecting.count;
  if (optical > collecting.light_peak) collecting.light_peak = optical;
  if (light.sample(optical, tick)) ++collecting.flashes;
  if (current <= 1 || current >= 4094 || optical <= 1 || optical >= 4094)
    collecting.flags |= FLAG_ADC_CLIPPED;
  if (collecting.count == BLOCK_SAMPLES) {
    collecting.end_sample = tick;
    const uint8_t next = (head + 1) % QUEUE_SIZE;
    if (next == tail) stickyFaults |= FLAG_QUEUE_FULL;
    else { queue[head] = collecting; head = next; }
    collecting = Block{};
  }
}

bool popBlock(Block &out) {
  noInterrupts();
  if (head == tail) { interrupts(); return false; }
  out = queue[tail];
  tail = (tail + 1) % QUEUE_SIZE;
  out.flags |= stickyFaults;
  stickyFaults = 0;
  interrupts();
  return true;
}

void transmit(const char *text) {
  digitalWrite(PB0, HIGH); // EN nối chung DE và /RE trên module MAX3485 của node
  delayMicroseconds(10);
  rs485.print(text);
  rs485.flush(); // Lõi Arduino STM32 chờ truyền hoàn tất (cờ TC).
  digitalWrite(PB0, LOW);
}

void setup() {
  pinMode(PB0, OUTPUT);
  digitalWrite(PB0, LOW);
  pinMode(PA0, INPUT_ANALOG);
  pinMode(PA1, INPUT_ANALOG);
  analogReadResolution(12);
  rs485.begin(115200, SERIAL_8N1);
  // Trong 1 giây đầu: tắt LED, để cảm biến nhận ánh sáng môi trường thực tế.
  uint32_t sum = 0;
  const uint32_t started = millis();
  uint32_t count = 0;
  while (uint32_t(millis() - started) < 1000) {
    sum += analogRead(PA1); ++count; delayMicroseconds(500);
  }
  light = FlashDetector(sum / count);
  sampleTimer.setOverflow(SAMPLE_HZ, HERTZ_FORMAT);
  sampleTimer.attachInterrupt(sampleInputs);
  sampleTimer.resume();
}

void loop() {
  static uint32_t seq = 0, sum = 0, samples = 0;
  static uint64_t squares = 0;
  static uint16_t peak = 0, flashes = 0, flags = 0;
  static bool alarm = false;
  Block b;
  while (popBlock(b)) {
    const uint32_t nodeMs = uint32_t(uint64_t(b.end_sample) * 1000 / SAMPLE_HZ);
    alarm |= coincidence.update(rmsAmps(b.sum, b.sum_squares, b.count), b.flashes > 0, nodeMs);
    sum += b.sum; squares += b.sum_squares; samples += b.count;
    if (b.light_peak > peak) peak = b.light_peak;
    flashes += b.flashes; flags |= b.flags;
    if (samples >= SAMPLE_HZ) {
      const uint32_t mA = lroundf(rmsAmps(sum, squares, samples) * 1000);
      const uint32_t mV = lroundf(peak * ADC_REFERENCE_V / 4095 * 1000);
      char payload[120], frame[130];
      snprintf(payload, sizeof(payload), "DATA,%lu,%lu,%lu,%lu,%u,%u,%u",
               (unsigned long)++seq, (unsigned long)nodeMs, (unsigned long)mA,
               (unsigned long)mV, unsigned(flashes), unsigned(alarm), unsigned(flags));
      uint8_t checksum = 0;
      for (const char *p = payload; *p; ++p) checksum ^= uint8_t(*p);
      snprintf(frame, sizeof(frame), "%s*%02X\n", payload, checksum);
      transmit(frame);
      sum = samples = 0; squares = 0; peak = flashes = flags = 0; alarm = false;
    }
  }
}
