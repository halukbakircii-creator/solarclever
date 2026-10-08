import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from portfolio_engine import evaluate_portfolio, SolarPlant
from pv_model import simulate_clear_sky_production
from weather_service import get_rain_risk
from benchmark_engine import generate_benchmark_dataset, calculate_validation_metrics

st.set_page_config(
    page_title="SolarClever Core | Enterprise Soiling Optimization",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 1. Dünya Çapında Hızlı & Güvenli Şehir Arama (Cache korumalı)
@st.cache_data(ttl=86400)
def search_global_locations(query: str):
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={query.strip()}&count=6&language=tr&format=json"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            results = res.json().get("results", [])
            out = []
            for r in results:
                admin1 = r.get("admin1", "")
                country = r.get("country", "")
                label = f"{r.get('name')} - {admin1} ({country})" if admin1 else f"{r.get('name')} ({country})"
                out.append({
                    "label": label,
                    "city": r.get("name"),
                    "lat": round(r.get("latitude"), 4),
                    "lon": round(r.get("longitude"), 4),
                })
            return out
    except Exception:
        pass
    return []

# 2. Gerçek Uydu Aerosol (PM10) ile Toz Oranı
def fetch_live_soiling(lat: float, lon: float) -> float:
    try:
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            pm10 = res.json().get("current", {}).get("pm10", 25.0)
            calc = min(0.35, max(0.04, (pm10 / 110.0) * 0.16 + 0.04))
            return round(calc, 3)
    except Exception:
        pass
    return 0.10

# 3. Portföy Durumunu Session State'te Tutma
if "portfolio_list" not in st.session_state:
    st.session_state.portfolio_list = [
        SolarPlant(id="PLANT-01", name="Konya Karapınar GES", latitude=37.87, longitude=33.55, capacity_kwp=3000.0, current_soiling_ratio=0.12, washing_cost_usd=1600.0, electricity_tariff_usd=0.08),
        SolarPlant(id="PLANT-02", name="Şanlıurfa GAP GES", latitude=37.16, longitude=38.79, capacity_kwp=2500.0, current_soiling_ratio=0.15, washing_cost_usd=1400.0, electricity_tariff_usd=0.08),
        SolarPlant(id="PLANT-03", name="Mersin Akdeniz GES", latitude=36.81, longitude=34.64, capacity_kwp=2000.0, current_soiling_ratio=0.08, washing_cost_usd=1100.0, electricity_tariff_usd=0.08),
    ]

st.title("⚡ SolarClever: Portföy Düzeyi GES Tozlanma & Karar Destek Sistemi")
st.caption("Açık meteoroloji (Open-Meteo GFS), aerosol (PM10) uydu verileri ve NREL RdTools uyumlu fiziksel performans motoru")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Portföy & Coğrafi İzleme",
    "🔬 Tek Saha Fiziksel Analiz",
    "📈 Bilimsel Doğrulama (RdTools)",
    "🎯 What-If Finansal Simülatör",
])

