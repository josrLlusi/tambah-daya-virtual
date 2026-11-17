"""Uji seluruh alur TAMBAH DAYA VIRTUAL dengan satu perintah (tanpa perangkat keras).

    python uji_semua.py            # semua langkah, sekitar 1-2 menit
    python uji_semua.py --simpan   # simpan berkas hasil uji di folder uji_keluaran/ untuk dilihat

Semua data yang dipakai SINTETIS. Uji ini membuktikan kode berjalan dan saling tersambung,
BUKAN kinerja alat. Berkas di repositori tidak diubah; hasil ditulis ke folder sementara.
Kode keluar 0 bila semua LULUS, 1 bila ada yang GAGAL.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parent
PY = sys.executable
hasil = []


def jalankan(*argumen, batas=600):
    """Jalankan skrip Python dari folder utama. Pola * sengaja TIDAK diperluas shell (seperti PowerShell)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([PY, *map(str, argumen)], cwd=AKAR, capture_output=True, text=True, timeout=batas,
                       encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip()
                           else f"kode keluar {r.returncode}")
    return r.stdout


def langkah(nama):
    def bungkus(f):
        t0 = time.time()
        try:
            ket = f() or ""
            hasil.append((nama, "LULUS", ket, time.time() - t0))
        except Dilewati as e:
            hasil.append((nama, "DILEWATI", str(e), time.time() - t0))
        except Exception as e:  # noqa: BLE001
            hasil.append((nama, "GAGAL", f"{type(e).__name__}: {e}", time.time() - t0))
        print(f"  [{hasil[-1][1]:8s}] {nama}  {hasil[-1][2]}", flush=True)
        return f
    return bungkus


class Dilewati(Exception):
    pass


