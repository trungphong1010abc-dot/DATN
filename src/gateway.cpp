// ESP32-WROOM-32: GPIO17 nối RXD (DI) của module, GPIO16 nhận từ TXD (RO) của module.
// Bo MAX13487E tự chuyển chiều truyền; chương trình không điều khiển GPIO21/EN.
// Xác nhận nguồn cấp của bo thực và đầu ra UART an toàn với mức 3,3 V trước khi nối dây.
#include <Arduino.h>

HardwareSerial nodeBus(2);
char line[160];
size_t length = 0;
bool discard = false;
uint32_t lastValid = 0, lastWarning = 0;

bool validFrame(const char *s) {
  if (strncmp(s, "DATA,", 5)) return false;
  const char *star = strchr(s, '*');
  if (!star || strlen(star + 1) != 2) return false;
  uint8_t checksum = 0;
  for (const char *p = s; p < star; ++p) checksum ^= uint8_t(*p);
  char *end;
  const unsigned long expected = strtoul(star + 1, &end, 16);
  return end == star + 3 && checksum == expected;
}

void setup() {
  Serial.begin(115200);
  nodeBus.begin(115200, SERIAL_8N1, 16, 17);
  Serial.println("#Gateway MAX13487E ready; waiting for node");
}

void loop() {
  while (nodeBus.available()) {
    const char c = nodeBus.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[length] = 0;
      if (!discard && validFrame(line)) {
        Serial.println(line); lastValid = millis();
      } else Serial.println("#WARN invalid RS485 frame");
      length = 0; discard = false;
    } else if (!discard) {
      if (length + 1 < sizeof(line)) line[length++] = c;
      else discard = true;
    }
  }
  if (uint32_t(millis() - lastValid) > 3000 && uint32_t(millis() - lastWarning) > 3000) {
    Serial.println("#WARN no valid node frame for 3 seconds");
    lastWarning = millis();
  }
}