# ==========================================
# SEKME 1: PORTFÖY & COĞRAFİ İZLEME
# ==========================================
with tab1:
    with st.expander("➕ Sisteme Yeni GES Ekle (Dünya Çapında Serbest Arama & Gerçek Veri)", expanded=True):
        col_search, col_inputs = st.columns([1, 2])
        
        with col_search:
            st.markdown("##### 🌍 1. Konum / Şehir Ara")
            search_query = st.text_input("Şehir / Bölge Adı:", value="Ankara", help="İstediğiniz il veya dünya şehrini yazın.")
            found_locs = search_global_locations(search_query)
            
            if found_locs:
                loc_map = {item["label"]: item for item in found_locs}
                selected_label = st.selectbox("Eşleşen Konumlar:", options=list(loc_map.keys()))
                current_loc = loc_map[selected_label]
            else:
                current_loc = {"city": "Ankara", "label": "Ankara (Türkiye)", "lat": 39.9334, "lon": 32.8597}
                st.caption("Varsayılan konum kullanılıyor.")

            lat_val = current_loc["lat"]
            lon_val = current_loc["lon"]
            live_soil_ratio = fetch_live_soiling(lat_val, lon_val)

            st.info(f"📍 **Koordinatlar:** Enlem `{lat_val:.4f}`, Boylam `{lon_val:.4f}`")
            st.success(f"🛰️ **Anlık Uydu PM10 Toz Kaybı:** %{live_soil_ratio * 100:.1f}")

        with col_inputs:
            st.markdown("##### ⚙️ 2. Santral Bilgileri")
            c_name = st.text_input("Santral Adı", value=f"{current_loc['city']} Güneş Santrali")
            c_code = st.text_input("Saha Kodu", value=f"PLANT-{len(st.session_state.portfolio_list)+1:02d}")
            c_kwp = st.number_input("Kurulu Güç (kWp)", value=2500.0, step=250.0)

            sub_c1, sub_c2 = st.columns(2)
            auto_wash = float(round(c_kwp * 0.55, 0))
            c_cost = sub_c1.number_input("Yıkama Maliyeti ($)", value=auto_wash, step=50.0)
            c_tariff = sub_c2.number_input("Elektrik Satış Tarifesi ($/kWh)", value=0.08, format="%.2f", step=0.01)

            # Form tagi olmadan doğrudan ekleme butonu (Kayıp ve donma yaşanmaz)
            if st.button("🚀 Sahayı Portföye Ekle", type="primary", use_container_width=True):
                new_solar_plant = SolarPlant(
                    id=c_code,
                    name=c_name,
                    latitude=lat_val,
                    longitude=lon_val,
                    capacity_kwp=c_kwp,
                    current_soiling_ratio=live_soil_ratio,
                    washing_cost_usd=c_cost,
                    electricity_tariff_usd=c_tariff,
                )
                st.session_state.portfolio_list.append(new_solar_plant)
                st.success(f"✅ {c_name} portföye başarıyla eklendi!")
                st.rerun()

    # Portföy Değerlendirme
    if len(st.session_state.portfolio_list) == 0:
        st.warning("Portföyde hiç santral bulunmuyor. Lütfen yukarıdan en az bir santral ekleyin.")
        st.stop()

    with st.spinner("Tüm sahaların canlı meteoroloji ve toz kayıpları analiz ediliyor..."):
        df_portfolio = evaluate_portfolio(st.session_state.portfolio_list)

    # Dinamik KPI Kartları
    tot_mw = sum(p.capacity_kwp for p in st.session_state.portfolio_list) / 1000.0
    tot_loss = df_portfolio["Günlük Kayıp ($)"].sum()
    wash_needed = len(df_portfolio[df_portfolio["Karar"] == "YIKA"])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Toplam Kurulu Güç", f"{tot_mw:.2f} MWp")
    k2.metric("Günlük Toplam Toz Kaybı", f"${tot_loss:,.2f}")
    k3.metric("Müdahale Bekleyen Saha", f"{wash_needed} Santral", delta="Yıkama Acil" if wash_needed > 0 else "Stabil")
    k4.metric("Aktif Saha Sayısı", f"{len(st.session_state.portfolio_list)} Bölge")

    st.divider()

    # Coğrafi Harita ve Net Getiri Grafiği
    m_col, g_col = st.columns([1, 1])
    with m_col:
        st.subheader("🗺️ Coğrafi Saha Dağılımı")
        map_df = pd.DataFrame([
            {"latitude": p.latitude, "longitude": p.longitude, "name": p.name}
            for p in st.session_state.portfolio_list
        ])
        st.map(map_df, latitude="latitude", longitude="longitude", size=25, color="#F59E0B")

    with g_col:
        st.subheader("📊 Net Getiri Kıyaslaması ($)")
        fig_bar = px.bar(
            df_portfolio,
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
    v_df = df_portfolio.copy()
    v_df["Kapasite (kWp)"] = v_df["Kapasite (kWp)"].apply(lambda x: f"{x:,.0f} kWp")
    v_df["Mevcut Toz (%)"] = v_df["Mevcut Toz (%)"].apply(lambda x: f"%{x}")
    v_df["7G Yağış Olasılığı (%)"] = v_df["7G Yağış Olasılığı (%)"].apply(lambda x: f"%{x:.1f}")
    v_df["Günlük Kayıp ($)"] = v_df["Günlük Kayıp ($)"].apply(lambda x: f"${x:,.2f}")
    v_df["Beklenen Net Kazanç ($)"] = v_df["Beklenen Net Kazanç ($)"].apply(lambda x: f"${x:,.2f}")
    st.dataframe(v_df, use_container_width=True)

    with st.expander("🗑️ Santral Çıkar / Sil"):
        d1, d2 = st.columns([2, 1])
        del_target = d1.selectbox("Silinecek Santral:", options=[p.name for p in st.session_state.portfolio_list])
        if d2.button("❌ Portföyden Çıkar"):
            st.session_state.portfolio_list = [p for p in st.session_state.portfolio_list if p.name != del_target]
            st.rerun()

# ==========================================
# SEKME 2: TEK SAHA FİZİKSEL ANALİZ
# ==========================================
with tab2:
    st.markdown("### 🔬 Saha Fiziksel Simülasyonu & Meteoroloji İncelemesi")
    
    analysis_mode = st.radio("İnceleme Kaynağı Seçin:", ["Portföyümdeki Santrallerden Seç", "Dünyadan Serbest Bir Konum İncele"], horizontal=True)
    
    if analysis_mode == "Portföyümdeki Santrallerden Seç":
        p_names = [p.name for p in st.session_state.portfolio_list]
        selected_p_name = st.selectbox("İncelenecek Santral:", options=p_names)
        target_plant = next(p for p in st.session_state.portfolio_list if p.name == selected_p_name)
        sim_lat = target_plant.latitude
        sim_lon = target_plant.longitude
        sim_cap = target_plant.capacity_kwp
        sim_title = target_plant.name
    else:
        q_free = st.text_input("İncelemek İstediğiniz Şehir veya Ülke:", value="İzmir")
        free_matches = search_global_locations(q_free)
        if free_matches:
            f_map = {item["label"]: item for item in free_matches}
            f_label = st.selectbox("Konum Seçin:", options=list(f_map.keys()))
            f_chosen = f_map[f_label]
            sim_lat = f_chosen["lat"]
            sim_lon = f_chosen["lon"]
            sim_title = f_chosen["city"]
        else:
            sim_lat = 38.4237
            sim_lon = 27.1428
            sim_title = "İzmir"
        sim_cap = st.number_input("Simülasyon Kurulu Gücü (kWp):", value=2000.0, step=250.0)

    st.write(f"📍 **Aktif İncelenen Konum:** `{sim_title}` (Enlem: {sim_lat:.4f}, Boylam: {sim_lon:.4f})")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        df_pv = simulate_clear_sky_production(sim_lat, sim_lon, peak_power_kw=sim_cap)
        fig_pv = px.line(df_pv, x="timestamp", y="clean_power_kw", title=f"{sim_title} - Saatlik Clear-Sky Üretim Profili (kW)")
        st.plotly_chart(fig_pv, use_container_width=True)

    with col_g2:
        df_rain, rain_prob = get_rain_risk(sim_lat, sim_lon)
        st.metric("7 Günlük Yağış İhtimali", f"%{rain_prob:.1f}")
        scen_cols = [c for c in df_rain.columns if c.startswith("precipitation_member")]
        fig_rain = px.line(df_rain, x="timestamp", y=scen_cols, title=f"{sim_title} - Ensemble Yağış Senaryoları (mm)")
        st.plotly_chart(fig_rain, use_container_width=True)

# ==========================================
# SEKME 3: BİLİMSEL DOĞRULAMA (RdTools)
# ==========================================
with tab3:
    st.subheader("NREL RdTools Standardı ile Model Doğrulaması")
    df_bench = generate_benchmark_dataset(days=90)
    m = calculate_validation_metrics(df_bench)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("R² Skoru", f"{m.r_squared}")
    m2.metric("RMSE (Hata)", f"%{m.rmse}")
    m3.metric("MAE (Ortalama Hata)", f"%{m.mae}")
    m4.metric("Model Yanlılığı (Bias)", f"%{m.bias}")

    fig_bench = px.line(
        df_bench, x="date", y=["ground_truth_rdtools", "solarclever_predicted"],
        title="Gerçek Saha Kaybı (RdTools) vs SolarClever Modeli",
        color_discrete_map={"ground_truth_rdtools": "#3B82F6", "solarclever_predicted": "#F59E0B"}
    )
    st.plotly_chart(fig_bench, use_container_width=True)

# ==========================================
# SEKME 4: WHAT-IF FİNANSAL SİMÜLATÖR
# ==========================================
with tab4:
    st.subheader("Finansal Parametre Duyarlılık Matrisi")
    costs = [800, 1200, 1600, 2000, 2400]
    tariffs = [0.05, 0.07, 0.09, 0.11, 0.13]
    mat = []
    for c in costs:
        mat.append([round((2000.0 * t * 10) - c, 0) for t in tariffs])
    df_mat = pd.DataFrame(
        mat,
        index=[f"${c} Yıkama" for c in costs],
        columns=[f"${t}/kWh" for t in tariffs]
    )
    st.write("**Net Kazanç Matrisi ($):**")
    st.dataframe(df_mat, use_container_width=True)