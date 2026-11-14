/*
 * TAMBAH DAYA VIRTUAL - kerangka firmware ESP32 (BELUM DIUJI di perangkat keras)
 *
 * Alur: ukur tegangan dan arus total di jalur PLN -> hitung P, Q, faktor daya -> perbarui model termal MCB
 * -> bila pemanasan mendekati ambang aman, pindahkan alat yang boleh dipindah ke jalur baterai/inverter.
 *
 * Keluaran serial (untuk alat/perekam_serial.py), satu baris per jendela ukur (~0,3 detik):
 *   DATA,tegangan,arus,daya_aktif,faktor_daya,daya_reaktif,theta,baterai_aktif
 *
 * PENGKABELAN RELAY (lihat docs/pengkabelan.md):
 *  - Relay PINDAH (kontak tukar/SPDT, dua kutub: fasa dan netral):
 *      COM -> alat, NC -> jalur PLN, NO -> keluaran relay INVERTER.
 *    Koil mati = alat di PLN. Kontak tukar tidak bisa menyambung NC dan NO bersamaan.
 *  - Relay INVERTER (kontak NO, dua kutub): menyambung keluaran inverter ke terminal NO relay PINDAH.
 *    Koil mati = inverter terlepas.
 *  - Jadi bila ESP32 mati atau macet: kedua koil mati -> alat di PLN, inverter terlepas (fail-safe).
 *
 * ATURAN KESELAMATAN (jangan dilonggarkan):
 *  - Pindah PLN <-> inverter harus BREAK-BEFORE-MAKE: putus dulu, tunggu JEDA_PINDAH_MS, baru sambung.
 *    Keluaran inverter TIDAK BOLEH tersambung ke jaringan PLN walau sesaat.
 *  - RELAY_AKTIF_LOW harus sesuai modul relay yang dipakai. Disarankan modul "high level trigger"
 *    (jumper di posisi H) dan RELAY_AKTIF_LOW = false: bila ESP32 kehilangan daya, pin menjadi 0 V
 *    dan koil mati. Pada modul "low level trigger", pin 0 V justru MENGHIDUPKAN koil.
 *  - Uji dulu TANPA tegangan 220 V: saat ESP32 menyala normal dan saat kabel USB ESP32 dicabut,
 *    kedua relay harus dalam keadaan koil mati (lampu modul padam).
 *  - Alat yang dipindah akan mati sekitar 0,2 detik saat berpindah. Pilih alat yang tahan terhadap itu
 *    (pemanas, setrika, lampu). JANGAN memilih kompresor (kulkas, freezer, AC): kompresor yang dihidupkan
 *    kembali seketika dapat macet dan rusak.
 *  - Setelah pindah, alat ditahan minimal MIN_JEDA_AKSI_MS di baterai agar tidak berpindah bolak-balik.
 *  - Kode ini TIDAK menyentuh MCB pembatas PLN di meteran (disegel, milik PLN).
 *  - Pakai RCBO pada panel uji; uji pertama di laboratorium dengan pendampingan dosen.
 *
 * TODO: kalibrasi KAL_V dan KAL_I; isi TAU_DETIK dan THETA_TRIP dari analisis/fit_mcb.py
 *       (berkas parameter_mcb.json) untuk MCB yang dipakai.
 */
#include <math.h>

const int PIN_I = 34;                 // ADC1, sensor arus total di jalur PLN (setelah MCB, sebelum percabangan)
const int PIN_V = 35;                 // ADC1, sensor tegangan
const int PIN_RELAY_PINDAH = 25;      // relay kontak tukar: koil mati = alat di PLN, koil hidup = alat lepas dari PLN
const int PIN_RELAY_INV = 26;         // relay inverter: koil hidup = inverter tersambung ke sisi NO relay pindah
const bool RELAY_AKTIF_LOW = false;   // false: modul relay aktif saat pin HIGH (jumper modul di posisi H, disarankan)
                                      // true : modul relay aktif saat pin LOW
const int N_SAMPEL = 2000;

