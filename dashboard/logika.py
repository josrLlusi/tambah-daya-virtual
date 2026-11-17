"""Fungsi hitung untuk dasbor (tanpa Streamlit, supaya mudah diuji)."""
import numpy as np
import pandas as pd

IN_MCB = 20.0        # arus nominal MCB [A]; ganti sesuai MCB panel uji
THETA_TRIP = 1.6     # ambang trip model termal [relatif] (ilustratif, lihat sim/simulasi_mcb.py)
THETA_AMAN = 1.3     # ambang tindakan sistem [relatif] (ilustratif)
TEGANGAN = 220.0     # tegangan nominal [V]

KOLOM_WAJIB = ("waktu", "arus_tanpa_kendali", "arus_kendali")

NAMA_ALAT = {
    "lampu_kipas": "Lampu & kipas",
    "mesin_jahit": "Mesin jahit",
    "setrika_uap": "Setrika uap",
    "mesin_press": "Mesin press",
}

NAMA_AKSI = {
    "setrika_uap_ke_baterai": "Setrika uap dipindah ke baterai",
    "setrika_uap_kembali_ke_pln": "Setrika uap dikembalikan ke PLN",
}


def nama_alat(kode):
    return NAMA_ALAT.get(kode, kode.replace("_", " ").capitalize())


def nama_aksi(kode):
    return NAMA_AKSI.get(kode, kode.replace("_", " ").capitalize())


def muat(path_atau_buffer):
    df = pd.read_csv(path_atau_buffer, parse_dates=["waktu"])
    for k in ("aksi", "alat_aktif"):
        if k in df.columns:
            df[k] = df[k].fillna("")
    return df.sort_values("waktu").reset_index(drop=True)


def kolom_hilang(df):
    """Kolom wajib yang tidak ada di data."""
    return [k for k in KOLOM_WAJIB if k not in df.columns]


def kejadian_trip(df, kolom_trip="mcb_trip_tanpa_kendali"):
    """Jumlah kejadian trip (perpindahan 0 -> 1)."""
    if kolom_trip not in df.columns:
        return 0
    s = df[kolom_trip].to_numpy()
    return int(((s[1:] == 1) & (s[:-1] == 0)).sum() + (1 if len(s) and s[0] == 1 else 0))


def waktu_trip_pertama(df, kolom_trip="mcb_trip_tanpa_kendali"):
    """Waktu trip pertama, atau None."""
    if kolom_trip not in df.columns:
        return None
    d = df.loc[df[kolom_trip] == 1, "waktu"]
    return d.iloc[0] if len(d) else None


def energi_baterai_kwh(df, daya_alat_w=2000.0):
    """Perkiraan energi yang dialihkan ke baterai (alat dipindah selama baterai_aktif=1)."""
    if "baterai_aktif" not in df.columns or len(df) < 2:
        return 0.0
    dt_jam = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy() / 3600.0
    return float((df["baterai_aktif"].to_numpy() * dt_jam).sum() * daya_alat_w / 1000.0)


def durasi_baterai_menit(df):
    if "baterai_aktif" not in df.columns or len(df) < 2:
        return 0.0
    dt = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy()
    return float((df["baterai_aktif"].to_numpy() * dt).sum() / 60.0)


def tambahan_daya_va(df, tegangan=TEGANGAN, kolom_tanpa="arus_tanpa_kendali", in_mcb=IN_MCB,
                     kolom_trip_kendali="mcb_trip_kendali"):
    """Tambahan daya efektif (VA): beban puncak yang diminta melebihi daya terpasang MCB.

    Klaim ini HANYA diberikan bila bisa diverifikasi, karena angkanya dipakai sebagai klaim kinerja:
      - kolom trip dengan kendali harus ada (tanpa kolom itu tidak diketahui apakah MCB turun),
      - kolom arus tanpa kendali harus ada dan berisi angka,
      - tidak boleh ada MCB turun pada kondisi dengan kendali.
    Bila salah satu tidak terpenuhi, tambahan_va = 0.0 dan `alasan` menjelaskan; `terverifikasi` False hanya bila
    datanya tidak cukup untuk menilai (bila ada trip dengan kendali, hasil 0 itu sendiri adalah penilaian yang sah).
    ada_trip: True/False, atau None bila tidak dapat dinilai."""
    terpasang = in_mcb * tegangan
    puncak = df[kolom_tanpa].max() if kolom_tanpa in df.columns and len(df) else float("nan")
    diminta = float(puncak * tegangan) if pd.notna(puncak) else float("nan")
    if kolom_trip_kendali not in df.columns:
        ada_trip, terverifikasi = None, False
        alasan = f"kolom {kolom_trip_kendali} tidak ada: tidak diketahui apakah MCB turun dengan kendali"
    elif pd.isna(diminta):
        ada_trip, terverifikasi = kejadian_trip(df, kolom_trip_kendali) > 0, False
        alasan = f"kolom {kolom_tanpa} tidak ada atau kosong: beban puncak tidak diketahui"
    else:
        ada_trip, terverifikasi, alasan = kejadian_trip(df, kolom_trip_kendali) > 0, True, ""
    tambahan = max(diminta - terpasang, 0.0) if terverifikasi and not ada_trip else 0.0
    return dict(terpasang_va=terpasang, beban_diminta_va=diminta, ada_trip=ada_trip,
                terverifikasi=terverifikasi, alasan=alasan, tambahan_va=tambahan)


