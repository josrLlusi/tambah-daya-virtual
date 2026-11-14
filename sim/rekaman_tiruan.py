"""Rekaman TIRUAN dalam format data perangkat, untuk mencoba dasbor dan mode demo tanpa perangkat keras.

    python sim/rekaman_tiruan.py                       # -> data/sample/rekaman_tiruan.csv
    python sim/rekaman_tiruan.py --jam 2 --in-mcb 10 --alat-pindah setrika_uap

Beban berasal dari analisis/data_sintetis.py (alat UMKM ilustratif). Logika kendali di sini sama dengan
firmware/esp32_panel (model termal orde-1, batas aman, jeda), sehingga kolom keluarannya sama dengan
yang direkam alat/perekam_serial.py: tegangan, arus, daya_aktif, faktor_daya, daya_reaktif, theta, baterai_aktif.
Kolom tambahan: mcb_trip, alat_aktif (alat yang terlihat di jalur PLN), alat_di_baterai.

PENTING: ini SIMULASI. Semua daya alat dan parameter MCB adalah nilai ilustratif, bukan hasil pengukuran.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "analisis"))
from data_sintetis import ALAT, jadwal  # noqa: E402

# sama dengan firmware/esp32_panel/esp32_panel.ino
MARGIN, THETA_LEPAS = 0.80, 1.0
MIN_DI_BATERAI_S, MIN_JEDA_LINDUNG_S = 180, 10
RESET_SETELAH_TRIP_S = 120          # MCB dinaikkan lagi oleh orang setelah 2 menit


def simulasikan(jam, seed, in_mcb, tau, theta_trip, alat_pindah, kendali=True):
    rng = np.random.default_rng(seed)
    n = int(jam * 3600)
    v = 220 + 3 * np.sin(np.arange(n) / 3000) + rng.normal(0, 0.8, n)
    status = {k: jadwal(rng, n, lama, jeda) for k, (_, _, lama, jeda) in ALAT.items()}
    derauP = {k: 1 + rng.normal(0, 0.01, n) for k in ALAT}
    derauQ = {k: 1 + rng.normal(0, 0.02, n) for k in ALAT}
    dasarP, dasarQ = 15 + rng.normal(0, 3, n), 10 + rng.normal(0, 3, n)

    theta, lepas, t_aksi, pernah, padam_sampai = 0.0, False, 0, False, -1
    baris, n_trip = [], 0
    for j in range(n):
        padam = j <= padam_sampai
        skala = (v[j] / 220.0) ** 2
        P, Q, terlihat = dasarP[j], dasarQ[j], []
        for k, (p, q, _, _) in ALAT.items():
            if not status[k][j] or (lepas and k == alat_pindah):
                continue
            P += p * skala * derauP[k][j]
            Q += q * skala * derauQ[k][j]
            terlihat.append(k)
        if padam:
            P, Q, terlihat = 0.0, 0.0, []
        S = float(np.hypot(P, Q))
        arus = S / v[j]
        theta += ((arus / in_mcb) ** 2 - theta) * (1 - np.exp(-1.0 / tau))
        trip = 0
        if not padam and theta >= theta_trip:
            trip, n_trip, padam_sampai = 1, n_trip + 1, j + RESET_SETELAH_TRIP_S
        if kendali and not padam:
            sejak = j - t_aksi
            if not lepas and theta > MARGIN * theta_trip and (not pernah or sejak >= MIN_JEDA_LINDUNG_S):
                lepas, t_aksi, pernah = True, j, True
            elif lepas and theta < THETA_LEPAS and sejak >= MIN_DI_BATERAI_S:
                lepas, t_aksi = False, j
        baris.append((round(float(v[j]), 1), round(arus, 3), round(float(P), 1),
                      round(float(P / S), 3) if S > 1 else 0.0, round(float(Q), 1), round(theta, 4),
                      int(lepas), trip, "|".join(terlihat),
                      alat_pindah if (lepas and status[alat_pindah][j] and not padam) else ""))
    waktu = pd.Timestamp("2026-11-01 08:00:00") + pd.to_timedelta(np.arange(n), unit="s")
    df = pd.DataFrame(baris, columns=["tegangan", "arus", "daya_aktif", "faktor_daya", "daya_reaktif", "theta",
                                      "baterai_aktif", "mcb_trip", "alat_aktif", "alat_di_baterai"])
    df.insert(0, "sesi", "tiruan")
    df.insert(0, "id_perangkat", "tiruan")
    df.insert(0, "waktu", waktu)
    return df, n_trip


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jam", type=float, default=3)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--in-mcb", type=float, default=10.0, help="arus nominal MCB (A); 10 A = 2.200 VA")
    ap.add_argument("--tau", type=float, default=1200.0, help="konstanta waktu termal (detik), tebakan")
    ap.add_argument("--theta-trip", type=float, default=1.6, help="ambang trip model, tebakan")
    ap.add_argument("--alat-pindah", default="setrika_uap", choices=list(ALAT))
    ap.add_argument("--keluaran", default=str(AKAR / "data" / "sample" / "rekaman_tiruan.csv"))
    a = ap.parse_args()

    _, trip_tanpa = simulasikan(a.jam, a.seed, a.in_mcb, a.tau, a.theta_trip, a.alat_pindah, kendali=False)
    df, trip_dengan = simulasikan(a.jam, a.seed, a.in_mcb, a.tau, a.theta_trip, a.alat_pindah, kendali=True)
    out = Path(a.keluaran); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    menit_bat = (df["alat_di_baterai"] != "").sum() / 60
    kwh_bat = menit_bat / 60 * ALAT[a.alat_pindah][0] / 1000
    print(f"{len(df)} baris -> {out}")
    print(f"SIMULASI, MCB {a.in_mcb:g} A, alat yang dipindah: {a.alat_pindah}")
    print(f"  MCB turun tanpa kendali : {trip_tanpa} kali")
    print(f"  MCB turun dengan kendali: {trip_dengan} kali")
    print(f"  Alat di baterai {menit_bat:.0f} menit, kira-kira {kwh_bat:.2f} kWh dari baterai")
    print("Angka ini ilustratif (daya alat dan parameter MCB tebakan), bukan kinerja alat.")


if __name__ == "__main__":
    main()
