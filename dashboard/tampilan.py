"""Elemen visual dasbor: CSS, ikon, banner, diagram panel, dan gauge (HTML/SVG murni)."""
import math

# Palet
NAVY = "#12263F"
BIRU = "#1F4E79"
MERAH = "#B4413C"
KUNING = "#C98A12"
HIJAU = "#2E7D5B"
ABU = "#C9D1DB"
TEKS2 = "#5B6573"

# Ikon garis sederhana (viewBox 24x24, stroke)
_IKON = {
    "bolt": '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "battery": '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2M6 10v4M10 10v4"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "trend": '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
    "cpu": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/>'
           '<path d="M9 2v3M15 2v3M9 19v3M15 19v3M19 9h3M19 15h3M2 9h3M2 15h3"/>',
    "wave": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "plug": '<path d="M12 22v-5M9 8V2M15 8V2"/><path d="M18 8v5a6 6 0 0 1-12 0V8z"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "factory": '<path d="M2 20V9l6 4V9l6 4V4h8v16z"/><path d="M6 17h2M11 17h2M16 17h2"/>',
    "tower": '<path d="M12 2 7 22M12 2l5 20M5 8h14M6 13h12M9 22l3-6 3 6"/>',
    "switch": '<circle cx="5" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><path d="m7 11 10-5"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
             '<path d="M12 9v4M12 17h.01"/>',
}


def ikon(nama, ukuran=18, warna="currentColor", tebal=2):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ukuran}" height="{ukuran}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{warna}" stroke-width="{tebal}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="vertical-align:middle;flex-shrink:0">{_IKON[nama]}</svg>')


