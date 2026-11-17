"""Pengendali online: NILM -> keputusan kendali, satu sampel per detik.

    pengendali = PengendaliNILM(paket, konfigurasi)          # paket dari analisis/latih_klasifikasi.py (model.joblib)
    for t, P, Q, V in aliran_ukur_1_detik:
        for k in pengendali.langkah(t, P, Q, V):             # daftar Keputusan (kosong bila 'tunggu')
            if k.aksi == "pindah":   ... perintahkan firmware memindahkan k.alat ke baterai
            if k.aksi == "kembali":  ... perintahkan firmware mengembalikan k.alat ke PLN

Isi: pemanasan MCB (model termal dari arus terukur) + deteksi event + klasifikasi + pelacakan status alat
(PelacakStatus, sama dengan analisis/disagregasi.py) + aturan keputusan (analisis/keputusan_kendali.py).

Catatan penting:
  - Masukan harus 1 sampel per detik (rata-ratakan dulu bila perangkat mengirim lebih cepat).
  - Status alat tertunda sekitar 9 detik (deteksi event perlu data 'sesudah'); pemanasan MCB tidak tertunda.
  - Saat pengendali memindahkan alat, daya di sensor turun. Event itu dikenali sebagai akibat perintah sendiri
    (bukan alat yang dimatikan pengguna), dan alat dicatat sebagai 'di baterai'. Selama di baterai alat tidak
    terlihat oleh sensor; dayanya diambil dari ukuran terakhir sebelum dipindah.
  - Modul ini hanya MENGUSULKAN aksi. Urutan relay dan keadaan aman tetap tanggung jawab firmware.
  - Belum pernah dijalankan dengan perangkat keras; diuji hanya pada data sintetis/simulasi.
"""
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deteksi_event import deteksi  # noqa: E402
from disagregasi import PelacakStatus  # noqa: E402
from keputusan_kendali import Keadaan, Keputusan, arus, keputusan  # noqa: E402
from latih_klasifikasi import fitur  # noqa: E402

TUNDA = 9                 # sampel: lag (3) + jendela (5) deteksi event + 1
JENDELA = 150             # sampel yang disimpan untuk deteksi
TOPENG_S = 25             # event dalam rentang ini setelah perintah sendiri dianggap akibat perintah itu
TOPENG_TOLERANSI = 0.4    # selisih dP yang masih dianggap alat yang sama (relatif)
JEDA_PERINGATAN_S = 60.0