def perlu(syarat, pesan):
    if not syarat:
        raise AssertionError(pesan)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simpan", action="store_true", help="simpan keluaran di uji_keluaran/")
    a = ap.parse_args()
    if a.simpan:
        tmp = AKAR / "uji_keluaran"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
    else:
        tmp = Path(tempfile.mkdtemp(prefix="uji_tdv_"))
    print(f"Folder keluaran uji: {tmp}\n")
    import pandas as pd

    @langkah("1. Simulasi MCB dua skenario (sim/simulasi_mcb.py)")
    def _():
        sys.path.insert(0, str(AKAR / "sim"))
        import simulasi_mcb
        df, trip_a, trip_b = simulasi_mcb.buat_data()
        perlu(len(df) > 100 and trip_a is not None, "simulasi tidak menghasilkan trip pada skenario tanpa kendali")
        return f"{len(df)} baris; trip tanpa kendali menit {trip_a}, dengan kendali {trip_b}"

    @langkah("2. Rekaman tiruan format perangkat (sim/rekaman_tiruan.py)")
    def _():
        out = jalankan("sim/rekaman_tiruan.py", "--jam", "2", "--keluaran", tmp / "rekaman_tiruan.csv")
        df = pd.read_csv(tmp / "rekaman_tiruan.csv")
        perlu({"arus", "daya_aktif", "theta", "baterai_aktif"} <= set(df.columns), "kolom rekaman tidak lengkap")
        return "; ".join(x.strip() for x in out.splitlines()[2:4])

    @langkah("3. Data agregat sintetis (analisis/data_sintetis.py)")
    def _():
        jalankan("analisis/data_sintetis.py", "--jam", "6", "--keluaran", tmp / "agregat_latih.csv")
        jalankan("analisis/data_sintetis.py", "--jam", "6", "--seed", "9", "--keluaran", tmp / "uji_agregat.csv")
        perlu((tmp / "agregat_latih_event.csv").exists(), "berkas event kebenaran tidak dibuat")

    @langkah("4. Deteksi event, pola berkas diperluas oleh skrip (analisis/deteksi_event.py)")
    def _():
        out = jalankan("analisis/deteksi_event.py", tmp / "agregat_lati?.csv", "--keluaran", tmp / "event.csv")
        ev = pd.read_csv(tmp / "event.csv")
        benar = pd.read_csv(tmp / "agregat_latih_event.csv")
        perlu(0.8 * len(benar) <= len(ev) <= 1.1 * len(benar), f"{len(ev)} event terdeteksi vs {len(benar)} kebenaran")
        return f"{len(ev)} event terdeteksi dari {len(benar)} event kebenaran"

    @langkah("5. Deteksi event pada rekaman cepat (3 baris per detik)")
    def _():
        d = pd.read_csv(tmp / "agregat_latih.csv", parse_dates=["waktu"]).iloc[:3600]
        cepat = d.loc[d.index.repeat(3)].reset_index(drop=True)
        cepat["waktu"] = cepat["waktu"] + pd.to_timedelta(cepat.index % 3 / 3, unit="s")
        d.to_csv(tmp / "satu_jam_1hz.csv", index=False)
        cepat.to_csv(tmp / "satu_jam_3hz.csv", index=False)
        jalankan("analisis/deteksi_event.py", tmp / "satu_jam_1hz.csv", "--keluaran", tmp / "ev_1hz.csv")
        jalankan("analisis/deteksi_event.py", tmp / "satu_jam_3hz.csv", "--keluaran", tmp / "ev_3hz.csv")
        n1, n3 = len(pd.read_csv(tmp / "ev_1hz.csv")), len(pd.read_csv(tmp / "ev_3hz.csv"))
        perlu(n1 > 0 and n1 == n3, f"jumlah event berbeda: 1 Hz = {n1}, 3 Hz = {n3}")
        return f"{n1} event pada kedua laju"

    @langkah("6. Latih pengklasifikasi alat (analisis/latih_klasifikasi.py)")
    def _():
        out = jalankan("analisis/latih_klasifikasi.py", tmp / "event.csv", "--kebenaran",
                       tmp / "agregat_latih_event.csv", "--keluaran", tmp / "laporan" / "klasifikasi")
        perlu((tmp / "laporan" / "klasifikasi" / "model.joblib").exists(), "model.joblib tidak dibuat")
        r = json.loads(out[out.index("{"):out.rindex("}") + 1])
        terbaik = r["terbaik"]
        perlu(r[terbaik]["akurasi_%"] > 80, f"akurasi {r[terbaik]['akurasi_%']} % terlalu rendah untuk data sintetis")
        return f"terbaik: {terbaik}, akurasi {r[terbaik]['akurasi_%']} % (data sintetis)"

    @langkah("7. Disagregasi pada data lain (analisis/disagregasi.py)")
    def _():
        out = jalankan("analisis/disagregasi.py", tmp / "uji_agregat.csv",
                       tmp / "laporan" / "klasifikasi" / "model.joblib", "--keluaran", tmp / "disagregasi.csv")
        r = json.loads(out[out.index("{"):out.rindex("}") + 1])
        ak = r["akurasi_status_per_alat_%"]
        perlu(min(ak.values()) > 50, f"akurasi status terlalu rendah: {ak}")
        return f"akurasi status per alat {min(ak.values())}-{max(ak.values())} % (data sintetis)"

    @langkah("8. Parameter MCB dari uji trip buatan (analisis/fit_mcb.py)")
    def _():
        tau, th, in_mcb = 900.0, 1.45, 4.0
        baris = ["arus_A,waktu_trip_detik,theta_awal"]
        for arus in (5.0, 6.0, 7.0, 9.0, 11.0):
            s = (arus / in_mcb) ** 2
            baris.append(f"{arus},{tau * math.log(s / (s - th)):.1f},0")
        (tmp / "uji_trip.csv").write_text("\n".join(baris), encoding="utf-8")
        jalankan("analisis/fit_mcb.py", tmp / "uji_trip.csv", "--in-mcb", in_mcb, "--keluaran", tmp / "laporan" / "mcb")
        par = json.loads((tmp / "laporan" / "mcb" / "parameter_mcb.json").read_text(encoding="utf-8"))
        perlu(abs(par["tau_detik"] - tau) / tau < 0.05 and abs(par["theta_trip"] - th) < 0.05,
              f"parameter tidak kembali: {par}")
        return f"tau {par['tau_detik']} s (asli {tau:g}), ambang {par['theta_trip']} (asli {th})"

    @langkah("9. Perekam serial mode uji (alat/perekam_serial.py --uji)")
    def _():
        jalankan("alat/perekam_serial.py", "--uji", "--durasi", "3", "--sesi", "uji", "--folder", tmp / "raw")
        ada = list((tmp / "raw").glob("uji_*.csv"))
        perlu(len(ada) == 1 and len(pd.read_csv(ada[0])) >= 2, "rekaman uji tidak terbentuk")
        perlu((tmp / "raw" / "logbook.csv").exists(), "logbook tidak terisi")
        return f"{len(pd.read_csv(ada[0]))} baris"

    @langkah("10. Fungsi hitung dasbor (dashboard/logika.py)")
    def _():
        sys.path.insert(0, str(AKAR / "dashboard"))
        import numpy as np
        import logika
        contoh = logika.muat(AKAR / "data" / "sample" / "pengukuran_sim.csv")
        perlu(logika.jenis_data(contoh) == "simulasi", "berkas contoh tidak dikenali")
        perlu(logika.kejadian_trip(contoh) >= 1, "contoh simulasi harus punya trip tanpa kendali")
        rek = logika.muat(tmp / "rekaman_tiruan.csv")
        perlu(logika.jenis_data(rek) == "rekaman", "rekaman tiruan tidak dikenali")
        th = logika.hitung_theta(rek, in_mcb=10.0, tau=1200.0)
        selisih = float(np.abs(th - rek["theta"].to_numpy()).max())
        perlu(selisih < 0.02, f"theta dasbor berbeda dari theta rekaman (selisih {selisih:.3f})")
        perlu(len(logika.aksi_dari_status(rek)) >= 1, "aksi kendali tidak terbaca")
        perlu(math.isinf(logika.sisa_waktu_menit(0.5, 10.0, 10.0, 1200.0, 1.6)), "arus nominal seharusnya aman")
        perlu(logika.sisa_waktu_menit(1.0, 14.0, 10.0, 1200.0, 1.6) > 0, "sisa waktu harus positif")
        r = logika.ringkas_rekaman(rek, 10.0)
        tabel, energi = logika.disagregasi(logika.potong(rek, 0.5), tmp / "laporan" / "klasifikasi" / "model.joblib")
        perlu(len(tabel) > 0 and len(energi) > 0, "disagregasi dasbor kosong")
        return f"theta cocok (selisih maks {selisih:.3f}); {r['jumlah_aksi']} aksi; {len(energi)} alat"

    @langkah("11. Logika firmware di komputer (firmware/uji_host, butuh g++)")
    def _():
        gpp = shutil.which("g++")
        if not gpp:
            raise Dilewati("g++ tidak terpasang; uji ini opsional")
        exe = tmp / ("uji_logika.exe" if sys.platform.startswith("win") else "uji_logika")
        r = subprocess.run([gpp, "-std=c++17", "-O2", "-o", str(exe), "firmware/uji_host/uji_logika.cpp"],
                           cwd=AKAR, capture_output=True, text=True)
        perlu(r.returncode == 0, "firmware tidak lolos kompilasi g++: " + r.stderr.strip()[-300:])
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        perlu(r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "uji gagal")
        return r.stdout.strip().splitlines()[-2]

    @langkah("12. Halaman dasbor saling cocok (impor antar-berkas, tanpa menjalankan Streamlit)")
    def _():
        import ast
        folder = AKAR / "dashboard"
        modul = {}
        for f in ["logika.py", "simulator.py", "tampilan.py"]:
            if (folder / f).exists():
                t = ast.parse((folder / f).read_text(encoding="utf-8"))
                nama = set()
                for n in t.body:
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                        nama.add(n.name)
                    elif isinstance(n, ast.Assign):
                        for x in n.targets:
                            for y in (x.elts if isinstance(x, ast.Tuple) else [x]):
                                if isinstance(y, ast.Name):
                                    nama.add(y.id)
                modul[f[:-3]] = nama
        halaman = [folder / "app.py"] + sorted((folder / "pages").glob("*.py"))
        hilang = []
        for h in halaman:
            t = ast.parse(h.read_text(encoding="utf-8"))
            for n in ast.walk(t):
                if isinstance(n, ast.ImportFrom) and n.module in modul:
                    hilang += [f"{h.name}: {n.module}.{x.name}" for x in n.names if x.name not in modul[n.module]]
        perlu(not hilang, "nama tidak ditemukan: " + ", ".join(hilang))
        return f"{len(halaman)} halaman, semua impor ditemukan"

    @langkah("13. Kendali berbasis NILM, loop tertutup 1 jam (sim/simulasi_nilm_kendali.py)")
    def _():
        sys.path.insert(0, str(AKAR / "sim"))
        import simulasi_nilm_kendali as sk
        h = sk.jalankan(jam=1, seed_uji=(9,), tampil=lambda *_: None).set_index("skenario")
        perlu(h.loc["tanpa", "mcb_turun"] >= 1, "skenario uji harus membuat MCB turun bila tanpa kendali")
        for nama in ("termal_1", "nilm_1", "nilm_2"):
            perlu(h.loc[nama, "mcb_turun"] == 0, f"{nama}: MCB turun {h.loc[nama, 'mcb_turun']} kali")
            perlu(h.loc[nama, "aksi_pindah"] >= 1, f"{nama}: tidak pernah memindah alat")
        perlu(h.loc["nilm_1", "aksi_pindah"] <= h.loc["termal_1", "aksi_pindah"] + 2, "NILM terlalu sering memindah")
        return (f"MCB turun: tanpa kendali {h.loc['tanpa', 'mcb_turun']}x, termal {h.loc['termal_1', 'mcb_turun']}x, "
                f"NILM {h.loc['nilm_1', 'mcb_turun']}x (simulasi)")

    n_gagal = sum(1 for h in hasil if h[1] == "GAGAL")
    print(f"\n{sum(1 for h in hasil if h[1] == 'LULUS')} lulus, {n_gagal} gagal, "
          f"{sum(1 for h in hasil if h[1] == 'DILEWATI')} dilewati, {sum(h[3] for h in hasil):.0f} detik.")
    print("Catatan: semua data sintetis. Hasil ini bukan kinerja alat.")
    if not a.simpan:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if n_gagal else 0)


if __name__ == "__main__":
    main()
