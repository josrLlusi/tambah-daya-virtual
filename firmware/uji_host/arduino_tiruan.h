// Arduino tiruan untuk menjalankan logika firmware di komputer (bukan di ESP32).
// Hanya menguji LOGIKA (hitung daya, model termal, urutan relay). Tidak menguji ADC, pewaktuan nyata, atau rangkaian.
#pragma once
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0

extern unsigned long long waktu_us;          // jam simulasi
int analogRead(int pin);                     // diisi oleh uji_logika.cpp
void digitalWrite(int pin, int nilai);       // diisi oleh uji_logika.cpp
void barisSerial(const char *teks);          // diisi oleh uji_logika.cpp
inline void pinMode(int, int) {}
inline void analogReadResolution(int) {}
inline unsigned long millis() { return (unsigned long)(waktu_us / 1000ULL); }
inline void delay(unsigned long ms) { waktu_us += (unsigned long long)ms * 1000ULL; }
inline void delayMicroseconds(unsigned int us) { waktu_us += us; }

struct SerialTiruan {
  void begin(long) {}
  void println(const char *s) { barisSerial(s); }
  void printf(const char *fmt, ...) {
    char buf[256];
    va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap);
    size_t n = strlen(buf);
    if (n && buf[n - 1] == '\n') buf[n - 1] = 0;
    barisSerial(buf);
  }
};
static SerialTiruan Serial;