CSS = """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1400px;}
footer {visibility: hidden;}
h1, h2, h3 {letter-spacing: -0.01em;}

/* ---------- Banner ---------- */
.tdv-hero {position:relative; overflow:hidden; border-radius:14px; padding:1.6rem 1.8rem 1.4rem;
    margin-bottom:1.1rem; color:#fff;
    background: radial-gradient(1200px 300px at 85% -20%, rgba(78,148,214,.35), transparent 60%),
                linear-gradient(120deg, #0E2238 0%, #15365A 55%, #1F4E79 100%);}
.tdv-hero-circuit {position:absolute; right:-10px; top:0; height:100%; opacity:.14; pointer-events:none;}
.tdv-hero-inner {position:relative; display:flex; gap:2rem; justify-content:space-between; align-items:center;
    flex-wrap:wrap;}
.tdv-eyebrow {font-size:.72rem; font-weight:600; letter-spacing:.12em; text-transform:uppercase;
    color:#9CC3E8; margin-bottom:.35rem; display:flex; align-items:center; gap:.4rem;}
.tdv-title {font-size:2rem; font-weight:800; line-height:1.15; margin:0; color:#fff !important;
    padding:0 !important;}
.tdv-title span {color:#F6C343;}
.tdv-sub {color:#D5E3F1; font-size:.95rem; margin-top:.4rem; max-width:640px; line-height:1.5;}
.tdv-meta {display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; font-size:.8rem;
    color:#BFD3E6; margin-top:.9rem;}
.tdv-meta b {color:#fff; font-weight:600;}
.tdv-meta .sep {color:rgba(255,255,255,.3);}
.tdv-badge {display:inline-flex; align-items:center; gap:.3rem; padding:.22rem .65rem; border-radius:999px;
    font-weight:700; font-size:.7rem; letter-spacing:.05em;}
.tdv-badge.sim {background:#FFF1D6; color:#7A4F00;}
.tdv-badge.ukur {background:#D8F0E3; color:#1E5E43;}

/* alur PLN -> MCB -> kendali -> mesin pada banner */
.tdv-flow {display:flex; align-items:center; gap:.35rem; background:rgba(255,255,255,.07);
    border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:.8rem 1rem;}
.tdv-flow-node {display:flex; flex-direction:column; align-items:center; gap:.3rem; min-width:62px;
    font-size:.68rem; color:#D5E3F1; text-align:center;}
.tdv-flow-node .bulat {width:40px; height:40px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.2);}
.tdv-flow-line {width:34px; height:2px; margin-bottom:1.1rem;
    background:repeating-linear-gradient(90deg,#F6C343 0 6px,transparent 6px 11px);
    background-size:22px 2px; animation:tdv-geser 0.9s linear infinite;}
.tdv-flow-line.hijau {background:repeating-linear-gradient(90deg,#6FD3A0 0 6px,transparent 6px 11px);
    background-size:22px 2px;}
@keyframes tdv-geser {to {background-position:22px 0;}}

/* ---------- Kartu KPI ---------- */
.tdv-kpis {display:grid; grid-template-columns:repeat(auto-fit, minmax(175px, 1fr)); gap:.75rem;
    margin-bottom:1rem;}
.tdv-kpi {position:relative; background:#FFFFFF; border:1px solid #E1E6ED; border-radius:12px;
    padding:.9rem 1rem; box-shadow:0 1px 2px rgba(16,24,40,.04); transition:transform .15s, box-shadow .15s;}
.tdv-kpi:hover {transform:translateY(-2px); box-shadow:0 6px 16px rgba(16,24,40,.08);}
.tdv-kpi::before {content:""; position:absolute; left:0; top:12px; bottom:12px; width:3px;
    border-radius:0 3px 3px 0; background:var(--aksen, #1F4E79);}
.tdv-kpi-head {display:flex; align-items:center; gap:.45rem;}
.tdv-kpi-ikon {width:28px; height:28px; border-radius:8px; display:flex; align-items:center;
    justify-content:center; background:var(--aksen-bg, #E8EFF7); color:var(--aksen, #1F4E79);}
.tdv-kpi-label {font-size:.72rem; color:#5B6573; font-weight:600; text-transform:uppercase;
    letter-spacing:.04em; line-height:1.25;}
.tdv-kpi-value {font-size:1.6rem; font-weight:700; color:#12263F; margin-top:.45rem;
    font-variant-numeric:tabular-nums;}
.tdv-kpi-value small {font-size:.9rem; font-weight:600; color:#5B6573; margin-left:.2rem;}
.tdv-kpi-sub {font-size:.78rem; margin-top:.15rem; color:#5B6573;}
.tdv-kpi-sub.ok {color:#1E7A50;} .tdv-kpi-sub.bad {color:#B4413C;} .tdv-kpi-sub.warn {color:#9A6700;}

.tdv-note {font-size:.85rem; color:#5B6573; margin:-.2rem 0 .6rem 0;}
.tdv-section {font-size:1.05rem; font-weight:650; color:#12263F; margin:.4rem 0 .15rem 0;
    display:flex; align-items:center; gap:.45rem;}

/* ---------- Putar ulang ---------- */
.tdv-live {display:flex; align-items:center; gap:1rem; flex-wrap:wrap; background:#F7F9FC;
    border:1px solid #E1E6ED; border-radius:12px; padding:.7rem 1rem; margin:.3rem 0 .8rem;}
.tdv-jam {font-size:1.9rem; font-weight:700; color:#12263F; font-variant-numeric:tabular-nums;
    letter-spacing:.02em;}
.tdv-chip {display:inline-flex; align-items:center; gap:.35rem; padding:.3rem .75rem; border-radius:999px;
    font-weight:700; font-size:.78rem; letter-spacing:.04em;}
.tdv-chip.ok {background:#E3F4EA; color:#1E6B47;}
.tdv-chip.warn {background:#FFF1D6; color:#7A4F00;}
.tdv-chip.bad {background:#FBE4E2; color:#9B2F2A;}
.tdv-chip.mati {background:#E9ECF0; color:#3D4652;}
.tdv-dot {width:8px; height:8px; border-radius:50%; background:currentColor; animation:tdv-kedip 1.2s infinite;}
@keyframes tdv-kedip {50% {opacity:.25;}}
.tdv-progress {flex:1; min-width:160px; height:6px; background:#E1E6ED; border-radius:6px; overflow:hidden;}
.tdv-progress > div {height:100%; background:#1F4E79;}

.tdv-card {background:#fff; border:1px solid #E1E6ED; border-radius:12px; padding:.9rem 1rem; margin-bottom:.7rem;}
.tdv-card-title {font-size:.75rem; font-weight:700; color:#5B6573; text-transform:uppercase;
    letter-spacing:.05em; margin-bottom:.4rem; display:flex; align-items:center; gap:.4rem;}
.tdv-bar {position:relative; height:12px; border-radius:6px; background:#EDF0F4; overflow:visible; margin:.6rem 0 .3rem;}
.tdv-bar > .isi {height:100%; border-radius:6px;}
.tdv-bar > .tanda {position:absolute; top:-4px; bottom:-4px; width:2px; background:#5B6573;}
.tdv-bar-ket {display:flex; justify-content:space-between; font-size:.72rem; color:#5B6573;}

.tdv-flowsvg .flow {stroke-dasharray:7 7; animation:tdv-alir linear infinite;}
@keyframes tdv-alir {to {stroke-dashoffset:-28;}}

.tdv-events {list-style:none; padding:0; margin:0; font-size:.85rem;}
.tdv-events li {display:flex; gap:.6rem; padding:.42rem 0; border-bottom:1px dashed #E1E6ED; color:#3D4652;}
.tdv-events li:last-child {border-bottom:none;}
.tdv-events .t {font-variant-numeric:tabular-nums; color:#5B6573; min-width:62px;}
.tdv-events li.baru {color:#12263F; font-weight:600;}
.tdv-events li.nanti {opacity:.4;}

/* ---------- Tentang ---------- */
.tdv-steps {display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:.8rem; margin:.4rem 0 1rem;}
@media (max-width: 1000px) {.tdv-steps {grid-template-columns:repeat(2, minmax(0,1fr));}}
.tdv-step {background:#fff; border:1px solid #E1E6ED; border-radius:12px; padding:1rem;}
.tdv-step .no {font-size:.7rem; font-weight:700; color:#1F4E79; letter-spacing:.08em;}
.tdv-step .ik {width:40px; height:40px; border-radius:10px; background:#E8EFF7; color:#1F4E79;
    display:flex; align-items:center; justify-content:center; margin:.4rem 0 .6rem;}
.tdv-step h4 {font-size:.95rem; margin:0 0 .3rem; color:#12263F; padding:0;}
.tdv-step p {font-size:.83rem; color:#4A5563; margin:0; line-height:1.5;}

.tdv-footer {margin-top:2.5rem; padding-top:1rem; border-top:1px solid #E1E6ED; font-size:.78rem;
    color:#5B6573; display:flex; justify-content:space-between; flex-wrap:wrap; gap:.5rem;}

[data-testid="stSidebar"] h3 {font-size:.78rem; text-transform:uppercase; letter-spacing:.06em;
    color:#5B6573; margin-top:.6rem;}
.tdv-brand {display:flex; align-items:center; gap:.55rem; padding:.2rem 0 .6rem; border-bottom:1px solid #DCE2EA;
    margin-bottom:.4rem;}
.tdv-brand .logo {width:34px; height:34px; border-radius:9px; background:linear-gradient(135deg,#15365A,#1F4E79);
    display:flex; align-items:center; justify-content:center;}
.tdv-brand b {display:block; font-size:.9rem; color:#12263F; line-height:1.1;}
.tdv-brand span {font-size:.72rem; color:#5B6573;}
.stTabs [data-baseweb="tab-list"] {gap:.15rem; border-bottom:1px solid #E1E6ED; flex-wrap:wrap;}
.stTabs [data-baseweb="tab"] {padding:.55rem .85rem; font-weight:600;}
</style>
"""

