# TAMBAH DAYA VIRTUAL

Sistem pengenalan beban non-intrusif (NILM) dan kendali cerdas beban dan baterai agar UMKM dapat **menambah kapasitas produksi tanpa menaikkan daya PLN**.

Proyek untuk UNS Innovation Hackathon 2026, Sub-tema A (energi terbarukan dan penyimpanan untuk fasilitas publik dan UMKM).

> **Status: tahap konsep, TKT 3.** Yang ada saat ini adalah simulasi, kerangka firmware yang belum diuji di perangkat keras, dan dasbor yang membaca data simulasi. Belum ada hasil pengukuran. Jangan mengutip angka dari repositori ini sebagai kinerja alat.

## Cara kerja singkat

1. Satu sensor arus dan tegangan di panel mengenali alat yang menyala (NILM).
2. Model termal MCB menghitung seberapa dekat MCB ke batas turun.
3. Bila hampir turun, sistem menunda alat yang boleh ditunda (relay) atau memindahkan satu alat ke baterai dan inverter (sakelar pindah).
4. Dasbor menampilkan daya, alat aktif, pemanasan MCB, log aksi, dan tambahan daya efektif.

Pembeda dari produk smart panel di luar negeri: satu sensor di panel yang sudah ada (tanpa mengganti panel), untuk listrik 220 V UMKM Indonesia, dengan biaya jauh lebih rendah.

## Isi repositori

| Folder | Isi |
|---|---|
| `docs/` | proposal (Word dan PDF), diagram blok, grafik simulasi |
| `sim/` | simulasi MCB dan kendali, pembuat data contoh |
| `firmware/esp32_panel/` | kerangka firmware ESP32: P, Q, model termal MCB, relay (belum diuji) |
| `alat/` | perekam serial ESP32 ke CSV |
| `analisis/` | deteksi event, klasifikasi alat, disagregasi, model MCB, dataset publik, data sintetis |
| `dashboard/` | dasbor Streamlit dan fungsi hitung |
| `data/` | skema data dan data contoh simulasi |
| `docs/protokol_uji.md` | langkah rekam alat, uji trip MCB, uji kendali |
| `docs/logbook.md` | templat logbook eksperimen |

## Mulai cepat

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python sim/simulasi_mcb.py           # membuat data contoh dan grafik
streamlit run dashboard/app.py       # membuka dasbor
```

## Alur kerja NILM dan model MCB

Coba seluruh alur dengan data sintetis (tanpa perangkat keras):

```bash
python analisis/data_sintetis.py --jam 6 --keluaran data/sample/agregat_sintetis.csv
python analisis/deteksi_event.py data/sample/agregat_sintetis.csv --keluaran data/olah/event_agregat.csv
python analisis/latih_klasifikasi.py data/olah/event_agregat.csv --kebenaran data/sample/agregat_sintetis_event.csv --keluaran laporan/klasifikasi_sintetis
python analisis/data_sintetis.py --jam 6 --seed 9 --keluaran data/sample/agregat_uji.csv
python analisis/disagregasi.py data/sample/agregat_uji.csv laporan/klasifikasi_sintetis/model.joblib
```

Dengan data nyata (lihat `docs/protokol_uji.md`):

```bash
# rekam tiap alat sendirian, deteksi event berlabel, latih
python alat/perekam_serial.py --port COM5 --sesi setrika_uap --durasi 900
python analisis/deteksi_event.py data/raw/setrika_uap_*.csv --label setrika_uap --keluaran data/olah/ev_setrika_uap.csv
python analisis/latih_klasifikasi.py data/olah/ev_*.csv --keluaran laporan/klasifikasi_v1

# parameter model termal MCB dari uji waktu trip
python analisis/fit_mcb.py data/raw/uji_trip_mcb4A.csv --in-mcb 4 --keluaran laporan/mcb4A

# (opsional) event dari dataset publik UK-DALE / REDD untuk pra-latih atau uji kode
python analisis/dataset_publik.py --folder PATH/ukdale/house_1 --daftar
```

Model klasifikasi yang dibandingkan: pohon keputusan (mudah dijelaskan), random forest, dan jaringan saraf
kecil (MLP). Fitur saat ini: perubahan daya aktif dan reaktif, rasionya, dan lonjakan arus saat start.
Model jaringan saraf konvolusi (CNN 1D) pada bentuk gelombang belum dibuat; itu butuh data berfrekuensi
tinggi dari ESP32 dan pustaka seperti PyTorch atau TensorFlow.

Hasil pada data sintetis (hanya untuk menguji kode, bukan kinerja alat): deteksi event menangkap sekitar
96% event tanpa event palsu; status alat besar (setrika, oven, mixer) terlacak 95-99% dari waktu,
sedangkan alat kecil yang sering menyala (lampu/kipas, freezer) 68-95%. Alat kecil yang berubah status
bersamaan dengan alat besar adalah bagian tersulit.

## Batas simulasi

- Aturan kendali pada simulasi sangat sederhana dan hanya untuk menguji alur. Logika di firmware dan model NILM harus dikembangkan dan diuji terpisah.
- Parameter model termal MCB (konstanta waktu, ambang) adalah tebakan ilustratif. Ganti dengan nilai dari datasheet dan uji waktu trip MCB yang dipakai.
- Kolom `alat_aktif` pada data simulasi adalah label skenario, bukan keluaran model NILM.

## Yang harus dikerjakan berikutnya

- [ ] Rakit panel uji di laboratorium (MCB kecil, relay, sensor, RCBO, beban uji)
- [ ] Ukur waktu trip MCB pada 4-6 tingkat arus; jalankan `analisis/fit_mcb.py`
- [ ] Rekam 5-8 alat, masing-masing 10x nyala-mati; latih `analisis/latih_klasifikasi.py`
- [ ] Rekam kombinasi alat dan uji `analisis/disagregasi.py`
- [ ] Uji kendali: relay dan sakelar pindah dengan inverter dan baterai
- [ ] Ukur: jumlah MCB turun sebelum dan sesudah kendali; akurasi pengenalan alat
- [ ] Hubungkan firmware ke basis data; ganti sumber data dasbor
- [ ] Mode demo (putar ulang data rekaman) untuk presentasi

## Keselamatan

Proyek ini memutus dan menyambung beban 220 V. Ikuti aturan di komentar `firmware/esp32_panel/esp32_panel.ino`: relay fail-safe ke PLN, sakelar pindah break-before-make, tidak menyentuh MCB pembatas PLN, RCBO di setiap panel uji, uji pertama di laboratorium dengan pendampingan dosen.

## Catatan orisinalitas

NILM berasal dari Hart (1992) dan sudah diteliti di Indonesia (antara lain di ITB). Pengaturan beban dan baterai agar tidak perlu naik daya sudah dijual di luar negeri dalam bentuk smart panel. Lihat daftar pustaka di proposal. Bila memakai kode atau data dari riset lain, sebutkan sumbernya dan periksa izinnya.

## Lisensi

Belum ditentukan. Tanpa lisensi, semua hak dipegang tim. Tentukan lisensi setelah masa seleksi dan penjurian selesai.
