/*
 * TAMBAH DAYA VIRTUAL - kerangka firmware ESP32 (BELUM DIUJI di perangkat keras)
 *
 * Alur: ukur tegangan dan arus total di jalur PLN -> hitung P, Q, faktor daya -> perbarui model termal MCB
 * -> bila pemanasan mendekati ambang aman, pindahkan alat yang boleh dipindah ke jalur baterai/inverter.
 *
 * Keluaran serial (untuk alat/perekam_serial.py), satu baris per jendela ukur (~0,3 detik):
 *   DATA,tegangan,arus,daya_aktif,faktor_daya,daya_reaktif,theta,baterai_aktif
 *
 * ATURAN KESELAMATAN (jangan dilonggarkan):
 *  - Relay dipasang NORMALLY CLOSED ke jalur PLN: bila ESP32 mati, alat tetap tersambung ke PLN.
 *  - Pindah PLN <-> inverter harus BREAK-BEFORE-MAKE: putus dulu, tunggu JEDA_PINDAH_MS, baru sambung.
 *    Keluaran inverter TIDAK BOLEH tersambung ke jaringan PLN walau sesaat.
 *  - Jeda minimum antar perpindahan (MIN_JEDA_AKSI_MS) agar motor/kompresor tidak hidup-mati berulang.
 *  - Kode ini TIDAK menyentuh MCB pembatas PLN di meteran (disegel, milik PLN).
 *  - Pakai RCBO pada panel uji; uji pertama di laboratorium dengan pendampingan dosen.
 *
 * TODO: kalibrasi KAL_V dan KAL_I; isi TAU_DETIK dan THETA_TRIP dari analisis/fit_mcb.py
 *       (berkas parameter_mcb.json) untuk MCB yang dipakai.
 */
#include <math.h>

const int PIN_I = 34;                 // ADC1, sensor arus total di jalur PLN (setelah MCB, sebelum percabangan)
const int PIN_V = 35;                 // ADC1, sensor tegangan
const int PIN_RELAY_PLN = 25;         // kontak alat yang dipindah: jalur PLN
const int PIN_RELAY_INV = 26;         // kontak alat yang dipindah: jalur inverter
const int N_SAMPEL = 2000;

const float IN_MCB = 4.0f;            // arus nominal MCB panel uji [A]
float TAU_DETIK = 1200.0f;            // TODO dari parameter_mcb.json
float THETA_TRIP = 1.6f;              // TODO dari parameter_mcb.json
const float MARGIN = 0.80f;           // bertindak saat theta mencapai 80% ambang trip
const float THETA_LEPAS = 1.0f;       // kembali ke PLN bila di bawah ini (dan beban lain turun)
const unsigned long JEDA_PINDAH_MS = 200;
const unsigned long MIN_JEDA_AKSI_MS = 180000UL;   // 3 menit
float KAL_V = 1.0f;                   // TODO kalibrasi: volt per unit ADC
float KAL_I = 1.0f;                   // TODO kalibrasi: ampere per unit ADC

float theta = 0.0f;                   // pemanasan model termal (relatif); 0 = MCB dingin saat ESP32 menyala
bool diBaterai = false;
unsigned long terakhirAksi = 0, terakhirHitung = 0;

struct Ukur { float vrms, irms, p, q, pf; };

Ukur baca() {
  static float offV = 2048, offI = 2048;
  double sV2 = 0, sI2 = 0, sP = 0;
  for (int k = 0; k < N_SAMPEL; k++) {
    int rv = analogRead(PIN_V), ri = analogRead(PIN_I);
    offV += (rv - offV) * 0.001f; offI += (ri - offI) * 0.001f;
    float v = (rv - offV) * KAL_V, i = (ri - offI) * KAL_I;
    sV2 += v * v; sI2 += i * i; sP += v * i;
    delayMicroseconds(100);
  }
  Ukur u;
  u.vrms = sqrt(sV2 / N_SAMPEL);
  u.irms = sqrt(sI2 / N_SAMPEL);
  u.p = sP / N_SAMPEL;
  float s = u.vrms * u.irms;
  u.pf = s > 0.01f ? fabs(u.p) / s : 0;
  u.q = s > fabs(u.p) ? sqrt(s * s - u.p * u.p) : 0;   // besaran saja, tanpa tanda induktif/kapasitif
  return u;
}

void keBaterai() {
  digitalWrite(PIN_RELAY_PLN, LOW);   // putus dulu (break)
  delay(JEDA_PINDAH_MS);
  digitalWrite(PIN_RELAY_INV, HIGH);  // baru sambung (make)
  diBaterai = true;
  Serial.println("AKSI,pindah_ke_baterai");
}

void keJalurPLN() {
  digitalWrite(PIN_RELAY_INV, LOW);
  delay(JEDA_PINDAH_MS);
  digitalWrite(PIN_RELAY_PLN, HIGH);
  diBaterai = false;
  Serial.println("AKSI,kembali_ke_pln");
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_RELAY_PLN, OUTPUT);
  pinMode(PIN_RELAY_INV, OUTPUT);
  digitalWrite(PIN_RELAY_INV, LOW);
  digitalWrite(PIN_RELAY_PLN, HIGH);  // keadaan awal: semua dari PLN
  terakhirHitung = millis();
}

void loop() {
  Ukur u = baca();
  unsigned long now = millis();
  float dt = (now - terakhirHitung) / 1000.0f;
  terakhirHitung = now;

  float r = u.irms / IN_MCB;
  theta += dt * (r * r - theta) / TAU_DETIK;

  bool boleh = (now - terakhirAksi) >= MIN_JEDA_AKSI_MS;
  if (!diBaterai && theta > MARGIN * THETA_TRIP && boleh) { keBaterai(); terakhirAksi = now; }
  else if (diBaterai && theta < THETA_LEPAS && boleh) { keJalurPLN(); terakhirAksi = now; }

  Serial.printf("DATA,%.1f,%.3f,%.1f,%.3f,%.1f,%.4f,%d\n", u.vrms, u.irms, u.p, u.pf, u.q, theta, diBaterai);
}
