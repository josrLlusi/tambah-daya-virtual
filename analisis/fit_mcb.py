"""Tentukan parameter model termal MCB (tau, ambang trip) dari uji waktu trip.

    python analisis/fit_mcb.py data/raw/uji_trip_mcb4A.csv --in-mcb 4 --keluaran laporan/mcb4A

Format CSV (satu baris per uji; MCB dibiarkan dingin minimal 15-30 menit di antara uji, theta_awal=0):
    arus_A,waktu_trip_detik,theta_awal
    6.0,312,0
    8.0,95,0
Kolom theta_awal opsional (default 0 = MCB dingin).

Model orde-1: dtheta/dt = ((I/In)^2 - theta) / tau ; trip saat theta >= theta_trip.
Untuk arus tetap dari theta0: t_trip = tau * ln((s - theta0) / (s - theta_trip)), s = (I/In)^2.
Catatan: model ini hanya mewakili bagian TERMAL (beban lebih). Bagian MAGNETIK (hubung singkat,
mis. 5-10 x In pada kurva C) bekerja seketika dan tidak boleh diuji dengan cara ini.
Keluaran: parameter_mcb.json (dipakai simulasi/firmware) dan kurva_trip.png.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


def t_trip(I_rel, tau, th_trip, th0=0.0):
    s = np.asarray(I_rel, float) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        t = tau * np.log((s - th0) / (s - th_trip))
    return np.where(s > th_trip, t, np.inf)


def fit(I_rel, t_ukur, th0):
    def resid(x):
        tau, th = x
        return np.log(t_trip(I_rel, tau, th, th0)) - np.log(t_ukur)   # galat relatif (log)
    s_min = float(np.min(np.asarray(I_rel) ** 2))
    r = least_squares(resid, x0=[np.median(t_ukur), min(1.2, 0.9 * s_min)],
                      bounds=([1.0, 1.0], [1e5, 0.999 * s_min]))
    return r.x, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--in-mcb", type=float, required=True, help="arus nominal MCB (A)")
    ap.add_argument("--keluaran", default="laporan/mcb")
    a = ap.parse_args()
    d = pd.read_csv(a.csv)
    th0 = d["theta_awal"].to_numpy(float) if "theta_awal" in d else np.zeros(len(d))
    I_rel = d["arus_A"].to_numpy(float) / a.in_mcb
    t = d["waktu_trip_detik"].to_numpy(float)
    if len(d) < 3:
        raise SystemExit("Butuh minimal 3 uji pada arus berbeda.")
    (tau, th), r = fit(I_rel, t, th0)
    t_model = t_trip(I_rel, tau, th, th0)
    galat = np.abs(t_model - t) / t * 100

    out = Path(a.keluaran); out.mkdir(parents=True, exist_ok=True)
    par = {"in_mcb_A": a.in_mcb, "tau_detik": round(float(tau), 1), "tau_menit": round(float(tau) / 60, 2),
           "theta_trip": round(float(th), 4), "arus_tak_trip_relatif": round(float(np.sqrt(th)), 3),
           "galat_waktu_trip_rata2_%": round(float(galat.mean()), 1), "jumlah_uji": int(len(d))}
    (out / "parameter_mcb.json").write_text(json.dumps(par, indent=2), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.linspace(np.sqrt(th) * 1.01, max(I_rel.max() * 1.2, 2.0), 200)
    fig, ax = plt.subplots(figsize=(6, 4), dpi=130)
    ax.plot(x, t_trip(x, tau, th), label="model")
    ax.scatter(I_rel, t, c="k", zorder=3, label="uji")
    ax.set(xscale="linear", yscale="log", xlabel="Arus / arus nominal", ylabel="Waktu trip (detik)",
           title=f"MCB {a.in_mcb:g} A: tau={tau / 60:.1f} menit, ambang={th:.2f}")
    ax.grid(alpha=0.3, which="both"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "kurva_trip.png")
    print(json.dumps(par, indent=2))


if __name__ == "__main__":
    main()
