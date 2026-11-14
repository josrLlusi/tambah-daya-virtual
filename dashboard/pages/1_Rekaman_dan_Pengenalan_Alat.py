"""Halaman kedua dasbor: rekaman panel uji (ESP32) dan pengenalan alat (NILM).

Halaman ini muncul otomatis di menu kiri saat menjalankan halaman utama:
    streamlit run dashboard/app.py

Sumber data:
  - Rekaman di data/raw (hasil alat/perekam_serial.py); bisa disegarkan otomatis saat merekam
  - Rekaman tiruan (data/sample/rekaman_tiruan.csv, dibuat oleh sim/rekaman_tiruan.py) untuk mencoba
  - Unggah CSV
Mode putar ulang memutar rekaman dari awal, untuk presentasi tanpa perangkat keras.
"""
import math
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

FOLDER_DASBOR = Path(__file__).resolve().parents[1]
if str(FOLDER_DASBOR) not in sys.path:
    sys.path.insert(0, str(FOLDER_DASBOR))

from logika import (TAU_TEBAKAN, THETA_TRIP_TEBAKAN, aksi_dari_status, daftar_model,  # noqa: E402
                    daftar_rekaman, disagregasi, hitung_theta, jenis_data, kejadian_trip, muat,
                    parameter_mcb, potong, ringkas_rekaman, sisa_waktu_menit)

try:  # gaya tampilan halaman utama, bila tersedia
    from tampilan import CSS, brand_sidebar  # noqa: E402
except Exception:  # pragma: no cover
    CSS, brand_sidebar = "", None

AKAR = FOLDER_DASBOR.parent
TIRUAN = AKAR / "data" / "sample" / "rekaman_tiruan.csv"

st.set_page_config(page_title="Rekaman dan Pengenalan Alat", page_icon="⚡", layout="wide")
if CSS:
    st.markdown(CSS, unsafe_allow_html=True)
st.title("Rekaman panel uji dan pengenalan alat")
st.caption("Membaca rekaman ESP32 (alat/perekam_serial.py): arus terhadap batas MCB, pemanasan MCB menurut model, "
           "perkiraan waktu sebelum MCB turun, alat yang dikenali menyala, dan log aksi kendali.")


@st.cache_data(show_spinner=False)
def nilm_tersimpan(kunci, path_model, _df):
    """Hasil pengenalan alat disimpan per (sumber data, jumlah baris, model) agar putar ulang tidak menghitung ulang."""
    return disagregasi(_df, path_model)


def ulang():
    """Jalankan ulang skrip (nama fungsinya berbeda pada Streamlit lama)."""
    (getattr(st, "rerun", None) or st.experimental_rerun)()


