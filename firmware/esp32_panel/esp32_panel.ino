/*
 * TAMBAH DAYA VIRTUAL - kerangka firmware ESP32 (BELUM DIUJI di perangkat keras)
 *
 * Alur: ukur arus total panel -> perbarui model termal MCB -> bila pemanasan mendekati
 * ambang aman, pindahkan alat yang boleh dipindah ke jalur baterai/inverter.
 *
 * ATURAN KESELAMATAN (jangan dilonggarkan):
 *  - Relay dipasang NORMALLY CLOSED ke jalur PLN: bila ESP32 mati, alat tetap tersambung ke PLN.
 *  - Pindah PLN <-> inverter harus BREAK-BEFORE-MAKE: putus dulu, tunggu JEDA_PINDAH_MS, baru sambung.
 *    Keluaran inverter TIDAK BOLEH tersambung ke jaringan PLN walau sesaat.
 *  - Jeda minimum antar perpindahan (MIN_JEDA_AKSI_MS) agar motor/kompresor tidak hidup-mati berulang.
 *  - Kode ini TIDAK menyentuh MCB pembatas PLN di meteran (disegel, milik PLN).
 *  - Pakai RCBO pada panel uji; uji pertama di laboratorium dengan pendampingan dosen.
 *
 * TODO: kalibrasi KAL_I, ukur TAU_MENIT dan AMBANG dari uji waktu trip MCB yang dipakai.
 */
#include <math.h>

const int PIN_I = 34;                 // ADC1, sensor arus total
const int PIN_RELAY_PLN = 25;         // kontak ke jalur PLN
const int PIN_RELAY_INV = 26;         // kontak ke jalur inverter
const int N_SAMPEL = 2000;

const float IN_MCB = 4.0f;            // arus nominal MCB panel uji [A]
const float TAU_MENIT = 20.0f;        // TODO ukur
const float THETA_AMAN = 1.3f;        // ambang tindakan; trip model ~1,6 (TODO dari datasheet)
const float THETA_LEPAS = 1.0f;       // kembali ke PLN bila di bawah ini
const unsigned long JEDA_PINDAH_MS = 200;
const unsigned long MIN_JEDA_AKSI_MS = 180000UL;   // 3 menit
float KAL_I = 1.0f;                   // TODO kalibrasi: ampere per unit ADC

float theta = 0.70f;                  // pemanasan model termal (relatif)
bool diBaterai = false;
unsigned long terakhirAksi = 0, terakhirHitung = 0;

float bacaIrms() {
  static float off = 2048;
  double s2 = 0;
  for (int k = 0; k < N_SAMPEL; k++) {
    int r = analogRead(PIN_I);
    off += (r - off) * 0.001f;
    float i = (r - off) * KAL_I;
    s2 += i * i;
    delayMicroseconds(100);
  }
  return sqrt(s2 / N_SAMPEL);
}

void keBaterai() {
  digitalWrite(PIN_RELAY_PLN, LOW);   // putus dulu (break)
  delay(JEDA_PINDAH_MS);
  digitalWrite(PIN_RELAY_INV, HIGH);  // baru sambung (make)
  diBaterai = true;
}

void keJalurPLN() {
  digitalWrite(PIN_RELAY_INV, LOW);
  delay(JEDA_PINDAH_MS);
  digitalWrite(PIN_RELAY_PLN, HIGH);
  diBaterai = false;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_RELAY_PLN, OUTPUT);
  pinMode(PIN_RELAY_INV, OUTPUT);
  digitalWrite(PIN_RELAY_INV, LOW);
  digitalWrite(PIN_RELAY_PLN, HIGH);  // keadaan awal: semua dari PLN
  // TODO: tambahkan koneksi WiFi dan kirim data seperti firmware METER-AIR-TANAH
}

void loop() {
  float irms = bacaIrms();            // arus yang dilihat sensor, termasuk alat yang ada di jalur baterai?
                                      // TODO: sensor harus di jalur PLN saja agar mewakili beban pada MCB
  unsigned long now = millis();
  float dtMenit = (now - terakhirHitung) / 60000.0f;
  terakhirHitung = now;

  theta += dtMenit * (((irms / IN_MCB) * (irms / IN_MCB)) - theta) / TAU_MENIT;

  bool boleh = (now - terakhirAksi) >= MIN_JEDA_AKSI_MS;
  if (!diBaterai && theta > THETA_AMAN && boleh) { keBaterai(); terakhirAksi = now; }
  else if (diBaterai && theta < THETA_LEPAS && boleh) { keJalurPLN(); terakhirAksi = now; }

  Serial.printf("Irms=%.2f A  theta=%.3f  baterai=%d\n", irms, theta, diBaterai);
}
