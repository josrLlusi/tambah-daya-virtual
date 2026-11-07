"""Disagregasi: dari data agregat panel -> alat mana yang menyala tiap detik dan energinya.

    python analisis/disagregasi.py data/sample/agregat_sintetis.csv laporan/klasifikasi_v1/model.joblib --keluaran hasil/disagregasi.csv

Langkah: deteksi event -> klasifikasi alat -> pelacakan status:
  - event 'nyala' : alat hasil klasifikasi dinyatakan menyala
  - event 'mati'  : dipasangkan dengan alat yang sedang menyala dan dP-nya paling mirip
Bila data punya kolom alat_aktif (kebenaran, misalnya data sintetis), dihitung akurasi status per alat.
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deteksi_event import deteksi  # noqa: E402
from latih_klasifikasi import fitur  # noqa: E402


def lacak(df, ev, paket, periode_koreksi=30, ambang_relatif=0.6):
    """Pelacakan status berbasis event + koreksi keseimbangan daya.
    Koreksi: setiap `periode_koreksi` sampel, bandingkan daya terukur dengan jumlah daya tipikal alat yang
    dianggap menyala. Selisih besar berarti ada event yang terlewat -> nyalakan/matikan alat yang paling cocok."""
    model, kelas, tipikal = paket["model"], paket["kelas"], paket["dP_tipikal"]
    X = fitur(ev)[paket["fitur"]]
    ev = ev.copy()
    ev["alat_pred"] = model.predict(X) if len(ev) else []
    per_indeks = {int(e["indeks"]): e for _, e in ev.iterrows()}
    P = df["daya_aktif"].to_numpy(float)
    # beban siaga: level terendah yang bertahan (minimum dari median bergerak), bukan persentil,
    # karena alat yang hampir selalu menyala akan ikut terhitung sebagai "siaga" bila memakai persentil
    dasar = float(pd.Series(P).rolling(11, center=True, min_periods=1).median().min())
    n = len(df)
    status = {k: np.zeros(n, dtype=bool) for k in kelas}
    aktif = set()
    for j in range(n):
        e = per_indeks.get(j)
        if e is not None:
            if e["arah"] == "nyala":
                aktif.add(e["alat_pred"])
            elif aktif:
                kand = e["alat_pred"] if e["alat_pred"] in aktif else min(
                    aktif, key=lambda k: abs(tipikal.get(k, 0) - abs(e["dP"])))
                aktif.discard(kand)
        elif j % periode_koreksi == 0 and j >= 10:
            sisa = float(np.median(P[j - 10:j + 1])) - dasar - sum(tipikal.get(k, 0) for k in aktif)
            if sisa < 0 and aktif:
                k = min(aktif, key=lambda k: abs(tipikal.get(k, 0) + sisa))
                if -sisa > ambang_relatif * tipikal.get(k, 0):
                    aktif.discard(k)
            elif sisa > 0:
                mati = [k for k in kelas if k not in aktif]
                if mati:
                    k = min(mati, key=lambda k: abs(tipikal.get(k, 0) - sisa))
                    if sisa > ambang_relatif * tipikal.get(k, 0) and abs(tipikal.get(k, 0) - sisa) < 0.4 * tipikal.get(k, 0):
                        aktif.add(k)
        for k in aktif:
            status[k][j] = True
    return ev, status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("model")
    ap.add_argument("--keluaran", default="hasil/disagregasi.csv")
    a = ap.parse_args()
    df = pd.read_csv(a.csv, parse_dates=["waktu"]).sort_values("waktu").reset_index(drop=True)
    paket = joblib.load(a.model)
    ev = deteksi(df)
    ev, status = lacak(df, ev, paket)

    out = df[["waktu", "daya_aktif"]].copy()
    out["alat_aktif_est"] = ["|".join(k for k in paket["kelas"] if status[k][i]) for i in range(len(df))]
    dt_jam = df["waktu"].diff().dt.total_seconds().fillna(0).to_numpy() / 3600.0
    energi = {k: round(float((status[k] * paket["dP_tipikal"].get(k, 0) * dt_jam).sum() / 1000), 3)
              for k in paket["kelas"]}
    ringkas = {"event": int(len(ev)), "energi_perkiraan_kWh": energi}

    if "alat_aktif" in df:
        benar = {}
        for k in paket["kelas"]:
            gt = df["alat_aktif"].fillna("").str.split("|").apply(lambda s: k in s).to_numpy()
            benar[k] = round(float((gt == status[k]).mean() * 100), 1)
        ringkas["akurasi_status_per_alat_%"] = benar
    Path(a.keluaran).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.keluaran, index=False)
    print(json.dumps(ringkas, indent=2))
    print(f"-> {a.keluaran}")


if __name__ == "__main__":
    main()
