"""Dasbor TAMBAH DAYA VIRTUAL (Streamlit).

Jalankan:  streamlit run dashboard/app.py
Sumber data: CSV (contoh simulasi di data/sample, atau unggah CSV hasil panel uji).
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from logika import (
    IN_MCB, KOLOM_WAJIB, TEGANGAN, THETA_AMAN, THETA_TRIP,
    durasi_baterai_menit, energi_baterai_kwh, kejadian_trip, kolom_hilang, log_aksi, muat,
    nama_aksi, nama_alat, segmen_alat, segmen_biner, tambahan_daya_va, waktu_trip_pertama,
)
from simulator import rencana_kendali, simulasikan, tabel_bawaan
from tampilan import (
    CSS, NAVY, banner, bar_progres, brand_sidebar, footer, ikon, kartu, svg_gauge, svg_panel,
)

ROOT = Path(__file__).resolve().parents[1]
CONTOH = ROOT / "data" / "sample" / "pengukuran_sim.csv"

# Palet warna (konsisten di semua grafik)
WARNA_TANPA = "#B4413C"     # skenario tanpa kendali
WARNA_KENDALI = "#1F4E79"   # skenario dengan kendali
WARNA_BATAS = "#5B6573"     # garis batas MCB
WARNA_AMAN = "#C98A12"      # ambang tindakan
WARNA_BATERAI = "#2E7D5B"   # periode baterai aktif
LABEL_TANPA = "Tanpa kendali"
LABEL_KENDALI = "Dengan kendali"

alt.data_transformers.disable_max_rows()

st.set_page_config(
    page_title="Dasbor TAMBAH DAYA VIRTUAL",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Format angka (gaya Indonesia: titik ribuan, koma desimal)
# ---------------------------------------------------------------------------
def fmt(x, des=1):
    s = f"{x:,.{des}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def jam(t):
    return pd.Timestamp(t).strftime("%H:%M:%S") if t is not None else "–"


@st.cache_data(show_spinner=False)
def muat_cache(sumber):
    return muat(sumber)


# ---------------------------------------------------------------------------
# Sidebar: sumber data dan parameter
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(brand_sidebar(), unsafe_allow_html=True)
    st.markdown("### Sumber data")
    unggah = st.file_uploader(
        "Unggah CSV pengukuran", type="csv",
        help="Kosongkan untuk memakai data contoh simulasi.",
    )
    with st.expander("Format CSV yang diterima"):
        st.markdown(
            "Kolom wajib: " + ", ".join(f"`{k}`" for k in KOLOM_WAJIB) + ".\n\n"
            "Kolom opsional: `theta_tanpa_kendali`, `theta_kendali`, `baterai_aktif`, `aksi`, "
            "`alat_aktif` (dipisah `|`), `mcb_trip_tanpa_kendali`, `mcb_trip_kendali`, "
            "`tegangan`, `id_perangkat`.\n\nRincian: `data/README.md`."
        )

try:
    df = muat_cache(unggah if unggah is not None else CONTOH)
except Exception as e:  # noqa: BLE001 - tampilkan galat apa pun ke pengguna
    st.error(f"Berkas tidak dapat dibaca sebagai CSV pengukuran: {e}")
    st.stop()

hilang = kolom_hilang(df)
if hilang:
    st.error("Kolom wajib tidak ditemukan: " + ", ".join(f"`{k}`" for k in hilang)
             + ". Lihat panduan format di panel kiri.")
    st.stop()
if df.empty:
    st.error("Berkas tidak berisi baris data.")
    st.stop()

simulasi = unggah is None
tegangan_data = float(df["tegangan"].mean()) if "tegangan" in df.columns else TEGANGAN
perangkat = ", ".join(map(str, df["id_perangkat"].unique())) if "id_perangkat" in df.columns else "–"
t0, t1 = df["waktu"].iloc[0], df["waktu"].iloc[-1]
interval = df["waktu"].diff().median()

with st.sidebar:
    st.markdown("### Parameter MCB")
    in_mcb = st.number_input("Arus nominal MCB (A)", value=float(IN_MCB), min_value=1.0, step=1.0,
                             help="Arus pengenal MCB pada panel. Menentukan batas daya terpasang.")
    tegangan = st.number_input("Tegangan nominal (V)", value=round(tegangan_data, 1), min_value=100.0,
                               step=1.0, help="Bawaan: rata-rata kolom `tegangan` pada data.")
    st.caption(f"Daya terpasang: **{fmt(in_mcb * tegangan, 0)} VA**")

    with st.expander("Ambang model termal (ilustratif)"):
        theta_trip = st.number_input("Ambang trip θ", value=THETA_TRIP, min_value=0.1, step=0.05,
                                     help="Hanya untuk garis acuan grafik. Ganti sesuai datasheet MCB.")
        theta_aman = st.number_input("Ambang tindakan θ", value=THETA_AMAN, min_value=0.1, step=0.05,
                                     help="Batas saat sistem mulai mengambil tindakan.")

    st.markdown("### Baterai")
    daya_alat = st.number_input("Daya alat yang dipindah (W)", value=2000.0, min_value=0.0, step=100.0,
                                help="Dipakai untuk memperkirakan energi yang dipasok baterai.")

    st.markdown("### Informasi data")
    st.markdown(
        f"""
        | | |
        |---|---|
        | Perangkat | {perangkat} |
        | Tanggal | {t0:%d-%m-%Y} |
        | Rentang | {t0:%H:%M} – {t1:%H:%M} |
        | Jumlah baris | {fmt(len(df), 0)} |
        | Interval | {fmt(interval.total_seconds(), 0) if pd.notna(interval) else '–'} detik |
        """
    )

# ---------------------------------------------------------------------------
# Hitungan utama
# ---------------------------------------------------------------------------
trip_tanpa = kejadian_trip(df, "mcb_trip_tanpa_kendali")
trip_kendali = kejadian_trip(df, "mcb_trip_kendali")
wt_trip_tanpa = waktu_trip_pertama(df, "mcb_trip_tanpa_kendali")
wt_trip_kendali = waktu_trip_pertama(df, "mcb_trip_kendali")
td = tambahan_daya_va(df, tegangan=tegangan, in_mcb=in_mcb)
energi = energi_baterai_kwh(df, daya_alat_w=daya_alat)
durasi_bat = durasi_baterai_menit(df)
puncak_tanpa = float(df["arus_tanpa_kendali"].max())
puncak_kendali = float(df["arus_kendali"].max())
aksi = log_aksi(df)

# ---------------------------------------------------------------------------
# Kepala halaman
# ---------------------------------------------------------------------------
nama_berkas = CONTOH.name if simulasi else unggah.name
st.markdown(banner(simulasi, nama_berkas, perangkat, f"{t0:%d-%m-%Y}, {t0:%H:%M} – {t1:%H:%M}"),
            unsafe_allow_html=True)

if simulasi:
    st.warning(
        "**Data simulasi.** Angka di halaman ini berasal dari model ilustratif untuk menguji dasbor, "
        "bukan hasil pengukuran. Unggah CSV dari panel uji melalui panel kiri untuk melihat data nyata.",
        icon="⚠️",
    )


# ---------------------------------------------------------------------------
# Indikator utama
# ---------------------------------------------------------------------------
def di_atas_nominal_menit(kolom):
    dt = df["waktu"].diff().dt.total_seconds().fillna(0)
    return float(dt[df[kolom] > in_mcb].sum() / 60)


def status_arus(kolom):
    puncak = float(df[kolom].max())
    persen = f"{fmt(puncak / in_mcb * 100, 0)}% nominal"
    if puncak > in_mcb:
        return f"{persen} · {fmt(di_atas_nominal_menit(kolom), 0)} menit di atasnya", "bad"
    if puncak > 0.9 * in_mcb:
        return f"{persen} · mendekati batas", "warn"
    return f"{persen} · aman", "ok"


s1, k1 = status_arus("arus_tanpa_kendali")
s2, k2 = status_arus("arus_kendali")
kartu_html = "".join([
    kartu("Arus puncak · tanpa kendali", fmt(puncak_tanpa), "A", s1, k1, "trend"),
    kartu("Arus puncak · dengan kendali", fmt(puncak_kendali), "A", s2, k2, "gauge"),
    kartu("MCB turun (trip)", f"{trip_tanpa} → {trip_kendali}", "kali",
          "tanpa kendali → dengan kendali", "ok" if trip_kendali == 0 else "bad", "shield"),
    kartu("Tambahan daya efektif", fmt(td["tambahan_va"], 0), "VA",
          "batal: masih ada trip dengan kendali" if td["ada_trip"]
          else f"di atas daya terpasang {fmt(td['terpasang_va'], 0)} VA",
          "bad" if td["ada_trip"] else "ok", "bolt"),
    kartu("Energi dari baterai", fmt(energi, 2), "kWh",
          f"baterai aktif {fmt(durasi_bat, 0)} menit", "", "battery"),
])
st.markdown(f'<div class="tdv-kpis">{kartu_html}</div>', unsafe_allow_html=True)

if trip_kendali == 0 and trip_tanpa > 0:
    st.success(
        f"**Kendali berhasil mencegah MCB turun.** Tanpa kendali, MCB turun pada pukul "
        f"{jam(wt_trip_tanpa)}. Dengan kendali, MCB tetap menyala sepanjang periode "
        f"dan {len(aksi)} aksi kendali dijalankan.", icon="✅")
elif trip_kendali > 0:
    st.error(
        f"**MCB tetap turun walaupun dengan kendali** (pertama pukul {jam(wt_trip_kendali)}). "
        "Periksa aturan kendali atau kapasitas baterai.", icon="⛔")
else:
    st.info("MCB tidak turun pada kedua skenario selama periode data ini.", icon="ℹ️")

# ---------------------------------------------------------------------------
# Komponen grafik
# ---------------------------------------------------------------------------
def sumbu_x(kolom="waktu"):
    return alt.X(f"{kolom}:T", title=None, axis=alt.Axis(format="%H:%M", labelColor="#4A5563",
                                                          tickColor="#C9D1DB", domainColor="#C9D1DB"))


def gaya(chart, tinggi=320):
    if tinggi is not None:
        chart = chart.properties(height=tinggi)
    return (chart
            .configure_view(stroke=None)
            .configure_axis(gridColor="#EDF0F4", labelFontSize=11, titleFontSize=12,
                            titleColor="#4A5563", titleFontWeight="normal")
            .configure_legend(orient="top", title=None, labelFontSize=12, symbolStrokeWidth=3)
            .configure_text(font="sans-serif"))


def lapisan_baterai(d, y_maks):
    seg = segmen_biner(d, "baterai_aktif")
    if seg.empty:
        return []
    seg["y"], seg["y2"] = 0, y_maks
    return [alt.Chart(seg).mark_rect(color=WARNA_BATERAI, opacity=0.08).encode(
        x="mulai:T", x2="selesai:T",
        tooltip=[alt.Tooltip("mulai:T", title="Baterai aktif dari", format="%H:%M:%S"),
                 alt.Tooltip("selesai:T", title="sampai", format="%H:%M:%S")])]


def lapisan_aksi(rentang, y_maks):
    a = aksi[(aksi["waktu"] >= rentang[0]) & (aksi["waktu"] <= rentang[1])].copy()
    if a.empty:
        return []
    a["keterangan"] = a["aksi"].map(nama_aksi)
    a["y"] = y_maks
    garis = alt.Chart(a).mark_rule(color=WARNA_AMAN, strokeWidth=1.5, strokeDash=[2, 2]).encode(
        x="waktu:T",
        tooltip=[alt.Tooltip("waktu:T", title="Waktu", format="%H:%M:%S"),
                 alt.Tooltip("keterangan:N", title="Aksi")])
    teks = alt.Chart(a).mark_text(align="left", dx=4, dy=8, fontSize=11, color="#7A5200").encode(
        x="waktu:T", y=alt.Y("y:Q"), text="keterangan:N")
    return [garis, teks]


def lapisan_trip(d, kolom_trip, kolom_y):
    w = waktu_trip_pertama(d, kolom_trip)
    if w is None:
        return []
    baris = d.loc[d["waktu"] == w]
    titik = pd.DataFrame({"waktu": [w], "y": [float(baris[kolom_y].iloc[0]) if len(baris) else 0.0],
                          "ket": ["MCB turun"]})
    return [
        alt.Chart(titik).mark_point(shape="cross", size=140, color=WARNA_TANPA, strokeWidth=3).encode(
            x="waktu:T", y="y:Q",
            tooltip=[alt.Tooltip("waktu:T", title="MCB turun", format="%H:%M:%S")]),
        alt.Chart(titik).mark_text(align="left", dx=8, dy=-8, color=WARNA_TANPA, fontWeight="bold",
                                   fontSize=11).encode(x="waktu:T", y="y:Q", text="ket:N"),
    ]


def grafik_dua_skenario(d, rentang, kol_tanpa, kol_kendali, judul_y, satuan, garis_acuan, kolom_trip):
    """Grafik garis dua skenario + garis acuan + penanda aksi, trip, dan periode baterai."""
    lebar = d[["waktu", kol_tanpa, kol_kendali]].rename(
        columns={kol_tanpa: LABEL_TANPA, kol_kendali: LABEL_KENDALI})
    panjang = lebar.melt("waktu", var_name="Skenario", value_name="nilai")
    y_maks = max(float(panjang["nilai"].max()), max(v for v, *_ in garis_acuan)) * 1.12

    warna = alt.Color("Skenario:N", scale=alt.Scale(domain=[LABEL_TANPA, LABEL_KENDALI],
                                                    range=[WARNA_TANPA, WARNA_KENDALI]))
    sumbu_y = alt.Y("nilai:Q", title=judul_y, scale=alt.Scale(domain=[0, y_maks], nice=False))
    garis = alt.Chart(panjang).mark_line(strokeWidth=2.2, interpolate="monotone").encode(
        x=sumbu_x(), y=sumbu_y, color=warna)

    acuan = []
    for nilai, label, warna_acuan in garis_acuan:
        g = pd.DataFrame({"y": [nilai], "label": [label], "waktu": [rentang[0]]})
        acuan += [
            alt.Chart(g).mark_rule(color=warna_acuan, strokeDash=[6, 4], strokeWidth=1.4).encode(y="y:Q"),
            alt.Chart(g).mark_text(align="left", dx=4, dy=-7, color=warna_acuan, fontSize=11).encode(
                x="waktu:T", y="y:Q", text="label:N"),
        ]

    sorot = alt.selection_point(fields=["waktu"], nearest=True, on="pointerover",
                                empty=False, clear="pointerout")
    penanda = alt.Chart(lebar).mark_rule(color="#8792A2", strokeWidth=1).encode(
        x="waktu:T",
        opacity=alt.condition(sorot, alt.value(0.9), alt.value(0)),
        tooltip=[alt.Tooltip("waktu:T", title="Waktu", format="%H:%M:%S"),
                 alt.Tooltip(f"{LABEL_TANPA}:Q", title=f"{LABEL_TANPA} ({satuan})", format=".2f"),
                 alt.Tooltip(f"{LABEL_KENDALI}:Q", title=f"{LABEL_KENDALI} ({satuan})", format=".2f")],
    ).add_params(sorot)
    titik = garis.mark_point(filled=True, size=45).encode(
        opacity=alt.condition(sorot, alt.value(1), alt.value(0)))

    lapisan = (lapisan_baterai(d, y_maks) + [garis] + acuan + lapisan_aksi(rentang, y_maks)
               + lapisan_trip(d, kolom_trip, kol_tanpa) + [penanda, titik])
    return gaya(alt.layer(*lapisan))


# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------
(tab_putar, tab_pantau, tab_alat, tab_sim, tab_validasi, tab_data, tab_tentang) = st.tabs([
    ":material/play_circle: Putar ulang panel", ":material/show_chart: Grafik arus & MCB",
    ":material/view_timeline: Alat & kendali", ":material/tune: Simulator apa-jika",
    ":material/fact_check: Validasi", ":material/table_chart: Data", ":material/info: Tentang sistem"])

# ---------------------------------------------------------------------------
# Putar ulang panel (mode demo)
# ---------------------------------------------------------------------------
KECEPATAN = {"Lambat": 2, "Normal": 6, "Cepat": 20}
waktu_py = [t.to_pydatetime() for t in df["waktu"]]
waktu_np = df["waktu"].to_numpy()
n_baris = len(df)
_seg_urut = segmen_alat(df).sort_values("mulai")
daftar_alat = list(dict.fromkeys(_seg_urut["alat"]))
alat_baterai = next((k[: -len("_ke_baterai")] for k in aksi["aksi"] if k.endswith("_ke_baterai")), None)
if alat_baterai and alat_baterai not in daftar_alat:
    daftar_alat.append(alat_baterai)

ss = st.session_state
ss.setdefault("main", False)
if "t_putar" not in ss or not (waktu_py[0] <= ss.t_putar <= waktu_py[-1]):
    ss.t_putar = waktu_py[0]


def peristiwa(skenario_kendali):
    """Daftar (waktu, teks, jenis) untuk skenario terpilih."""
    ev = []
    if skenario_kendali:
        ev += [(r.waktu, nama_aksi(r.aksi), "aksi") for r in aksi.itertuples()]
        w = waktu_trip_pertama(df, "mcb_trip_kendali")
    else:
        w = waktu_trip_pertama(df, "mcb_trip_tanpa_kendali")
    if w is not None:
        ev.append((w, "MCB turun (trip)", "trip"))
    kol = "arus_kendali" if skenario_kendali else "arus_tanpa_kendali"
    lebih = df[kol] > in_mcb
    mulai = df.loc[lebih & ~lebih.shift(fill_value=False), "waktu"]
    ev += [(t, f"Arus melewati nominal MCB ({fmt(in_mcb, 0)} A)", "lebih") for t in mulai]
    return sorted(ev, key=lambda e: e[0])


@st.fragment(run_every=0.5 if ss.main else None)
def putar_ulang():
    idx = int(np.clip(np.searchsorted(waktu_np, np.datetime64(ss.t_putar), side="right") - 1, 0, n_baris - 1))
    if ss.main:
        idx = min(idx + KECEPATAN.get(ss.get("kecepatan") or "Normal", 6), n_baris - 1)
        ss.t_putar = waktu_py[idx]
        if idx >= n_baris - 1:
            ss.main = False
            st.rerun()

    k4, k5 = st.columns(2)
    k1, k2, k3, _ = st.columns([1.2, 0.6, 2, 2.2], vertical_alignment="bottom")
    if k1.button(":material/pause: Jeda" if ss.main else ":material/play_arrow: Putar", type="primary",
                 use_container_width=True):
        if not ss.main and idx >= n_baris - 1:
            ss.t_putar = waktu_py[0]
        ss.main = not ss.main
        st.rerun()
    if k2.button(":material/first_page:", help="Kembali ke awal", use_container_width=True):
        ss.t_putar, ss.main = waktu_py[0], False
        st.rerun()
    skenario = k5.segmented_control("Skenario", [LABEL_KENDALI, LABEL_TANPA], default=LABEL_KENDALI,
                                    key="skenario_putar") or LABEL_KENDALI
    pakai_kendali = skenario == LABEL_KENDALI
    ev = peristiwa(pakai_kendali)
    berikut = next((e for e in ev if e[0] > pd.Timestamp(ss.t_putar)), None)
    if k3.button(":material/skip_next: Peristiwa berikutnya", use_container_width=True, disabled=berikut is None,
                 help="Lompat ke aksi kendali, beban lebih, atau MCB turun berikutnya."):
        ss.t_putar = berikut[0].to_pydatetime()
        st.rerun()
    k4.segmented_control("Kecepatan", list(KECEPATAN), default="Normal", key="kecepatan")

    st.slider("Waktu", min_value=waktu_py[0], max_value=waktu_py[-1], key="t_putar",
              step=(waktu_py[1] - waktu_py[0]) if n_baris > 1 else None, format="HH:mm:ss",
              label_visibility="collapsed")
    idx = int(np.clip(np.searchsorted(waktu_np, np.datetime64(ss.t_putar), side="right") - 1, 0, n_baris - 1))
    r = df.iloc[idx]

    akh = "kendali" if pakai_kendali else "tanpa_kendali"
    arus = float(r[f"arus_{akh}"])
    theta = float(r[f"theta_{akh}"]) if f"theta_{akh}" in df.columns else None
    trip = bool(r.get(f"mcb_trip_{akh}", 0) == 1)
    bat_on = pakai_kendali and bool(r.get("baterai_aktif", 0) == 1)
    aktif = set(filter(None, str(r.get("alat_aktif", "")).split("|")))

    if trip:
        chip = f'<span class="tdv-chip mati">{ikon("alert", 14)} MCB TURUN · LISTRIK PADAM</span>'
    elif arus > in_mcb or (theta is not None and theta >= theta_aman):
        chip = '<span class="tdv-chip bad"><span class="tdv-dot"></span>BEBAN LEBIH</span>'
    elif arus > 0.9 * in_mcb:
        chip = '<span class="tdv-chip warn"><span class="tdv-dot"></span>WASPADA</span>'
    else:
        chip = '<span class="tdv-chip ok"><span class="tdv-dot"></span>NORMAL</span>'
    chip_bat = (f'<span class="tdv-chip ok">{ikon("battery", 14)} BATERAI AKTIF</span>' if bat_on else "")
    menit = (pd.Timestamp(ss.t_putar) - t0).total_seconds() / 60
    total_menit = (t1 - t0).total_seconds() / 60
    persen = idx / max(n_baris - 1, 1) * 100
    st.markdown(
        f'<div class="tdv-live"><div class="tdv-jam">{pd.Timestamp(ss.t_putar):%H:%M:%S}</div>{chip}{chip_bat}'
        f'<div class="tdv-progress"><div style="width:{persen:.1f}%"></div></div>'
        f'<span style="font-size:.8rem;color:#5B6573">menit {fmt(menit, 0)} dari {fmt(total_menit, 0)}'
        f' · {skenario.lower()}</span></div>', unsafe_allow_html=True)

    kiri, kanan = st.columns([2.6, 1], gap="medium")
    with kiri:
        st.markdown(
            f'<div class="tdv-card"><div class="tdv-card-title">{ikon("cpu", 14)} Diagram panel saat ini</div>'
            + svg_panel(arus, in_mcb, trip, daftar_alat, aktif, alat_baterai, bat_on, nama_alat)
            + "</div>", unsafe_allow_html=True)
    with kanan:
        st.markdown(
            f'<div class="tdv-card"><div class="tdv-card-title">{ikon("gauge", 14)} Arus dari PLN</div>'
            + svg_gauge(arus, in_mcb * 1.5, in_mcb, "A", f"nominal {fmt(in_mcb, 0)} A") + "</div>",
            unsafe_allow_html=True)
        if theta is not None:
            w_th = WARNA_TANPA if theta >= theta_aman else (WARNA_AMAN if theta >= 1 else WARNA_BATERAI)
            st.markdown(
                f'<div class="tdv-card"><div class="tdv-card-title">{ikon("trend", 14)} Pemanasan MCB θ</div>'
                f'<div class="tdv-kpi-value" style="margin:0">{fmt(theta, 2)}'
                f'<small>/ {fmt(theta_trip, 2)} trip</small></div>'
                + bar_progres(theta, theta_trip, theta_aman, w_th, "0", f"ambang tindakan {fmt(theta_aman, 2)}")
                + "</div>", unsafe_allow_html=True)

    bawah_kiri, bawah_kanan = st.columns([1.7, 1], gap="medium")
    with bawah_kiri:
        kol = f"arus_{akh}"
        seri = df[["waktu", kol]].rename(columns={kol: "arus"})
        lalu = seri.iloc[: idx + 1]
        warna = WARNA_KENDALI if pakai_kendali else WARNA_TANPA
        sekarang = pd.DataFrame({"waktu": [r["waktu"]], "arus": [arus]})
        batas = pd.DataFrame({"y": [in_mcb]})
        grafik = alt.layer(
            alt.Chart(seri).mark_line(color="#DCE2EA", strokeWidth=2).encode(
                x=sumbu_x(), y=alt.Y("arus:Q", title="Arus (A)")),
            alt.Chart(lalu).mark_area(color=warna, opacity=0.12, interpolate="monotone").encode(
                x="waktu:T", y="arus:Q"),
            alt.Chart(lalu).mark_line(color=warna, strokeWidth=2.2, interpolate="monotone").encode(
                x="waktu:T", y="arus:Q"),
            alt.Chart(batas).mark_rule(color=WARNA_BATAS, strokeDash=[6, 4]).encode(y="y:Q"),
            alt.Chart(sekarang).mark_rule(color=NAVY, strokeWidth=1.5).encode(x="waktu:T"),
            alt.Chart(sekarang).mark_point(filled=True, size=90, color=warna, stroke="white",
                                           strokeWidth=2).encode(x="waktu:T", y="arus:Q"),
        )
        st.altair_chart(gaya(grafik, tinggi=190), use_container_width=True)
    with bawah_kanan:
        items = []
        lalu_ev = [e for e in ev if e[0] <= pd.Timestamp(ss.t_putar)]
        terakhir = lalu_ev[-1] if lalu_ev else None
        for e in ev:
            kelas = "baru" if e is terakhir else ("nanti" if e[0] > pd.Timestamp(ss.t_putar) else "")
            ik = {"aksi": ("switch", WARNA_AMAN), "trip": ("alert", WARNA_TANPA),
                  "lebih": ("trend", WARNA_TANPA)}[e[2]]
            items.append(f'<li class="{kelas}"><span class="t">{e[0]:%H:%M:%S}</span>'
                         f'{ikon(ik[0], 15, ik[1])}<span>{e[1]}</span></li>')
        st.markdown(
            f'<div class="tdv-card"><div class="tdv-card-title">{ikon("wave", 14)} Peristiwa</div>'
            f'<ul class="tdv-events">{"".join(items) or "<li>Tidak ada peristiwa.</li>"}</ul></div>',
            unsafe_allow_html=True)


with tab_putar:
    st.markdown(f'<div class="tdv-section">{ikon("monitor", 18)} Putar ulang kondisi panel</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="tdv-note">Tekan <b>Putar</b> untuk memutar ulang data seperti siaran langsung, atau geser '
        'penggeser waktu. Ganti skenario untuk membandingkan panel dengan dan tanpa kendali.</div>',
        unsafe_allow_html=True)
    putar_ulang()


with tab_pantau:
    c_rentang, c_opsi = st.columns([3, 1])
    with c_rentang:
        rentang = st.slider(
            "Rentang waktu grafik", min_value=t0.to_pydatetime(), max_value=t1.to_pydatetime(),
            value=(t0.to_pydatetime(), t1.to_pydatetime()), format="HH:mm",
            help="Geser kedua ujung untuk memperbesar bagian tertentu.")
    with c_opsi:
        st.write("")
        tampil_theta = st.toggle("Tampilkan model termal", value="theta_kendali" in df.columns,
                                 disabled="theta_kendali" not in df.columns)
    rentang = (pd.Timestamp(rentang[0]), pd.Timestamp(rentang[1]))
    d = df[(df["waktu"] >= rentang[0]) & (df["waktu"] <= rentang[1])]
    if d.empty:
        st.info("Tidak ada data pada rentang waktu ini.")
    else:
        st.markdown('<div class="tdv-section">Arus total dari PLN</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tdv-note">Garis putus-putus abu-abu adalah arus nominal MCB. Garis kuning '
            'menandai aksi kendali; area hijau menandai periode alat dipasok baterai. '
            'Arahkan kursor ke grafik untuk melihat nilai.</div>', unsafe_allow_html=True)
        st.altair_chart(
            grafik_dua_skenario(d, rentang, "arus_tanpa_kendali", "arus_kendali", "Arus (A)", "A",
                                [(in_mcb, f"Nominal MCB {fmt(in_mcb, 0)} A", WARNA_BATAS)],
                                "mcb_trip_tanpa_kendali"),
            use_container_width=True)

        if tampil_theta and {"theta_tanpa_kendali", "theta_kendali"} <= set(d.columns):
            st.markdown('<div class="tdv-section">Pemanasan MCB menurut model termal</div>',
                        unsafe_allow_html=True)
            st.markdown(
                '<div class="tdv-note">θ = 1,0 berarti kondisi tunak pada arus nominal. Ambang trip dan '
                'ambang tindakan bersifat ilustratif dan dapat diubah di panel kiri.</div>',
                unsafe_allow_html=True)
            st.altair_chart(
                grafik_dua_skenario(d, rentang, "theta_tanpa_kendali", "theta_kendali", "Pemanasan θ (relatif)", "",
                                    [(theta_trip, f"Ambang trip {fmt(theta_trip, 2)}", WARNA_TANPA),
                                     (theta_aman, f"Ambang tindakan {fmt(theta_aman, 2)}", WARNA_AMAN)],
                                    "mcb_trip_tanpa_kendali"),
                use_container_width=True)

with tab_alat:
    st.markdown('<div class="tdv-section">Linimasa alat dan status sistem</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tdv-note">Alat yang dikenali menyala setiap saat. '
        + ('Pada data simulasi, daftar alat adalah label skenario, bukan keluaran model NILM.'
           if simulasi else '') + '</div>', unsafe_allow_html=True)

    seg = segmen_alat(df)
    seg["Baris"] = seg["alat"].map(nama_alat)
    seg["Kategori"] = "Alat menyala"
    bat = segmen_biner(df, "baterai_aktif").assign(Baris="Baterai & inverter", Kategori="Baterai aktif")
    trp = segmen_biner(df, "mcb_trip_tanpa_kendali").assign(Baris="MCB (tanpa kendali)",
                                                           Kategori="MCB turun")
    bagian = [b[["Baris", "Kategori", "mulai", "selesai"]] for b in (seg, bat, trp) if not b.empty]
    lini = pd.concat(bagian, ignore_index=True) if bagian else pd.DataFrame()

    if lini.empty:
        st.info("Data tidak memuat kolom `alat_aktif` atau `baterai_aktif`.")
    else:
        lini["Durasi (menit)"] = (lini["selesai"] - lini["mulai"]).dt.total_seconds() / 60
        urutan = list(dict.fromkeys(lini["Baris"]))
        chart = alt.Chart(lini).mark_bar(cornerRadius=3, height=18).encode(
            x=sumbu_x("mulai"), x2="selesai:T",
            y=alt.Y("Baris:N", title=None, sort=urutan, axis=alt.Axis(labelFontSize=12, labelLimit=200)),
            color=alt.Color("Kategori:N", scale=alt.Scale(
                domain=["Alat menyala", "Baterai aktif", "MCB turun"],
                range=[WARNA_KENDALI, WARNA_BATERAI, WARNA_TANPA])),
            tooltip=[alt.Tooltip("Baris:N", title="Komponen"),
                     alt.Tooltip("mulai:T", title="Mulai", format="%H:%M:%S"),
                     alt.Tooltip("selesai:T", title="Selesai", format="%H:%M:%S"),
                     alt.Tooltip("Durasi (menit):Q", format=".1f")])
        lapisan = [chart]
        if len(aksi):
            lapisan.append(alt.Chart(aksi.assign(keterangan=aksi["aksi"].map(nama_aksi)))
                           .mark_rule(color=WARNA_AMAN, strokeWidth=1.5, strokeDash=[2, 2])
                           .encode(x="waktu:T",
                                   tooltip=[alt.Tooltip("waktu:T", title="Waktu", format="%H:%M:%S"),
                                            alt.Tooltip("keterangan:N", title="Aksi")]))
        st.altair_chart(gaya(alt.layer(*lapisan), tinggi=max(140, 42 * len(urutan))),
                        use_container_width=True)

    kiri, kanan = st.columns([3, 2], gap="large")
    with kiri:
        st.markdown('<div class="tdv-section">Log aksi kendali</div>', unsafe_allow_html=True)
        if len(aksi):
            tabel = aksi.assign(Aksi=aksi["aksi"].map(nama_aksi), Kode=aksi["aksi"])[["waktu", "Aksi", "Kode"]]
            st.dataframe(tabel, hide_index=True, use_container_width=True,
                         column_config={"waktu": st.column_config.DatetimeColumn("Waktu", format="HH:mm:ss")})
        else:
            st.info("Belum ada aksi kendali pada data ini.")
    with kanan:
        st.markdown('<div class="tdv-section">Ringkasan pemakaian alat</div>', unsafe_allow_html=True)
        if not seg.empty:
            ringkas = (seg.assign(menit=(seg["selesai"] - seg["mulai"]).dt.total_seconds() / 60)
                       .groupby("Baris", sort=False)["menit"].sum().reset_index())
            st.dataframe(ringkas, hide_index=True, use_container_width=True, column_config={
                "Baris": "Alat",
                "menit": st.column_config.NumberColumn("Total menyala (menit)", format="%.1f")})
        else:
            st.info("Tidak ada data alat.")

with tab_validasi:
    st.markdown('<div class="tdv-section">Perbandingan skenario</div>', unsafe_allow_html=True)
    st.markdown('<div class="tdv-note">Indikator dihitung atas seluruh periode data.</div>',
                unsafe_allow_html=True)

    def theta_maks(kolom):
        return fmt(df[kolom].max(), 3) if kolom in df.columns else "–"

    banding = pd.DataFrame({
        "Indikator": ["Arus puncak (A)", "Lama di atas nominal MCB (menit)", "Pemanasan θ maksimum",
                      "Jumlah MCB turun", "MCB turun pertama"],
        LABEL_TANPA: [fmt(puncak_tanpa, 2), fmt(di_atas_nominal_menit("arus_tanpa_kendali")),
                      theta_maks("theta_tanpa_kendali"), str(trip_tanpa), jam(wt_trip_tanpa)],
        LABEL_KENDALI: [fmt(puncak_kendali, 2), fmt(di_atas_nominal_menit("arus_kendali")),
                        theta_maks("theta_kendali"), str(trip_kendali), jam(wt_trip_kendali)],
    })
    st.dataframe(banding, hide_index=True, use_container_width=True)

    st.markdown('<div class="tdv-section">Perhitungan tambahan daya efektif</div>', unsafe_allow_html=True)
    rinci = pd.DataFrame({
        "Komponen": ["Daya terpasang (nominal MCB × tegangan)", "Beban puncak yang diminta (tanpa kendali)",
                     "Ada MCB turun dengan kendali?", "Tambahan daya efektif"],
        "Nilai": [f"{fmt(td['terpasang_va'], 0)} VA", f"{fmt(td['beban_diminta_va'], 0)} VA",
                  "Ya" if td["ada_trip"] else "Tidak", f"{fmt(td['tambahan_va'], 0)} VA"],
    })
    st.dataframe(rinci, hide_index=True, use_container_width=True)

    with st.expander("Metode perhitungan"):
        st.markdown(
            f"""
            - **MCB turun** dihitung sebagai jumlah perpindahan status trip dari 0 ke 1.
            - **Tambahan daya efektif** = beban puncak yang diminta − daya terpasang, **hanya bila** MCB
              tidak turun pada skenario dengan kendali. Bila masih ada trip, nilainya 0.
            - **Energi dari baterai** = lama baterai aktif × daya alat yang dipindah
              ({fmt(daya_alat, 0)} W, dapat diubah di panel kiri).
            - Parameter model termal MCB bersifat ilustratif; ganti dengan hasil uji waktu trip MCB
              (IEC 60898-1) sebelum mengutip angka.
            """
        )
    if simulasi:
        st.info("Angka pada data simulasi hanya untuk menguji dasbor. Hasil sebenarnya harus berasal "
                "dari panel uji dan UMKM nyata.")

with tab_data:
    st.markdown('<div class="tdv-section">Data pengukuran</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="tdv-note">{fmt(len(df), 0)} baris · {len(df.columns)} kolom</div>',
                unsafe_allow_html=True)
    st.dataframe(
        df, hide_index=True, use_container_width=True, height=460,
        column_config={"waktu": st.column_config.DatetimeColumn("waktu", format="DD-MM-YYYY HH:mm:ss")})
    st.download_button("Unduh CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"tambah_daya_virtual_{t0:%Y%m%d}.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# Simulator apa-jika
# ---------------------------------------------------------------------------
with tab_sim:
    st.markdown(f'<div class="tdv-section">{ikon("switch", 18)} '
                'Simulator apa-jika: bolehkah UMKM menambah mesin?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tdv-note">Atur alat yang menyala dan parameter baterai. Dasbor menghitung apakah MCB '
        'akan turun, lalu apa yang dilakukan sistem kendali. Model termal sama dengan simulasi '
        '(ilustratif, bukan karakteristik MCB tertentu).</div>', unsafe_allow_html=True)

    kol_in, kol_out = st.columns([1.4, 2], gap="large")
    with kol_in:
        st.markdown(f'<div class="tdv-card-title">{ikon("plug", 14)} Alat di bengkel</div>',
                    unsafe_allow_html=True)
        alat_sim = st.data_editor(
            tabel_bawaan(), num_rows="dynamic", hide_index=True, use_container_width=True, key="alat_sim",
            column_config={
                "Alat": st.column_config.TextColumn(required=True),
                "Arus (A)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.1,
                                                          format="%.1f", required=True),
                "Menyala": st.column_config.CheckboxColumn(default=True),
                "Boleh ke baterai": st.column_config.CheckboxColumn(
                    default=False, help="Alat yang boleh dipindah ke baterai dan inverter."),
            })
        alat_sim = alat_sim.dropna(subset=["Alat", "Arus (A)"]).fillna({"Menyala": False,
                                                                         "Boleh ke baterai": False})
        st.caption("Klik sel untuk mengubah; baris kosong di bawah untuk menambah mesin baru.")

        st.markdown(f'<div class="tdv-card-title" style="margin-top:.6rem">{ikon("battery", 14)} '
                    'Baterai & inverter</div>', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        kap_wh = b1.number_input("Kapasitas baterai (Wh)", value=3000.0, min_value=0.0, step=100.0,
                                 help="Energi yang dapat dipakai (setelah batas kedalaman pengosongan).")
        inv_w = b2.number_input("Daya inverter (W)", value=2500.0, min_value=0.0, step=100.0)

        with st.expander("Kondisi awal & model termal"):
            theta0 = st.slider("Pemanasan awal θ₀", 0.0, 1.5, 0.7, 0.05,
                               help="0 = MCB dingin; 1 = tunak pada arus nominal.")
            tau = st.number_input("Konstanta waktu τ (menit)", value=20.0, min_value=1.0, step=1.0)
            horizon = st.slider("Lama operasi yang disimulasikan (menit)", 30, 240, 90, 10)

    plan = rencana_kendali(alat_sim, in_mcb, tegangan, theta_aman, inv_w)
    lama_bat = kap_wh / plan["daya_baterai_w"] * 60 if plan["daya_baterai_w"] > 0 else 0.0
    sim_a, trip_a = simulasikan(plan["total"], 0.0, 0.0, in_mcb, theta0, tau, theta_trip, horizon)
    sim_b, trip_b = simulasikan(plan["total"], plan["arus_pindah"], lama_bat, in_mcb, theta0, tau,
                                theta_trip, horizon)

    with kol_out:
        persen_total = plan["total"] / in_mcb * 100
        kartu_sim = "".join([
            kartu("Beban total diminta", fmt(plan["total"]), "A",
                  f"{fmt(persen_total, 0)}% nominal · {fmt(plan['total'] * tegangan, 0)} VA",
                  "bad" if plan["total"] > in_mcb else "ok", "factory"),
            kartu("Tanpa kendali", "Turun" if trip_a is not None else "Aman", "",
                  f"MCB turun pada menit ke-{fmt(trip_a, 0)}" if trip_a is not None
                  else f"MCB bertahan {horizon} menit", "bad" if trip_a is not None else "ok", "shield"),
            kartu("Dengan kendali", "Turun" if trip_b is not None else "Aman", "",
                  f"MCB turun pada menit ke-{fmt(trip_b, 0)}" if trip_b is not None
                  else f"arus PLN {fmt(plan['arus_pln'])} A", "bad" if trip_b is not None else "ok", "cpu"),
            kartu("Baterai", fmt(plan["daya_baterai_w"], 0), "W",
                  (f"cukup {fmt(lama_bat, 0)} menit" if plan["daya_baterai_w"] > 0 else "tidak dipakai"),
                  "warn" if 0 < lama_bat < horizon else "", "battery"),
        ])
        st.markdown(f'<div class="tdv-kpis" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">'
                    f'{kartu_sim}</div>', unsafe_allow_html=True)

        dipindah_teks = ", ".join(plan["dipindah"])
        if trip_a is None:
            st.success("**MCB aman tanpa kendali.** Beban ini masih di bawah kemampuan MCB untuk "
                       f"{horizon} menit operasi.", icon="✅")
        elif trip_b is None:
            st.success(f"**Kendali mencegah MCB turun.** Sistem memindahkan **{dipindah_teks}** ke baterai; "
                       f"arus dari PLN turun dari {fmt(plan['total'])} A menjadi {fmt(plan['arus_pln'])} A.",
                       icon="✅")
        elif not plan["dipindah"]:
            st.error("**MCB tetap turun.** Tidak ada alat menyala yang boleh dipindah ke baterai, atau daya "
                     "inverter tidak cukup. Tandai alat di kolom *Boleh ke baterai* atau naikkan daya inverter.",
                     icon="⛔")
        elif lama_bat < horizon and trip_b > lama_bat:
            st.warning(f"**Baterai habis pada menit ke-{fmt(lama_bat, 0)}**, lalu {dipindah_teks} kembali ke PLN "
                       f"dan MCB turun pada menit ke-{fmt(trip_b, 0)}. Perbesar kapasitas baterai menjadi sekitar "
                       f"{fmt(plan['daya_baterai_w'] * horizon / 60, 0)} Wh.", icon="⚠️")
        else:
            st.error(f"**MCB tetap turun** walau {dipindah_teks} dipindah ke baterai. Beban sisa "
                     f"{fmt(plan['arus_pln'])} A masih terlalu besar.", icon="⛔")

        # Komposisi beban
        nyala = alat_sim[alat_sim["Menyala"]]
        komp = pd.concat([
            nyala.assign(Skenario=LABEL_TANPA, Sumber="PLN"),
            nyala.assign(Skenario=LABEL_KENDALI,
                         Sumber=np.where(nyala["Alat"].isin(plan["dipindah"]), "Baterai", "PLN")),
        ])
        komp["urut"] = (komp["Sumber"] == "Baterai").astype(int)
        komp = komp.rename(columns={"Arus (A)": "arus"})
        st.markdown(f'<div class="tdv-card-title" style="margin-top:.4rem">{ikon("bolt", 14)} '
                    'Komposisi beban · garis merah = nominal MCB</div>', unsafe_allow_html=True)
        if komp.empty:
            st.info("Belum ada alat yang menyala.")
        else:
            batang = alt.Chart(komp).mark_bar(stroke="white", strokeWidth=2, cornerRadius=3, size=30).encode(
                x=alt.X("sum(arus):Q", title="Arus (A)"),
                y=alt.Y("Skenario:N", title=None, scale=alt.Scale(domain=[LABEL_TANPA, LABEL_KENDALI])),
                color=alt.Color("Sumber:N", scale=alt.Scale(domain=["PLN", "Baterai"],
                                                            range=[WARNA_KENDALI, WARNA_BATERAI])),
                order=alt.Order("urut:Q"),
                tooltip=["Alat", alt.Tooltip("arus:Q", title="Arus (A)", format=".1f"), "Sumber"])
            batas = alt.Chart(pd.DataFrame({"x": [in_mcb], "t": [f"Nominal MCB {fmt(in_mcb, 0)} A"]}))
            st.altair_chart(gaya(alt.layer(
                batang,
                batas.mark_rule(color=WARNA_TANPA, strokeDash=[6, 4], strokeWidth=2).encode(
                    x="x:Q", tooltip=alt.Tooltip("t:N", title="Batas")),
            ).properties(height=alt.Step(46)), tinggi=None), use_container_width=True)

        # Kurva θ
        st.markdown(f'<div class="tdv-card-title" style="margin-top:.4rem">{ikon("trend", 14)} '
                    'Pemanasan MCB selama operasi</div>', unsafe_allow_html=True)
        kurva = pd.concat([sim_a.assign(Skenario=LABEL_TANPA), sim_b.assign(Skenario=LABEL_KENDALI)])
        acuan = pd.DataFrame({"y": [theta_trip, theta_aman],
                              "t": [f"Ambang trip {fmt(theta_trip, 2)}", f"Ambang tindakan {fmt(theta_aman, 2)}"],
                              "w": [WARNA_TANPA, WARNA_AMAN]})
        titik_trip = pd.DataFrame([{"menit": m, "theta": theta_trip, "Skenario": s}
                                   for m, s in ((trip_a, LABEL_TANPA), (trip_b, LABEL_KENDALI)) if m is not None])
        lapis = [
            alt.Chart(kurva).mark_line(strokeWidth=2.4).encode(
                x=alt.X("menit:Q", title="Menit operasi"),
                y=alt.Y("theta:Q", title="θ (relatif)"),
                color=alt.Color("Skenario:N", scale=alt.Scale(domain=[LABEL_TANPA, LABEL_KENDALI],
                                                              range=[WARNA_TANPA, WARNA_KENDALI])),
                tooltip=["Skenario", alt.Tooltip("menit:Q", format=".1f"), alt.Tooltip("theta:Q", format=".3f"),
                         alt.Tooltip("arus:Q", title="Arus PLN (A)", format=".1f")]),
            alt.Chart(acuan).mark_rule(strokeDash=[6, 4]).encode(y="y:Q", color=alt.Color("w:N", scale=None)),
            alt.Chart(acuan).mark_text(align="left", x=4, dy=-7, fontSize=11).encode(
                y="y:Q", text="t:N", color=alt.Color("w:N", scale=None)),
        ]
        if lama_bat and lama_bat < horizon and plan["dipindah"]:
            lapis.append(alt.Chart(pd.DataFrame({"x": [lama_bat]})).mark_rule(
                color=WARNA_BATERAI, strokeDash=[2, 3]).encode(x="x:Q", tooltip=[alt.Tooltip(
                    "x:Q", title="Baterai habis (menit)", format=".0f")]))
        if not titik_trip.empty:
            lapis.append(alt.Chart(titik_trip).mark_point(shape="cross", size=150, strokeWidth=3).encode(
                x="menit:Q", y="theta:Q", color=alt.Color("Skenario:N", legend=None, scale=alt.Scale(
                    domain=[LABEL_TANPA, LABEL_KENDALI], range=[WARNA_TANPA, WARNA_KENDALI])),
                tooltip=["Skenario", alt.Tooltip("menit:Q", title="MCB turun (menit)", format=".1f")]))
        st.altair_chart(gaya(alt.layer(*lapis), tinggi=260), use_container_width=True)

# ---------------------------------------------------------------------------
# Tentang sistem
# ---------------------------------------------------------------------------
with tab_tentang:
    st.markdown(f'<div class="tdv-section">{ikon("bolt", 18)} Cara kerja sistem</div>',
                unsafe_allow_html=True)
    langkah = [
        ("wave", "Kenali beban", "Satu sensor arus dan tegangan di panel yang sudah ada mengenali alat yang "
         "menyala (NILM), tanpa sensor di tiap alat."),
        ("trend", "Hitung risiko MCB", "Model termal MCB memperkirakan seberapa dekat MCB ke batas turun "
         "berdasarkan arus dari waktu ke waktu."),
        ("switch", "Kendalikan beban", "Bila hampir turun, sistem menunda alat yang boleh ditunda (relay) "
         "atau memindahkan satu alat ke baterai dan inverter."),
        ("monitor", "Pantau di dasbor", "Pemilik UMKM melihat daya, alat aktif, pemanasan MCB, log aksi, dan "
         "tambahan daya efektif."),
    ]
    st.markdown('<div class="tdv-steps">' + "".join(
        f'<div class="tdv-step"><div class="no">LANGKAH {i}</div><div class="ik">{ikon(ik, 22)}</div>'
        f'<h4>{judul}</h4><p>{isi}</p></div>' for i, (ik, judul, isi) in enumerate(langkah, 1)) + "</div>",
        unsafe_allow_html=True)

    kiri, kanan = st.columns([3, 2], gap="large")
    with kiri:
        diagram = ROOT / "docs" / "diagram_blok.png"
        if diagram.exists():
            st.markdown(f'<div class="tdv-section">{ikon("cpu", 18)} Diagram blok</div>', unsafe_allow_html=True)
            st.image(str(diagram), use_container_width=True)
    with kanan:
        st.markdown(f'<div class="tdv-section">{ikon("shield", 18)} Prinsip keselamatan</div>',
                    unsafe_allow_html=True)
        st.markdown(
            "- Relay **fail-safe** ke PLN: bila sistem mati, beban kembali ke PLN.\n"
            "- Sakelar pindah **break-before-make**.\n"
            "- Tidak menyentuh MCB pembatas milik PLN.\n"
            "- **RCBO** di setiap panel uji.\n"
            "- Uji pertama di laboratorium dengan pendampingan dosen.")
        st.markdown(f'<div class="tdv-section">{ikon("factory", 18)} Pembeda</div>', unsafe_allow_html=True)
        st.markdown(
            "Satu sensor di panel yang sudah ada (tanpa mengganti panel), untuk listrik 220 V UMKM "
            "Indonesia, dengan biaya jauh lebih rendah daripada *smart panel* di luar negeri.")
        st.info("**Status: tahap konsep (TKT 3).** Yang ada saat ini adalah simulasi, kerangka firmware yang "
                "belum diuji, dan dasbor ini. Belum ada hasil pengukuran.", icon="ℹ️")

st.markdown(footer(), unsafe_allow_html=True)
