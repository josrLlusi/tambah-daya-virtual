# Skema data

Kolom yang sama dipakai CSV dan basis data (Supabase/PostgreSQL).

## `pengukuran` (dari perangkat)

| Kolom | Tipe | Keterangan |
|---|---|---|
| waktu | timestamp | waktu pengukuran |
| id_perangkat | teks | contoh `panel-01` |
| tegangan | angka | Vrms (V) |
| arus | angka | Irms total di jalur PLN (A) |
| daya_aktif | angka | W |
| faktor_daya | angka | 0 sampai 1 |

## `hasil` (dari model)

| Kolom | Keterangan |
|---|---|
| waktu, id_perangkat | kunci |
| alat_aktif | alat yang dikenali menyala, dipisah `|` |
| theta | pemanasan model termal MCB (relatif) |
| sisa_waktu_mcb_menit | perkiraan waktu sebelum MCB turun |
| versi_model | versi model NILM/MCB |

## `kejadian`

| Kolom | Keterangan |
|---|---|
| waktu, id_perangkat | kunci |
| jenis | `peringatan`, `aksi_relay`, `pindah_baterai`, `mcb_trip` |
| keterangan | teks bebas |

## Berkas contoh simulasi (`data/sample/pengukuran_sim.csv`)

Menggabungkan dua skenario dalam satu berkas agar dasbor mudah diuji: kolom `*_tanpa_kendali`
dan `*_kendali`, `baterai_aktif`, `aksi`, `alat_aktif`, `mcb_trip_*`. Ini **bukan** format data perangkat.

## Aturan

- `data/sample/` berisi data simulasi dan diberi nama yang jelas.
- Data hasil panel uji atau UMKM disimpan di `data/raw/` (tidak ikut di-commit; lihat `.gitignore`).
  Catat tiap sesi di logbook: tanggal, alat, kondisi, siapa yang merekam.
- Data dari UMKM nyata hanya dengan izin pemilik; samarkan nama bila diminta.
- Jangan menimpa data mentah. Hasil olahan disimpan di file terpisah.
