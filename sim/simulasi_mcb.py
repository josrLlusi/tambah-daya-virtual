"""TAMBAH DAYA VIRTUAL: simulasi MCB trip vs kendali beban + pembuat data contoh.

Menjalankan:  python sim/simulasi_mcb.py
Keluaran   :  docs/simulasi_mcb.png  dan  data/sample/pengukuran_sim.csv

PENTING: semua angka ILUSTRATIF. Model termal MCB orde-1 (tau, ambang) harus diganti
dengan nilai dari datasheet kurva trip dan uji waktu trip MCB yang dipakai
(IEC 60898-1). Jangan mengutip hasil simulasi ini sebagai kinerja alat.
"""
from pathlib import Path
import numpy as np
import pandas as pd

IN = 20.0            # arus nominal MCB [A]
TAU = 20.0           # konstanta waktu termal [menit]  (TODO: ukur)
THETA_TRIP = 1.6     # ambang trip pada model [relatif] (TODO: dari datasheet)
THETA_AMAN = 1.3     # ambang tindakan sistem (sebelum trip), margin keselamatan
DT = 0.05            # langkah waktu [menit] = 3 detik
ROOT = Path(__file__).resolve().parents[1]


def beban(t):
    """Arus tiap alat [A] pada waktu t (menit). Skenario konveksi."""
    return {
        "lampu_kipas": 2.0 + 0 * t,
        "mesin_jahit": 6.0 + 0.4 * np.sin(t * 2.1),
        "setrika_uap": np.where(t >= 5, 9.0, 0.0),
        "mesin_press": np.where((t >= 15) & (t < 45), 11.4, 0.0),
    }


def jalankan(t, kendali):
    """Simulasi. Bila kendali=True: pindahkan setrika_uap ke baterai saat model memprediksi bahaya."""
    b = beban(t)
    th, trip_t, pindah = 0.70, None, False
    kolom = {"arus": [], "theta": [], "baterai": [], "aksi": [], "aktif": []}
    for k, tk in enumerate(t):
        arus_alat = {n: float(v[k]) for n, v in b.items()}
        aksi = ""
        if kendali:
            # Prediksi sederhana: bila arus total sekarang membuat theta menuju ambang aman, pindahkan.
            total_tanpa_pindah = sum(arus_alat.values())
            tampak = th + DT * ((total_tanpa_pindah / IN) ** 2 - th) / TAU * (5 / DT)  # pandangan 5 menit
            if not pindah and arus_alat["mesin_press"] > 0 and tampak > THETA_AMAN:
                pindah, aksi = True, "setrika_uap_ke_baterai"
            if pindah and arus_alat["mesin_press"] == 0:
                pindah, aksi = False, "setrika_uap_kembali_ke_pln"
        i_alat = dict(arus_alat)
        if pindah:
            i_alat["setrika_uap"] = 0.0
        total = sum(i_alat.values())
        if trip_t is not None:
            total = 0.0
        th += DT * ((total / IN) ** 2 - th) / TAU
        if trip_t is None and th >= THETA_TRIP:
            trip_t = float(tk)
        kolom["arus"].append(total)
        kolom["theta"].append(th)
        kolom["baterai"].append(pindah)
        kolom["aksi"].append(aksi)
        kolom["aktif"].append("|".join(n for n, v in arus_alat.items() if v > 0.5))
    return {n: np.array(v) if n in ("arus", "theta", "baterai") else v for n, v in kolom.items()}, trip_t


def buat_data():
    t = np.arange(0, 60.01, DT)
    a, trip_a = jalankan(t, kendali=False)
    b, trip_b = jalankan(t, kendali=True)
    waktu = pd.Timestamp("2026-11-01 09:00:00") + pd.to_timedelta(t, unit="m")
    df = pd.DataFrame({
        "waktu": waktu, "id_perangkat": "panel-01", "tegangan": 220.0,
        "arus_tanpa_kendali": a["arus"].round(2), "theta_tanpa_kendali": a["theta"].round(3),
        "arus_kendali": b["arus"].round(2), "theta_kendali": b["theta"].round(3),
        "baterai_aktif": b["baterai"].astype(int), "aksi": b["aksi"], "alat_aktif": b["aktif"],
    })
    df["daya_kendali"] = (df["arus_kendali"] * df["tegangan"]).round(0)
    for nama, tm in (("mcb_trip_tanpa_kendali", trip_a), ("mcb_trip_kendali", trip_b)):
        df[nama] = (df["waktu"] >= waktu[0] + pd.Timedelta(minutes=tm)).astype(int) if tm is not None else 0
    return df, trip_a, trip_b


def gambar(df, trip_a, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = (df["waktu"] - df["waktu"].iloc[0]).dt.total_seconds() / 60
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.8), dpi=150)
    ax[0].axhline(IN, ls="--", c="gray"); ax[0].plot(t, df["arus_tanpa_kendali"], label="Tanpa kendali")
    ax[0].plot(t, df["arus_kendali"], label="Dengan kendali")
    ax[0].set(xlabel="Menit", ylabel="Arus dari PLN (A)", title="a. Arus total"); ax[0].legend()
    ax[1].axhline(THETA_TRIP, ls="--", c="gray"); ax[1].plot(t, df["theta_tanpa_kendali"]); ax[1].plot(t, df["theta_kendali"])
    ax[1].set(xlabel="Menit", ylabel="Pemanasan MCB (relatif)", title="b. Model termal MCB")
    for a in ax:
        a.grid(alpha=0.3)
    fig.suptitle("Simulasi ilustratif, bukan hasil pengukuran")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


if __name__ == "__main__":
    df, trip_a, trip_b = buat_data()
    out = ROOT / "data" / "sample" / "pengukuran_sim.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    gambar(df, trip_a, ROOT / "docs" / "simulasi_mcb.png")
    print(f"{len(df)} baris -> {out}")
    print(f"MCB trip tanpa kendali: menit {trip_a}; dengan kendali: {trip_b}")
    print(f"Arus puncak: tanpa {df['arus_tanpa_kendali'].max():.1f} A, dengan {df['arus_kendali'].max():.1f} A")
