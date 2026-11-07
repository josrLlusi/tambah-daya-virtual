# Protokol uji TAMBAH DAYA VIRTUAL

Semua uji dilakukan di **panel uji laboratorium** dengan MCB kecil (misalnya 4 A), RCBO, dan pendampingan dosen.
Tidak ada uji yang menyentuh MCB pembatas PLN.

## A. Persiapan

- [ ] Panel uji dirakit: MCB uji, RCBO, sensor arus dan tegangan di jalur PLN, stopkontak beban, relay dan sakelar pindah
- [ ] Kalibrasi tegangan dan arus terhadap multimeter atau power meter (catat KAL_V, KAL_I)
- [ ] Daftar alat uji beserta nameplate (foto ke `docs/`); pilih 5-8 alat dengan daya berbeda
- [ ] Cek sakelar pindah: keluaran inverter tidak pernah tersambung ke jalur PLN (uji dengan multimeter, tanpa beban)

## B. Rekam tiap alat sendirian (untuk label NILM)

Untuk setiap alat: nyalakan dan matikan **10 kali**, jeda 20-60 detik, alat lain mati.

```bash
pip install pyserial
python alat/perekam_serial.py --port COM5 --sesi setrika_uap --durasi 900 --catatan "setrika 350 W, 10x nyala-mati"
python analisis/deteksi_event.py data/raw/setrika_uap_*.csv --label setrika_uap --keluaran data/olah/ev_setrika_uap.csv
```

Ulangi untuk semua alat, lalu latih:

```bash
python analisis/latih_klasifikasi.py data/olah/ev_*.csv --keluaran laporan/klasifikasi_v1
```

## C. Rekam kombinasi (untuk menguji disagregasi)

Nyalakan beberapa alat bersamaan dan bergantian selama 30-60 menit. Catat urutan dan jam nyala-mati
tiap alat di logbook (ini kebenaran untuk menilai hasil).

```bash
python alat/perekam_serial.py --port COM5 --sesi kombinasi_1 --durasi 3600
python analisis/disagregasi.py data/raw/kombinasi_1_*.csv laporan/klasifikasi_v1/model.joblib --keluaran hasil/kombinasi_1.csv
```

## D. Uji waktu trip MCB (untuk model termal)

Pakai beban **resistif** (pemanas, setrika, lampu pijar) agar arus stabil.
Uji 4-6 tingkat arus antara 1,2 dan 3 x arus nominal MCB (contoh MCB 4 A: 5, 6, 7, 9, 11 A).
Jangan uji di atas sekitar 4-5 x arus nominal: itu wilayah trip magnetik (seketika), bukan termal.

1. MCB dingin (istirahat minimal 20 menit sejak trip terakhir).
2. Nyalakan beban, mulai stopwatch, catat arus terukur.
3. Catat waktu sampai MCB trip. Bila lebih dari 60 menit tanpa trip, catat "tidak trip".
4. Isi `data/raw/uji_trip_mcb4A.csv`:

```
arus_A,waktu_trip_detik,theta_awal
5.0,1650,0
6.0,880,0
```

```bash
python analisis/fit_mcb.py data/raw/uji_trip_mcb4A.csv --in-mcb 4 --keluaran laporan/mcb4A
```

Salin `tau_detik` dan `theta_trip` dari `parameter_mcb.json` ke firmware.

## E. Uji kendali "MCB tidak turun"

Skenario: beban dasar + satu beban besar yang dinyalakan sehingga arus melebihi batas MCB.

| Uji | Kendali | Ulangan | Yang dicatat |
|---|---|---|---|
| E1 | mati | 3 | waktu sampai MCB trip |
| E2 | hidup | 3 | apakah MCB trip; kapan alat dipindah; arus PLN maksimum; energi baterai |

Hasil yang dilaporkan: jumlah trip E1 vs E2, waktu reaksi sistem, tambahan daya efektif (VA).

## F. Yang dilaporkan jujur

- Jumlah alat, event per alat, akurasi dan F1 pada validasi silang (bukan pada data latih)
- Hasil disagregasi pada rekaman kombinasi, termasuk alat yang sering salah
- Parameter MCB dari uji sendiri, beserta galat model terhadap waktu trip terukur
- Hasil E1/E2 apa adanya, termasuk bila ada uji yang gagal
