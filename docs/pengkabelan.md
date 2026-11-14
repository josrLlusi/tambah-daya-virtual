# Pengkabelan panel uji

> Rancangan ini **belum pernah dirakit atau diuji**. Pekerjaan 220 V dilakukan dengan pendampingan dosen atau
> teknisi laboratorium. Selesaikan **uji kering** (bagian 5) sebelum panel diberi tegangan.

## 1. Gambaran

```
JALUR PLN                                    JALUR BATERAI

Steker PLN                                   Aki 12 V
   |                                            |
RCBO 6 A / 30 mA                             sekring DC
   |                                            |
   +--- adaptor USB 5 V (ESP32, relay)       inverter 12 V ke 220 V
   |                                            |
MCB uji (2 A atau 4 A)                       relay INVERTER (kontak NO, fasa dan netral)
   |                                            |
   +--- ZMPT101B (fasa-netral)                  |
   |                                            |
[SCT-013 pada kabel fasa]                       |
   |                                            |
   +--- stopkontak A dan B (beban dasar)        |
   |                                            |
   NC                                           NO
    \_________ relay PINDAH (fasa dan netral) __/
                         |
                        COM
                         |
               stopkontak C (alat yang dapat dipindah)
```

Cara membacanya:

- Adaptor USB dicabangkan sebelum MCB uji, supaya ESP32 tetap hidup dan tetap merekam saat MCB uji turun.
  Saat merekam, ESP32 dicatu dari kabel USB laptop, jadi adaptor tidak dipakai.
- Sensor arus dan MCB uji dilewati **semua** arus beban dari PLN, sehingga yang diukur adalah arus yang memanaskan MCB.
- Stopkontak C mendapat listrik dari PLN lewat kontak **NC** relay PINDAH. Bila koil mati, C ada di PLN.
- Kontak **NO** relay PINDAH menuju relay INVERTER, lalu ke inverter.
- Relay PINDAH adalah kontak tukar: COM hanya bisa menempel ke NC **atau** NO, tidak keduanya. Karena itu kabel PLN
  dan keluaran inverter tidak bisa tersambung lewat relay ini.
- Fasa dan netral stopkontak C dipindah bersama (dua kanal relay digerakkan satu pin). Netral inverter **tidak**
  disatukan dengan netral PLN.
- Kabel pembumian (PE) dari steker diteruskan ke semua stopkontak dan badan kotak panel.

## 2. Sisi tegangan rendah (ESP32)

| Pin ESP32 | Ke | Catatan |
|---|---|---|
| GPIO34 | keluaran sensor arus SCT-013 (lewat rangkaian titik tengah) | hanya masukan, ADC1 |
| GPIO35 | pin OUT modul ZMPT101B | hanya masukan, ADC1 |
| GPIO25 | IN1 dan IN2 modul relay (relay PINDAH: fasa dan netral) | satu pin menggerakkan dua kanal |
| GPIO26 | IN3 dan IN4 modul relay (relay INVERTER: fasa dan netral) | satu pin menggerakkan dua kanal |
| 3V3 | VCC ZMPT101B, ujung atas pembagi tegangan 10 kΩ | |
| VIN (5 V) | VCC modul relay | relay 5 V tidak boleh diambil dari pin 3V3 |
| GND | GND semua modul | satu titik bersama |

Rangkaian titik tengah untuk SCT-013 (keluaran sensor bolak-balik, ADC hanya menerima 0 sampai 3,3 V):

```
3V3 ---[10 kΩ]---+---[10 kΩ]--- GND
                 |
                 +---||--- GND        (kapasitor 10 µF, kaki positif ke titik tengah)
                 |
        kabel 1 SCT-013
        kabel 2 SCT-013 --------------- GPIO34
```

Catatan sensor:

- **SCT-013-030** sudah punya resistor beban di dalam (keluaran 1 V pada 30 A). Jangan menambah resistor beban.
  Tipe SCT-013-000 (keluaran arus 50 mA) berbeda: wajib diberi resistor beban dan tidak boleh dibiarkan terbuka.
- Sinyalnya kecil pada arus kecil. Lilitkan kabel fasa melewati lubang sensor **5 kali untuk MCB 2 A** atau
  **2 kali untuk MCB 4 A**. Sinyal menjadi 5 atau 2 kali lebih besar; kalibrasi `KAL_I` sudah mencakupnya.
