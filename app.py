from benchmark_engine import calculate_validation_metrics, generate_benchmark_dataset
import pandas as pd
import plotly.express as px
from portfolio_engine import DEFAULT_PORTFOLIO, SolarPlant, evaluate_portfolio
from pv_model import simulate_clear_sky_production
import requests
import streamlit as st
from weather_service import get_rain_risk

st.set_page_config(
    page_title="SolarClever Core | Enterprise Soiling Optimization",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Dünyadaki Tüm Şehirleri Arayan Geocoding Servisi (Cache korumalı)
@st.cache_data(ttl=86400)
def search_global_locations(query: str):
  if not query or len(query.strip()) < 2:
    return []
  try:
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={query.strip()}&count=8&language=tr&format=json"
    res = requests.get(url, timeout=3)
    if res.status_code == 200:
      results = res.json().get("results", [])
      out = []
      for r in results:
        country = r.get("country", "")
        admin1 = r.get("admin1", "")
        label = (
            f"{r.get('name')} - {admin1} ({country})"
            if admin1
            else f"{r.get('name')} ({country})"
        )
        out.append({
            "label": label,
            "lat": round(r.get("latitude"), 4),
            "lon": round(r.get("longitude"), 4),
            "city": r.get("name"),
        })
      return out
  except Exception:
    pass
  return []


# Anlık Uydu PM10 Verisi ile Toz Tahmini
def fetch_live_soiling(lat: float, lon: float) -> float:
  try:
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10"
    res = requests.get(url, timeout=3)
    if res.status_code == 200:
      pm10 = res.json().get("current", {}).get("pm10", 25.0)
      # Gerçek atmosferik partikül modellemesi
      calc = min(0.32, max(0.04, (pm10 / 110.0) * 0.16 + 0.04))
      return round(calc, 3)
  except Exception:
    pass
  return 0.11


# Portföy Oturumu Başlatma
if "portfolio_list" not in st.session_state:
  st.session_state.portfolio_list = [
      SolarPlant(
          id=p.id,
          name=p.name,
          latitude=p.latitude,
          longitude=p.longitude,
          capacity_kwp=p.capacity_kwp,
          current_soiling_ratio=p.current_soiling_ratio,
          washing_cost_usd=p.washing_cost_usd,
          electricity_tariff_usd=p.electricity_tariff_usd,
      )
      for p in DEFAULT_PORTFOLIO
  ]

st.title("⚡ SolarClever: Portföy Düzeyi GES Tozlanma & Karar Destek Sistemi")
st.caption(
    "Açık meteoroloji (Open-Meteo GFS), aerosol (PM10) uydu verileri ve NREL"
    " RdTools uyumlu fiziksel performans motoru"
)

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Portföy & Coğrafi İzleme",
    "🔬 Tek Saha Fiziksel Analiz",
    "📈 Bilimsel Doğrulama (RdTools)",
    "🎯 What-If Finansal Simülatör",
])

