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
| `firmware/esp32_panel/` | kerangka firmware ESP32 (belum diuji) |
| `dashboard/` | dasbor Streamlit dan fungsi hitung |
| `data/` | skema data dan data contoh simulasi |

## Mulai cepat

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r dashboard/requirements.txt
python sim/simulasi_mcb.py           # membuat data contoh dan grafik
streamlit run dashboard/app.py       # membuka dasbor
```

## Batas simulasi

- Aturan kendali pada simulasi sangat sederhana dan hanya untuk menguji alur. Logika di firmware dan model NILM harus dikembangkan dan diuji terpisah.
- Parameter model termal MCB (konstanta waktu, ambang) adalah tebakan ilustratif. Ganti dengan nilai dari datasheet dan uji waktu trip MCB yang dipakai.
- Kolom `alat_aktif` pada data simulasi adalah label skenario, bukan keluaran model NILM.

## Yang harus dikerjakan berikutnya

- [ ] Rakit panel uji di laboratorium (MCB kecil, relay, sensor, RCBO, beban uji)
- [ ] Ukur waktu trip MCB pada beberapa tingkat arus; fit model termal
- [ ] Pra-latih model NILM dengan UK-DALE dan REDD (normalisasi 220 V/50 Hz); rekam alat UMKM lokal
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
