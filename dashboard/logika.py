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
    """Tambahan daya efektif (VA): beban puncak yang diminta melebihi daya terpasang MCB,
    dihitung HANYA bila tidak ada MCB trip pada kondisi dengan kendali. Bila ada trip, hasilnya 0."""
    terpasang = in_mcb * tegangan
    diminta = float(df[kolom_tanpa].max() * tegangan)
    ada_trip = kejadian_trip(df, kolom_trip_kendali) > 0
    return dict(terpasang_va=terpasang, beban_diminta_va=diminta, ada_trip=ada_trip,
                tambahan_va=0.0 if ada_trip else max(diminta - terpasang, 0.0))


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