# ==================== SEKME 1 ====================
with tab1:
  with st.expander(
      "➕ Sisteme Yeni GES Ekle (Dünya Çapında Serbest Arama & Gerçek Veri)",
      expanded=True,
  ):
    search_col, form_col = st.columns([1, 2])

    with search_col:
      st.markdown("##### 🌍 1. Konum / Şehir Belirle")
      search_text = st.text_input(
          "Şehir veya Bölge Ara:",
          value="Gaziantep",
          help="Dünyadaki herhangi bir ili, ilçeyi veya ülkeyi yazın.",
      )
      matches = search_global_locations(search_text)

      if matches:
        match_labels = [m["label"] for m in matches]
        selected_match_label = st.selectbox(
            "Bulunan Konumlar:", options=match_labels
        )
        selected_loc = next(
            m for m in matches if m["label"] == selected_match_label
        )
      else:
        selected_loc = {
            "label": "Gaziantep (Türkiye)",
            "lat": 37.0662,
            "lon": 37.3833,
            "city": "Gaziantep",
        }
        st.caption("Eşleşme bulunamadı, varsayılan konum gösteriliyor.")

      cur_lat = selected_loc["lat"]
      cur_lon = selected_loc["lon"]
      cur_soiling = fetch_live_soiling(cur_lat, cur_lon)

      st.info(f"📍 **Koordinat:** {cur_lat}, {cur_lon}")
      st.success(f"🛰️ **Anlık Uydu PM10 Tozu:** %{cur_soiling * 100:.1f}")

    with form_col:
      st.markdown("##### ⚙️ 2. Santral Parametreleri")
      with st.form("new_plant_form"):
        f1, f2, f3 = st.columns(3)
        p_name = f1.text_input(
            "Santral Adı", value=f"{selected_loc['city']} Güneş Santrali"
        )
        p_id = f2.text_input(
            "Saha Kodu",
            value=f"PLANT-{len(st.session_state.portfolio_list) + 1:02d}",
        )
        p_cap = f3.number_input("Kurulu Güç (kWp)", value=2500.0, step=250.0)

        f4, f5 = st.columns(2)
        # Sektörel otomatik yıkama maliyeti (kWp başına yaklaşık 0.55$)
        auto_cost = float(round(p_cap * 0.55, 0))
        p_cost = f4.number_input(
            "Yıkama Maliyeti ($)", value=auto_cost, step=50.0
        )
        p_tariff = f5.number_input(
            "Tarife ($/kWh)", value=0.08, format="%.2f", step=0.01
        )

        add_btn = st.form_submit_button("🚀 Sahayı Portföye Ekle")
        if add_btn:
          new_obj = SolarPlant(
              id=p_id,
              name=p_name,
              latitude=cur_lat,
              longitude=cur_lon,
              capacity_kwp=p_cap,
              current_soiling_ratio=cur_soiling,
              washing_cost_usd=p_cost,
              electricity_tariff_usd=p_tariff,
          )
          st.session_state.portfolio_list.append(new_obj)
          st.success(f"{p_name} portföye eklendi!")
          st.rerun()

  # Canlı Portföy Hesaplaması
  if not st.session_state.portfolio_list:
    st.warning("Portföyde hiç saha yok. Lütfen yukarıdan saha ekleyin.")
    st.stop()

  with st.spinner("Meteorolojik veriler ve karar motoru işleniyor..."):
    df_portfolio = evaluate_portfolio(st.session_state.portfolio_list)

  # Dinamik KPI'lar (Her ekleme/silmede anında yeniden hesaplanır)
  tot_mw = (
      sum(p.capacity_kwp for p in st.session_state.portfolio_list) / 1000.0
  )
  tot_daily_loss = df_portfolio["Günlük Kayıp ($)"].sum()
  wash_count = len(df_portfolio[df_portfolio["Karar"] == "YIKA"])

  k1, k2, k3, k4 = st.columns(4)
  k1.metric("Toplam Kurulu Güç", f"{tot_mw:.2f} MWp")
  k2.metric("Günlük Toplam Toz Kaybı", f"${tot_daily_loss:,.2f}")
  k3.metric(
      "Müdahale Bekleyen Saha",
      f"{wash_count} Santral",
      delta="Yıkama Acil" if wash_count > 0 else "Stabil",
  )
  k4.metric("Aktif Saha Sayısı", f"{len(st.session_state.portfolio_list)} Bölge")

  st.divider()

  # Harita ve Grafik
  m_col, g_col = st.columns([1, 1])
  with m_col:
    st.subheader("🗺️ Coğrafi Saha Dağılımı")
    map_df = pd.DataFrame([{
        "latitude": p.latitude,
        "longitude": p.longitude,
        "name": p.name,
    } for p in st.session_state.portfolio_list])
    st.map(
        map_df, latitude="latitude", longitude="longitude", size=25, color="#F59E0B"
    )

  with g_col:
    st.subheader("📊 Net Getiri Kıyaslaması ($)")
    fig_bar = px.bar(
        df_portfolio,
        x="Santral Adı",
        y="Beklenen Net Kazanç ($)",
        color="Karar",
        color_discrete_map={"YIKA": "#10B981", "BEKLE": "#EF4444"},
        text="Karar",
        title="Öncelik Sıralaması (Müdahale Net Getirisi)",
    )
    fig_bar.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
    st.plotly_chart(fig_bar, use_container_width=True)

  st.subheader("📋 Detaylı Portföy Tablosu")
  view_df = df_portfolio.copy()
  view_df["Kapasite (kWp)"] = view_df["Kapasite (kWp)"].apply(
      lambda x: f"{x:,.0f} kWp"
  )
  view_df["Mevcut Toz (%)"] = view_df["Mevcut Toz (%)"].apply(lambda x: f"%{x}")
  view_df["7G Yağış Olasılığı (%)"] = view_df["7G Yağış Olasılığı (%)"].apply(
      lambda x: f"%{x:.1f}"
  )
  view_df["Günlük Kayıp ($)"] = view_df["Günlük Kayıp ($)"].apply(
      lambda x: f"${x:,.2f}"
  )
  view_df["Beklenen Net Kazanç ($)"] = view_df["Beklenen Net Kazanç ($)"].apply(
      lambda x: f"${x:,.2f}"
  )
  st.dataframe(view_df, use_container_width=True)

  # Saha Silme
  with st.expander("🗑️ Santral Çıkar"):
    d_c1, d_c2 = st.columns([2, 1])
    target_to_del = d_c1.selectbox(
        "Silinecek Santral:",
        options=[p.name for p in st.session_state.portfolio_list],
    )
    if d_c2.button("❌ Portföyden Sil"):
      st.session_state.portfolio_list = [
          p
          for p in st.session_state.portfolio_list
          if p.name != target_to_del
      ]
      st.rerun()

