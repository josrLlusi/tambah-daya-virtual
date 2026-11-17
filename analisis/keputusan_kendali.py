"""Keputusan kendali beban berdasarkan hasil NILM + model termal MCB (fungsi murni, tanpa perangkat keras).

Masukan : keadaan panel saat ini (daya terukur, pemanasan MCB, alat yang dikenali NILM menyala beserta dayanya,
          alat yang sedang dipindah ke baterai).
Keluaran: satu Keputusan: 'pindah' alat X ke baterai, 'kembali' alat X ke PLN, 'peringatan', atau 'tunggu'.

Perbedaan dari kendali termal saja (firmware esp32_panel.ino sekarang):
  1. Hanya alat yang BENAR-BENAR menyala (menurut NILM) yang dipindah, dan hanya bila pemindahannya cukup meredam
     beban. Firmware memindahkan alat yang terpasang di relay walau alat itu sedang mati (percuma).
  2. Bila ada beberapa kanal relay, dipilih alat yang PALING BANYAK meredam beban (pemanasan tunak terendah
     setelah dilepas). Inverter hanya muat sedikit alat, jadi pilihan pertama harus menyisakan ruang terbesar
     untuk lonjakan berikutnya (sama dengan "terbesar dulu" pada rencana_kendali di dasbor).
  3. Alat dikembalikan ke PLN hanya bila pemanasan sudah turun DAN daya alat itu (dari NILM) tidak membuat
     beban melewati batas lagi. Firmware cuma melihat pemanasan sehingga bisa bolak-balik.
  4. Jaring pengaman: bila NILM tidak menemukan kandidat padahal pemanasan sudah melewati ambang aman, perilakunya
     sama dengan kendali termal (pindahkan alat di kanal bebas). Jadi NILM yang keliru tidak lebih buruk dari firmware.

Yang TIDAK diputuskan di sini: urutan relay. Putus-dulu-baru-sambung, jeda pindah, dan keadaan aman saat daya
hilang tetap dijaga firmware. Modul ini hanya mengusulkan "pindah/kembali"; firmware tetap pelaksana.

Asumsi: daya tiap alat dijumlahkan sebagai daya kompleks (P dan Q), jadi arus setelah satu alat dilepas dihitung
dari (P - P_alat, Q - Q_alat). Besaran Q tanpa tanda (beban induktif); beban kapasitif besar tidak ditangani.
Semua parameter ILUSTRATIF sampai ada datasheet dan uji waktu trip MCB (lihat analisis/fit_mcb.py).
"""
import math
from dataclasses import dataclass, field

# Alat yang tidak boleh dipasang pada kanal pindah: kompresor yang dihidupkan kembali seketika dapat macet dan
# rusak (lihat catatan keselamatan di firmware/esp32_panel/esp32_panel.ino).
KOMPRESOR = frozenset({"freezer", "kulkas", "lemari_es", "ac", "pendingin", "chiller"})


@dataclass
class Konfigurasi:
    in_mcb: float                        # arus nominal MCB [A]
    tau: float                           # konstanta waktu termal [detik]
    theta_trip: float                    # ambang trip model [relatif]
    kanal: dict = field(default_factory=dict)   # alat -> nomor kanal relay (hanya alat ini yang boleh dipindah)
    margin: float = 0.80                 # beban dianggap aman bila pemanasan tunak < margin x theta_trip
    theta_lepas: float = 1.0             # alat boleh kembali ke PLN bila pemanasan di bawah ini
    tegangan: float = 220.0              # [V]
    kapasitas_inverter_va: float = 2000.0
    horizon_s: float = 120.0             # bertindak bila pemanasan diperkirakan mencapai ambang aman dalam waktu ini
    min_jeda_lindung_s: float = 10.0     # jeda minimal antar aksi pelindung
    min_jeda_kembali_s: float = 180.0    # alat minimal selama ini di baterai sebelum boleh kembali

    def __post_init__(self):
        if self.in_mcb <= 0 or self.tau <= 0 or self.theta_trip <= 1.0:
            raise ValueError("in_mcb dan tau harus > 0, theta_trip harus > 1")
        if not 0 < self.margin < 1:
            raise ValueError("margin harus di antara 0 dan 1")
        salah = sorted(set(self.kanal) & KOMPRESOR)
        if salah:
            raise ValueError(f"alat {salah} adalah kompresor: tidak boleh dipasang pada kanal pindah "
                             "(dihidupkan kembali seketika dapat macet dan rusak)")

    @property
    def ambang(self):
        """Pemanasan tunak tertinggi yang dianggap aman."""
        return self.margin * self.theta_trip