def tampil_rekaman(df, df_penuh, in_mcb, tau, theta_trip, path_model, kunci):
    # theta dihitung ulang dari arus dengan parameter MCB di sisi kiri, supaya grafik, ambang, dan
    # perkiraan waktu memakai parameter yang sama. theta dari firmware dipakai sebagai nilai awal saja.
    df = df.copy()
    awal = float(df["theta"].iloc[0]) if "theta" in df.columns else 0.0
    df["theta"] = hitung_theta(df, in_mcb, tau, theta_awal=awal)
    akhir = df.iloc[-1]
    arus, theta = float(akhir["arus"]), float(akhir["theta"])
    sisa = sisa_waktu_menit(theta, arus, in_mcb, tau, theta_trip)
    lepas = "baterai_aktif" in df.columns and float(akhir["baterai_aktif"]) > 0.5

    tab1, tab2, tab3, tab4 = st.tabs(["Real-time", "Alat (NILM)", "Kendali", "Ringkasan"])
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Arus dari PLN", f"{arus:.2f} A", f"{arus / in_mcb * 100:.0f} % dari batas MCB", delta_color="off")
        c2.metric("Daya aktif", f"{float(akhir['daya_aktif']):.0f} W")
        c3.metric("Pemanasan MCB (model)", f"{theta / theta_trip * 100:.0f} % ambang")
        if math.isinf(sisa):
            c4.metric("Perkiraan waktu sebelum MCB turun", "aman")
        else:
            c4.metric("Perkiraan waktu sebelum MCB turun", f"{sisa:.1f} menit")
        if lepas:
            st.warning("Alat yang dapat dipindah sedang LEPAS dari PLN (di baterai atau ditunda).")
        grafik = df.set_index("waktu")[["arus"]].copy()
        grafik["batas_mcb"] = in_mcb
        st.line_chart(grafik)
        st.write("Pemanasan MCB menurut model termal, dihitung dari arus dengan parameter MCB di sisi kiri. "
                 "Garis ambang adalah perkiraan saat MCB turun.")
        g2 = df.set_index("waktu")[["theta"]].copy()
        g2["ambang_trip"] = theta_trip
        st.line_chart(g2)

    with tab2:
        if path_model is None:
            st.info("Belum ada model pengenalan alat. Latih dulu dengan analisis/latih_klasifikasi.py; "
                    "berkas laporan/<nama>/model.joblib akan muncul di sini.")
        else:
            try:
                tabel, _ = nilm_tersimpan(kunci, str(path_model), df_penuh)
                tabel = tabel[tabel["waktu"] <= df["waktu"].iloc[-1]]
                alat = [k for k in tabel.columns if k != "waktu"]
                nyala = [k for k in alat if len(tabel) and bool(tabel[k].iloc[-1])]
                st.metric("Alat yang dikenali menyala sekarang", ", ".join(nyala) if nyala else "tidak ada")
                st.write("Lama menyala per alat menurut model (menit).")
                menit = {k: float(tabel[k].sum()) / 60.0 for k in alat}
                st.bar_chart(pd.Series(menit, name="menit"))
                st.caption(f"Model: {Path(path_model).parent.name}. Hasil pengenalan adalah perkiraan model, "
                           "bukan pengukuran per alat.")
            except Exception as e:  # model tidak cocok dengan data, dsb.
                st.error(f"Pengenalan alat gagal dijalankan pada data ini: {e}")

    with tab3:
        a = aksi_dari_status(df)
        st.write("Log aksi kendali (dari kolom baterai_aktif pada rekaman).")
        if len(a):
            st.dataframe(a, use_container_width=True)
        else:
            st.write("Belum ada aksi pada rekaman ini.")

    with tab4:
        r = ringkas_rekaman(df, in_mcb)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Durasi rekaman", f"{r['durasi_menit']:.1f} menit")
        c2.metric("Energi dari PLN", f"{r['energi_pln_kwh']:.3f} kWh")
        c3.metric("Arus maksimum", f"{r['arus_maks']:.2f} A")
        c4.metric("Waktu di atas batas MCB", f"{r['menit_di_atas_batas']:.1f} menit")
        c1, c2, c3 = st.columns(3)
        c1.metric("Jumlah aksi kendali", r["jumlah_aksi"])
        c2.metric("Waktu alat lepas dari PLN", f"{r['menit_lepas_dari_pln']:.1f} menit")
        if "mcb_trip" in df.columns:
            c3.metric("MCB turun", kejadian_trip(df, "mcb_trip"))