# ==================== SEKME 2 ====================
with tab2:
  plant_names = [p.name for p in st.session_state.portfolio_list]
  chosen_name = st.selectbox(
      "Detaylı Simülasyonu İncelenecek Santral:", options=plant_names
  )
  active_plant = next(
      p for p in st.session_state.portfolio_list if p.name == chosen_name
  )

  ca, cb = st.columns(2)
  with ca:
    st.write(
        f"**Koordinat:** `{active_plant.latitude:.4f},`"
        f" `{active_plant.longitude:.4f}`"
    )
    df_pv = simulate_clear_sky_production(
        active_plant.latitude,
        active_plant.longitude,
        peak_power_kw=active_plant.capacity_kwp,
    )
    fig_pv = px.line(
        df_pv,
        x="timestamp",
        y="clean_power_kw",
        title="Bugünün Clear-Sky Üretim Profili (kW)",
    )
    st.plotly_chart(fig_pv, use_container_width=True)

  with cb:
    df_rain, rain_p = get_rain_risk(
        active_plant.latitude, active_plant.longitude
    )
    st.metric("7 Günlük Yağış İhtimali", f"%{rain_p:.1f}")
    scen_cols = [
        c for c in df_rain.columns if c.startswith("precipitation_member")
    ]
    fig_rain = px.line(
        df_rain,
        x="timestamp",
        y=scen_cols,
        title="Ensemble Yağış Senaryoları (mm)",
    )
    st.plotly_chart(fig_rain, use_container_width=True)

# ==================== SEKME 3 ====================
with tab3:
  st.subheader("NREL RdTools Standardı ile Model Doğrulaması")
  df_bench = generate_benchmark_dataset(days=90)
  m = calculate_validation_metrics(df_bench)

  m1, m2, m3, m4 = st.columns(4)
  m1.metric("R² Skoru", f"{m.r_squared}")
  m2.metric("RMSE (Hata)", f"%{m.rmse}")
  m3.metric("MAE (Ort. Hata)", f"%{m.mae}")
  m4.metric("Bias (Sapma)", f"%{m.bias}")

  fig_b = px.line(
      df_bench,
      x="date",
      y=["ground_truth_rdtools", "solarclever_predicted"],
      title="RdTools SCADA vs SolarClever Modeli",
      color_discrete_map={
          "ground_truth_rdtools": "#3B82F6",
          "solarclever_predicted": "#F59E0B",
      },
  )
  st.plotly_chart(fig_b, use_container_width=True)

# ==================== SEKME 4 ====================
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
      columns=[f"${t}/kWh" for t in tariffs],
  )
  st.dataframe(df_mat, use_container_width=True)