- ZMPT101B: beri catu 3,3 V. Putar potensiometer modul sampai gelombang 220 V tidak terpotong
  (lihat di Serial Plotter), baru kalibrasi `KAL_V`.
- ADC ESP32 tidak linear di dekat 0 V dan di atas sekitar 3 V. Jaga sinyal di antara kira-kira 0,2 dan 3,0 V.
- Kalibrasi `KAL_V` dan `KAL_I` terhadap alat ukur acuan (multimeter, tang ampere, atau PZEM-004T) pada
  beberapa beban, lalu catat di logbook.

## 3. Modul relay

- Pasang jumper pemicu di posisi **H** (high level trigger) dan biarkan `RELAY_AKTIF_LOW = false` di firmware.
  Dengan begitu, bila ESP32 mati atau kabelnya lepas, pin menjadi 0 V dan kedua koil mati: alat kembali ke PLN
  dan inverter terlepas.
- Bila modul hanya mendukung pemicu LOW, setel `RELAY_AKTIF_LOW = true`. Kelemahannya: bila ESP32 kehilangan daya
  sementara modul relay masih bercatu, relay bisa menyala. Hindari bila bisa.
- Kontak modul relay kecil bernilai sekitar 10 A untuk beban resistif. Itu cukup untuk panel uji dengan beban
  beberapa ratus watt. Untuk pemasangan di UMKM dibutuhkan kontaktor atau sakelar pindah yang sesuai standar,
  bukan modul relay hobi.

## 4. Alat yang boleh dipindah

Saat berpindah, stopkontak C mati sekitar 0,2 detik.

- Boleh: pemanas, setrika, lampu, solder, pengisi daya.
- Jangan: kulkas, freezer, AC, pompa (kompresor dan motor bisa macet bila dihidupkan kembali seketika),
  dan komputer tanpa UPS.
- Daya alat di stopkontak C harus di bawah kemampuan inverter dan aki.
- Firmware belum memantau tegangan aki. Bila aki habis, inverter mati dan alat di stopkontak C ikut mati
  sampai sistem mengembalikannya ke PLN. Awasi aki selama uji.

## 5. Uji kering (tanpa 220 V, tanpa inverter)

Unggah `firmware/uji_relay/uji_relay.ino`. Sketsa ini mengulang urutan pindah tiap 5 detik.
Steker PLN **tidak** dicolok dan inverter **tidak** tersambung. Periksa dengan multimeter mode kontinuitas:

- [ ] Saat ESP32 menyala pada keadaan AWAL: lampu modul relay padam.
- [ ] Keadaan AWAL: fasa stopkontak C tersambung ke kabel fasa PLN; tidak tersambung ke kabel inverter.
- [ ] Keadaan INVERTER: fasa stopkontak C tersambung ke kabel inverter; tidak tersambung ke kabel PLN.
- [ ] Ulangi dua pemeriksaan di atas untuk netral.
- [ ] Pada semua keadaan: kabel PLN dan kabel inverter tidak pernah tersambung satu sama lain.
- [ ] Cabut kabel USB ESP32 pada keadaan INVERTER: kedua relay langsung padam dan stopkontak C kembali ke PLN.
- [ ] Ada jeda yang terdengar (dua bunyi klik) antara putus dari PLN dan sambung ke inverter.

Bila ada satu saja yang tidak sesuai, jangan lanjut. Perbaiki pengkabelan atau polaritas relay dulu.

## 6. Pertama kali diberi tegangan

1. Panel diperiksa dosen atau teknisi laboratorium.
2. Unggah `firmware/esp32_panel/esp32_panel.ino` dengan `IN_MCB` yang benar.
3. Colok steker tanpa beban. Tekan tombol uji RCBO: RCBO harus turun.
4. Pasang beban kecil (lampu pijar) di stopkontak A. Bandingkan tegangan, arus, dan daya di Serial Monitor
   dengan alat ukur acuan.
5. Baru setelah itu lanjut ke `docs/protokol_uji.md`.

## 7. Uji logika di komputer

Urutan relay, hitungan daya, dan model termal firmware bisa diperiksa tanpa ESP32:

```bash
g++ -std=c++17 -O2 -o uji_logika firmware/uji_host/uji_logika.cpp
./uji_logika
```

Uji ini hanya memeriksa **logika** dengan sinyal buatan. Uji ini tidak memeriksa ADC, derau, pewaktuan nyata,
atau pengkabelan, dan tidak menggantikan uji kering maupun uji di panel.
