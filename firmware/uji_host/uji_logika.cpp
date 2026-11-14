// Uji logika firmware esp32_panel di komputer.
//   g++ -std=c++17 -O2 -o uji_logika firmware/uji_host/uji_logika.cpp && ./uji_logika
// Skenario: beban dasar 3 A, lalu beban total 7 A pada MCB 4 A. Alat yang dipindah menarik 4,5 A.
// Yang diperiksa:
//   1. Vrms, Irms, daya aktif yang dihitung firmware sesuai sinyal masukan (galat < 2 %).
//   2. Urutan relay selalu putus-dulu-baru-sambung, dengan jeda >= JEDA_PINDAH_MS.
//   3. Relay inverter tidak pernah hidup saat relay pindah mati.
//   4. Dengan kendali, pemanasan model (theta) tidak mencapai THETA_TRIP.
//   5. Alat bertahan di baterai >= MIN_JEDA_AKSI_MS sebelum kembali ke PLN.
#include "arduino_tiruan.h"
#include "../esp32_panel/esp32_panel.ino"

unsigned long long waktu_us = 0;
static const double PI2 = 6.283185307179586;
static const double V_RMS = 220.0, PF = 0.95;
static const double KV = 0.25, KI = 0.01;        // volt dan ampere per unit ADC pada uji ini
static double arus_total = 3.0, arus_alat_pindah = 4.5;
static bool koil_pindah = false, koil_inv = false;
static unsigned long long t_pindah_berubah = 0, t_aksi_terakhir = 0;
static int gagal = 0, n_aksi = 0;
static double theta_maks = 0, v_akhir = 0, i_akhir = 0, p_akhir = 0;

static void periksa(bool ok, const char *pesan) {
  if (!ok) { gagal++; std::printf("GAGAL: %s (t = %.1f s)\n", pesan, waktu_us / 1e6); }
}

int analogRead(int pin) {
  double t = waktu_us / 1e6, sudut = PI2 * 50.0 * t;
  // arus di jalur PLN: bila alat sudah dipindah (koil pindah hidup), arusnya tidak lewat sensor PLN
  double irms = arus_total - (koil_pindah ? arus_alat_pindah : 0.0);
  double nilai = (pin == PIN_V) ? V_RMS * std::sqrt(2.0) * std::sin(sudut) / KV
                                : irms * std::sqrt(2.0) * std::sin(sudut - std::acos(PF)) / KI;
  int adc = (int)std::lround(2048 + nilai);
  return adc < 0 ? 0 : (adc > 4095 ? 4095 : adc);
}

void digitalWrite(int pin, int nilai) {
  bool koil = RELAY_AKTIF_LOW ? (nilai == LOW) : (nilai == HIGH);
  if (pin == PIN_RELAY_PINDAH) {
    if (koil != koil_pindah) {
      if (!koil) periksa(!koil_inv, "relay pindah kembali ke PLN saat inverter masih tersambung");
      koil_pindah = koil; t_pindah_berubah = waktu_us;
    }
  } else if (pin == PIN_RELAY_INV) {
    if (koil && !koil_inv) {
      periksa(koil_pindah, "inverter disambung saat alat masih di jalur PLN");
      periksa(waktu_us - t_pindah_berubah >= JEDA_PINDAH_MS * 1000ULL, "jeda putus-sambung terlalu pendek");
    }
    koil_inv = koil;
  }
}

void barisSerial(const char *teks) {
  if (std::strncmp(teks, "AKSI,", 5) == 0) {
    bool kembali = std::strcmp(teks + 5, "kembali_ke_pln") == 0;
    if (n_aksi > 0) periksa(waktu_us - t_aksi_terakhir >= (kembali ? MIN_JEDA_AKSI_MS : MIN_JEDA_LINDUNG_MS) * 1000ULL,
                            "jeda antar aksi terlalu pendek");
    t_aksi_terakhir = waktu_us; n_aksi++;
    std::printf("  t = %6.1f s  %s\n", waktu_us / 1e6, teks + 5);
  } else if (std::strncmp(teks, "DATA,", 5) == 0) {
    double v, i, p, pf, q, th; int bat;
    if (std::sscanf(teks + 5, "%lf,%lf,%lf,%lf,%lf,%lf,%d", &v, &i, &p, &pf, &q, &th, &bat) == 7) {
      v_akhir = v; i_akhir = i; p_akhir = p;
      if (th > theta_maks) theta_maks = th;
    } else periksa(false, "baris DATA tidak sesuai format perekam");
  }
}

int main() {
  KAL_V = (float)KV; KAL_I = (float)KI;
  setup();
  periksa(!koil_pindah && !koil_inv, "keadaan awal harus: alat di PLN, inverter terlepas");

  while (waktu_us < 60ULL * 1000000ULL) loop();                 // 1 menit beban dasar
  periksa(std::fabs(v_akhir - V_RMS) / V_RMS < 0.02, "Vrms meleset > 2 %");
  periksa(std::fabs(i_akhir - 3.0) / 3.0 < 0.02, "Irms meleset > 2 %");
  periksa(std::fabs(p_akhir - V_RMS * 3.0 * PF) / (V_RMS * 3.0 * PF) < 0.02, "daya aktif meleset > 2 %");
  std::printf("Ukur beban dasar: %.1f V, %.3f A, %.1f W (masukan 220 V, 3 A, %.1f W)\n",
              v_akhir, i_akhir, p_akhir, V_RMS * 3.0 * PF);

  arus_total = 7.0;                                             // beban besar menyala
  while (waktu_us < 120ULL * 60ULL * 1000000ULL) loop();        // 2 jam
  periksa(n_aksi >= 1, "tidak ada aksi kendali padahal beban melebihi batas");
  periksa(theta_maks < THETA_TRIP, "theta mencapai ambang trip walau kendali aktif");
  periksa(theta_maks < MARGIN * THETA_TRIP * 1.02, "theta melewati batas aman lebih dari 2 %");
  std::printf("Aksi kendali: %d; theta maksimum: %.3f (ambang trip %.2f)\n", n_aksi, theta_maks, THETA_TRIP);
  std::printf(gagal ? "HASIL: %d pemeriksaan GAGAL\n" : "HASIL: semua pemeriksaan LULUS\n", gagal);
  return gagal ? 1 : 0;
}
