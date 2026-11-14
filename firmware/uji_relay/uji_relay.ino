/*
 * UJI KERING RELAY - dijalankan TANPA tegangan 220 V dan TANPA inverter tersambung.
 * (BELUM DIUJI di perangkat keras)
 *
 * Tujuan: memastikan polaritas modul relay dan urutan putus-dulu-baru-sambung sebelum panel diberi tegangan.
 * Sketsa ini mengulang urutan berikut tiap 5 detik dan mencetak keadaannya di Serial Monitor (115200):
 *   1. AWAL      : kedua koil mati  -> stopkontak alat tersambung ke sisi PLN (NC)
 *   2. PUTUS     : koil PINDAH hidup -> stopkontak alat lepas dari PLN
 *   3. INVERTER  : koil INVERTER hidup -> stopkontak alat tersambung ke sisi inverter
 *   4. LEPAS     : koil INVERTER mati
 *   5. kembali ke AWAL
 *
 * Yang diperiksa dengan multimeter (mode kontinuitas), lihat docs/pengkabelan.md bagian uji kering:
 *   - Pada AWAL: lampu modul relay padam. Stopkontak alat tersambung ke kabel PLN, tidak ke kabel inverter.
 *   - Pada INVERTER: stopkontak alat tersambung ke kabel inverter, TIDAK ke kabel PLN.
 *   - Pada semua keadaan: kabel PLN dan kabel inverter tidak pernah tersambung satu sama lain.
 *   - Cabut kabel USB ESP32 saat keadaan INVERTER: kedua relay harus langsung kembali padam.
 * PIN dan RELAY_AKTIF_LOW harus sama dengan firmware/esp32_panel/esp32_panel.ino.
 */
const int PIN_RELAY_PINDAH = 25;
const int PIN_RELAY_INV = 26;
const bool RELAY_AKTIF_LOW = false;   // samakan dengan esp32_panel.ino
const unsigned long JEDA_PINDAH_MS = 200;
const unsigned long TAHAN_MS = 5000;

void setKoil(int pin, bool koil) {
  digitalWrite(pin, (koil != RELAY_AKTIF_LOW) ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY_INV, OUTPUT);
  setKoil(PIN_RELAY_INV, false);
  pinMode(PIN_RELAY_PINDAH, OUTPUT);
  setKoil(PIN_RELAY_PINDAH, false);
}

void loop() {
  Serial.println("1. AWAL     : kedua koil mati, alat di sisi PLN");
  delay(TAHAN_MS);
  setKoil(PIN_RELAY_PINDAH, true);
  Serial.println("2. PUTUS    : koil PINDAH hidup, alat lepas dari PLN");
  delay(JEDA_PINDAH_MS);
  setKoil(PIN_RELAY_INV, true);
  Serial.println("3. INVERTER : koil INVERTER hidup, alat di sisi inverter");
  delay(TAHAN_MS);
  setKoil(PIN_RELAY_INV, false);
  Serial.println("4. LEPAS    : koil INVERTER mati");
  delay(JEDA_PINDAH_MS);
  setKoil(PIN_RELAY_PINDAH, false);
}
