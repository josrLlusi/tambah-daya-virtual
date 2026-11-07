"""Deteksi event nyala/mati dari data daya (P, dan Q bila ada) dengan sampling sekitar 1 detik.

    python analisis/deteksi_event.py data/raw/setrika_*.csv --label setrika_uap --keluaran data/olah/event_setrika.csv
    python analisis/deteksi_event.py data/sample/agregat_sintetis.csv --keluaran data/olah/event_agregat.csv

Cara kerja: median filter untuk meredam derau, lalu cari perubahan daya > ambang antara
rata-rata 'sebelum' dan 'sesudah' (kondisi tunak). Event yang berdekatan digabung.
--label dipakai saat merekam satu alat saja (semua event diberi label alat itu).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter

AMBANG_W = 40.0      # perubahan daya minimum dianggap event (sesuaikan dengan alat terkecil)
JENDELA = 5          # sampel untuk rata-rata tunak sebelum/sesudah
JARAK_MIN = 5        # sampel minimum antar event


def muat(paths):
    bag = [pd.read_csv(p, parse_dates=["waktu"]) for p in paths]
    return pd.concat(bag, ignore_index=True).sort_values("waktu").reset_index(drop=True)


def deteksi(df, ambang=AMBANG_W, jendela=JENDELA, jarak_min=JARAK_MIN, faktor_derau=6.0):
    """Event = perubahan daya yang (1) lebih besar dari ambang, (2) lebih besar dari faktor_derau x derau lokal,
    dan (3) bertahan: rata-rata 'sesudah' berbeda dari 'sebelum' pada jendela tunak di luar masa transisi."""
    P_asli = df["daya_aktif"].to_numpy(float)
    P = median_filter(P_asli, size=7, mode="nearest")
    Q = median_filter(df["daya_reaktif"].to_numpy(float), size=7, mode="nearest") if "daya_reaktif" in df else None
    n = len(P)
    lag = 3
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
    ev = pd.DataFrame(kandidat)
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
