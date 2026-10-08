from dataclasses import dataclass
import numpy as np
import pandas as pd
from pv_model import simulate_clear_sky_production
from weather_service import get_rain_risk


@dataclass
class SolarPlant:

  id: str
  name: str
  latitude: float
  longitude: float
  capacity_kwp: float
  current_soiling_ratio: float  # Örn: 0.12 (%12)
  washing_cost_usd: float
  electricity_tariff_usd: float  # $/kWh


# Global Referans Şablon Portföyü
DEFAULT_PORTFOLIO = [
    SolarPlant(
        id="PLANT-01",
        name="Konya Karapınar GES",
        latitude=37.87,
        longitude=33.55,
        capacity_kwp=3000.0,
        current_soiling_ratio=0.12,
        washing_cost_usd=1600.0,
        electricity_tariff_usd=0.08,
    ),
    SolarPlant(
        id="PLANT-02",
        name="Şanlıurfa GAP GES",
        latitude=37.16,
        longitude=38.79,
        capacity_kwp=2500.0,
        current_soiling_ratio=0.15,
        washing_cost_usd=1400.0,
        electricity_tariff_usd=0.08,
    ),
    SolarPlant(
        id="PLANT-03",
        name="Mersin Akdeniz GES",
        latitude=36.81,
        longitude=34.64,
        capacity_kwp=2000.0,
        current_soiling_ratio=0.08,
        washing_cost_usd=1100.0,
        electricity_tariff_usd=0.08,
    ),
]


def evaluate_portfolio(plants: list[SolarPlant]) -> pd.DataFrame:
  """Tüm portföydeki sahaları meteorolojik yağış riski ve fiziksel kayba göre analiz eder."""
  records = []

  for plant in plants:
    # 1. Fiziksel Üretim Potansiyeli
    try:
      df_pv = simulate_clear_sky_production(
          plant.latitude, plant.longitude, peak_power_kw=plant.capacity_kwp
      )
      daily_clean_kwh = float(df_pv["clean_power_kw"].sum())
    except Exception:
      daily_clean_kwh = plant.capacity_kwp * 4.5  # Günlük ortalama 4.5 Eşdeğer Güneş Saati

    # 2. Meteorolojik Yağmur Riski
    _, rain_risk_percent = get_rain_risk(plant.latitude, plant.longitude)

    # 3. Finansal Kayıp ve Karar Motoru
    daily_energy_loss_kwh = daily_clean_kwh * plant.current_soiling_ratio
    daily_revenue_loss = daily_energy_loss_kwh * plant.electricity_tariff_usd

    # 14 günlük kurtarılabilir enerji değeri
    recovered_energy_14d_usd = daily_revenue_loss * 14.0

    # Olasılıklı Net Fayda: E[ROI] = (1 - P_rain) * Gain - Cost
    p_rain = rain_risk_percent / 100.0
    expected_gain = ((1.0 - p_rain) * recovered_energy_14d_usd) - (
        plant.washing_cost_usd
    )

    # Karar Fonksiyonu
    decision = "YIKA" if expected_gain > 0 else "BEKLE"
    priority_score = expected_gain / (plant.washing_cost_usd + 1.0)

    records.append({
        "Saha Kodu": plant.id,
        "Santral Adı": plant.name,
        "Enlem": plant.latitude,
        "Boylam": plant.longitude,
        "Kapasite (kWp)": plant.capacity_kwp,
        "Mevcut Toz (%)": round(plant.current_soiling_ratio * 100, 1),
        "7G Yağış Olasılığı (%)": round(rain_risk_percent, 1),
        "Günlük Kayıp ($)": round(daily_revenue_loss, 2),
        "Beklenen Net Kazanç ($)": round(expected_gain, 2),
        "Karar": decision,
        "Öncelik Skoru": round(priority_score, 3),
    })

  df = pd.DataFrame(records)
  if not df.empty:
    df = df.sort_values(by="Beklenen Net Kazanç ($)", ascending=False)
  return df