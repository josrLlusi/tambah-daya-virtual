"""Fungsi hitung untuk dasbor (tanpa Streamlit, supaya mudah diuji)."""
import numpy as np
import pandas as pd

IN_MCB = 20.0  # arus nominal MCB [A]; ganti sesuai MCB panel uji


def muat(path_atau_buffer):
    df = pd.read_csv(path_atau_buffer, parse_dates=["waktu"])
    for k in ("aksi", "alat_aktif"):
        if k in df.columns:
            df[k] = df[k].fillna("")
    return df.sort_values("waktu").reset_index(drop=True)


def kejadian_trip(df, kolom_trip="mcb_trip_tanpa_kendali"):
    """Jumlah kejadian trip (perpindahan 0 -> 1)."""
    if kolom_trip not in df.columns:
        return 0
    s = df[kolom_trip].to_numpy()
    return int(((s[1:] == 1) & (s[:-1] == 0)).sum() + (1 if len(s) and s[0] == 1 else 0))


def energi_baterai_kwh(df, daya_alat_w=2000.0):
    """Perkiraan energi yang dialihkan ke baterai (alat dipindah selama baterai_aktif=1)."""
    if "baterai_aktif" not in df.columns or len(df) < 2:
        return 0.0
    dt_jam = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy() / 3600.0
    return float((df["baterai_aktif"].to_numpy() * dt_jam).sum() * daya_alat_w / 1000.0)


def tambahan_daya_va(df, tegangan=220.0, kolom_tanpa="arus_tanpa_kendali", in_mcb=IN_MCB,
                     kolom_trip_kendali="mcb_trip_kendali"):
    """Tambahan daya efektif (VA): beban puncak yang diminta melebihi daya terpasang MCB,
    dihitung HANYA bila tidak ada MCB trip pada kondisi dengan kendali. Bila ada trip, hasilnya 0."""
    terpasang = in_mcb * tegangan
    diminta = float(df[kolom_tanpa].max() * tegangan)
    ada_trip = kejadian_trip(df, kolom_trip_kendali) > 0
    return dict(terpasang_va=terpasang, beban_diminta_va=diminta,
                tambahan_va=0.0 if ada_trip else max(diminta - terpasang, 0.0))


def log_aksi(df):
    d = df[df["aksi"] != ""][["waktu", "aksi"]]
    return d.reset_index(drop=True)