class PengendaliNILM:
    def __init__(self, paket, cfg, tiap=2):
        self.paket, self.cfg, self.tiap = paket, cfg, tiap
        self.reset()

    def reset(self):
        """Mulai ulang (mis. setelah MCB turun dan semua beban terputus)."""
        self.pelacak = PelacakStatus(self.paket)
        self.P, self.Q, self.A = (deque(maxlen=JENDELA) for _ in range(3))
        self.n = 0                 # jumlah sampel yang sudah diterima
        self.j_proc = 0            # indeks sampel berikutnya yang akan diproses pelacak
        self.theta = 0.0
        self.t_prev = None
        self.dasar = None
        self.dibaterai = {}        # alat -> {"p", "q", "t"}
        self.topeng = []           # perintah sendiri yang menunggu event akibatnya
        self.t_lindung = None
        self.t_peringatan = -math.inf
        self.riwayat = []          # [{"t", "aksi", "alat", "alasan"}]

    # --- daya perkiraan satu alat -------------------------------------------------------------------------
    def daya_alat(self, a):
        if a in self.pelacak.ukur:
            return self.pelacak.ukur[a]
        return (float(self.paket["dP_tipikal"].get(a, 0.0)), float(self.paket.get("dQ_tipikal", {}).get(a, 0.0)))

    # --- langkah utama ------------------------------------------------------------------------------------
    def langkah(self, t, p, q, v):
        dt = 0.0 if self.t_prev is None else max(t - self.t_prev, 0.0)
        self.t_prev = t
        s = (arus(p, q, v) / self.cfg.in_mcb) ** 2
        self.theta = s + (self.theta - s) * math.exp(-dt / self.cfg.tau)   # langkah eksak model orde-1
        self.P.append(p); self.Q.append(q); self.A.append(arus(p, q, v))
        self.n += 1
        if self.n % self.tiap == 0 and self.n - TUNDA > self.j_proc:
            self._perbarui_status()
        return self._putuskan(t)

    # --- status alat (tertunda TUNDA sampel) ------------------------------------------------------------------
    def _perbarui_status(self):
        akhir = self.n - TUNDA
        mulai = self.n - len(self.P)
        P, Q, A = np.array(self.P), np.array(self.Q), np.array(self.A)
        win = pd.DataFrame({"waktu": pd.Timestamp("2026-01-01") + pd.to_timedelta(np.arange(mulai, self.n), unit="s"),
                            "daya_aktif": P, "daya_reaktif": Q, "arus": A})
        ev = deteksi(win)
        baru = {}
        if len(ev):
            ev = ev.assign(abs_idx=mulai + ev["indeks"].astype(int))
            ev = ev[(ev["abs_idx"] >= self.j_proc) & (ev["abs_idx"] < akhir)]
            if len(ev):
                ev = ev.assign(alat_pred=self.paket["model"].predict(fitur(ev)[self.paket["fitur"]]))
                baru = {int(r["abs_idx"]): r for _, r in ev.iterrows()}
        for j in range(self.j_proc, akhir):
            lo, hi = max(j - 5, mulai), min(j + 5, self.n - 1)
            med = float(np.median(P[lo - mulai:hi - mulai + 1]))
            self.dasar = med if self.dasar is None else min(self.dasar, med)
            e = baru.get(j)
            if e is not None and self._akibat_perintah_sendiri(j, e):
                e = None
            m = None
            if e is None and self.pelacak.perlu_koreksi(j) and j - 10 >= mulai:
                m = float(np.median(P[j - 10 - mulai:j + 1 - mulai]))
            self.pelacak.langkah(j, e, m, self.dasar)
        self.j_proc = akhir
        self.topeng = [x for x in self.topeng if akhir <= x["j0"] + TOPENG_S]

    def _akibat_perintah_sendiri(self, j, e):
        for x in self.topeng:
            if (e["arah"] == x["arah"] and abs(j - x["j0"]) <= TOPENG_S
                    and abs(abs(float(e["dP"])) - x["p"]) <= TOPENG_TOLERANSI * max(x["p"], 1.0)):
                self.topeng.remove(x)
                return True
        return False

    # --- keputusan (tidak tertunda) -------------------------------------------------------------------------
    def _putuskan(self, t):
        k5 = 5
        p = float(np.mean(list(self.P)[-k5:])); q = float(np.mean(list(self.Q)[-k5:]))
        aktif = {a: self.daya_alat(a) for a in self.pelacak.aktif}
        k = Keadaan(theta=self.theta, p=p, q=q, aktif=aktif,
                    dibaterai={a: (d["p"], d["q"]) for a, d in self.dibaterai.items()},
                    detik_di_baterai={a: t - d["t"] for a, d in self.dibaterai.items()},
                    detik_sejak_lindung=None if self.t_lindung is None else t - self.t_lindung,
                    tipikal={a: (float(self.paket["dP_tipikal"].get(a, 0.0)), float(self.paket.get("dQ_tipikal", {}).get(a, 0.0)))
                             for a in self.cfg.kanal})
        kep = keputusan(self.cfg, k)
        if kep.aksi == "pindah":
            pa, qa = self.daya_alat(kep.alat)
            self.dibaterai[kep.alat] = {"p": pa, "q": qa, "t": t}
            self.pelacak.aktif.discard(kep.alat)
            self.pelacak.terlarang.add(kep.alat)      # koreksi tidak boleh menyalakannya lagi selama di baterai
            self.topeng.append({"arah": "mati", "p": pa, "j0": self.n - 1})
            self.t_lindung = t
        elif kep.aksi == "kembali":
            d = self.dibaterai.pop(kep.alat)
            self.pelacak.aktif.add(kep.alat)
            self.pelacak.terlarang.discard(kep.alat)
            self.topeng.append({"arah": "nyala", "p": d["p"], "j0": self.n - 1})
        elif kep.aksi == "peringatan":
            if t - self.t_peringatan < JEDA_PERINGATAN_S:
                return []
            self.t_peringatan = t
        else:
            return []
        self.riwayat.append({"t": t, "aksi": kep.aksi, "alat": kep.alat, "alasan": kep.alasan})
        return [kep]
