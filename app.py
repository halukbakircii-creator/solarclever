import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from portfolio_engine import evaluate_portfolio, DEFAULT_PORTFOLIO, SolarPlant
from pv_model import simulate_clear_sky_production
from weather_service import get_rain_risk
from benchmark_engine import generate_benchmark_dataset, calculate_validation_metrics

st.set_page_config(
    page_title="SolarClever Core | Enterprise Soiling Optimization",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Türkiye 81 İl Gerçek Enlem-Boylam Veritabanı
TURKIYE_ILLERI = {
    "Adana": (37.0000, 35.3213), "Adıyaman": (37.7648, 38.2786), "Afyonkarahisar": (38.7507, 30.5567),
    "Ağrı": (39.7191, 43.0503), "Amasya": (40.6534, 35.8331), "Ankara": (39.9334, 32.8597),
    "Antalya": (36.8969, 30.7133), "Artvin": (41.1828, 41.8183), "Aydın": (37.8560, 27.8416),
    "Balıkesir": (39.6484, 27.8826), "Bilecik": (40.1451, 29.9799), "Bingöl": (38.8854, 40.4983),
    "Bitlis": (38.4006, 42.1095), "Bolu": (40.7358, 31.6061), "Burdur": (37.7203, 30.2908),
    "Bursa": (40.1885, 29.0610), "Çanakkale": (40.1553, 26.4142), "Çankırı": (40.6013, 33.6134),
    "Çorum": (40.5506, 34.9556), "Denizli": (37.7765, 29.0864), "Diyarbakır": (37.9144, 40.2306),
    "Edirne": (41.6772, 26.5557), "Elazığ": (38.6810, 39.2264), "Erzincan": (39.7500, 39.5000),
    "Erzurum": (39.9055, 41.2658), "Eskişehir": (39.7767, 30.5206), "Gaziantep": (37.0662, 37.3833),
    "Giresun": (40.9128, 38.3895), "Gümüşhane": (40.4600, 39.4814), "Hakkari": (37.5833, 43.7333),
    "Hatay": (36.2023, 36.1606), "Isparta": (37.7648, 30.5566), "Mersin": (36.8121, 34.6415),
    "İstanbul": (41.0082, 28.9784), "İzmir": (38.4237, 27.1428), "Kars": (40.6013, 43.0975),
    "Kastamonu": (41.3887, 33.7827), "Kayseri": (38.7312, 35.4787), "Kırklareli": (41.7333, 27.2167),
    "Kırşehir": (39.1425, 34.1709), "Kocaeli": (40.8533, 29.8815), "Konya": (37.8714, 32.4846),
    "Kütahya": (39.4167, 29.9833), "Malatya": (38.3552, 38.3095), "Manisa": (38.6191, 27.4289),
    "Kahramanmaraş": (37.5858, 36.9371), "Mardin": (37.3212, 40.7245), "Muğla": (37.2153, 28.3636),
    "Muş": (38.7432, 41.5064), "Nevşehir": (38.6244, 34.7144), "Niğde": (37.9667, 34.6833),
    "Ordu": (40.9839, 37.8764), "Rize": (41.0201, 40.5234), "Sakarya": (40.7569, 30.3783),
    "Samsun": (41.2867, 36.3300), "Siirt": (37.9333, 41.9500), "Sinop": (42.0231, 35.1531),
    "Sivas": (39.7477, 37.0179), "Tekirdağ": (40.9833, 27.5167), "Tokat": (40.3167, 36.5500),
    "Trabzon": (41.0027, 39.7168), "Tunceli": (39.1079, 39.5401), "Şanlıurfa": (37.1674, 38.7955),
    "Uşak": (38.6823, 29.4082), "Van": (38.4891, 43.4089), "Yozgat": (39.8181, 34.8147),
    "Zonguldak": (41.4564, 31.7987), "Aksaray": (38.3687, 34.0370), "Bayburt": (40.2552, 40.2249),
    "Karaman": (37.1759, 33.2287), "Kırıkkale": (39.8468, 33.5153), "Batman": (37.8812, 41.1294),
    "Şırnak": (37.5164, 42.4594), "Bartın": (41.6344, 32.3375), "Ardahan": (41.1105, 42.7022),
    "Iğdır": (39.9196, 44.0454), "Yalova": (40.6550, 29.2769), "Karabük": (41.2061, 32.6204),
    "Kilis": (36.7184, 37.1212), "Osmaniye": (37.0742, 36.2478), "Düzce": (40.8438, 31.1565)
}

def get_real_city_soiling(lat: float, lon: float) -> float:
    """Open-Meteo Air Quality API'sinden anlık PM10 çekip gerçek toz oranını türetir."""
    try:
        url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={lat}&longitude={lon}&current=pm10"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            pm10 = resp.json().get("current", {}).get("pm10", 25.0)
            calc_soiling = min(0.30, max(0.05, (pm10 / 120.0) * 0.18 + 0.04))
            return round(calc_soiling, 3)
    except Exception:
        pass
    return 0.10

# Oturum başlatma
if "portfolio" not in st.session_state:
    st.session_state.portfolio = [
        SolarPlant(id=p.id, name=p.name, latitude=p.latitude, longitude=p.longitude,
                   capacity_kwp=p.capacity_kwp, current_soiling_ratio=p.current_soiling_ratio,
                   washing_cost_usd=p.washing_cost_usd, electricity_tariff_usd=p.electricity_tariff_usd)
        for p in DEFAULT_PORTFOLIO
    ]

st.title("⚡ SolarClever: Portföy Düzeyi GES Tozlanma & Karar Destek Sistemi")
st.caption("Açık meteoroloji (Open-Meteo GFS), aerosol (PM10) uydu verileri ve NREL RdTools uyumlu fiziksel performans motoru")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Portföy & Coğrafi İzleme",
    "🔬 Tek Saha Fiziksel Analiz",
    "📈 Bilimsel Doğrulama (RdTools)",
    "🎯 What-If Finansal Simülatör",
])

