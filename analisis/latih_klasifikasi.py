"""Latih pengklasifikasi alat dari event nyala/mati.

Alur data nyata (disarankan):
  1. Rekam tiap alat SENDIRIAN beberapa kali nyala-mati (alat/perekam_serial.py --sesi setrika_uap ...).
  2. python analisis/deteksi_event.py data/raw/setrika_uap_*.csv --label setrika_uap --keluaran data/olah/ev_setrika.csv
     (ulangi untuk tiap alat)
  3. python analisis/latih_klasifikasi.py data/olah/ev_*.csv --keluaran laporan/klasifikasi_v1

Untuk data sintetis (label dari berkas kebenaran):
  python analisis/latih_klasifikasi.py data/olah/event_agregat.csv --kebenaran data/sample/agregat_sintetis_event.csv

Model yang dibandingkan: pohon keputusan (mudah dijelaskan), random forest, jaringan saraf kecil (MLP).
Evaluasi: validasi silang bertingkat (stratified k-fold). Keluaran: laporan.md, matriks_kebingungan.png, model.joblib.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


def fitur(ev):
    """Fitur dari event; dipakai bersama oleh pelatihan dan disagregasi."""
    X = pd.DataFrame({"abs_dP": ev["dP"].abs()})
    if "dQ" in ev and ev["dQ"].notna().all():
        X["abs_dQ"] = ev["dQ"].abs()
        X["rasio_QP"] = ev["dQ"].abs() / np.maximum(ev["dP"].abs(), 1.0)
    if "rasio_puncak" in ev and ev["rasio_puncak"].notna().all():
        X["rasio_puncak"] = ev["rasio_puncak"]
    return X


def label_dari_kebenaran(ev, path_kebenaran, toleransi_s=6):
    gt = pd.read_csv(path_kebenaran, parse_dates=["waktu"]).sort_values("waktu")
    ev = ev.sort_values("waktu")
    m = pd.merge_asof(ev, gt[["waktu", "alat"]], on="waktu", direction="nearest",
                      tolerance=pd.Timedelta(seconds=toleransi_s))
    return m.dropna(subset=["alat"])


def model_model():
    return {
        "pohon_keputusan": DecisionTreeClassifier(max_depth=6, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=0),
        "jaringan_saraf_mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16),
                                                                            max_iter=2000, random_state=0)),
    }


def gambar_cm(cm, kelas, path, judul):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(1.1 * len(kelas) + 2, 1.0 * len(kelas) + 1.5), dpi=130)
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(kelas)), kelas, rotation=45, ha="right")
    ax.set_yticks(range(len(kelas)), kelas)
    for i in range(len(kelas)):
        for j in range(len(kelas)):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center", fontsize=9)
    ax.set(xlabel="Prediksi", ylabel="Sebenarnya", title=judul)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("berkas", nargs="+")
    ap.add_argument("--kebenaran", default=None)
    ap.add_argument("--keluaran", default="laporan/klasifikasi")
    ap.add_argument("--fold", type=int, default=5)
    a = ap.parse_args()

    ev = pd.concat([pd.read_csv(p, parse_dates=["waktu"]) for p in a.berkas], ignore_index=True)
    if a.kebenaran:
        ev = label_dari_kebenaran(ev, a.kebenaran)
    if "alat" not in ev:
        raise SystemExit("Event belum berlabel. Pakai --label saat deteksi_event.py, atau --kebenaran.")
    X, y = fitur(ev), ev["alat"].to_numpy()
    jumlah = pd.Series(y).value_counts()
    fold = int(min(a.fold, jumlah.min()))
    if fold < 2:
        raise SystemExit(f"Tiap alat butuh minimal 2 event. Jumlah sekarang: {jumlah.to_dict()}")

    out = Path(a.keluaran); out.mkdir(parents=True, exist_ok=True)
    cv = StratifiedKFold(n_splits=fold, shuffle=True, random_state=0)
    hasil, pred = {}, {}
    for nama, m in model_model().items():
        p = cross_val_predict(m, X, y, cv=cv)
        pred[nama] = p
        hasil[nama] = {"akurasi_%": round(accuracy_score(y, p) * 100, 1),
                       "F1_makro_%": round(f1_score(y, p, average="macro") * 100, 1)}
    terbaik = max(hasil, key=lambda k: hasil[k]["F1_makro_%"])
    kelas = sorted(jumlah.index)
    gambar_cm(confusion_matrix(y, pred[terbaik], labels=kelas), kelas, out / "matriks_kebingungan.png",
              f"{terbaik} (validasi silang {fold}-fold)")

    model = model_model()[terbaik].fit(X, y)
    joblib.dump({"fitur": list(X.columns), "model": model, "kelas": kelas,
                 "dP_tipikal": ev.assign(a=ev["dP"].abs()).groupby("alat")["a"].median().to_dict()},
                out / "model.joblib")
    baris = ["# Laporan klasifikasi alat\n", f"- Event: {len(ev)}; alat: {len(kelas)}; fold: {fold}",
             f"- Fitur: {', '.join(X.columns)}", f"- Event per alat: {jumlah.to_dict()}\n",
             "| Model | Akurasi (%) | F1 makro (%) |", "|---|---|---|"]
    baris += [f"| {k}{' (terbaik)' if k == terbaik else ''} | {v['akurasi_%']} | {v['F1_makro_%']} |"
              for k, v in hasil.items()]
    baris += ["\n![matriks kebingungan](matriks_kebingungan.png)\n",
              "## Catatan\n",
              "- Bila data sintetis, angka ini bukan kinerja alat.",
              "- Alat dengan dP dan dQ mirip akan tertukar; tambahkan fitur bentuk gelombang (harmonik, arus start) bila perlu."]
    (out / "laporan.md").write_text("\n".join(baris), encoding="utf-8")
    print(json.dumps({"terbaik": terbaik, **hasil}, indent=2))
    print(f"Laporan: {out / 'laporan.md'}")


if __name__ == "__main__":
    main()
