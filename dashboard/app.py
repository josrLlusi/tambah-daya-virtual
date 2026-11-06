"""Dasbor TAMBAH DAYA VIRTUAL (Streamlit).

Jalankan:  streamlit run dashboard/app.py
Sumber data: CSV (contoh simulasi di data/sample, atau unggah CSV hasil panel uji).
"""
from pathlib import Path
import streamlit as st
from logika import muat, kejadian_trip, energi_baterai_kwh, tambahan_daya_va, log_aksi, IN_MCB

CONTOH = Path(__file__).resolve().parents[1] / "data" / "sample" / "pengukuran_sim.csv"

st.set_page_config(page_title="TAMBAH DAYA VIRTUAL", layout="wide")
st.title("TAMBAH DAYA VIRTUAL")
st.caption("Pengenalan beban dan kendali cerdas beban dan baterai agar UMKM dapat menambah mesin tanpa menaikkan daya PLN.")

with st.sidebar:
    st.header("Sumber data")
    unggah = st.file_uploader("Unggah CSV pengukuran", type="csv")
    df = muat(unggah if unggah is not None else CONTOH)
    simulasi = unggah is None
    if simulasi:
        st.warning("Menampilkan DATA SIMULASI, bukan hasil pengukuran.")
    in_mcb = st.number_input("Arus nominal MCB (A)", value=float(IN_MCB), min_value=1.0)
    st.write(f"{len(df)} baris")

tab1, tab2, tab3 = st.tabs(["Real-time", "Alat dan kendali", "Validasi"])

with tab1:
    st.write("Arus total dari PLN dibanding batas MCB.")
    grafik = df.set_index("waktu")[["arus_tanpa_kendali", "arus_kendali"]].copy()
    grafik["batas_mcb"] = in_mcb
    st.line_chart(grafik)
    st.write("Pemanasan MCB menurut model (1,0 = kondisi tunak pada arus nominal; ambang trip bergantung MCB).")
    st.line_chart(df.set_index("waktu")[["theta_tanpa_kendali", "theta_kendali"]])

with tab2:
    st.write("Alat yang dikenali menyala (pada simulasi: label skenario, bukan hasil model).")
    st.dataframe(df[["waktu", "alat_aktif", "daya_kendali"]].iloc[::20].reset_index(drop=True), use_container_width=True)
    st.write("Log aksi kendali")
    a = log_aksi(df)
    if len(a):
        st.dataframe(a, use_container_width=True)
    else:
        st.write("Belum ada aksi.")

with tab3:
    t = tambahan_daya_va(df, in_mcb=in_mcb)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MCB turun, tanpa kendali", kejadian_trip(df))
    c2.metric("MCB turun, dengan kendali", kejadian_trip(df, "mcb_trip_kendali"))
    c3.metric("Tambahan daya efektif", f"{t['tambahan_va']:.0f} VA")
    c4.metric("Energi dialihkan ke baterai", f"{energi_baterai_kwh(df):.2f} kWh")
    if simulasi:
        st.info("Angka pada data simulasi hanya untuk menguji dasbor. Hasil sebenarnya harus berasal dari panel uji dan UMKM nyata.")