def log_aksi(df):
    if "aksi" not in df.columns:
        return pd.DataFrame(columns=["waktu", "aksi"])
    d = df[df["aksi"] != ""][["waktu", "aksi"]]
    return d.reset_index(drop=True)


def segmen_alat(df):
    """Rentang waktu tiap alat menyala, dari kolom alat_aktif (dipisah '|').
    Hasil: DataFrame [alat, mulai, selesai]."""
    if "alat_aktif" not in df.columns or df.empty:
        return pd.DataFrame(columns=["alat", "mulai", "selesai"])
    waktu = df["waktu"].to_numpy()
    akhir = df["waktu"].iloc[-1]
    if len(df) > 1:
        akhir = akhir + (df["waktu"].iloc[-1] - df["waktu"].iloc[-2])
    set_aktif = [set(filter(None, s.split("|"))) for s in df["alat_aktif"]]
    semua = sorted(set().union(*set_aktif))
    baris = []
    for alat in semua:
        nyala = np.array([alat in s for s in set_aktif])
        mulai = None
        for i, v in enumerate(nyala):
            if v and mulai is None:
                mulai = waktu[i]
            elif not v and mulai is not None:
                baris.append((alat, mulai, waktu[i]))
                mulai = None
        if mulai is not None:
            baris.append((alat, mulai, akhir))
    return pd.DataFrame(baris, columns=["alat", "mulai", "selesai"])


def segmen_biner(df, kolom):
    """Rentang waktu kolom biner bernilai 1. Hasil: DataFrame [mulai, selesai]."""
    if kolom not in df.columns or df.empty:
        return pd.DataFrame(columns=["mulai", "selesai"])
    s = df[kolom].to_numpy()
    w = df["waktu"].to_numpy()
    baris, mulai = [], None
    for i, v in enumerate(s):
        if v == 1 and mulai is None:
            mulai = w[i]
        elif v != 1 and mulai is not None:
            baris.append((mulai, w[i]))
            mulai = None
    if mulai is not None:
        baris.append((mulai, w[-1]))
    return pd.DataFrame(baris, columns=["mulai", "selesai"])


# ---------------------------------------------------------------------------
# Rekaman panel uji (keluaran alat/perekam_serial.py), dipakai halaman
# dashboard/pages/1_Rekaman_dan_Pengenalan_Alat.py dan uji_semua.py
# ---------------------------------------------------------------------------
import json
import math
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
TAU_TEBAKAN, THETA_TRIP_TEBAKAN = 1200.0, 1.6   # hanya dipakai bila belum ada hasil analisis/fit_mcb.py


def jenis_data(df):
    """'simulasi' = berkas contoh dua skenario; 'rekaman' = data perangkat (kolom arus, daya_aktif)."""
    if "arus_tanpa_kendali" in df.columns:
        return "simulasi"
    if {"arus", "daya_aktif"} <= set(df.columns):
        return "rekaman"
    return "tidak_dikenal"


def daftar_rekaman(folder=None):
    """Berkas rekaman di data/raw, terbaru dulu. Logbook dan tabel uji trip tidak ikut."""
    folder = Path(folder) if folder else AKAR / "data" / "raw"
    if not folder.exists():
        return []
    ada = [p for p in folder.glob("*.csv") if p.name != "logbook.csv" and not p.name.startswith("uji_trip")]
    return sorted(ada, key=lambda p: p.stat().st_mtime, reverse=True)


def potong(df, bagian):
    """Ambil bagian awal data (0-1) untuk mode demo putar ulang. Minimal 2 baris."""
    n = max(2, int(round(len(df) * min(max(bagian, 0.0), 1.0))))
    return df.iloc[:n].reset_index(drop=True)