@dataclass
class Keadaan:
    theta: float                         # pemanasan MCB sekarang (perkiraan model)
    p: float                             # daya aktif terukur di jalur PLN [W]
    q: float                             # daya reaktif terukur di jalur PLN [var]
    aktif: dict = field(default_factory=dict)       # alat menyala menurut NILM (di jalur PLN): nama -> (P_W, Q_var)
    dibaterai: dict = field(default_factory=dict)   # alat yang sedang dipindah: nama -> (P_W, Q_var) terakhir terukur
    detik_di_baterai: dict = field(default_factory=dict)   # nama -> berapa detik sudah di baterai
    detik_sejak_lindung: float = None    # sejak aksi pelindung terakhir (None = belum pernah)
    tipikal: dict = field(default_factory=dict)     # alat berkanal -> (P_W, Q_var) tipikal, untuk jaring pengaman


@dataclass
class Keputusan:
    aksi: str                            # 'pindah' | 'kembali' | 'peringatan' | 'tunggu'
    alat: str = None
    alasan: str = ""
    cukup: bool = None                   # untuk 'pindah': True bila pemanasan tunak setelahnya di bawah ambang aman
    s_setelah: float = None              # pemanasan tunak yang diperkirakan setelah aksi


def arus(p, q, v):
    return math.hypot(p, q) / v


def pemanasan_tunak(i, in_mcb):
    """(I/In)^2: nilai yang didekati pemanasan MCB bila arus i bertahan."""
    return (i / in_mcb) ** 2


def waktu_ke_ambang(theta, s, ambang, tau):
    """Detik sampai pemanasan mencapai `ambang` bila pemanasan tunak s bertahan. 0 bila sudah lewat, inf bila tak pernah."""
    if theta >= ambang:
        return 0.0
    if s <= ambang:
        return math.inf
    return tau * math.log((s - theta) / (s - ambang))


def s_tanpa_alat(cfg, k, p_alat, q_alat):
    """Pemanasan tunak bila alat dengan daya (p_alat, q_alat) dilepas dari jalur PLN."""
    return pemanasan_tunak(arus(max(k.p - p_alat, 0.0), max(k.q - q_alat, 0.0), cfg.tegangan), cfg.in_mcb)


def s_dengan_alat(cfg, k, p_alat, q_alat):
    """Pemanasan tunak bila alat dengan daya (p_alat, q_alat) dikembalikan ke jalur PLN."""
    return pemanasan_tunak(arus(k.p + p_alat, k.q + q_alat, cfg.tegangan), cfg.in_mcb)