# Jejak sirkuit dekoratif untuk banner
_SIRKUIT = """
<svg class="tdv-hero-circuit" viewBox="0 0 520 200" preserveAspectRatio="xMaxYMid slice"
     xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#9CC3E8" stroke-width="1.4">
  <path d="M0 40h120l20 20h120l20-20h240"/><path d="M60 100h80l20-20h90l20 20h250"/>
  <path d="M0 160h170l20-20h100l20 20h210"/><path d="M300 0v40M380 60v80M440 100v100M220 160v40"/>
  <g fill="#9CC3E8"><circle cx="140" cy="60" r="3"/><circle cx="280" cy="40" r="3"/><circle cx="160" cy="80" r="3"/>
  <circle cx="270" cy="100" r="3"/><circle cx="380" cy="60" r="3"/><circle cx="440" cy="100" r="3"/>
  <circle cx="190" cy="140" r="3"/><circle cx="310" cy="160" r="3"/><circle cx="220" cy="160" r="3"/></g>
  <rect x="360" y="120" width="40" height="26" rx="3"/><rect x="250" y="70" width="34" height="20" rx="3"/>
</svg>
"""


def banner(simulasi, nama_berkas, perangkat, rentang):
    badge = (f'<span class="tdv-badge sim">{ikon("alert", 12)} DATA SIMULASI</span>' if simulasi
             else f'<span class="tdv-badge ukur">{ikon("shield", 12)} DATA PENGUKURAN</span>')

    def node(nama_ikon, label, warna="#fff"):
        return (f'<div class="tdv-flow-node"><div class="bulat">{ikon(nama_ikon, 20, warna)}</div>'
                f'{label}</div>')

    alur = (node("tower", "PLN") + '<div class="tdv-flow-line"></div>'
            + node("shield", "MCB") + '<div class="tdv-flow-line"></div>'
            + node("cpu", "Sensor &amp;<br>kendali", "#F6C343") + '<div class="tdv-flow-line"></div>'
            + node("factory", "Mesin<br>UMKM") + '<div class="tdv-flow-line hijau"></div>'
            + node("battery", "Baterai", "#6FD3A0"))
    return f"""
<div class="tdv-hero">{_SIRKUIT}
  <div class="tdv-hero-inner">
    <div>
      <div class="tdv-eyebrow">{ikon("bolt", 13, "#F6C343")} Dasbor pemantauan panel listrik UMKM</div>
      <h1 class="tdv-title">TAMBAH DAYA <span>VIRTUAL</span></h1>
      <div class="tdv-sub">Pengenalan beban non-intrusif (NILM) dan kendali cerdas beban serta baterai,
        agar UMKM dapat menambah mesin tanpa menaikkan daya PLN.</div>
      <div class="tdv-meta">{badge}
        <span>Berkas <b>{nama_berkas}</b></span><span class="sep">|</span>
        <span>Perangkat <b>{perangkat}</b></span><span class="sep">|</span><span>{rentang}</span>
      </div>
    </div>
    <div class="tdv-flow">{alur}</div>
  </div>
</div>"""


