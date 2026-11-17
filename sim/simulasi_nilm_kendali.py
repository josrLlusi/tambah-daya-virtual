"""Simulasi LOOP TERTUTUP: NILM -> keputusan kendali -> beban di jalur PLN -> pemanasan MCB.

    python sim/simulasi_nilm_kendali.py                     # 3 data uji, 6 jam masing-masing
    python sim/simulasi_nilm_kendali.py --jam 2 --seed-uji 9

Empat skenario pada jadwal beban yang sama:
  tanpa        : tanpa kendali
  termal_1     : kendali termal saja seperti firmware esp32_panel.ino sekarang. Alat di satu kanal relay dipindah
                 saat pemanasan melewati margin x ambang trip, TANPA tahu alat itu sedang menyala atau tidak.
  nilm_1       : NILM + keputusan (analisis/pengendali_nilm.py), satu kanal relay (alat yang sama).
  nilm_2       : NILM + keputusan, dua kanal relay (setrika dan oven): memilih alat yang tepat.

Model NILM dilatih pada satu data sintetis (seed berbeda) lalu dipakai pada data uji yang belum pernah dilihat.
Bila MCB turun: semua beban terputus 120 detik, lalu menyala lagi; pengendali dimulai ulang.

PENTING: SEMUA HASIL ADALAH SIMULASI pada data sintetis dengan parameter MCB dan alat ILUSTRATIF
(tau, ambang, daya alat, kapasitas inverter). Ini membuktikan alur berjalan dan membandingkan strategi,
BUKAN kinerja alat. Jangan dikutip sebagai hasil pengukuran.
"""
import argparse
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "analisis"))
import data_sintetis as ds  # noqa: E402
from deteksi_event import deteksi  # noqa: E402
from keputusan_kendali import Konfigurasi, Keputusan, arus  # noqa: E402
from latih_klasifikasi import fitur, label_dari_kebenaran  # noqa: E402
from pengendali_nilm import PengendaliNILM  # noqa: E402

RESET_S = 120            # lama semua beban terputus setelah MCB turun
DAYA_NYALA_W = 50        # ambang untuk menyatakan sebuah alat benar-benar menarik daya


def latih_paket(jam, seed):
    """Latih pengklasifikasi (pohon keputusan) dari satu data sintetis berlabel kebenaran."""
    df, gt = ds.buat(jam, seed)
    with tempfile.TemporaryDirectory() as tmp:
        berkas = Path(tmp) / "gt.csv"
        gt.to_csv(berkas, index=False)
        ev = label_dari_kebenaran(deteksi(df), berkas)
    X, y = fitur(ev), ev["alat"].to_numpy()
    model = DecisionTreeClassifier(max_depth=6, random_state=0).fit(X, y)
    med = lambda k: ev.assign(a=ev[k].abs()).groupby("alat")["a"].median().to_dict()  # noqa: E731
    return {"fitur": list(X.columns), "model": model, "kelas": sorted(set(y)), "dP_tipikal": med("dP"),
            "dQ_tipikal": med("dQ")}


class PengendaliTermal:
    """Meniru logika firmware esp32_panel.ino: hanya model termal; memindah alat terpasang walau sedang mati."""

    def __init__(self, cfg, alat):
        self.cfg, self.alat = cfg, alat
        self.reset()

    def reset(self):
        self.theta, self.t_prev, self.di_baterai, self.t_aksi = 0.0, None, False, None

    def langkah(self, t, p, q, v):
        dt = 0.0 if self.t_prev is None else max(t - self.t_prev, 0.0)
        self.t_prev = t
        s = (arus(p, q, v) / self.cfg.in_mcb) ** 2
        self.theta = s + (self.theta - s) * math.exp(-dt / self.cfg.tau)
        sejak = math.inf if self.t_aksi is None else t - self.t_aksi
        if not self.di_baterai and self.theta > self.cfg.ambang and sejak >= self.cfg.min_jeda_lindung_s:
            self.di_baterai, self.t_aksi = True, t
            return [Keputusan("pindah", self.alat)]
        if self.di_baterai and self.theta < self.cfg.theta_lepas and sejak >= self.cfg.min_jeda_kembali_s:
            self.di_baterai, self.t_aksi = False, t
            return [Keputusan("kembali", self.alat)]
        return []