const float IN_MCB = 4.0f;            // arus nominal MCB panel uji [A]; ubah bila memakai MCB 2 A
float TAU_DETIK = 1200.0f;            // TODO dari parameter_mcb.json
float THETA_TRIP = 1.6f;              // TODO dari parameter_mcb.json
const float MARGIN = 0.80f;           // bertindak saat theta mencapai 80% ambang trip
const float THETA_LEPAS = 1.0f;       // kembali ke PLN bila di bawah ini (dan beban lain turun)
const unsigned long JEDA_PINDAH_MS = 200;
const unsigned long MIN_JEDA_AKSI_MS = 180000UL;   // alat minimal 3 menit di baterai sebelum boleh kembali ke PLN
const unsigned long MIN_JEDA_LINDUNG_MS = 10000UL; // jeda minimal sebelum aksi pelindung (pindah/tunda) berikutnya
const bool PAKAI_BATERAI = true;      // true: alat dipindah ke inverter; false: alat hanya ditunda (diputus sementara)
float KAL_V = 1.0f;                   // TODO kalibrasi: volt per unit ADC
float KAL_I = 1.0f;                   // TODO kalibrasi: ampere per unit ADC

float theta = 0.0f;                   // pemanasan model termal (relatif); 0 = MCB dingin saat ESP32 menyala
bool diBaterai = false;               // true = alat sedang lepas dari PLN (di baterai, atau ditunda)
bool pernahAksi = false;
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

// koil = true -> koil relay diberi arus; koil = false -> koil mati (keadaan aman)
void setKoil(int pin, bool koil) {
  digitalWrite(pin, (koil != RELAY_AKTIF_LOW) ? HIGH : LOW);
}

void keBaterai() {
  setKoil(PIN_RELAY_PINDAH, true);    // putus dari PLN dulu (break)
  if (PAKAI_BATERAI) {
    delay(JEDA_PINDAH_MS);
    setKoil(PIN_RELAY_INV, true);     // baru sambung inverter (make)
  }
  diBaterai = true;
  Serial.println(PAKAI_BATERAI ? "AKSI,pindah_ke_baterai" : "AKSI,tunda_alat");
}

void keJalurPLN() {
  setKoil(PIN_RELAY_INV, false);      // lepas inverter dulu
  delay(JEDA_PINDAH_MS);
  setKoil(PIN_RELAY_PINDAH, false);   // baru kembali ke PLN
  diBaterai = false;
  Serial.println("AKSI,kembali_ke_pln");
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_RELAY_INV, OUTPUT);
  setKoil(PIN_RELAY_INV, false);      // keadaan awal: inverter terlepas
  pinMode(PIN_RELAY_PINDAH, OUTPUT);
  setKoil(PIN_RELAY_PINDAH, false);   // keadaan awal: semua dari PLN
  terakhirHitung = millis();
}

void loop() {
  Ukur u = baca();
  unsigned long now = millis();
  float dt = (now - terakhirHitung) / 1000.0f;
  terakhirHitung = now;

  float r = u.irms / IN_MCB;
  theta += dt * (r * r - theta) / TAU_DETIK;

  // Aksi pelindung (lepas dari PLN) tidak boleh tertahan lama: MCB turun lebih merugikan.
  // Kembali ke PLN ditahan minimal MIN_JEDA_AKSI_MS agar alat tidak berpindah bolak-balik.
  unsigned long sejak = now - terakhirAksi;
  if (!diBaterai && theta > MARGIN * THETA_TRIP && (!pernahAksi || sejak >= MIN_JEDA_LINDUNG_MS)) {
    keBaterai(); terakhirAksi = millis(); pernahAksi = true;
  } else if (diBaterai && theta < THETA_LEPAS && sejak >= MIN_JEDA_AKSI_MS) {
    keJalurPLN(); terakhirAksi = millis(); pernahAksi = true;
  }

  Serial.printf("DATA,%.1f,%.3f,%.1f,%.3f,%.1f,%.4f,%d\n", u.vrms, u.irms, u.p, u.pf, u.q, theta, diBaterai);
}