def keputusan(cfg, k):
    s_now = pemanasan_tunak(arus(k.p, k.q, cfg.tegangan), cfg.in_mcb)
    t_amb = waktu_ke_ambang(k.theta, s_now, cfg.ambang, cfg.tau)
    jeda_ok = k.detik_sejak_lindung is None or k.detik_sejak_lindung >= cfg.min_jeda_lindung_s

    # 1. Perlindungan: beban SEKARANG menahan pemanasan di atas ambang aman (tunak > ambang) dan ambang itu akan
    #    tercapai dalam horizon -> pindahkan alat. Bila beban sudah ringan (tunak <= ambang), pemanasan hanya akan
    #    turun, jadi tidak perlu tindakan walau pemanasan sekarang masih di atas ambang (mis. sesaat setelah memindah).
    if s_now > cfg.ambang and t_amb <= cfg.horizon_s and jeda_ok:
        sisa_va = cfg.kapasitas_inverter_va - sum(math.hypot(*pq) for pq in k.dibaterai.values())
        kandidat = []
        for a, (pa, qa) in k.aktif.items():
            if a not in cfg.kanal or a in k.dibaterai:
                continue
            sa = math.hypot(pa, qa)
            if sa > sisa_va:
                continue                       # melebihi kapasitas inverter
            if pa > 1.25 * k.p + 50:
                continue                       # NILM mengira alat menyala, tetapi total terukur lebih kecil: tidak konsisten
            kandidat.append((a, sa, s_tanpa_alat(cfg, k, pa, qa)))
        if kandidat:
            a, sa, s_set = min(kandidat, key=lambda c: c[2])     # yang paling banyak meredam
            if s_set < cfg.ambang:
                return Keputusan("pindah", a, f"pemanasan {k.theta:.2f} menuju ambang aman {cfg.ambang:.2f} "
                                 f"(tunak {s_now:.2f}); pindah {a} ({sa:.0f} VA) cukup (tunak jadi {s_set:.2f})", True, s_set)
            return Keputusan("pindah", a, f"pemanasan menuju ambang aman (tunak {s_now:.2f}); pindah {a} belum cukup "
                             f"(tunak jadi {s_set:.2f}), alat lain diperlukan", False, s_set)
        if k.theta >= cfg.ambang:
            # JARING PENGAMAN: pemanasan sudah melewati ambang aman tetapi NILM tidak menemukan kandidat. NILM bisa
            # keliru, sedangkan MCB turun lebih merugikan daripada memindah alat yang ternyata sedang mati.
            # Bertindak seperti kendali termal: pindahkan alat di kanal bebas (daya tipikal terbesar yang muat).
            bebas = [(a, math.hypot(*k.tipikal.get(a, (0.0, 0.0)))) for a in cfg.kanal if a not in k.dibaterai]
            bebas = [(a, sa) for a, sa in bebas if sa <= sisa_va]
            if bebas:
                a, sa = max(bebas, key=lambda c: c[1])
                return Keputusan("pindah", a, f"DARURAT: pemanasan {k.theta:.2f} sudah melewati ambang aman {cfg.ambang:.2f} dan NILM "
                                 f"tidak menemukan alat menyala yang bisa dipindah; {a} dipindah tanpa konfirmasi NILM", None, None)
        return Keputusan("peringatan", None, f"pemanasan menuju ambang aman (tunak {s_now:.2f}) tetapi tidak ada alat menyala "
                         "yang bisa dipindah (tak ada kanal, kapasitas inverter habis, atau data NILM tidak konsisten)")

    # 2. Kembali ke PLN: pemanasan sudah turun, alat sudah cukup lama di baterai, dan tidak akan membebani lagi.
    if k.theta < cfg.theta_lepas:
        for a in sorted(k.dibaterai, key=lambda x: math.hypot(*k.dibaterai[x])):
            if k.detik_di_baterai.get(a, 0.0) < cfg.min_jeda_kembali_s:
                continue
            pa, qa = k.dibaterai[a]
            s_kembali = s_dengan_alat(cfg, k, pa, qa)
            if s_kembali < cfg.ambang:
                return Keputusan("kembali", a, f"pemanasan {k.theta:.2f} < {cfg.theta_lepas:.2f} dan beban dengan {a} "
                                 f"kembali (tunak {s_kembali:.2f}) di bawah ambang aman", None, s_kembali)
            return Keputusan("tunggu", a, f"{a} ditahan di baterai: bila kembali, tunak {s_kembali:.2f} "
                             f"melewati ambang aman {cfg.ambang:.2f}")
    return Keputusan("tunggu")