def jalankan_satu(df, komp, cfg_nyata, pengendali):
    """Simulasi satu skenario. cfg_nyata: parameter MCB yang SEBENARNYA (boleh beda dari yang diketahui pengendali)."""
    v = df["tegangan"].to_numpy(float)
    n = len(df)
    alat = [k for k in komp if k != "_siaga"]
    sp, sq = komp["_siaga"]
    pindah, theta = set(), 0.0
    trip_hingga, n_trip = -1, 0
    n_pindah = n_kembali = n_percuma = 0
    e_bat_wh, detik_bat, theta_maks = 0.0, 0, 0.0
    for i in range(n):
        if i < trip_hingga:
            P = Q = 0.0
        else:
            P = sp[i] + sum(komp[a][0][i] for a in alat if a not in pindah)
            Q = sq[i] + sum(komp[a][1][i] for a in alat if a not in pindah)
        s = (arus(P, Q, v[i]) / cfg_nyata.in_mcb) ** 2
        theta = s + (theta - s) * math.exp(-1.0 / cfg_nyata.tau)
        theta_maks = max(theta_maks, theta)
        if i >= trip_hingga and theta >= cfg_nyata.theta_trip:
            n_trip += 1
            trip_hingga = i + RESET_S
            pindah.clear()
            if pengendali is not None:
                pengendali.reset()
        if pindah:
            detik_bat += 1
            e_bat_wh += sum(komp[a][0][i] for a in pindah) / 3600.0
        if pengendali is not None and i >= trip_hingga:
            for k in pengendali.langkah(float(i), P, Q, float(v[i])):
                if k.aksi == "pindah":
                    n_pindah += 1
                    n_percuma += int(komp[k.alat][0][i] < DAYA_NYALA_W)     # alat sebenarnya sedang mati
                    pindah.add(k.alat)
                elif k.aksi == "kembali":
                    n_kembali += 1
                    pindah.discard(k.alat)
    return {"mcb_turun": n_trip, "pemanasan_maks": round(theta_maks, 3), "aksi_pindah": n_pindah,
            "aksi_kembali": n_kembali, "pindah_percuma": n_percuma, "menit_di_baterai": round(detik_bat / 60, 1),
            "energi_baterai_kwh": round(e_bat_wh / 1000, 2)}


def jalankan(jam=6, seed_latih=1, seed_uji=(9, 10, 11), in_mcb=10.0, tau=900.0, theta_trip=1.45,
             inverter_va=2500.0, salah_tau=1.0, tampil=print):
    """Bandingkan keempat skenario pada tiap data uji. salah_tau: tau SEBENARNYA = salah_tau x tau yang diketahui
    pengendali (uji ketahanan terhadap parameter MCB yang tebakan)."""
    tampil(f"Melatih pengklasifikasi pada data sintetis seed {seed_latih} ({jam} jam)...")
    paket = latih_paket(jam, seed_latih)
    dasar = dict(in_mcb=in_mcb, tau=tau, theta_trip=theta_trip, kapasitas_inverter_va=inverter_va)
    cfg = {"termal_1": Konfigurasi(**dasar, kanal={"setrika_uap": 1}),
           "nilm_1": Konfigurasi(**dasar, kanal={"setrika_uap": 1}),
           "nilm_2": Konfigurasi(**dasar, kanal={"setrika_uap": 1, "oven_listrik": 2})}
    nyata = Konfigurasi(**{**dasar, "tau": tau * salah_tau})
    baris = []
    for seed in seed_uji:
        df, _, komp = ds.buat(jam, seed, komponen=True)
        tampil(f"Data uji seed {seed}...")
        skenario = {"tanpa": None,
                    "termal_1": PengendaliTermal(cfg["termal_1"], "setrika_uap"),
                    "nilm_1": PengendaliNILM(paket, cfg["nilm_1"]),
                    "nilm_2": PengendaliNILM(paket, cfg["nilm_2"])}
        for nama, peng in skenario.items():
            baris.append({"seed": seed, "skenario": nama, **jalankan_satu(df, komp, nyata, peng)})
    return pd.DataFrame(baris)


NAMA_SKENARIO = {"tanpa": "Tanpa kendali", "termal_1": "Termal saja (seperti firmware)",
                 "nilm_1": "NILM, 1 kanal", "nilm_2": "NILM, 2 kanal"}

# Warna grafik (lihat panduan dataviz): aksen untuk sistem yang diusulkan, abu-abu untuk pembanding (emphasis).
PERMUKAAN, INK, INK2, MUTED, GRID, GARIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
AKSEN, PEMBANDING = "#2a78d6", "#898781"