def brand_sidebar():
    return (f'<div class="tdv-brand"><div class="logo">{ikon("bolt", 18, "#F6C343")}</div>'
            '<div><b>Tambah Daya Virtual</b><span>NILM · Kendali beban · Baterai</span></div></div>')


def kartu(label, nilai, satuan="", sub="", kelas="", nama_ikon="bolt"):
    aksen = {"ok": ("#1E7A50", "#E3F4EA"), "bad": (MERAH, "#FBE4E2"),
             "warn": ("#9A6700", "#FFF1D6")}.get(kelas, (BIRU, "#E8EFF7"))
    return (f'<div class="tdv-kpi" style="--aksen:{aksen[0]};--aksen-bg:{aksen[1]}">'
            f'<div class="tdv-kpi-head"><div class="tdv-kpi-ikon">{ikon(nama_ikon, 16)}</div>'
            f'<div class="tdv-kpi-label">{label}</div></div>'
            f'<div class="tdv-kpi-value">{nilai}<small>{satuan}</small></div>'
            f'<div class="tdv-kpi-sub {kelas}">{sub}</div></div>')


def footer():
    return ('<div class="tdv-footer"><span>TAMBAH DAYA VIRTUAL · UNS Innovation Hackathon 2026 · '
            'Sub-tema A: energi terbarukan dan penyimpanan</span>'
            '<span>Status: tahap konsep (TKT 3). Angka simulasi bukan kinerja alat.</span></div>')


# ---------------------------------------------------------------------------
# Diagram panel hidup (untuk putar ulang)
# ---------------------------------------------------------------------------
def _durasi_alir(arus):
    """Makin besar arus, makin cepat animasi aliran."""
    return max(0.35, 2.2 - arus / 18)


def _saklar(x, y, tertutup, warna):
    """Simbol relay: dua titik dan tuas."""
    ujung = (x + 26, y) if tertutup else (x + 22, y - 11)
    return (f'<circle cx="{x}" cy="{y}" r="3" fill="{warna}"/><circle cx="{x + 28}" cy="{y}" r="3" fill="{warna}"/>'
            f'<line x1="{x}" y1="{y}" x2="{ujung[0]}" y2="{ujung[1]}" stroke="{warna}" stroke-width="2.5" '
            f'stroke-linecap="round"/>')


