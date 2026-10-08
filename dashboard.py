import streamlit as st
import plotly.express as px
from weather_service import get_rain_risk
from pv_model import simulate_clear_sky_production
from decision_engine import CleaningEconomics, calculate_cleaning_roi

st.set_page_config(page_title="SolarClever | Soiling Decision Support", layout="wide")

st.title("☀️ SolarClever: GES Tozlanma & Yıkama Karar Destek Sistemi")
st.caption("Açık veri tabanlı belirsizlik farkındalıklı soiling optimizasyon paneli")

# Kenar Çubuğu: Parametreler
st.sidebar.header("📍 Saha & Finansal Parametreler")
lat = st.sidebar.number_input("Enlem (Latitude)", value=37.71, format="%.2f")
lon = st.sidebar.number_input("Boylam (Longitude)", value=33.55, format="%.2f")
plant_capacity_kw = st.sidebar.number_input("Santral Kurulu Gücü (kWp)", value=1000.0, step=100.0)

st.sidebar.subheader("Maliyet ve Tarife")
tariff = st.sidebar.slider("Elektrik Satış Tarifesi ($/kWh)", 0.04, 0.20, 0.08, 0.01)
washing_cost = st.sidebar.number_input("Saha Yıkama Maliyeti ($)", value=1200.0, step=50.0)
soiling_pct = st.sidebar.slider("Tahmini Toz Kaybı (%)", 1, 30, 8) / 100.0

# 1. Hava Durumu ve Yağış Riski Çek
with st.spinner("Meteorolojik ensemble verileri alınıyor..."):
    df_rain, rain_prob = get_rain_risk(lat, lon)

# 2. PVLib Temiz Üretim Simülasyonu
df_pv = simulate_clear_sky_production(lat, lon, peak_power_kw=plant_capacity_kw)

# 3. Karar Motoru Hesabı
daily_mwh_est = (df_pv["clean_power_kw"].sum() / 1000.0)
econ = CleaningEconomics(
    electricity_tariff_usd_per_kwh=tariff,
    washing_cost_usd=washing_cost,
    daily_production_mwh=daily_mwh_est,
    current_soiling_ratio=soiling_pct
)
roi = calculate_cleaning_roi(rain_probability_pct=rain_prob, economics=econ)

# Üst Metrik Kartları
col1, col2, col3, col4 = st.columns(4)
col1.metric("7 Günlük Yağış Olasılığı", f"%{rain_prob}")
col2.metric("Günlük Temiz Üretim", f"{daily_mwh_est:.1f} MWh")
col3.metric("Günlük Toz Kaybı Maliyeti", f"${roi['daily_saved_value_usd']}")
col4.metric("Öneri", "HEMEN YIKA" if roi["should_wash"] else "BEKLE", delta_color="normal")

st.info(f"**Karar Gerekçesi:** {roi['recommendation_text']}")

st.divider()

# Grafikler
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Güneş Işınımı ve Beklenen Temiz Güç (Bugün)")
    fig_pv = px.line(
        df_pv, 
        x="timestamp", 
        y="clean_power_kw", 
        title="Saatlik Teorik Güç Profili (kW)",
        labels={"clean_power_kw": "Güç (kW)", "timestamp": "Zaman (UTC)"}
    )
    st.plotly_chart(fig_pv, use_container_width=True)

with col_right:
    st.subheader("Ensemble Yağış Senaryoları (7 Gün)")
    member_cols = [c for c in df_rain.columns if c.startswith("precipitation_member")]
    fig_rain = px.line(
        df_rain, 
        x="timestamp", 
        y=member_cols[:5],  # İlk 5 senaryo örneği
        title="Olası Yağış Senaryoları (mm)",
        labels={"value": "Yağış (mm)", "timestamp": "Tarih"}
    )
    st.plotly_chart(fig_rain, use_container_width=True)