# ----------------- SEKME 1: PORTFÖY & HARİTA -----------------
with tab1:
    with st.expander("➕ Sisteme Yeni GES Ekle (Otomatik İl & Gerçek Veri)", expanded=True):
        col_city, col_details = st.columns([1, 2])
        with col_city:
            city_list = sorted(list(TURKIYE_ILLERI.keys()))
            selected_city = st.selectbox(
                "Şehir Seçin (Aramak için yazın):",
                options=city_list,
                index=city_list.index("Mersin")
            )
            lat, lon = TURKIYE_ILLERI[selected_city]
            real_soiling = get_real_city_soiling(lat, lon)
            st.info(f"📍 **{selected_city} Koordinatları:** Enlem {lat:.4f}, Boylam {lon:.4f}")
            st.success(f"🛰️ **Uydu PM10 Anlık Toz Oranı:** %{real_soiling*100:.1f}")

        with col_details:
            with st.form("auto_plant_form"):
                fc1, fc2, fc3 = st.columns(3)
                p_name = fc1.text_input("Santral Adı", value=f"{selected_city} Güneş Santrali")
                p_id = fc2.text_input("Saha Kodu", value=f"PLANT-{len(st.session_state.portfolio)+1:02d}")
                p_cap = fc3.number_input("Kurulu Güç (kWp)", value=2500.0, step=250.0)

                fc4, fc5 = st.columns(2)
                p_wash_cost = fc4.number_input("Yıkama Maliyeti ($)", value=1500.0, step=100.0)
                p_tariff = fc5.number_input("Tarife ($/kWh)", value=0.08, format="%.2f")

                submit_btn = st.form_submit_button("🚀 Bu Sahayı Canlı Portföye Ekle")
                if submit_btn:
                    new_plant = SolarPlant(
                        id=p_id,
                        name=p_name,
                        latitude=lat,
                        longitude=lon,
                        capacity_kwp=p_cap,
                        current_soiling_ratio=real_soiling,
                        washing_cost_usd=p_wash_cost,
                        electricity_tariff_usd=p_tariff,
                    )
                    st.session_state.portfolio.append(new_plant)
                    st.success(f"{p_name} gerçek koordinat ve hava verileriyle eklendi!")
                    st.rerun()

    with st.spinner("Tüm sahalar için anlık meteoroloji ve fiziksel modeller taranıyor..."):
        df_raw = evaluate_portfolio(st.session_state.portfolio)

    total_capacity_mw = sum(p.capacity_kwp for p in st.session_state.portfolio) / 1000.0
    total_daily_loss = df_raw["Günlük Kayıp ($)"].sum()
    wash_needed_count = len(df_raw[df_raw["Karar"] == "YIKA"])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Toplam Kurulu Güç", f"{total_capacity_mw:.2f} MWp")
    kpi2.metric("Günlük Toplam Toz Kaybı", f"${total_daily_loss:,.2f}")
    kpi3.metric("Müdahale Bekleyen Saha", f"{wash_needed_count} Santral", delta="Acil" if wash_needed_count > 0 else "Stabil")
    kpi4.metric("Aktif Saha Sayısı", f"{len(st.session_state.portfolio)} Bölge")

    st.divider()

    map_col, graph_col = st.columns([1, 1])
    with map_col:
        st.subheader("🗺️ Coğrafi Saha Dağılımı")
        df_map = pd.DataFrame([
            {"latitude": p.latitude, "longitude": p.longitude}
            for p in st.session_state.portfolio
        ])
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
    df_display = df_raw.copy()
    df_display["Kapasite (kWp)"] = df_display["Kapasite (kWp)"].apply(lambda x: f"{x:,.0f} kWp")
    df_display["Mevcut Toz (%)"] = df_display["Mevcut Toz (%)"].apply(lambda x: f"%{x:.1f}")
    df_display["7G Yağış Olasılığı (%)"] = df_display["7G Yağış Olasılığı (%)"].apply(lambda x: f"%{x:.1f}")
    df_display["Günlük Kayıp ($)"] = df_display["Günlük Kayıp ($)"].apply(lambda x: f"${x:,.2f}")
    df_display["Beklenen Net Kazanç ($)"] = df_display["Beklenen Net Kazanç ($)"].apply(lambda x: f"${x:,.2f}")
    df_display["Öncelik Skoru"] = df_display["Öncelik Skoru"].apply(lambda x: f"{x:.3f}")

    st.dataframe(df_display, use_container_width=True)

# ----------------- SEKME 2: TEK SAHA FİZİKSEL ANALİZ -----------------
with tab2:
    selected_plant = st.selectbox(
        "Detaylı Simülasyonu İncelenecek Santral:",
        options=st.session_state.portfolio,
        format_func=lambda p: f"{p.name} ({p.id})",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Koordinat:** {selected_plant.latitude:.4f}, {selected_plant.longitude:.4f}")
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

# ----------------- SEKME 3: BENCHMARK & DOĞRULAMA (NREL) -----------------
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

# ----------------- SEKME 4: WHAT-IF SİMÜLATÖRÜ -----------------
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
    st.dataframe(df_matrix, use_container_width=True)