def _batang_bulat(ax, y, nilai, warna, tebal_px, radius_px):
    """Batang horizontal dari 0 sampai `nilai`: pangkal siku di garis dasar, ujung kanan membulat (radius_px).
    Digambar dalam koordinat layar supaya radiusnya sama di semua panel; simpan gambar dengan dpi yang sama."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    from matplotlib.transforms import IdentityTransform
    (x0, yc), (x1, _) = ax.transData.transform([(0, y), (nilai, y)])
    if x1 - x0 < 1:
        return                                   # nilai 0: tidak ada batang; nilainya tetap dilabeli
    h = tebal_px / 2
    r = min(radius_px, h, x1 - x0)
    k = 0.5523 * r                               # pendekatan busur lingkaran dengan kurva Bezier
    v = [(x0, yc - h), (x1 - r, yc - h), (x1 - r + k, yc - h), (x1, yc - h + r - k), (x1, yc - h + r),
         (x1, yc + h - r), (x1, yc + h - r + k), (x1 - r + k, yc + h), (x1 - r, yc + h),
         (x0, yc + h), (x0, yc - h)]
    c = [Path.MOVETO, Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
         Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(v, c), facecolor=warna, edgecolor="none", transform=IdentityTransform()))


def gambar(benar, salah, path, salah_tau=0.6, jam=6, dpi=150):
    """Gambar perbandingan strategi kendali (SIMULASI). benar/salah: keluaran jalankan() untuk tau sesuai tebakan dan
    tau sebenarnya `salah_tau` x tebakan. Empat panel dengan skala masing-masing (bukan sumbu ganda)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    matplotlib.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    skala = dpi / 96.0                            # spesifikasi mark dalam px CSS -> piksel gambar
    urut = list(NAMA_SKENARIO)
    jml = lambda df, kol: [float(df.groupby("skenario")[kol].sum()[s]) for s in urut]  # noqa: E731
    n_data = len(set(benar["seed"]))
    panel = [
        ("MCB turun (kali)", "parameter MCB sesuai tebakan", jml(benar, "mcb_turun"), (0, 55), "{:.0f}"),
        ("MCB turun (kali)", f"MCB lebih cepat panas dari tebakan (tau sebenarnya {salah_tau:g}x)".replace(".", ","),
         jml(salah, "mcb_turun"), (0, 55), "{:.0f}"),
        ("Aksi pindah ke baterai (kali)", "parameter MCB sesuai tebakan", jml(benar, "aksi_pindah"), (0, 38), "{:.0f}"),
        ("Energi dialihkan ke baterai (kWh)", "parameter MCB sesuai tebakan", jml(benar, "energi_baterai_kwh"),
         (0, 9.6), "{:.1f}"),
    ]
    fig = plt.figure(figsize=(11, 6.6), dpi=dpi, facecolor=PERMUKAAN)
    fig.subplots_adjust(left=0.215, right=0.975, top=0.755, bottom=0.115, hspace=0.62, wspace=0.07)
    axs = fig.subplots(2, 2, sharey="row")
    for ax, (judul, sub, nilai, xlim, f) in zip(axs.flat, panel):
        ax.set_facecolor(PERMUKAAN)
        ax.set_xlim(*xlim)
        ax.set_ylim(len(urut) - 0.5, -0.5)
        ax.set_yticks(range(len(urut)), [NAMA_SKENARIO[s] for s in urut])
        ax.tick_params(axis="y", length=0, labelsize=9.5, labelcolor=INK2, pad=8)
        ax.tick_params(axis="x", length=0, labelsize=8.5, labelcolor=MUTED, pad=4)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for nama, sp in ax.spines.items():
            sp.set_visible(nama == "left")
            sp.set_color(GARIS)
        ax.set_title(judul, loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=17)
        ax.text(0, 1.045, sub, transform=ax.transAxes, fontsize=8.8, color=INK2, va="bottom")
        if ax in axs[:, 1]:
            ax.tick_params(axis="y", labelleft=False)
    fig.canvas.draw()                              # tata letak final sebelum menggambar batang dalam koordinat layar
    for ax, (_, _, nilai, xlim, f) in zip(axs.flat, panel):
        for i, (s, v) in enumerate(zip(urut, nilai)):
            _batang_bulat(ax, i, v, AKSEN if s.startswith("nilm") else PEMBANDING, 24 * skala * 0.62, 4 * skala)
            ax.annotate(f.format(v).replace(".", ","), (v, i), xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=9.5, fontweight="bold", color=INK)

    fig.text(0.04, 0.945, "Perbandingan strategi kendali beban", fontsize=15, fontweight="bold", color=INK, va="center")
    fig.text(0.965, 0.945, "SIMULASI", fontsize=10, fontweight="bold", color=INK2, ha="right", va="center",
             bbox=dict(boxstyle="round,pad=0.45", facecolor=PERMUKAAN, edgecolor=INK2, linewidth=1.2))
    fig.text(0.04, 0.895, f"Jumlah {n_data} data uji sintetis x {jam:g} jam. Parameter MCB, alat, dan inverter bersifat ILUSTRATIF; "
             "ini bukan hasil pengukuran.", fontsize=9.3, color=INK2, va="center")
    fig.legend(handles=[Patch(color=PEMBANDING, label="Pembanding"), Patch(color=AKSEN, label="Kendali berbasis NILM")],
               loc="upper left", bbox_to_anchor=(0.04, 0.865), ncol=2, frameon=False, fontsize=9.3,
               labelcolor=INK2, handlelength=1.0, handleheight=1.0, columnspacing=1.6, borderpad=0, borderaxespad=0)
    fig.text(0.04, 0.035, "Sumber: sim/simulasi_nilm_kendali.py. Satu keluarga skenario sintetis; model NILM dilatih pada generator "
             "yang sama dengan data ujinya (hasil nyata hampir pasti lebih buruk).", fontsize=8, color=MUTED, va="center")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor=PERMUKAAN)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jam", type=float, default=6)
    ap.add_argument("--seed-latih", type=int, default=1)
    ap.add_argument("--seed-uji", type=int, nargs="+", default=[9, 10, 11])
    ap.add_argument("--in-mcb", type=float, default=10.0)
    ap.add_argument("--tau", type=float, default=900.0, help="detik (ilustratif)")
    ap.add_argument("--theta-trip", type=float, default=1.45)
    ap.add_argument("--inverter-va", type=float, default=2500.0)
    ap.add_argument("--salah-tau", type=float, default=1.0,
                    help="tau sebenarnya = faktor ini x tau yang diketahui pengendali (mis. 0.6 = MCB lebih cepat panas)")
    ap.add_argument("--keluaran", default=None, help="simpan tabel hasil ke CSV")
    ap.add_argument("--gambar", default=None, help="simpan gambar perbandingan (PNG); menjalankan juga skenario tau salah, sekitar 2x lebih lama")
    ap.add_argument("--salah-tau-gambar", type=float, default=0.6, help="tau sebenarnya (x tebakan) pada panel kedua gambar")
    a = ap.parse_args()
    hasil = jalankan(a.jam, a.seed_latih, tuple(a.seed_uji), a.in_mcb, a.tau, a.theta_trip, a.inverter_va, a.salah_tau)
    pd.set_option("display.width", 200)
    print("\nPer data uji (SIMULASI):\n" + hasil.to_string(index=False))
    rata = hasil.drop(columns="seed").groupby("skenario", sort=False).sum(numeric_only=True)
    rata["pemanasan_maks"] = hasil.groupby("skenario", sort=False)["pemanasan_maks"].max()
    print("\nJumlah seluruh data uji (pemanasan_maks = nilai terbesar), SIMULASI:\n" + rata.to_string())
    print(f"\nParameter ILUSTRATIF: MCB {a.in_mcb:g} A, tau {a.tau:g} s, ambang trip {a.theta_trip:g}, inverter "
          f"{a.inverter_va:g} VA, tau sebenarnya = {a.salah_tau:g} x tau yang diketahui pengendali.")
    print("Semua angka ini SIMULASI pada data sintetis, bukan kinerja alat.")
    if a.keluaran:
        Path(a.keluaran).parent.mkdir(parents=True, exist_ok=True)
        hasil.to_csv(a.keluaran, index=False)
        print(f"Tabel disimpan: {a.keluaran}")
    if a.gambar:
        benar = hasil if a.salah_tau == 1.0 else jalankan(a.jam, a.seed_latih, tuple(a.seed_uji), a.in_mcb, a.tau,
                                                         a.theta_trip, a.inverter_va, 1.0)
        salah = hasil if a.salah_tau == a.salah_tau_gambar else jalankan(a.jam, a.seed_latih, tuple(a.seed_uji), a.in_mcb,
                                                                        a.tau, a.theta_trip, a.inverter_va, a.salah_tau_gambar)
        gambar(benar, salah, a.gambar, a.salah_tau_gambar, a.jam)
        print(f"Gambar disimpan: {a.gambar}")


if __name__ == "__main__":
    main()
