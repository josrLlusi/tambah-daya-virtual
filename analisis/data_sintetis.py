"""Data agregat sintetis (1 detik) dengan label alat, untuk menguji pipeline NILM tanpa perangkat keras.

    python analisis/data_sintetis.py --jam 6 --keluaran data/sample/agregat_sintetis.csv

Hasil: kolom waktu, tegangan, daya_aktif, daya_reaktif, arus, faktor_daya, alat_aktif (label kebenaran),
serta berkas *_event.csv berisi event kebenaran. Nilai daya tiap alat ILUSTRATIF; ganti dengan hasil ukur.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# nama: (P [W], Q [var], lama nyala menit (min,maks), jeda menit (min,maks))
ALAT = {
    "setrika_uap": (2000, 40, (5, 25), (5, 30)),
    "oven_listrik": (1500, 30, (10, 40), (20, 60)),
    "mixer": (600, 330, (3, 10), (10, 40)),
    "mesin_jahit": (250, 260, (5, 30), (2, 15)),
    "freezer": (150, 200, (8, 15), (10, 20)),
    "lampu_kipas": (120, 60, (60, 180), (5, 20)),
}


def jadwal(rng, n, lama, jeda):
    s = np.zeros(n, dtype=bool)
    t = int(rng.uniform(0, jeda[1] * 60))
    while t < n:
        d = int(rng.uniform(*lama) * 60)
        s[t:t + d] = True
        t += d + int(rng.uniform(*jeda) * 60)
    return s


def buat(jam=6, seed=1):
    rng = np.random.default_rng(seed)
    n = int(jam * 3600)
    waktu = pd.Timestamp("2026-11-01 08:00:00") + pd.to_timedelta(np.arange(n), unit="s")
    v = 220 + 3 * np.sin(np.arange(n) / 3000) + rng.normal(0, 0.8, n)
    P = np.zeros(n); Q = np.zeros(n)
    status = {}
    for nama, (p, q, lama, jeda) in ALAT.items():
        s = jadwal(rng, n, lama, jeda)
        status[nama] = s
        skala = (v / 220.0) ** 2                       # beban resistif mengikuti V^2 (pendekatan)
        P += s * p * skala * (1 + rng.normal(0, 0.01, n))
        Q += s * q * skala * (1 + rng.normal(0, 0.02, n))
    P += 15 + rng.normal(0, 3, n)                       # beban siaga + derau
    Q += 10 + rng.normal(0, 3, n)
    S = np.sqrt(P**2 + Q**2)
    df = pd.DataFrame({
        "waktu": waktu, "id_perangkat": "sintetis", "tegangan": v.round(1),
        "daya_aktif": P.round(1), "daya_reaktif": Q.round(1),
        "arus": (S / v).round(3), "faktor_daya": (P / S).round(3),
        "alat_aktif": ["|".join(k for k in ALAT if status[k][i]) for i in range(n)],
    })
    ev = []
    for nama, s in status.items():
        d = np.diff(s.astype(int))
        for i in np.where(d != 0)[0]:
            ev.append({"waktu": waktu[i + 1], "alat": nama, "arah": "nyala" if d[i] > 0 else "mati"})
    return df, pd.DataFrame(ev).sort_values("waktu")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jam", type=float, default=6)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--keluaran", default="data/sample/agregat_sintetis.csv")
    a = ap.parse_args()
    df, ev = buat(a.jam, a.seed)
    out = Path(a.keluaran); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    ev.to_csv(out.with_name(out.stem + "_event.csv"), index=False)
    print(f"{len(df)} baris, {len(ev)} event kebenaran -> {out}")
