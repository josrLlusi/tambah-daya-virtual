"""Perekam data ESP32 lewat USB serial ke CSV.

Firmware mengirim satu baris per pengukuran dengan awalan DATA, misalnya:
    DATA,220.4,9.512,2050.3,0.980,410.7,1.12,0
Urutan kolom diatur dengan --kolom (default sesuai firmware esp32_panel).

Contoh:
    pip install pyserial
    python alat/perekam_serial.py --port COM5 --sesi setrika_uap --catatan "setrika sendirian, 5x nyala-mati"
    python alat/perekam_serial.py --port /dev/ttyUSB0 --durasi 600
    python alat/perekam_serial.py --uji --durasi 5          # tanpa ESP32, data palsu untuk mencoba

Hasil: data/raw/<sesi>_<tanggal-jam>.csv dan satu baris ringkasan di data/raw/logbook.csv.
Tekan Ctrl+C untuk berhenti.
"""
import argparse
import csv
import random
import time
from datetime import datetime
from pathlib import Path

KOLOM_DEFAULT = "tegangan,arus,daya_aktif,faktor_daya,daya_reaktif,theta,baterai_aktif"


def sumber_uji():
    """Baris palsu untuk mencoba perekam tanpa perangkat keras."""
    while True:
        v = 220 + random.gauss(0, 2)
        p = 2050 + random.gauss(0, 10)
        yield f"DATA,{v:.1f},{p / (v * 0.98):.3f},{p:.1f},0.980,{p * 0.2:.1f},1.12,0"
        time.sleep(1)


def sumber_serial(port, baud):
    import serial  # pip install pyserial
    with serial.Serial(port, baud, timeout=2) as s:
        while True:
            baris = s.readline().decode("utf-8", errors="replace").strip()
            if baris:
                yield baris


def urai(baris, kolom):
    """Ubah 'DATA,...' menjadi dict. Baris lain (log, error) dikembalikan None."""
    if not baris.startswith("DATA,"):
        return None
    nilai = baris.split(",")[1:]
    if len(nilai) != len(kolom):
        return None
    try:
        return {k: float(v) for k, v in zip(kolom, nilai)}
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="COM5 (Windows) atau /dev/ttyUSB0 (Linux/Mac)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--kolom", default=KOLOM_DEFAULT)
    ap.add_argument("--sesi", default="sesi")
    ap.add_argument("--perangkat", default="panel-01")
    ap.add_argument("--catatan", default="")
    ap.add_argument("--durasi", type=float, default=0, help="detik; 0 = sampai Ctrl+C")
    ap.add_argument("--folder", default="data/raw")
    ap.add_argument("--uji", action="store_true", help="pakai data palsu, tanpa ESP32")
    a = ap.parse_args()
    if not a.uji and not a.port:
        ap.error("isi --port, atau pakai --uji untuk mencoba")

    kolom = [k.strip() for k in a.kolom.split(",")]
    folder = Path(a.folder)
    folder.mkdir(parents=True, exist_ok=True)
    mulai = datetime.now()
    path = folder / f"{a.sesi}_{mulai:%Y%m%d_%H%M%S}.csv"
    sumber = sumber_uji() if a.uji else sumber_serial(a.port, a.baud)

    n, n_buang = 0, 0
    print(f"Merekam ke {path}  (Ctrl+C untuk berhenti)")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["waktu", "id_perangkat", "sesi", *kolom])
        w.writeheader()
        try:
            for baris in sumber:
                data = urai(baris, kolom)
                if data is None:
                    n_buang += 1
                    if not baris.startswith("DATA"):
                        print("  [log]", baris)
                    continue
                w.writerow({"waktu": datetime.now().isoformat(timespec="milliseconds"),
                            "id_perangkat": a.perangkat, "sesi": a.sesi, **data})
                n += 1
                if n % 10 == 0:
                    f.flush()
                    print(f"  {n} baris")
                if a.durasi and (datetime.now() - mulai).total_seconds() >= a.durasi:
                    break
        except KeyboardInterrupt:
            pass

    selesai = datetime.now()
    log = folder / "logbook.csv"
    baru = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["mulai", "selesai", "berkas", "perangkat", "sesi", "baris", "baris_dibuang", "catatan"])
        w.writerow([mulai.isoformat(timespec="seconds"), selesai.isoformat(timespec="seconds"), path.name,
                    a.perangkat, a.sesi, n, n_buang, a.catatan])
    print(f"Selesai: {n} baris tersimpan, {n_buang} baris bukan data. Logbook: {log}")


if __name__ == "__main__":
    main()
