"""Uji kasus tepi (data kosong, data pendek, nilai ekstrem, berkas hilang) untuk kode analisis dan dasbor.

    python uji_kasus_tepi.py            # semua uji; kode keluar 1 hanya bila ada yang GAGAL
    python uji_kasus_tepi.py --ketat    # CELAH juga dianggap gagal (untuk dipakai setelah celah diperbaiki)

Berbeda dengan uji_semua.py (alur utama, lewat skrip), uji ini memanggil fungsi langsung dan cepat (beberapa detik).
Semua data SINTETIS; uji ini membuktikan kode tahan terhadap masukan aneh, BUKAN kinerja alat.
Tidak ada berkas di repositori yang diubah; berkas bantu ditulis ke folder sementara.

Status:
  LULUS   perilaku sesuai harapan.
  GAGAL   perilaku salah pada kasus yang seharusnya sudah benar (regresi).
  CELAH   kekurangan yang SUDAH DIKETAHUI di kode sumber. Uji memeriksa perilaku yang diinginkan; selama kode
          belum diperbaiki hasilnya CELAH, begitu diperbaiki otomatis menjadi LULUS (lalu ubah `celah(...)` jadi `cek(...)`).
"""
import argparse
import contextlib
import io
import json
import math
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

AKAR = Path(__file__).resolve().parent
sys.path[:0] = [str(AKAR / "analisis"), str(AKAR / "dashboard"), str(AKAR / "alat")]
warnings.filterwarnings("ignore")

import deteksi_event as de  # noqa: E402
import disagregasi as dg  # noqa: E402
import fit_mcb as fm  # noqa: E402
import latih_klasifikasi as lk  # noqa: E402
import logika as lg  # noqa: E402
import perekam_serial as ps  # noqa: E402
import data_sintetis as ds  # noqa: E402
import keputusan_kendali as kk  # noqa: E402
import pengendali_nilm as pn  # noqa: E402

hasil = []   # (kelompok, nama, status, keterangan)
kelompok_kini = ""


def kelompok(nama):
    global kelompok_kini
    kelompok_kini = nama
    print(f"\n{nama}", flush=True)


def perlu(syarat, pesan="syarat tidak terpenuhi"):
    if not syarat:
        raise AssertionError(pesan)


def _catat(nama, status, ket):
    hasil.append((kelompok_kini, nama, status, ket))
    tanda = {"LULUS": " ", "GAGAL": "!", "CELAH": "~"}[status]
    print(f"  [{status:5s}]{tanda}{nama}" + (f"  -> {ket}" if ket and status != "LULUS" else ""), flush=True)


def cek(nama):
    """Uji yang harus lulus."""
    def bungkus(f):
        try:
            f()
            _catat(nama, "LULUS", "")
        except Exception as e:  # noqa: BLE001
            _catat(nama, "GAGAL", f"{type(e).__name__}: {str(e)[:150]}")
        return f
    return bungkus


def celah(nama, alasan):
    """Uji perilaku yang DIINGINKAN untuk kekurangan yang sudah diketahui."""
    def bungkus(f):
        try:
            f()
            _catat(nama, "LULUS", "celah sudah diperbaiki; ganti celah(...) menjadi cek(...)")
        except Exception as e:  # noqa: BLE001
            _catat(nama, "CELAH", f"{alasan} [{type(e).__name__}: {str(e)[:90]}]")
        return f
    return bungkus


# ---------------------------------------------------------------------------
# Pembantu data
# ---------------------------------------------------------------------------
def seri(P, hz=1, **lain):
    """DataFrame daya_aktif dengan langkah 1/hz detik."""
    n = len(P)
    d = pd.DataFrame({"waktu": pd.Timestamp("2026-11-01") + pd.to_timedelta(np.arange(n) / hz, unit="s"),
                      "daya_aktif": np.asarray(P, float)})
    for k, v in lain.items():
        d[k] = v
    return d


def df_(**kolom):
    n = len(next(iter(kolom.values())))
    return pd.DataFrame({"waktu": pd.Timestamp("2026-11-01") + pd.to_timedelta(np.arange(n), unit="s"), **kolom})


def langkah_daya(*segmen, derau=1.0, seed=0):
    """Rangkaian daya konstan per segmen [(daya, jumlah_sampel), ...] ditambah derau kecil."""
    rng = np.random.default_rng(seed)
    P = np.concatenate([np.full(n, float(p)) for p, n in segmen])
    return P + rng.normal(0, derau, len(P))


