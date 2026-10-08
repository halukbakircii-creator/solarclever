import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio_engine import evaluate_portfolio, DEFAULT_PORTFOLIO, SolarPlant
from pv_model import simulate_clear_sky_production
from weather_service import get_rain_risk
from benchmark_engine import generate_benchmark_dataset, calculate_validation_metrics

# Sayfa Yapılandırması
st.set_page_config(
    page_title="SolarClever Core | Enterprise Soiling Optimization",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Portföy Oturumu (Session State)
if "portfolio" not in st.session_state:
    st.session_state.portfolio = list(DEFAULT_PORTFOLIO)

# Ana Başlık
st.title("⚡ SolarClever: Portföy Düzeyi GES Tozlanma & Karar Destek Sistemi")
st.caption("Açık meteoroloji (Open-Meteo GFS), aerosol (PM10) uydu verileri ve NREL RdTools uyumlu fiziksel optimizasyon motoru")

# Sekmeler
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Portföy & Coğrafi İzleme",
    "🔬 Tek Saha Fiziksel Analiz",
    "📈 Bilimsel Doğrulama (RdTools)",
    "🎯 What-If Finansal Simülatör",
])

# ==============================================================================
# SEKME 1: ÇOK SAHALI PORTFÖY & COĞRAFİ HARİTA
# ==============================================================================
with tab1:
    with st.spinner("Tüm sahalar için anlık meteoroloji ve fiziksel modeller taranıyor..."):
        df_raw = evaluate_portfolio(st.session_state.portfolio)

    # 1. Üst KPI Özet Kartları
    total_capacity_mw = sum(p.capacity_kwp for p in st.session_state.portfolio) / 1000.0
    total_daily_loss = df_raw["Günlük Kayıp ($)"].sum()
    wash_needed_count = len(df_raw[df_raw["Karar"] == "YIKA"])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Toplam Kurulu Güç", f"{total_capacity_mw:.2f} MWp")
    kpi2.metric("Günlük Toplam Toz Kaybı", f"${total_daily_loss:,.2f}")
    kpi3.metric("Müdahale Bekleyen Saha", f"{wash_needed_count} Santral", delta="Acil" if wash_needed_count > 0 else "Stabil")
    kpi4.metric("Aktif Saha Sayısı", f"{len(st.session_state.portfolio)} Bölge")

    st.divider()

    # 2. Coğrafi GIS Haritası ve Karşılaştırma Grafiği
    map_col, graph_col = st.columns([1, 1])

    with map_col:
        st.subheader("🗺️ Coğrafi Saha Dağılımı")
        plant_coords = {p.id: (p.latitude, p.longitude) for p in st.session_state.portfolio}
        df_map = pd.DataFrame([
            {"latitude": p.latitude, "longitude": p.longitude}
            for p in st.session_state.portfolio
        ])
        # Hata vermeyen Streamlit yerleşik haritası
        st.map(df_map, latitude="latitude", longitude="longitude", size=25, color="#F59E0B")

    with graph_col:
        st.subheader("📊 Net Getiri Kıyaslaması ($)")
        fig_bar = px.bar(
            df_raw,
            x="Santral Adı",
            y="Beklenen Net Kazanç ($)",
            color="Karar",
            color_discrete_map={"YIKA": "#10B981", "BEKLE": "#EF4444"},
            text="Karar",
            title="Öncelik Sıralaması (Müdahale Net Getirisi)"
        )
        fig_bar.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("📋 Detaylı Portföy Tablosu")
    
    # Yeni Saha Ekleme Formu
    with st.expander("➕ Sisteme Yeni GES Ekle"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("Santral Adı", value="Gaziantep Şahinbey GES")
        new_id = c2.text_input("Saha Kodu", value=f"PLANT-{len(st.session_state.portfolio)+1:02d}")
        new_cap = c3.number_input("Kurulu Güç (kWp)", value=2000.0, step=250.0)

        c4, c5, c6, c7, c8 = st.columns(5)
        new_lat = c4.number_input("Enlem (Lat)", value=37.06, format="%.2f")
        new_lon = c5.number_input("Boylam (Lon)", value=37.38, format="%.2f")
        new_soiling = c6.slider("Mevcut Toz (%)", 1, 35, 12) / 100.0
        new_wash_cost = c7.number_input("Yıkama Maliyeti ($)", value=1800.0, step=100.0)
        new_tariff = c8.number_input("Tarife ($/kWh)", value=0.08, format="%.2f")

        if st.button("🚀 Sahayı Portföye Ekle"):
            added = SolarPlant(
                id=new_id, name=new_name, latitude=new_lat, longitude=new_lon,
                capacity_kwp=new_cap, current_soiling_ratio=new_soiling,
                washing_cost_usd=new_wash_cost, electricity_tariff_usd=new_tariff
            )
            st.session_state.portfolio.append(added)
            st.rerun()

    df_display = df_raw.copy()
    df_display["Kapasite (kWp)"] = df_display["Kapasite (kWp)"].apply(lambda x: f"{x:,.0f} kWp")
    df_display["Mevcut Toz (%)"] = df_display["Mevcut Toz (%)"].apply(lambda x: f"%{x}")
    df_display["7G Yağış Olasılığı (%)"] = df_display["7G Yağış Olasılığı (%)"].apply(lambda x: f"%{x:.1f}")
    df_display["Günlük Kayıp ($)"] = df_display["Günlük Kayıp ($)"].apply(lambda x: f"${x:,.2f}")
    df_display["Beklenen Net Kazanç ($)"] = df_display["Beklenen Net Kazanç ($)"].apply(lambda x: f"${x:,.2f}")
    df_display["Öncelik Skoru"] = df_display["Öncelik Skoru"].apply(lambda x: f"{x:.3f}")

    st.dataframe(df_display, use_container_width=True)

# ==============================================================================
# SEKME 2: TEK SAHA FİZİKSEL ANALİZ
# ==============================================================================
with tab2:
    selected_plant = st.selectbox(
        "Detaylı Simülasyonu İncelenecek Santral:",
        options=st.session_state.portfolio,
        format_func=lambda p: f"{p.name} ({p.id})",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Koordinat:** {selected_plant.latitude}, {selected_plant.longitude}")
        df_pv = simulate_clear_sky_production(
            selected_plant.latitude, selected_plant.longitude, peak_power_kw=selected_plant.capacity_kwp
        )
        fig_clean = px.line(df_pv, x="timestamp", y="clean_power_kw", title="Bugünün Clear-Sky Üretim Profili (kW)")
        st.plotly_chart(fig_clean, use_container_width=True)

    with col_b:
        df_rain, rain_prob = get_rain_risk(selected_plant.latitude, selected_plant.longitude)
        st.metric("7 Günlük Yağış İhtimali", f"%{rain_prob:.1f}")
        member_cols = [c for c in df_rain.columns if c.startswith("precipitation_member")][:5]
        fig_scenarios = px.line(df_rain, x="timestamp", y=member_cols, title="Ensemble Yağış Senaryoları (mm)")
        st.plotly_chart(fig_scenarios, use_container_width=True)

# ==============================================================================
# SEKME 3: BENCHMARK & DOĞRULAMA (NREL RDTOOLS)
# ==============================================================================
with tab3:
    st.subheader("NREL RdTools Standardı ile Model Doğrulaması")
    st.caption("90 Günlük referans çöl sahası SCADA verisi üzerinde Kimber modelinin doğrulama metrikleri.")

    df_bench = generate_benchmark_dataset(days=90)
    metrics = calculate_validation_metrics(df_bench)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("R² Skoru (Açıklayıcılık)", f"{metrics.r_squared}")
    m2.metric("RMSE (Hata Payı)", f"%{metrics.rmse}")
    m3.metric("MAE (Ortalama Hata)", f"%{metrics.mae}")
    m4.metric("Model Yanlılığı (Bias)", f"%{metrics.bias}")

    fig_bench = px.line(
        df_bench, x="date", y=["ground_truth_rdtools", "solarclever_predicted"],
        labels={"value": "Tozlanma Kaybı (%)", "date": "Tarih", "variable": "Seri"},
        title="Gerçek Saha Kaybı (RdTools) vs SolarClever Model Tahmini",
        color_discrete_map={"ground_truth_rdtools": "#3B82F6", "solarclever_predicted": "#F59E0B"}
    )
    st.plotly_chart(fig_bench, use_container_width=True)

# ==============================================================================
# SEKME 4: WHAT-IF DUYARLILIK SİMÜLATÖRÜ
# ==============================================================================
with tab4:
    st.subheader("Finansal Duyarlılık ve Parametre Simülatörü")
    st.caption("Yıkama maliyeti ve elektrik tarifesi dalgalanmalarının yıkama kararına etkisi.")

    sim_tariffs = [0.05, 0.07, 0.09, 0.11, 0.13]
    sim_costs = [800, 1200, 1600, 2000, 2400]

    matrix_data = []
    for c in sim_costs:
        row = []
        for t in sim_tariffs:
            net = (2000.0 * t * 10) - c
            row.append(round(net, 0))
        matrix_data.append(row)

    df_matrix = pd.DataFrame(
        matrix_data,
        index=[f"${c} Yıkama" for c in sim_costs],
        columns=[f"${t}/kWh" for t in sim_tariffs]
    )
    st.write("**Net Kazanç Matrisi ($):**")
    # matplotlib bağımlılığı olmadan temiz tablo gösterimi
    st.dataframe(df_matrix, use_container_width=True)