# ------------------------------- sisi kiri --------------------------------
with st.sidebar:
    if brand_sidebar:
        st.markdown(brand_sidebar(), unsafe_allow_html=True)
    st.header("Sumber rekaman")
    pilihan = ["Rekaman di data/raw", "Rekaman tiruan (simulasi)", "Unggah CSV"]
    sumber = st.radio("Pilih sumber", pilihan)
    df_penuh, kunci, segarkan, simulasi = None, "", False, False
    if sumber == "Rekaman di data/raw":
        ada = daftar_rekaman()
        if not ada:
            st.info("Belum ada rekaman di data/raw. Jalankan alat/perekam_serial.py, "
                    "atau pilih rekaman tiruan.")
        else:
            pilih = st.selectbox("Berkas rekaman (terbaru di atas)", [p.name for p in ada])
            path = next(p for p in ada if p.name == pilih)
            df_penuh = muat(path)
            kunci = f"{path.name}:{len(df_penuh)}"
            segarkan = st.checkbox("Segarkan otomatis tiap 5 detik (saat merekam)")
    elif sumber == "Rekaman tiruan (simulasi)":
        if TIRUAN.exists():
            df_penuh, kunci, simulasi = muat(TIRUAN), "tiruan", True
        else:
            st.info("Rekaman tiruan belum dibuat. Jalankan: python sim/rekaman_tiruan.py")
    else:
        unggah = st.file_uploader("Unggah CSV rekaman", type="csv")
        if unggah is not None:
            try:
                unggah.seek(0)
                df_penuh = muat(unggah)
                kunci = f"unggah:{unggah.name}:{len(df_penuh)}"
            except Exception as e:  # berkas bukan CSV pengukuran
                st.error(f"Berkas tidak bisa dibaca sebagai rekaman ({e}).")

    jenis = jenis_data(df_penuh) if df_penuh is not None else None
    if df_penuh is not None:
        simulasi = simulasi or ("id_perangkat" in df_penuh.columns
                                and str(df_penuh["id_perangkat"].iloc[0]) in ("tiruan", "sintetis"))
        if simulasi:
            st.warning("DATA SIMULASI, bukan hasil pengukuran.")
        st.write(f"{len(df_penuh)} baris")

    st.header("MCB")
    par = parameter_mcb() if not simulasi else None
    in_awal = float(par["in_mcb_A"]) if par else (10.0 if simulasi else 4.0)
    in_mcb = st.number_input("Arus nominal MCB (A)", min_value=1.0, value=in_awal)
    tau = st.number_input("Konstanta waktu termal tau (detik)", min_value=1.0,
                          value=float(par["tau_detik"]) if par else TAU_TEBAKAN)
    theta_trip = st.number_input("Ambang trip (theta)", min_value=1.0,
                                 value=float(par["theta_trip"]) if par else THETA_TRIP_TEBAKAN)
    if par:
        st.caption(f"Parameter dari {par['sumber']}.")
    elif simulasi:
        st.caption("Parameter simulasi (tebakan ilustratif).")
    else:
        st.caption("Parameter MCB masih TEBAKAN. Jalankan analisis/fit_mcb.py dengan data uji trip.")
    model = daftar_model()
    path_model = None
    if model:
        nama = st.selectbox("Model pengenalan alat", [p.parent.name for p in model])
        path_model = next(p for p in model if p.parent.name == nama)

    st.header("Putar ulang")
    demo = st.checkbox("Putar ulang rekaman dari awal")
    putar, langkah = False, 2
    if demo:
        if "posisi_rekaman" not in st.session_state:
            st.session_state["posisi_rekaman"] = 5
        putar = st.checkbox("Putar otomatis")
        langkah = st.selectbox("Kecepatan (% per detik)", [1, 2, 5, 10], index=1)
        if putar:
            st.progress(min(int(st.session_state["posisi_rekaman"]), 100))
        else:
            st.session_state["posisi_rekaman"] = st.slider("Posisi (%)", 1, 100,
                                                           int(st.session_state["posisi_rekaman"]))

# ------------------------------- isi utama --------------------------------
if df_penuh is None:
    st.info("Pilih sumber rekaman di sisi kiri.")
elif jenis != "rekaman":
    st.error("Kolom CSV tidak dikenali sebagai rekaman. Butuh kolom 'waktu', 'arus', dan 'daya_aktif' "
             "(lihat data/README.md). Data dua skenario simulasi dibuka di halaman utama.")
else:
    df = potong(df_penuh, st.session_state["posisi_rekaman"] / 100.0) if demo else df_penuh
    if demo:
        st.caption(f"PUTAR ULANG: posisi {int(st.session_state['posisi_rekaman'])} %.")
    if simulasi:
        st.warning("DATA SIMULASI. Semua angka di halaman ini ilustratif dan bukan kinerja alat.")
    tampil_rekaman(df, df_penuh, in_mcb, tau, theta_trip, path_model, kunci)

# ------------------------- putar otomatis / segarkan -----------------------
if demo and putar and df_penuh is not None and st.session_state["posisi_rekaman"] < 100:
    time.sleep(1.0)
    st.session_state["posisi_rekaman"] = min(100, st.session_state["posisi_rekaman"] + langkah)
    ulang()
elif segarkan and not demo:
    time.sleep(5.0)
    ulang()
