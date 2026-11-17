"""Deteksi event nyala/mati dari data daya (P, dan Q bila ada) dengan sampling sekitar 1 detik.

    python analisis/deteksi_event.py data/raw/setrika_*.csv --label setrika_uap --keluaran data/olah/event_setrika.csv
    python analisis/deteksi_event.py data/sample/agregat_sintetis.csv --keluaran data/olah/event_agregat.csv

Cara kerja: median filter untuk meredam derau, lalu cari perubahan daya > ambang antara
rata-rata 'sebelum' dan 'sesudah' (kondisi tunak). Event yang berdekatan digabung.
--label dipakai saat merekam satu alat saja (semua event diberi label alat itu).
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter

AMBANG_W = 40.0      # perubahan daya minimum dianggap event (sesuaikan dengan alat terkecil)
JENDELA = 5          # sampel untuk rata-rata tunak sebelum/sesudah
JARAK_MIN = 5        # sampel minimum antar event


def perluas(paths):
    """Perluas pola seperti data/raw/setrika_*.csv. PowerShell dan CMD di Windows tidak
    memperluas tanda * sendiri, jadi dilakukan di sini agar perintah sama di semua sistem."""
    hasil = []
    for p in paths:
        cocok = sorted(glob.glob(str(p))) if any(c in str(p) for c in "*?[") else [str(p)]
        if not cocok:
            raise SystemExit(f"Tidak ada berkas yang cocok dengan pola: {p}")
        hasil += cocok
    return hasil


def seragamkan_1detik(df):
    """Rekaman ESP32 berisi beberapa baris per detik; analisis memakai langkah 1 detik.
    Bila selang median < 0,9 detik, data dirata-rata per detik. Detik kosong (jeda antar rekaman) dibuang."""
    if len(df) < 3:
        return df
    selang = df["waktu"].diff().dt.total_seconds().median()
    if not selang or selang >= 0.9:
        return df
    angka = [k for k in df.columns if k != "waktu" and pd.api.types.is_numeric_dtype(df[k])]
    lain = [k for k in df.columns if k != "waktu" and k not in angka]
    cara = {k: "mean" for k in angka}
    cara.update({k: "first" for k in lain})
    for k in ("baterai_aktif", "mcb_trip"):
        if k in cara:
            cara[k] = "max"
    d = df.set_index("waktu").resample("1s").agg(cara)
    d = d.dropna(subset=["daya_aktif"]).reset_index()
    return d[list(df.columns)]


def muat(paths):
    bag = [pd.read_csv(p, parse_dates=["waktu"]) for p in perluas(paths)]
    df = pd.concat(bag, ignore_index=True).sort_values("waktu").reset_index(drop=True)
    return seragamkan_1detik(df)


def deteksi(df, ambang=AMBANG_W, jendela=JENDELA, jarak_min=JARAK_MIN, faktor_derau=6.0):
    """Event = perubahan daya yang (1) lebih besar dari ambang, (2) lebih besar dari faktor_derau x derau lokal,
    dan (3) bertahan: rata-rata 'sesudah' berbeda dari 'sebelum' pada jendela tunak di luar masa transisi."""
    kolom = ["indeks", "waktu", "dP", "P_sebelum", "P_sesudah"]
    if "daya_reaktif" in df:
        kolom.append("dQ")
    if "arus" in df:
        kolom.append("rasio_puncak")
    kolom.append("arah")
    P_asli = df["daya_aktif"].to_numpy(float)
    n = len(P_asli)
    lag = 3
    if n <= 2 * (lag + jendela):
        # terlalu pendek untuk membandingkan 'sebelum' dan 'sesudah' (termasuk data kosong):
        # kembalikan tabel kosong BERKOLOM LENGKAP supaya kode berikutnya (fitur, disagregasi, CSV) tidak error
        return pd.DataFrame(columns=kolom)
    P = median_filter(P_asli, size=7, mode="nearest")
    Q = median_filter(df["daya_reaktif"].to_numpy(float), size=7, mode="nearest") if "daya_reaktif" in df else None
    d = np.zeros(n)
    d[lag:n - lag] = P[2 * lag:] - P[:n - 2 * lag]
    # derau lokal: deviasi absolut median dari selisih sampel berurutan (tahan terhadap event)
    selisih = pd.Series(np.abs(np.diff(P_asli, prepend=P_asli[0])))
    derau = selisih.rolling(61, center=True, min_periods=5).median().to_numpy() * 1.4826
    kandidat = []
    for j in range(lag + jendela, n - lag - jendela):
        if abs(d[j]) < ambang or abs(d[j]) < np.max(np.abs(d[max(j - jarak_min, 0):j + jarak_min + 1])):
            continue                                   # bukan puncak lokal perubahan
        sb = P_asli[j - lag - jendela:j - lag].mean()
        ss = P_asli[j + lag + 1:j + lag + 1 + jendela].mean()
        dp = ss - sb
        if abs(dp) < max(ambang, faktor_derau * derau[j] / np.sqrt(jendela)):
            continue
        if kandidat and j - kandidat[-1]["indeks"] < jarak_min:
            continue
        e = {"indeks": j, "waktu": df["waktu"].iloc[j], "dP": dp, "P_sebelum": sb, "P_sesudah": ss}
        if Q is not None:
            q = df["daya_reaktif"].to_numpy(float)
            e["dQ"] = q[j + lag + 1:j + lag + 1 + jendela].mean() - q[j - lag - jendela:j - lag].mean()
        if "arus" in df:
            a = df["arus"].to_numpy(float)
            # rasio lonjakan arus saat start (berguna bila sampling cukup cepat untuk menangkapnya)
            e["rasio_puncak"] = a[j - 1:j + lag + 1].max() / max(a[j + lag + 1:j + lag + 1 + jendela].mean(), 1e-6)
        kandidat.append(e)
    ev = pd.DataFrame(kandidat, columns=kolom)   # tanpa kandidat pun kolomnya lengkap
    if not ev.empty:
        ev["arah"] = np.where(ev["dP"] > 0, "nyala", "mati")
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("berkas", nargs="+")
    ap.add_argument("--label", default=None, help="nama alat bila rekaman berisi satu alat saja")
    ap.add_argument("--ambang", type=float, default=AMBANG_W)
    ap.add_argument("--keluaran", default="data/olah/event.csv")
    a = ap.parse_args()
    ev = deteksi(muat(a.berkas), ambang=a.ambang)
    if a.label:
        ev["alat"] = a.label
    Path(a.keluaran).parent.mkdir(parents=True, exist_ok=True)
    ev.to_csv(a.keluaran, index=False)
    print(f"{len(ev)} event -> {a.keluaran}")


if __name__ == "__main__":
    main()
