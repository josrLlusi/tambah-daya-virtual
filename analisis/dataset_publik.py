"""Ambil event berlabel dari dataset publik UK-DALE atau REDD (format .dat frekuensi rendah).

Unduh sendiri dataset-nya (perlu registrasi/persetujuan lisensi di situs resminya), lalu ekstrak:
    UK-DALE : .../ukdale/house_1/labels.dat, channel_1.dat, channel_2.dat, ...
    REDD    : .../low_freq/house_1/labels.dat, channel_1.dat, ...
Tiap channel_N.dat berisi baris "timestamp_unix daya_watt".

Contoh:
    python analisis/dataset_publik.py --folder D:/data/ukdale/house_1 --daftar
    python analisis/dataset_publik.py --folder D:/data/ukdale/house_1 \
        --alat kettle,washing_machine,microwave,toaster --skala-tegangan 0.915 \
        --mulai 2014-01-01 --hari 14 --keluaran data/olah/ev_ukdale_h1.csv

Batasan yang harus diingat:
  - Data frekuensi rendah ini hanya berisi daya aktif (tanpa daya reaktif), jadi fitur yang tersedia hanya dP.
  - Tegangan Inggris 230 V, Amerika 120 V; --skala-tegangan (mis. (220/230)^2 = 0.915) hanya tepat untuk beban resistif.
  - Alat rumah tangga Inggris/Amerika berbeda dengan mesin UMKM Indonesia. Gunakan untuk pra-latih atau
    menguji kode, lalu latih ulang dengan rekaman alat lokal.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deteksi_event import deteksi  # noqa: E402


def baca_label(folder):
    lab = {}
    for baris in (Path(folder) / "labels.dat").read_text().splitlines():
        if baris.strip():
            no, nama = baris.split(maxsplit=1)
            lab[nama.strip()] = int(no)
    return lab


def baca_channel(folder, no, mulai=None, hari=None):
    d = pd.read_csv(Path(folder) / f"channel_{no}.dat", sep=r"\s+", header=None,
                    names=["ts", "daya_aktif"], usecols=[0, 1])
    d["waktu"] = pd.to_datetime(d["ts"], unit="s")
    if mulai:
        t0 = pd.Timestamp(mulai)
        d = d[d["waktu"] >= t0]
        if hari:
            d = d[d["waktu"] < t0 + pd.Timedelta(days=hari)]
    return d[["waktu", "daya_aktif"]].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--daftar", action="store_true", help="tampilkan nama alat di labels.dat")
    ap.add_argument("--alat", default="")
    ap.add_argument("--skala-tegangan", type=float, default=1.0)
    ap.add_argument("--ambang", type=float, default=40.0)
    ap.add_argument("--mulai", default=None)
    ap.add_argument("--hari", type=float, default=None)
    ap.add_argument("--keluaran", default="data/olah/ev_publik.csv")
    a = ap.parse_args()

    lab = baca_label(a.folder)
    if a.daftar or not a.alat:
        for nama, no in sorted(lab.items(), key=lambda x: x[1]):
            print(f"{no:3d}  {nama}")
        return
    semua = []
    for nama in [x.strip() for x in a.alat.split(",") if x.strip()]:
        if nama not in lab:
            print(f"[lewati] '{nama}' tidak ada di labels.dat")
            continue
        d = baca_channel(a.folder, lab[nama], a.mulai, a.hari)
        d["daya_aktif"] *= a.skala_tegangan
        ev = deteksi(d, ambang=a.ambang)
        ev["alat"] = nama
        ev["sumber"] = f"{Path(a.folder).name}/channel_{lab[nama]}"
        print(f"{nama}: {len(d)} sampel, {len(ev)} event")
        semua.append(ev)
    if not semua:
        raise SystemExit("Tidak ada event.")
    out = pd.concat(semua, ignore_index=True)
    Path(a.keluaran).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.keluaran, index=False)
    print(f"{len(out)} event -> {a.keluaran}")


if __name__ == "__main__":
    main()