def parameter_mcb(folder=None):
    """Parameter MCB terbaru dari analisis/fit_mcb.py (laporan/*/parameter_mcb.json), atau None."""
    folder = Path(folder) if folder else AKAR / "laporan"
    ada = sorted(folder.glob("*/parameter_mcb.json"), key=lambda p: p.stat().st_mtime) if folder.exists() else []
    if not ada:
        return None
    par = json.loads(ada[-1].read_text(encoding="utf-8"))
    par["sumber"] = str(ada[-1].relative_to(folder.parent))
    return par


def hitung_theta(df, in_mcb, tau, theta_awal=0.0):
    """Pemanasan model termal orde-1 dari arus: dtheta/dt = ((I/In)^2 - theta)/tau (langkah eksak per sampel)."""
    arus = df["arus"].to_numpy(float)
    dt = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy()
    theta = np.empty(len(df))
    th = float(theta_awal)
    for j in range(len(df)):
        s = (arus[j] / in_mcb) ** 2
        th = s + (th - s) * math.exp(-max(dt[j], 0.0) / tau)
        theta[j] = th
    return theta


def sisa_waktu_menit(theta, arus, in_mcb, tau, theta_trip):
    """Perkiraan menit sebelum MCB turun bila arus sekarang bertahan. inf = tidak akan turun pada arus ini."""
    s = (arus / in_mcb) ** 2
    if theta >= theta_trip:
        return 0.0
    if s <= theta_trip:
        return float("inf")
    return tau * math.log((s - theta) / (s - theta_trip)) / 60.0


def aksi_dari_status(df, kolom="baterai_aktif"):
    """Log aksi dari perubahan kolom baterai_aktif (0 -> 1 pindah ke baterai, 1 -> 0 kembali ke PLN)."""
    if kolom not in df.columns or len(df) < 2:
        return pd.DataFrame(columns=["waktu", "aksi"])
    s = df[kolom].to_numpy(float) > 0.5
    ubah = np.where(s[1:] != s[:-1])[0] + 1
    return pd.DataFrame({"waktu": df["waktu"].iloc[ubah].to_numpy(),
                         "aksi": ["alat lepas dari PLN (baterai/tunda)" if s[j] else "alat kembali ke PLN" for j in ubah]})


def ringkas_rekaman(df, in_mcb):
    """Angka ringkas sebuah rekaman. Celah waktu > 10 detik (jeda rekam) tidak dihitung."""
    dt = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy()
    dt = np.where(dt > 10, 0, dt)
    arus = df["arus"].to_numpy(float)
    di_bat = df["baterai_aktif"].to_numpy(float) > 0.5 if "baterai_aktif" in df.columns else np.zeros(len(df), bool)
    return dict(
        durasi_menit=float(dt.sum() / 60),
        energi_pln_kwh=float((df["daya_aktif"].to_numpy(float) * dt).sum() / 3.6e6),
        arus_maks=float(arus.max()) if len(arus) else 0.0,
        menit_di_atas_batas=float(dt[arus > in_mcb].sum() / 60),
        menit_lepas_dari_pln=float(dt[di_bat].sum() / 60),
        jumlah_aksi=int(len(aksi_dari_status(df))),
    )


def daftar_model(folder=None):
    folder = Path(folder) if folder else AKAR / "laporan"
    return sorted(folder.glob("*/model.joblib"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []


def disagregasi(df, path_model):
    """Jalankan NILM (analisis/disagregasi.py) pada rekaman.
    Hasil: (tabel status per detik: kolom waktu + satu kolom bool per alat, energi kWh per alat)."""
    import joblib
    sys.path.insert(0, str(AKAR / "analisis"))
    from deteksi_event import deteksi, seragamkan_1detik
    from disagregasi import lacak

    d = seragamkan_1detik(df)
    paket = joblib.load(path_model)
    ev = deteksi(d)
    kelas = list(paket["kelas"])
    if ev.empty:
        status = {k: np.zeros(len(d), bool) for k in kelas}
    else:
        _, status = lacak(d, ev, paket)
    tabel = pd.DataFrame({"waktu": d["waktu"].to_numpy(), **{k: status[k] for k in kelas}})
    dt_jam = d["waktu"].diff().dt.total_seconds().fillna(0).to_numpy() / 3600.0
    dt_jam = np.where(dt_jam > 10 / 3600, 0, dt_jam)
    energi = {k: float((status[k] * paket["dP_tipikal"].get(k, 0.0) * dt_jam).sum() / 1000.0) for k in kelas}
    return tabel, energi
