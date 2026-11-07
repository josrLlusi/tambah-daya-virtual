"""Simulator apa-jika: model termal MCB orde-1 yang sama dengan sim/simulasi_mcb.py.

dθ/dt = ((I/In)^2 - θ) / τ ; MCB dianggap turun saat θ >= θ_trip.
Semua parameter ILUSTRATIF, bukan karakteristik MCB tertentu.
"""
import numpy as np
import pandas as pd

ALAT_BAWAAN = [
    # nama, arus (A), menyala, boleh dipindah ke baterai  (nilai dari skenario simulasi konveksi)
    ("Lampu & kipas", 2.0, True, False),
    ("Mesin jahit", 6.0, True, False),
    ("Setrika uap", 9.0, True, True),
    ("Mesin press", 11.4, True, False),
]


def tabel_bawaan():
    return pd.DataFrame(ALAT_BAWAAN, columns=["Alat", "Arus (A)", "Menyala", "Boleh ke baterai"])


def waktu_trip_menit(arus, in_mcb, theta0, tau, theta_trip):
    """Waktu (menit) hingga θ mencapai ambang trip pada arus konstan, atau None bila tidak pernah."""
    ss = (arus / in_mcb) ** 2
    if theta0 >= theta_trip:
        return 0.0
    if ss <= theta_trip:
        return None
    return float(-tau * np.log((ss - theta_trip) / (ss - theta0)))


def rencana_kendali(alat, in_mcb, tegangan, theta_aman, daya_inverter_w):
    """Pilih alat yang dipindah ke baterai (terbesar dulu) sampai θ tunak <= θ_aman
    atau tidak ada kandidat / kapasitas inverter habis.
    alat: DataFrame dengan kolom Alat, Arus (A), Menyala, Boleh ke baterai."""
    nyala = alat[alat["Menyala"]].copy()
    total = float(nyala["Arus (A)"].sum())
    kandidat = nyala[nyala["Boleh ke baterai"]].sort_values("Arus (A)", ascending=False)
    dipindah, arus_pindah, sisa_w = [], 0.0, daya_inverter_w
    for _, r in kandidat.iterrows():
        if ((total - arus_pindah) / in_mcb) ** 2 <= theta_aman:
            break
        daya = r["Arus (A)"] * tegangan
        if daya <= sisa_w:
            dipindah.append(r["Alat"])
            arus_pindah += r["Arus (A)"]
            sisa_w -= daya
    return dict(total=total, dipindah=dipindah, arus_pindah=arus_pindah,
                arus_pln=total - arus_pindah, daya_baterai_w=arus_pindah * tegangan)


def simulasikan(arus_total, arus_pindah, durasi_baterai_menit, in_mcb, theta0, tau, theta_trip,
                horizon=90.0, dt=0.1):
    """Simulasi Euler. Alat dipindah ke baterai selama durasi_baterai_menit, lalu kembali ke PLN.
    Setelah MCB turun, arus menjadi 0. Hasil: (DataFrame menit/arus/theta, menit_trip atau None)."""
    t = np.arange(0, horizon + dt, dt)
    th, trip = theta0, None
    arus_l, th_l = [], []
    for tk in t:
        i = arus_total - (arus_pindah if tk < durasi_baterai_menit else 0.0)
        if trip is not None:
            i = 0.0
        th += dt * ((i / in_mcb) ** 2 - th) / tau
        if trip is None and th >= theta_trip:
            trip = float(tk)
        arus_l.append(i)
        th_l.append(th)
    return pd.DataFrame({"menit": t, "arus": arus_l, "theta": th_l}), trip