def svg_panel(arus, in_mcb, trip, daftar_alat, aktif, alat_baterai=None, baterai_on=False, nama=None):
    """Diagram satu garis panel: PLN -> MCB -> sensor -> busbar -> alat; baterai -> alat yang dipindah.
    daftar_alat: kode alat; aktif: set kode alat yang diminta menyala."""
    nama = nama or (lambda k: k)
    n = max(len(daftar_alat), 1)
    jarak = 58
    tinggi = max(250, 50 + jarak * n)
    y_alat = [40 + jarak * i + 10 for i in range(n)]
    cy = (y_alat[0] + y_alat[-1]) / 2
    rasio = arus / in_mcb if in_mcb else 0
    if trip:
        w_mcb, st_mcb = "#6B7280", "TRIP"
    elif rasio > 1:
        w_mcb, st_mcb = MERAH, f"{rasio * 100:.0f}%"
    elif rasio > 0.9:
        w_mcb, st_mcb = KUNING, f"{rasio * 100:.0f}%"
    else:
        w_mcb, st_mcb = HIJAU, f"{rasio * 100:.0f}%"
    ada_arus = arus > 0.05 and not trip
    w_garis = BIRU if ada_arus else ABU
    dur = _durasi_alir(arus)
    kelas = 'class="flow"' if ada_arus else ""
    anim = f'style="animation-duration:{dur:.2f}s"'

    s = [f'<svg class="tdv-flowsvg" viewBox="0 0 800 {tinggi}" width="100%" xmlns="http://www.w3.org/2000/svg" '
         'font-family="sans-serif">']
    # PLN
    s.append(f'<rect x="10" y="{cy - 32}" width="78" height="64" rx="10" fill="#F0F3F7" stroke="#C9D1DB"/>')
    s.append(f'<g transform="translate(37 {cy - 26})">{ikon("tower", 24, NAVY)}</g>')
    s.append(f'<text x="49" y="{cy + 18}" text-anchor="middle" font-size="11" font-weight="700" fill="{NAVY}">PLN</text>')
    # PLN -> MCB
    s.append(f'<line x1="88" y1="{cy}" x2="135" y2="{cy}" stroke="{w_garis}" stroke-width="4" {kelas} {anim}/>')
    # MCB
    s.append(f'<rect x="135" y="{cy - 40}" width="84" height="80" rx="10" fill="#fff" stroke="{w_mcb}" stroke-width="3"/>')
    s.append(f'<text x="177" y="{cy - 20}" text-anchor="middle" font-size="11" font-weight="700" fill="{TEKS2}">MCB {in_mcb:.0f} A</text>')
    s.append(f'<text x="177" y="{cy + 4}" text-anchor="middle" font-size="18" font-weight="800" fill="{w_mcb}">{st_mcb}</text>')
    s.append(f'<text x="177" y="{cy + 26}" text-anchor="middle" font-size="12" fill="{NAVY}">{arus:.1f} A</text>')
    # MCB -> sensor
    s.append(f'<line x1="219" y1="{cy}" x2="290" y2="{cy}" stroke="{w_garis}" stroke-width="4" {kelas} {anim}/>')
    s.append(f'<circle cx="255" cy="{cy}" r="13" fill="none" stroke="{KUNING}" stroke-width="3"/>')
    s.append(f'<text x="255" y="{cy + 30}" text-anchor="middle" font-size="10" fill="{TEKS2}">Sensor CT</text>')
    # ESP32
    s.append(f'<line x1="255" y1="{cy - 13}" x2="255" y2="{cy - 46}" stroke="{KUNING}" stroke-width="1.5" stroke-dasharray="3 3"/>')
    s.append(f'<rect x="215" y="{cy - 82}" width="80" height="36" rx="8" fill="#FFF8E8" stroke="{KUNING}"/>')
    s.append(f'<text x="255" y="{cy - 66}" text-anchor="middle" font-size="10" font-weight="700" fill="#7A4F00">ESP32</text>')
    s.append(f'<text x="255" y="{cy - 53}" text-anchor="middle" font-size="9" fill="#7A4F00">NILM + kendali</text>')
    # busbar
    s.append(f'<line x1="290" y1="{cy}" x2="330" y2="{cy}" stroke="{w_garis}" stroke-width="4" {kelas} {anim}/>')
    s.append(f'<line x1="330" y1="{y_alat[0]}" x2="330" y2="{y_alat[-1]}" stroke="{w_garis}" stroke-width="6" stroke-linecap="round"/>')

    for kode, y in zip(daftar_alat, y_alat):
        diminta = kode in aktif
        dipindah = baterai_on and kode == alat_baterai and diminta
        dari_pln = diminta and not dipindah and not trip
        w = BIRU if dari_pln else ABU
        k = 'class="flow"' if dari_pln else ""
        s.append(f'<line x1="330" y1="{y}" x2="400" y2="{y}" stroke="{w}" stroke-width="3" {k} {anim}/>')
        s.append(_saklar(400, y, dari_pln, w))
        s.append(f'<line x1="428" y1="{y}" x2="470" y2="{y}" stroke="{w}" stroke-width="3" {k} {anim}/>')
        if dipindah:
            isi, garis, status, w_st = "#E3F4EA", HIJAU, "DIPASOK BATERAI", HIJAU
        elif diminta and trip:
            isi, garis, status, w_st = "#F3F4F6", "#9CA3AF", "PADAM", "#6B7280"
        elif diminta:
            isi, garis, status, w_st = "#E8EFF7", BIRU, "MENYALA", BIRU
        else:
            isi, garis, status, w_st = "#fff", "#DCE2EA", "MATI", "#9CA3AF"
        s.append(f'<rect x="470" y="{y - 22}" width="200" height="44" rx="9" fill="{isi}" stroke="{garis}" stroke-width="1.6"/>')
        s.append(f'<g transform="translate(480 {y - 9})">{ikon("plug", 18, w_st)}</g>')
        s.append(f'<text x="506" y="{y - 3}" font-size="12" font-weight="700" fill="{NAVY}">{nama(kode)}</text>')
        s.append(f'<text x="506" y="{y + 12}" font-size="9.5" font-weight="700" fill="{w_st}" '
                 f'letter-spacing=".5">{status}</text>')
        if kode == alat_baterai:
            wb = HIJAU if dipindah else ABU
            kb = 'class="flow"' if dipindah else ""
            s.append(f'<line x1="670" y1="{y}" x2="712" y2="{y}" stroke="{wb}" stroke-width="3" {kb} '
                     'style="animation-duration:.9s;animation-direction:reverse"/>')
            s.append(f'<rect x="712" y="{y - 26}" width="80" height="52" rx="9" fill="{"#E3F4EA" if dipindah else "#F7F9FC"}" '
                     f'stroke="{wb}" stroke-width="1.6"/>')
            s.append(f'<g transform="translate(740 {y - 21})">{ikon("battery", 22, HIJAU if dipindah else "#9CA3AF")}</g>')
            s.append(f'<text x="752" y="{y + 14}" text-anchor="middle" font-size="9.5" font-weight="700" '
                     f'fill="{HIJAU if dipindah else "#9CA3AF"}">{"AKTIF" if dipindah else "SIAGA"}</text>')
    s.append("</svg>")
    return "".join(s)


