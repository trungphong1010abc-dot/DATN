#include <Arduino.h>

volatile uint16_t adc_current = 0;
volatile uint16_t adc_light = 0;

HardwareSerial rs485(PA10, PA9);
uint32_t sequence = 0;

void setup() {
  pinMode(PA0, INPUT_ANALOG);
  pinMode(PA1, INPUT_ANALOG);
  analogReadResolution(12);
  rs485.begin(9600, SERIAL_8N1);
}

void loop() {
  adc_current = analogRead(PA0);
  adc_light = analogRead(PA1);
  ++sequence;

  rs485.print("SEQ=");
  rs485.print(sequence);
  rs485.print(",I=");
  rs485.print(adc_current);
  rs485.print(",L=");
  rs485.print(adc_light);
  rs485.print("\r\n");

  delay(500);
}
