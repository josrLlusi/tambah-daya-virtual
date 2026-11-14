# Daftar komponen panel uji

Panel uji adalah "meteran mini" di atas meja: satu MCB kecil, beberapa stopkontak, sensor, relay, inverter, dan aki.
Tujuannya menguji seluruh alur (pengenalan alat, model MCB, kendali) dengan daya kecil sebelum ke UMKM nyata.

> Rancangan ini **belum pernah dirakit atau diuji**. Tinjau bersama dosen atau teknisi laboratorium sebelum membeli
> dan sebelum memberi tegangan 220 V.

## Pilihan ukuran

Disarankan mulai dengan **MCB uji 2 A** (setara pelanggan 450 VA). Alasannya: beban uji dan inverter jadi kecil dan murah.
Dengan MCB 2 A, arus uji trip hanya 2,4 sampai 5 A (sekitar 500 sampai 1.100 W), dan memindahkan satu alat 100 sampai 300 W
ke baterai sudah terasa pengaruhnya. MCB 4 A (setara 900 VA) bisa dipakai setelah alur berjalan.
Ubah `IN_MCB` di firmware sesuai MCB yang dipakai.

## A. Pengukuran dan kendali

| Komponen | Jumlah | Fungsi | Harga acuan |
|---|---|---|---|
| ESP32 DevKit V1 (30 pin) | 1 (+1 cadangan) | pengukur dan pengendali | belum dicek |
| Sensor arus SCT-013-030 (30 A / 1 V, tipe jepit) | 1 | arus total di jalur PLN | Rp65.000 [1] |
| Modul sensor tegangan ZMPT101B | 1 | tegangan PLN | Rp30.000 [2] |
| Resistor 10 kΩ (2 buah) dan kapasitor 10 µF | 1 set | titik tengah 1,65 V untuk sensor arus | belum dicek |
| Modul relay 4 kanal 5 V, optocoupler, jumper H/L | 1 | relay PINDAH (2 kanal) dan relay INVERTER (2 kanal) | Rp27.500 [3] |
| PZEM-004T 100 A (opsional) | 1 | alat ukur acuan untuk kalibrasi tegangan, arus, daya | Rp168.500 [4] |
| Adaptor USB 5 V 2 A, kabel USB, kabel jumper, papan PCB lubang | 1 set | catu daya dan sambungan | belum dicek |

## B. Sisi 220 V

| Komponen | Jumlah | Fungsi | Harga acuan |
|---|---|---|---|
| RCBO 1P+N 6 A 30 mA | 1 | pengaman arus bocor dan arus lebih untuk seluruh panel | Rp490.640 [5] |
| MCB uji 1P kurva C, 2 A (dan 4 A) | 1 sampai 2 tiap ukuran | MCB yang dimodelkan dan diuji trip | belum dicek untuk 1P; versi 2P 4 A Rp272.727 [6] |
| Kotak panel dengan rel DIN | 1 | rumah RCBO, MCB, relay | belum dicek |
| Stopkontak tempel | 3 sampai 4 | beban dasar (2), alat yang dipindah (1), cadangan | belum dicek |
| Steker, kabel 3 x 1,5 mm², terminal blok, skun | 1 set | sambungan | belum dicek |

## C. Baterai dan inverter

| Komponen | Jumlah | Fungsi | Harga acuan |
|---|---|---|---|
| Inverter 12 V gelombang sinus murni (pure sine wave), 300 sampai 500 W, tipe off-grid | 1 | sumber untuk alat yang dipindah | 500 W: Rp1.250.000 [7] sampai Rp1.350.000 [8] |
| Aki kering VRLA 12 V 9 Ah | 1 | penyimpan energi | Rp350.000 [9] |
| Sekring DC 30 sampai 40 A dengan dudukan, kabel DC 6 mm² pendek | 1 set | pengaman antara aki dan inverter | belum dicek |
| Pengisi aki 12 V otomatis 1 sampai 2 A | 1 | mengisi aki | belum dicek |

Jangan memakai inverter grid-tie (on-grid). Inverter harus tipe off-grid yang keluarannya berdiri sendiri.

## D. Dipinjam dari laboratorium atau rumah

- Beban uji resistif: setrika, lampu pijar atau halogen, pemanas air kecil, solder
- Multimeter, tang ampere, stopwatch
- Laptop untuk merekam (`alat/perekam_serial.py`)

## Perkiraan biaya

Jumlah harga yang sudah dicek (baris bertanda sumber, memakai inverter Rp1.250.000 dan MCB versi 2P): sekitar **Rp2,65 juta**.
Komponen yang belum dicek (ESP32, kotak panel, stopkontak, kabel, sekring, pengisi aki) perlu ditambahkan.
Tanpa PZEM dan dengan MCB 1P, jumlahnya turun.

Harga di atas adalah **satu penawaran toko yang dibaca pada 10 November 2026**, bukan harga rata-rata, dan dapat berubah.
Bandingkan beberapa toko sebelum membeli.

## Berapa lama aki bertahan

Perkiraan kasar, belum diukur: aki 12 V 9 Ah menyimpan sekitar 108 Wh. Pada beban 100 W, inverter menarik sekitar
10 A dari aki. Pada arus sebesar itu, kapasitas aki VRLA yang bisa dipakai turun jauh di bawah angka nominalnya,
sehingga alat 100 W kira-kira bertahan **20 sampai 30 menit**. Itu cukup untuk demo, tidak untuk pemakaian harian.
Ukur sendiri lama bertahannya dan catat di logbook.

Uji logika firmware di komputer (`firmware/uji_host`) menunjukkan hal yang sama dari sisi lain: bila beban terus-menerus
jauh di atas batas MCB, alat yang dipindah berada di baterai sebagian besar waktu. Sistem ini untuk lonjakan
sementara, bukan untuk beban berlebih yang menetap.

## Sumber harga

1. https://www.tokopedia.com/jogjarobotika/sensor-arus-ac-yhdc-sct-013-30a
2. https://www.tokopedia.com/galerielectro/zmpt101b-sensor-tegangan-listrik-pln-220v-250v-ac-voltage-sensor
3. https://www.tokopedia.com/supreme/4-channel-relay-module-optocoupler-adjustable-hi-lo-trigger-5v-relay
4. https://www.tokopedia.com/cncstorebandung/pzem-004t-sensor-watt-volt-current-meter-ac-100a-80-260v-close-ct-1731520108712396350
5. https://www.tokopedia.com/schneiderel/schneider-electric-domae-new-rcbo-slim-1p-n-30ma-6a-domd1606
6. https://nale.co.id/produk/miniature-circuit-breaker-domae-2p-4-a-c-curve-6000-a
7. https://www.tokopedia.com/zafranelektronik/suoer-solar-power-inverter-psw-pure-sine-wave-murni-500watt-fpc-500-al
8. https://www.tokopedia.com/muratastore/suoer-pure-sine-wave-inverter-sinus-murni-500watt-12volt-fpc-500
9. https://www.tokopedia.com/jaringanhandal/aplus-vrla-battery-12v-9ah-apb-1290