def svg_gauge(nilai, maks, batas, satuan, label):
    """Gauge setengah lingkaran. batas = garis nominal."""
    f = max(0.0, min(nilai / maks, 1.0)) if maks else 0
    fb = max(0.0, min(batas / maks, 1.0)) if maks else 0
    warna = MERAH if nilai > batas else (KUNING if nilai > 0.9 * batas else HIJAU)
    busur = "M 20 100 A 80 80 0 0 1 180 100"
    xb = 100 - 80 * math.cos(math.pi * fb)
    yb = 100 - 80 * math.sin(math.pi * fb)
    xi = 100 - 92 * math.cos(math.pi * fb)
    yi = 100 - 92 * math.sin(math.pi * fb)
    return f"""
<svg viewBox="0 0 200 130" width="100%" style="max-width:260px;display:block;margin:auto"
     xmlns="http://www.w3.org/2000/svg" font-family="sans-serif">
  <path d="{busur}" fill="none" stroke="#EDF0F4" stroke-width="16" stroke-linecap="round"/>
  <path d="{busur}" fill="none" stroke="{warna}" stroke-width="16" stroke-linecap="round"
        pathLength="100" stroke-dasharray="{f * 100:.1f} 100" style="transition:stroke-dasharray .4s"/>
  <line x1="{xb:.1f}" y1="{yb:.1f}" x2="{xi:.1f}" y2="{yi:.1f}" stroke="{NAVY}" stroke-width="2.5"/>
  <text x="100" y="88" text-anchor="middle" font-size="28" font-weight="800" fill="{NAVY}">{nilai:.1f}</text>
  <text x="100" y="106" text-anchor="middle" font-size="11" fill="{TEKS2}">{satuan} · {label}</text>
  <text x="20" y="124" text-anchor="middle" font-size="9" fill="{TEKS2}">0</text>
  <text x="180" y="124" text-anchor="middle" font-size="9" fill="{TEKS2}">{maks:.0f}</text>
</svg>"""


def bar_progres(nilai, maks, tanda, warna, kiri, kanan):
    lebar = max(0.0, min(nilai / maks, 1.0)) * 100 if maks else 0
    pos = max(0.0, min(tanda / maks, 1.0)) * 100 if maks else 0
    return (f'<div class="tdv-bar"><div class="isi" style="width:{lebar:.1f}%;background:{warna}"></div>'
            f'<div class="tanda" style="left:{pos:.1f}%"></div></div>'
            f'<div class="tdv-bar-ket"><span>{kiri}</span><span>{kanan}</span></div>')