def utama(fungsi, *argv):
    """Jalankan main() sebuah skrip dengan argumen baris perintah buatan; keluaran dibuang."""
    lama = sys.argv
    sys.argv = ["x", *map(str, argv)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fungsi()
    finally:
        sys.argv = lama


def paket_sederhana():
    from sklearn.tree import DecisionTreeClassifier
    X = pd.DataFrame({"abs_dP": [500, 520, 2000, 1950]})
    m = DecisionTreeClassifier(random_state=0).fit(X, ["a", "a", "b", "b"])
    return {"fitur": ["abs_dP"], "model": m, "kelas": ["a", "b"], "dP_tipikal": {"a": 510.0, "b": 1975.0}}


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ketat", action="store_true", help="CELAH dianggap gagal")
    a = ap.parse_args()
    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="uji_tepi_"))
    print(f"Folder sementara: {tmp}")

    # -----------------------------------------------------------------------
    kelompok("Deteksi event (analisis/deteksi_event.py)")

    @cek("sinyal datar: tidak ada event")
    def _():
        perlu(len(de.deteksi(seri(np.full(300, 100.0)))) == 0)

    @cek("derau saja (sigma 3 W): tidak ada event palsu")
    def _():
        rng = np.random.default_rng(0)
        perlu(len(de.deteksi(seri(100 + rng.normal(0, 3, 600)))) == 0)

    @cek("naik 500 W lalu turun: 2 event (nyala, mati) dengan dP sekitar +-500 W")
    def _():
        ev = de.deteksi(seri(langkah_daya((100, 100), (600, 100), (100, 100))))
        perlu(ev["arah"].tolist() == ["nyala", "mati"], f"arah {ev['arah'].tolist()}")
        perlu(np.allclose(ev["dP"].abs(), 500, atol=15), f"dP {ev['dP'].round(0).tolist()}")

    @cek("loncatan 30 W (di bawah ambang 40 W): diabaikan")
    def _():
        perlu(len(de.deteksi(seri(langkah_daya((100, 100), (130, 100), (100, 100))))) == 0)

    @cek("ambang dinaikkan di atas besar loncatan: tidak ada event")
    def _():
        perlu(len(de.deteksi(seri(langkah_daya((100, 100), (600, 100))), ambang=1000)) == 0)

    @cek("lonjakan 1-2 sampel (transien) tidak dihitung sebagai event")
    def _():
        for lebar in (1, 2):
            P = np.full(300, 100.0)
            P[150:150 + lebar] = 900
            perlu(len(de.deteksi(seri(P))) == 0, f"lonjakan {lebar} sampel terdeteksi")

    @cek("data sangat pendek (1, 2, 3, 6, 10 baris) tidak membuat program berhenti")
    def _():
        for n in (1, 2, 3, 6, 10):
            de.deteksi(seri(np.arange(n) * 100.0))

    @cek("data 4-5 baris tidak membuat program berhenti")
    def _():
        for n in (4, 5):
            perlu(len(de.deteksi(seri(np.arange(n) * 100.0))) == 0)

    @cek("data kosong (0 baris) tidak membuat program berhenti")
    def _():
        perlu(len(de.deteksi(seri([]))) == 0)

    @cek("tanpa event pun tabel hasil berkolom lengkap (indeks, waktu, dP, ..., arah), baik data kosong, pendek, maupun datar")
    def _():
        wajib = {"indeks", "waktu", "dP", "P_sebelum", "P_sesudah", "arah"}
        for d in (seri([]), seri([1, 2, 3]), seri(np.full(300, 100.0))):
            ev = de.deteksi(d)
            perlu(len(ev) == 0 and wajib <= set(ev.columns), f"kolom {list(ev.columns)}")
        ev = de.deteksi(seri([], daya_reaktif=[], arus=[]))
        perlu({"dQ", "rasio_puncak"} <= set(ev.columns), f"kolom {list(ev.columns)}")

    @cek("deteksi_event.py lewat baris perintah pada rekaman tanpa event menulis CSV berkolom (bisa dibaca lagi)")
    def _():
        seri(np.full(120, 100.0)).to_csv(tmp / "datar.csv", index=False)
        utama(de.main, tmp / "datar.csv", "--keluaran", tmp / "ev_datar.csv")
        ev = pd.read_csv(tmp / "ev_datar.csv")
        perlu(len(ev) == 0 and "dP" in ev.columns, f"kolom {list(ev.columns)}")

    @cek("satu sampel NaN di tengah data tidak membuat program berhenti")
    def _():
        P = langkah_daya((100, 100), (600, 100))
        P[50] = np.nan
        de.deteksi(seri(P))

    @cek("kolom daya_reaktif dan arus opsional: dQ dan rasio_puncak hanya ada bila kolomnya ada")
    def _():
        P = langkah_daya((100, 100), (600, 100))
        tanpa = de.deteksi(seri(P))
        dengan = de.deteksi(seri(P, daya_reaktif=P * 0.2, arus=P / 220))
        perlu(len(tanpa) == 1 and "dQ" not in tanpa and "rasio_puncak" not in tanpa)
        perlu(len(dengan) == 1 and {"dQ", "rasio_puncak"} <= set(dengan.columns))

    @cek("seragamkan_1detik: kurang dari 3 baris dikembalikan apa adanya")
    def _():
        perlu(len(de.seragamkan_1detik(seri([1, 2]))) == 2)

    @cek("seragamkan_1detik: 3 baris per detik dirata-rata jadi 1 baris per detik")
    def _():
        d = de.seragamkan_1detik(seri(np.arange(30.0), hz=3))
        perlu(len(d) == 10, f"{len(d)} baris")
        perlu(abs(d["daya_aktif"].iloc[0] - 1.0) < 1e-9, "rata-rata detik pertama salah")

    @cek("seragamkan_1detik: jeda antar rekaman tidak diisi baris kosong")
    def _():
        a = seri(np.full(30, 100.0), hz=3)
        b = seri(np.full(30, 100.0), hz=3)
        b["waktu"] += pd.Timedelta(hours=1)
        d = de.seragamkan_1detik(pd.concat([a, b], ignore_index=True))
        perlu(len(d) == 20, f"{len(d)} baris, seharusnya 20")
        perlu(d["daya_aktif"].notna().all(), "ada nilai kosong")

    @cek("seragamkan_1detik: kolom penanda (baterai_aktif, mcb_trip) memakai nilai maksimum, bukan rata-rata")
    def _():
        d = seri(np.full(9, 100.0), hz=3, baterai_aktif=[0, 0, 1, 0, 0, 0, 0, 0, 0], mcb_trip=0)
        s = de.seragamkan_1detik(d)
        perlu(list(s["baterai_aktif"]) == [1, 0, 0], f"{list(s['baterai_aktif'])}")

    @cek("perluas: pola tanpa berkas yang cocok -> berhenti dengan pesan jelas")
    def _():
        try:
            de.perluas([str(tmp / "tidak_ada_*.csv")])
        except SystemExit as e:
            perlu("Tidak ada berkas" in str(e), str(e))
            return
        raise AssertionError("seharusnya SystemExit")

    @cek("perluas: pola ber-* diperluas dan diurutkan; nama biasa dikembalikan apa adanya")
    def _():
        for n in ("b_2.csv", "b_1.csv"):
            (tmp / n).write_text("x", encoding="utf-8")
        hasil_ = de.perluas([str(tmp / "b_*.csv"), "nama_biasa.csv"])
        perlu([Path(p).name for p in hasil_] == ["b_1.csv", "b_2.csv", "nama_biasa.csv"], str(hasil_))

    @cek("muat: berkas tidak berurutan waktu digabung dan diurutkan")
    def _():
        d1 = seri(np.full(5, 100.0))
        d2 = seri(np.full(5, 100.0))
        d2["waktu"] += pd.Timedelta(minutes=10)
        d2.to_csv(tmp / "m_terlambat.csv", index=False)
        d1.to_csv(tmp / "m_awal.csv", index=False)
        d = de.muat([tmp / "m_terlambat.csv", tmp / "m_awal.csv"])
        perlu(d["waktu"].is_monotonic_increasing and len(d) == 10)

    # -----------------------------------------------------------------------
    kelompok("Model termal MCB (analisis/fit_mcb.py)")

    @cek("t_trip: arus sama dengan atau di bawah ambang -> tidak pernah trip (tak hingga)")
    def _():
        perlu(np.isinf(fm.t_trip([0.5, 1.0, 1.1], 900, 1.45)).all())

    @cek("t_trip: makin besar arus makin singkat waktu trip, selalu positif")
    def _():
        t = fm.t_trip([1.3, 1.5, 2.0, 4.0, 10.0], 900, 1.45)
        perlu((t > 0).all() and (np.diff(t) < 0).all(), str(t))

    @cek("fit: data bersih memulihkan tau dan ambang (galat < 1 %)")
    def _():
        I = np.array([1.5, 2.0, 3.0])
        t = 900 * np.log(I ** 2 / (I ** 2 - 1.45))
        (tau, th), _ = fm.fit(I, t, np.zeros(3))
        perlu(abs(tau - 900) / 900 < 0.01 and abs(th - 1.45) < 0.015, f"tau {tau:.1f}, ambang {th:.3f}")

    @cek("fit: MCB sudah hangat (theta_awal = 0,5) tetap memulihkan parameter")
    def _():
        I = np.array([1.6, 2.0, 3.0, 4.0])
        th0 = np.array([0.5, 0.5, 0.5, 0.5])
        t = 900 * np.log((I ** 2 - th0) / (I ** 2 - 1.45))
        (tau, th), _ = fm.fit(I, t, th0)
        perlu(abs(tau - 900) / 900 < 0.02 and abs(th - 1.45) < 0.02, f"tau {tau:.1f}, ambang {th:.3f}")

    @cek("fit: derau 5 % pada waktu trip tidak membuat program berhenti; hasil masuk akal (ambang < arus uji terkecil^2)")
    def _():
        rng = np.random.default_rng(0)
        I = np.array([1.5, 2.0, 3.0, 4.0, 5.0])
        t = 900 * np.log(I ** 2 / (I ** 2 - 1.45)) * (1 + rng.normal(0, 0.05, 5))
        (tau, th), _ = fm.fit(I, t, np.zeros(5))
        perlu(tau > 0 and 1.0 <= th < I.min() ** 2, f"tau {tau:.1f}, ambang {th:.3f}")

    @cek("main: kurang dari 3 uji -> berhenti dengan pesan minimal 3 uji")
    def _():
        (tmp / "dua_uji.csv").write_text("arus_A,waktu_trip_detik\n6,300\n8,100\n", encoding="utf-8")
        try:
            utama(fm.main, tmp / "dua_uji.csv", "--in-mcb", 4, "--keluaran", tmp / "mcb_dua")
        except SystemExit as e:
            perlu("minimal 3" in str(e), str(e))
            return
        raise AssertionError("seharusnya SystemExit")

    @cek("fit: arus uji sama dengan atau di bawah arus nominal -> berhenti dengan pesan jelas (bukan galat mentah scipy)")
    def _():
        for I in ([1.0, 2.0, 3.0], [0.8, 2.0, 3.0]):
            try:
                fm.fit(np.array(I), np.array([100.0, 50.0, 20.0]), np.zeros(3))
            except SystemExit as e:
                perlu("arus nominal" in str(e), str(e))
            except ValueError as e:
                raise AssertionError(f"ValueError mentah dari scipy untuk arus {I}: {e}")
            else:
                raise AssertionError(f"arus {I} seharusnya ditolak")

    @cek("fit: arus uji terkecil sedikit di atas nominal (1,02 x) tidak lagi membuat tebakan awal di luar batas")
    def _():
        I = np.array([1.02, 2.0, 3.0])
        (tau, th), _ = fm.fit(I, np.array([5000.0, 60.0, 25.0]), np.zeros(3))
        perlu(np.isfinite(tau) and 1.0 <= th < 1.02 ** 2, f"tau {tau}, ambang {th}")

    @cek("main: arus uji sama dengan arus nominal (4 A pada MCB 4 A) -> berhenti dengan pesan jelas")
    def _():
        (tmp / "uji_nominal.csv").write_text("arus_A,waktu_trip_detik\n4,3000\n6,300\n8,100\n", encoding="utf-8")
        try:
            utama(fm.main, tmp / "uji_nominal.csv", "--in-mcb", 4, "--keluaran", tmp / "mcb_nominal")
        except SystemExit as e:
            perlu("arus nominal" in str(e), str(e))
            return
        raise AssertionError("seharusnya SystemExit")

    # -----------------------------------------------------------------------
    kelompok("Fungsi hitung dasbor (dashboard/logika.py)")

    @cek("kejadian_trip: data kosong = 0; kolom tidak ada = 0; mulai dari 1 dihitung satu kejadian")
    def _():
        perlu(lg.kejadian_trip(df_(mcb_trip_tanpa_kendali=[])) == 0)
        perlu(lg.kejadian_trip(df_(a=[1, 1])) == 0)
        perlu(lg.kejadian_trip(df_(mcb_trip_tanpa_kendali=[1, 1, 1])) == 1)
        perlu(lg.kejadian_trip(df_(mcb_trip_tanpa_kendali=[1, 1, 0, 1])) == 2)

    @cek("waktu_trip_pertama: tanpa trip atau tanpa kolom -> None")
    def _():
        perlu(lg.waktu_trip_pertama(df_(mcb_trip_tanpa_kendali=[0, 0])) is None)
        perlu(lg.waktu_trip_pertama(df_(a=[1])) is None)

    @cek("energi dan durasi baterai: 1 baris atau tanpa kolom = 0; 1 jam x 2 kW = 2 kWh")
    def _():
        perlu(lg.energi_baterai_kwh(df_(baterai_aktif=[1])) == 0.0)
        perlu(lg.durasi_baterai_menit(df_(a=[1, 2])) == 0.0)
        d = pd.DataFrame({"waktu": pd.to_datetime(["2026-11-01 00:00", "2026-11-01 01:00"]), "baterai_aktif": [1, 1]})
        perlu(abs(lg.energi_baterai_kwh(d) - 2.0) < 1e-9, str(lg.energi_baterai_kwh(d)))
        perlu(abs(lg.durasi_baterai_menit(d) - 60.0) < 1e-9)

    @cek("tambahan_daya_va: beban di bawah terpasang = 0; ada trip dengan kendali = 0 (tidak boleh mengklaim tambahan)")
    def _():
        aman = lg.tambahan_daya_va(df_(arus_tanpa_kendali=[5, 10], mcb_trip_kendali=[0, 0]))
        perlu(aman["tambahan_va"] == 0.0 and not aman["ada_trip"])
        gagal = lg.tambahan_daya_va(df_(arus_tanpa_kendali=[5, 30], mcb_trip_kendali=[0, 1]))
        perlu(gagal["tambahan_va"] == 0.0 and gagal["ada_trip"], str(gagal))
        ok = lg.tambahan_daya_va(df_(arus_tanpa_kendali=[5, 30], mcb_trip_kendali=[0, 0]))
        perlu(abs(ok["tambahan_va"] - (30 * 220 - 20 * 220)) < 1e-6, str(ok))

    @cek("segmen_alat: kosong, tanpa alat, dan 1 baris tidak membuat program berhenti")
    def _():
        perlu(len(lg.segmen_alat(df_(alat_aktif=[]))) == 0)
        perlu(len(lg.segmen_alat(df_(alat_aktif=["", ""]))) == 0)
        perlu(len(lg.segmen_alat(df_(alat_aktif=["a"]))) == 1)

    @cek("segmen_alat: alat yang masih menyala di baris terakhir tetap punya waktu selesai; dua alat tumpang-tindih")
    def _():
        s = lg.segmen_alat(df_(alat_aktif=["", "a", "a|b", "a"]))
        perlu(sorted(s["alat"]) == ["a", "b"], str(s))
        perlu(s["selesai"].notna().all() and (s["selesai"] > s["mulai"]).all(), str(s))

    @cek("segmen_biner: berakhir saat masih bernilai 1 tetap tertutup; kolom tidak ada -> kosong")
    def _():
        s = lg.segmen_biner(df_(x=[0, 1, 1]), "x")
        perlu(len(s) == 1 and s["selesai"].iloc[0] > s["mulai"].iloc[0])
        perlu(len(lg.segmen_biner(df_(x=[0, 1]), "tidak_ada")) == 0)

    @cek("potong: bagian negatif -> minimal 2 baris; bagian > 1 -> semua; data 1 baris tidak bertambah")
    def _():
        d = df_(x=range(10))
        perlu(len(lg.potong(d, -1)) == 2 and len(lg.potong(d, 5)) == 10 and len(lg.potong(d, 0.5)) == 5)
        perlu(len(lg.potong(df_(x=[1]), 0.5)) == 1)

    @cek("hitung_theta: data kosong -> kosong; arus 0 meluruh perlahan; arus tetap besar menuju (I/In)^2")
    def _():
        kosong = pd.DataFrame({"waktu": pd.to_datetime([]), "arus": []})
        perlu(len(lg.hitung_theta(kosong, 10, 1200)) == 0)
        th = lg.hitung_theta(df_(arus=[0, 0, 0]), 10, 1200, theta_awal=1.0)
        perlu(th[0] == 1.0 and (np.diff(th) < 0).all() and (th > 0.99).all(), str(th))
        d = pd.DataFrame({"waktu": pd.to_datetime(["2026-11-01 00:00", "2026-11-01 05:00"]), "arus": [15, 15]})
        perlu(abs(lg.hitung_theta(d, 10, 1200)[-1] - 2.25) < 1e-3)

    @cek("hitung_theta: waktu mundur tidak membuat theta turun di bawah nol atau menjadi NaN")
    def _():
        d = pd.DataFrame({"waktu": pd.to_datetime(["2026-11-01 00:00:10", "2026-11-01 00:00:00", "2026-11-01 00:00:05"]),
                          "arus": [10, 10, 10]})
        th = lg.hitung_theta(d, 10, 1200)
        perlu(np.isfinite(th).all() and (th >= 0).all(), str(th))

    @cek("sisa_waktu_menit: sudah melewati ambang = 0; arus di bawah ambang atau pas di ambang = tak hingga; sedikit di atas = terhingga")
    def _():
        perlu(lg.sisa_waktu_menit(1.6, 50, 10, 1200, 1.6) == 0.0)
        perlu(math.isinf(lg.sisa_waktu_menit(0.5, 10.0, 10, 1200, 1.6)))
        perlu(math.isinf(lg.sisa_waktu_menit(0.5, 10 * math.sqrt(1.6), 10, 1200, 1.6)))
        t = lg.sisa_waktu_menit(0.5, 10 * math.sqrt(1.6) + 0.01, 10, 1200, 1.6)
        perlu(math.isfinite(t) and t > 0, str(t))

    @cek("sisa_waktu_menit: arus lebih besar -> sisa waktu lebih singkat")
    def _():
        t = [lg.sisa_waktu_menit(0.5, i, 10, 1200, 1.6) for i in (13, 15, 20, 30)]
        perlu(all(np.diff(t) < 0), str(t))

    @cek("aksi_dari_status: 1 baris atau kolom tidak ada -> kosong; bolak-balik 0,1,1,0,1 = 3 aksi bergantian")
    def _():
        perlu(len(lg.aksi_dari_status(df_(baterai_aktif=[1]))) == 0)
        perlu(len(lg.aksi_dari_status(df_(x=[1, 0]))) == 0)
        a = lg.aksi_dari_status(df_(baterai_aktif=[0, 1, 1, 0, 1]))
        perlu(len(a) == 3 and "lepas" in a["aksi"].iloc[0] and "kembali" in a["aksi"].iloc[1], str(a))

    @cek("ringkas_rekaman: rekaman kosong semua nol; jeda rekam > 10 detik tidak dihitung sebagai durasi")
    def _():
        kosong = pd.DataFrame({"waktu": pd.to_datetime([]), "arus": [], "daya_aktif": []})
        r = lg.ringkas_rekaman(kosong, 10)
        perlu(r["durasi_menit"] == 0 and r["arus_maks"] == 0 and r["jumlah_aksi"] == 0, str(r))
        d = pd.DataFrame({"waktu": pd.to_datetime(["2026-11-01 00:00:00", "2026-11-01 00:00:05",
                                                   "2026-11-01 01:00:00", "2026-11-01 01:00:05"]),
                          "arus": [12.0] * 4, "daya_aktif": [2640.0] * 4})
        r = lg.ringkas_rekaman(d, 10)
        perlu(abs(r["durasi_menit"] - 10 / 60) < 1e-9, f"durasi {r['durasi_menit']} menit")
        perlu(abs(r["menit_di_atas_batas"] - r["durasi_menit"]) < 1e-9)

    @cek("jenis_data dan kolom_hilang: kolom asing -> tidak_dikenal, semua kolom wajib dilaporkan hilang")
    def _():
        perlu(lg.jenis_data(df_(a=[1])) == "tidak_dikenal")
        perlu(lg.kolom_hilang(df_(a=[1])) == list(lg.KOLOM_WAJIB[1:]))

    @cek("muat: waktu tidak berurutan diurutkan; sel kosong aksi/alat_aktif menjadi teks kosong, bukan NaN")
    def _():
        (tmp / "acak.csv").write_text("waktu,aksi,alat_aktif\n2026-11-01 00:00:02,,\n2026-11-01 00:00:01,x,a\n",
                                      encoding="utf-8")
        d = lg.muat(tmp / "acak.csv")
        perlu(d["waktu"].is_monotonic_increasing and d["aksi"].tolist() == ["x", ""] and d["alat_aktif"].tolist() == ["a", ""],
              str(d))

    @cek("daftar_rekaman: folder tidak ada -> []; logbook.csv dan uji_trip*.csv tidak ikut")
    def _():
        perlu(lg.daftar_rekaman(tmp / "tidak_ada") == [])
        raw = tmp / "raw"
        raw.mkdir()
        for n in ("logbook.csv", "uji_trip_4A.csv", "setrika_01.csv", "catatan.txt"):
            (raw / n).write_text("x", encoding="utf-8")
        perlu([p.name for p in lg.daftar_rekaman(raw)] == ["setrika_01.csv"], str(lg.daftar_rekaman(raw)))

    @cek("parameter_mcb dan daftar_model: folder tidak ada -> None / []; parameter terbaru dibaca bila ada")
    def _():
        perlu(lg.parameter_mcb(tmp / "tidak_ada") is None and lg.daftar_model(tmp / "tidak_ada") == [])
        lap = tmp / "laporan" / "mcb1"
        lap.mkdir(parents=True)
        (lap / "parameter_mcb.json").write_text(json.dumps({"tau_detik": 900.0}), encoding="utf-8")
        par = lg.parameter_mcb(tmp / "laporan")
        perlu(par and par["tau_detik"] == 900.0 and "sumber" in par, str(par))

    @cek("disagregasi dasbor: rekaman datar (tanpa event) menghasilkan status semua mati dan energi 0")
    def _():
        import joblib
        joblib.dump(paket_sederhana(), tmp / "model_kecil.joblib")
        tabel, energi = lg.disagregasi(seri(np.full(120, 100.0)), tmp / "model_kecil.joblib")
        perlu(len(tabel) == 120 and not tabel[["a", "b"]].to_numpy().any(), "ada alat dinyatakan menyala")
        perlu(all(v == 0 for v in energi.values()), str(energi))

    # -----------------------------------------------------------------------
    kelompok("Pelacakan dan pelatihan (analisis/disagregasi.py, latih_klasifikasi.py)")
    paket = paket_sederhana()

    @cek("lacak: satu alat 500 W menyala 100 detik -> alat a menyala sekitar 100 detik, alat b tidak")
    def _():
        d = seri(langkah_daya((100, 100), (600, 100), (100, 100)))
        _, st = dg.lacak(d, de.deteksi(d), paket)
        perlu(90 <= st["a"].sum() <= 110 and st["b"].sum() == 0, f"a={st['a'].sum()}, b={st['b'].sum()}")

    @cek("lacak: event mati tanpa event nyala sebelumnya tidak membuat program berhenti")
    def _():
        d = seri(langkah_daya((600, 100), (100, 100), seed=1))
        ev = de.deteksi(d)
        perlu(ev["arah"].tolist() == ["mati"], str(ev["arah"].tolist()))
        dg.lacak(d, ev, paket)

    @cek("lacak: rekaman tanpa satu pun event tidak membuat program berhenti; semua alat tetap mati")
    def _():
        d = seri(np.full(300, 100.0))
        ev, st = dg.lacak(d, de.deteksi(d), paket)
        perlu(st["a"].sum() == 0 and st["b"].sum() == 0 and len(ev) == 0)

    @cek("lacak: tabel event kosong tanpa kolom sama sekali (sumber lain) juga tidak membuat program berhenti")
    def _():
        d = seri(np.full(300, 100.0))
        _, st = dg.lacak(d, pd.DataFrame(), paket)
        perlu(st["a"].sum() == 0)

    @cek("disagregasi.py lewat baris perintah pada rekaman datar: selesai, energi semua alat 0")
    def _():
        import joblib
        joblib.dump(paket, tmp / "model_cli.joblib")
        seri(np.full(300, 100.0)).to_csv(tmp / "datar_cli.csv", index=False)
        utama(dg.main, tmp / "datar_cli.csv", tmp / "model_cli.joblib", "--keluaran", tmp / "hasil_cli.csv")
        out = pd.read_csv(tmp / "hasil_cli.csv")
        perlu(len(out) == 300 and out["alat_aktif_est"].fillna("").eq("").all())

    @cek("label_dari_kebenaran: event di luar toleransi waktu dibuang; yang cocok diberi label")
    def _():
        d = seri(langkah_daya((100, 100), (600, 100), (100, 100)))
        ev = de.deteksi(d)
        jauh = tmp / "gt_jauh.csv"
        pd.DataFrame({"waktu": [pd.Timestamp("2026-12-01")], "alat": ["a"]}).to_csv(jauh, index=False)
        perlu(len(lk.label_dari_kebenaran(ev, jauh)) == 0)
        dekat = tmp / "gt_dekat.csv"
        pd.DataFrame({"waktu": ev["waktu"], "alat": ["a", "a"]}).to_csv(dekat, index=False)
        perlu(lk.label_dari_kebenaran(ev, dekat)["alat"].tolist() == ["a", "a"])

    @cek("latih_klasifikasi: event tanpa label -> berhenti dengan pesan jelas")
    def _():
        ev = de.deteksi(seri(langkah_daya((100, 100), (600, 100), (100, 100))))
        ev.to_csv(tmp / "ev_tanpa_label.csv", index=False)
        try:
            utama(lk.main, tmp / "ev_tanpa_label.csv", "--keluaran", tmp / "lap_a")
        except SystemExit as e:
            perlu("belum berlabel" in str(e), str(e))
            return
        raise AssertionError("seharusnya SystemExit")

    @cek("latih_klasifikasi: tiap alat hanya 1 event -> berhenti dengan pesan minimal 2 event")
    def _():
        ev = de.deteksi(seri(langkah_daya((100, 100), (600, 100), (100, 100)))).assign(alat=["a", "b"])
        ev.to_csv(tmp / "ev_satu.csv", index=False)
        try:
            utama(lk.main, tmp / "ev_satu.csv", "--keluaran", tmp / "lap_b")
        except SystemExit as e:
            perlu("minimal 2" in str(e), str(e))
            return
        raise AssertionError("seharusnya SystemExit")

    # -----------------------------------------------------------------------
    kelompok("Perekam serial (alat/perekam_serial.py): baris dari ESP32 yang rusak")
    kol = ps.KOLOM_DEFAULT.split(",")
    normal = "DATA,220.1,9.5,2050.0,0.98,400.0,1.12,0"

    @cek("baris normal diurai menjadi 7 nilai desimal")
    def _():
        r = ps.urai(normal, kol)
        perlu(r is not None and len(r) == 7 and r["daya_aktif"] == 2050.0, str(r))

    @cek("baris bukan DATA (log, kosong, tanpa awalan) diabaikan")
    def _():
        for b in ("", "log: mulai", "ERR,1,2", "data,1,2,3,4,5,6,7", "  DATA,1,2,3,4,5,6,7"):
            perlu(ps.urai(b, kol) is None, f"diterima: {b!r}")

    @cek("jumlah kolom kurang atau lebih, kolom kosong, atau bukan angka -> ditolak")
    def _():
        for b in ("DATA,1,2", "DATA,1,2,3,4,5,6,7,8", "DATA,220,,2,3,4,5,0", "DATA,a,2,3,4,5,6,7", "DATA,"):
            perlu(ps.urai(b, kol) is None, f"diterima: {b!r}")

    @cek("spasi di sekitar angka dan karakter CR di ujung baris (kabel serial Windows) tetap bisa diurai")
    def _():
        perlu(ps.urai("DATA, 220 ,1,2,3,4,5,0", kol) is not None)
        perlu(ps.urai(normal + "\r", kol) is not None)

    @cek("nilai nan, inf, -inf ditolak (agar tidak masuk ke CSV dan merusak analisis); angka besar yang sah tetap diterima")
    def _():
        for b in ("DATA,nan,9.5,2050.0,0.98,400.0,1.12,0", "DATA,220,inf,2050.0,0.98,400.0,1.12,0",
                  "DATA,220,9.5,-inf,0.98,400.0,1.12,0", "DATA,220,9.5,2050.0,0.98,400.0,NaN,0"):
            perlu(ps.urai(b, kol) is None, f"diterima: {b!r}")
        perlu(ps.urai("DATA,220,9.5,1e6,0.98,400.0,1.12,0", kol) is not None, "angka besar yang sah ditolak")

    # -----------------------------------------------------------------------
    kelompok("Data sintetis (analisis/data_sintetis.py)")

    @cek("seed sama -> data identik; seed beda -> data berbeda")
    def _():
        a, b, c = (ds.buat(jam=0.3, seed=s)[0] for s in (3, 3, 4))
        perlu(a.equals(b) and not a.equals(c))

    @cek("kolom wajib ada dan daya tidak pernah negatif; jumlah baris = jam x 3600")
    def _():
        d, ev = ds.buat(jam=0.2, seed=1)
        perlu({"waktu", "daya_aktif", "daya_reaktif", "arus", "alat_aktif"} <= set(d.columns))
        perlu(len(d) == 720 and d["daya_aktif"].min() >= 0, f"{len(d)} baris, min {d['daya_aktif'].min()}")

    # -----------------------------------------------------------------------
    kelompok("Keputusan kendali dari NILM (analisis/keputusan_kendali.py, pengendali_nilm.py)")

    def cfg_(**lain):
        dasar = dict(in_mcb=10.0, tau=900.0, theta_trip=1.45, kapasitas_inverter_va=2500.0,
                     kanal={"setrika_uap": 1, "oven_listrik": 2})
        return kk.Konfigurasi(**{**dasar, **lain})

    def keadaan_(p, q=0.0, theta=0.5, aktif=None, **lain):
        return kk.Keadaan(theta=theta, p=p, q=q, aktif=aktif or {}, **lain)

    @cek("Konfigurasi menolak kompresor (freezer, kulkas, ac) di kanal pindah, dan parameter tak masuk akal")
    def _():
        for alat in ("freezer", "kulkas", "ac"):
            try:
                cfg_(kanal={alat: 1})
            except ValueError as e:
                perlu("kompresor" in str(e), str(e))
            else:
                raise AssertionError(f"{alat} seharusnya ditolak")
        for salah in (dict(in_mcb=0), dict(tau=-1), dict(theta_trip=1.0), dict(margin=0.0), dict(margin=1.0)):
            try:
                cfg_(**salah)
            except ValueError:
                continue
            raise AssertionError(f"{salah} seharusnya ditolak")

    @cek("waktu_ke_ambang: sudah lewat = 0; tunak di bawah ambang = tak hingga; makin besar beban makin cepat")
    def _():
        perlu(kk.waktu_ke_ambang(1.3, 3.0, 1.16, 900) == 0.0)
        perlu(math.isinf(kk.waktu_ke_ambang(0.5, 1.0, 1.16, 900)) and math.isinf(kk.waktu_ke_ambang(0.5, 1.16, 1.16, 900)))
        t = [kk.waktu_ke_ambang(0.5, s_, 1.16, 900) for s_ in (1.3, 2.0, 4.0)]
        perlu(all(np.diff(t) < 0) and t[-1] > 0, str(t))

    @cek("keputusan: beban aman (arus jauh di bawah batas) -> tunggu; tidak memindahkan apa pun")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=1200, aktif={"setrika_uap": (1000.0, 20.0)}))
        perlu(k.aksi == "tunggu", f"{k}")

    @cek("keputusan: beban lebih -> pindah alat berkanal yang PALING banyak meredam; alat tanpa kanal tidak pernah dipilih")
    def _():
        aktif = {"setrika_uap": (2000.0, 40.0), "oven_listrik": (1500.0, 30.0), "mixer": (2400.0, 300.0)}
        k = kk.keputusan(cfg_(), keadaan_(p=5900, q=370, theta=1.0, aktif=aktif))
        perlu(k.aksi == "pindah" and k.alat == "setrika_uap", f"{k}")
        perlu(k.s_setelah < kk.pemanasan_tunak(kk.arus(5900, 370, 220), 10.0))

    @cek("keputusan: pindah belum cukup -> tetap pindah, ditandai cukup=False")
    def _():
        k = kk.keputusan(cfg_(kanal={"oven_listrik": 1}),
                         keadaan_(p=5900, q=370, theta=1.0, aktif={"oven_listrik": (1500.0, 30.0)}))
        perlu(k.aksi == "pindah" and k.cukup is False, f"{k}")

    @cek("keputusan: alat yang melebihi kapasitas inverter dilewati; bila tak ada yang muat -> peringatan, bukan error")
    def _():
        k = kk.keputusan(cfg_(kapasitas_inverter_va=1000.0, kanal={"setrika_uap": 1}),
                         keadaan_(p=5900, q=370, theta=0.5, aktif={"setrika_uap": (2000.0, 40.0)}))
        perlu(k.aksi == "peringatan", f"{k}")

    @cek("keputusan: alat yang sudah di baterai tidak dipindah dua kali")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=4000, q=100, theta=1.0, aktif={"setrika_uap": (2000.0, 40.0)},
                                          dibaterai={"setrika_uap": (2000.0, 40.0)},
                                          detik_di_baterai={"setrika_uap": 30.0}))
        perlu(k.aksi != "pindah" or k.alat != "setrika_uap", f"{k}")

    @cek("keputusan: NILM tidak konsisten dengan ukuran (alat dikira 2000 W padahal total 300 W) -> bukan kandidat")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=300, q=50, theta=1.5, aktif={"setrika_uap": (2000.0, 40.0)}))
        perlu(not (k.aksi == "pindah" and k.cukup), f"{k}")

    @cek("jaring pengaman: pemanasan melewati ambang aman tetapi NILM tak menemukan kandidat -> pindah alat di kanal bebas (DARURAT)")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=5900, q=370, theta=1.3, aktif={},
                                          tipikal={"setrika_uap": (2035.0, 43.0), "oven_listrik": (1551.0, 29.0)}))
        perlu(k.aksi == "pindah" and k.alat == "setrika_uap" and "DARURAT" in k.alasan, f"{k}")

    @cek("jaring pengaman hanya bila pemanasan SUDAH melewati ambang aman; sebelum itu cukup peringatan")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=5900, q=370, theta=0.9, aktif={},
                                          tipikal={"setrika_uap": (2035.0, 43.0)}))
        perlu(k.aksi == "peringatan", f"{k}")

    @cek("keputusan: jeda minimal antar aksi pelindung dihormati walau berbahaya")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=5900, q=370, theta=1.0, aktif={"setrika_uap": (2000.0, 40.0)},
                                          detik_sejak_lindung=3.0))
        perlu(k.aksi == "tunggu", f"{k}")

    @cek("kembali ke PLN: butuh pemanasan rendah + cukup lama di baterai + beban dengan alat itu masih aman")
    def _():
        c = cfg_()
        dasar = dict(p=300, q=50, theta=0.4, dibaterai={"setrika_uap": (2000.0, 40.0)})
        perlu(kk.keputusan(c, keadaan_(**dasar, detik_di_baterai={"setrika_uap": 60.0})).aksi == "tunggu", "terlalu cepat kembali")
        perlu(kk.keputusan(c, keadaan_(**{**dasar, "theta": 1.2}, detik_di_baterai={"setrika_uap": 600.0})).aksi == "tunggu",
              "kembali padahal pemanasan masih tinggi")
        k = kk.keputusan(c, keadaan_(**dasar, detik_di_baterai={"setrika_uap": 600.0}))
        perlu(k.aksi == "kembali" and k.alat == "setrika_uap", f"{k}")
        k = kk.keputusan(c, keadaan_(**{**dasar, "p": 1800, "q": 40}, detik_di_baterai={"setrika_uap": 600.0}))
        perlu(k.aksi == "tunggu" and "ditahan" in k.alasan, f"bolak-balik tidak dicegah: {k}")

    @cek("setelah alat dipindah, pemanasan masih di atas ambang tetapi beban sudah ringan (pemanasan menurun) -> tidak memindah alat lain")
    def _():
        c = cfg_()
        perlu(c.ambang < 1.3, "asumsi tes: ambang aman di bawah 1,3")
        k = kk.keputusan(c, keadaan_(p=1500, q=100, theta=1.3, aktif={"oven_listrik": (1400.0, 30.0)},
                                     dibaterai={"setrika_uap": (2000.0, 40.0)}, detik_di_baterai={"setrika_uap": 20.0},
                                     detik_sejak_lindung=20.0))
        perlu(k.aksi == "tunggu", f"memindah/memperingatkan padahal beban sudah ringan: {k}")

    @cek("pemanasan di atas ambang DAN beban tunak masih di atas ambang -> tetap bertindak")
    def _():
        k = kk.keputusan(cfg_(), keadaan_(p=4500, q=100, theta=1.3, aktif={"setrika_uap": (2000.0, 40.0)}))
        perlu(k.aksi == "pindah" and k.alat == "setrika_uap", f"{k}")

    @cek("PelacakStatus: alat terlarang (sedang di baterai) tidak dinyalakan oleh koreksi keseimbangan daya")
    def _():
        for terlarang, harapan in ((set(), {"a"}), ({"a"}, set())):
            pel = dg.PelacakStatus(paket_sederhana())
            pel.terlarang = set(terlarang)
            pel.langkah(30, None, median_p=100.0 + 510.0, dasar=100.0)
            perlu(pel.aktif == harapan, f"terlarang={terlarang}: aktif={pel.aktif}")

    @cek("PengendaliNILM: beban konstan yang aman tidak menimbulkan aksi atau error")
    def _():
        peng = pn.PengendaliNILM(paket_sederhana(), cfg_(kanal={"b": 1}, in_mcb=20.0))
        for t in range(300):
            perlu(peng.langkah(float(t), 100.0, 20.0, 220.0) == [], f"aksi tak semestinya di t={t}")
        perlu(len(peng.riwayat) == 0)

    @cek("PengendaliNILM: beban lebih -> alat dikenali lalu dipindah; tidak kembali selagi sendirian saja sudah melebihi batas")
    def _():
        cfg = cfg_(kanal={"b": 1}, in_mcb=4.0, tau=300.0, kapasitas_inverter_va=2500.0)
        peng = pn.PengendaliNILM(paket_sederhana(), cfg)
        dipindah, aksi = False, []
        for t in range(900):
            p_b = 1975.0 if t >= 60 and not dipindah else 0.0
            for k in peng.langkah(float(t), 100.0 + p_b, 20.0 + (43.0 if p_b else 0.0), 220.0):
                aksi.append((t, k.aksi, k.alat))
                if k.aksi == "pindah":
                    dipindah = True
                elif k.aksi == "kembali":
                    dipindah = False
        pindahan = [a for a in aksi if a[1] == "pindah"]
        perlu(len(pindahan) == 1 and pindahan[0][2] == "b", f"aksi: {aksi}")
        perlu(60 < pindahan[0][0] < 200, f"pindah pada t={pindahan[0][0]} detik")
        perlu(not any(a[1] == "kembali" for a in aksi), f"alat kembali padahal sendirian saja melebihi batas: {aksi}")

    @cek("PengendaliNILM.reset: mengosongkan status, pemanasan, dan riwayat")
    def _():
        peng = pn.PengendaliNILM(paket_sederhana(), cfg_(kanal={"b": 1}, in_mcb=4.0, tau=300.0))
        for t in range(200):
            peng.langkah(float(t), 100.0 + (1975.0 if t >= 20 else 0.0), 20.0, 220.0)
        perlu(peng.theta > 0.5 and len(peng.riwayat) > 0)
        peng.reset()
        perlu(peng.theta == 0.0 and peng.n == 0 and not peng.riwayat and not peng.dibaterai and not peng.pelacak.aktif)

    # ---------------------------------------------------------------------
    n = {s: sum(1 for h in hasil if h[2] == s) for s in ("LULUS", "GAGAL", "CELAH")}
    print("\n" + "=" * 78)
    print(f"{n['LULUS']} lulus, {n['GAGAL']} gagal, {n['CELAH']} celah diketahui, {time.time() - t0:.1f} detik.")
    celah_ = [h for h in hasil if h[2] == "CELAH"]
    if celah_:
        print("\nCelah yang sudah diketahui (belum diperbaiki di kode sumber):")
        for k, nama, _, ket in celah_:
            print(f"  - {nama}\n      {ket}")
    gagal = [h for h in hasil if h[2] == "GAGAL"]
    if gagal:
        print("\nGAGAL:")
        for k, nama, _, ket in gagal:
            print(f"  - [{k}] {nama}\n      {ket}")
    print("\nCatatan: semua data sintetis. Hasil ini bukan kinerja alat.")
    sys.exit(1 if gagal or (a.ketat and celah_) else 0)


if __name__ == "__main__":
    main()
