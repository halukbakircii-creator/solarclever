from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd
from weather_service import get_rain_risk
from pv_model import simulate_clear_sky_production
from decision_engine import CleaningEconomics, calculate_cleaning_roi


@dataclass
class SolarPlant:
    id: str
    name: str
    latitude: float
    longitude: float
    capacity_kwp: float
    current_soiling_ratio: float
    washing_cost_usd: float
    electricity_tariff_usd: float


# Portföydeki Referans Santraller
DEFAULT_PORTFOLIO: List[SolarPlant] = [
    SolarPlant(
        id="PLANT-01",
        name="Konya Karapınar Bozkır GES",
        latitude=37.71,
        longitude=33.55,
        capacity_kwp=1500.0,
        current_soiling_ratio=0.09,
        washing_cost_usd=1400.0,
        electricity_tariff_usd=0.085,
    ),
    SolarPlant(
        id="PLANT-02",
        name="Şanlıurfa GAP Sanayi GES",
        latitude=37.16,
        longitude=38.79,
        capacity_kwp=2500.0,
        current_soiling_ratio=0.14,
        washing_cost_usd=2100.0,
        electricity_tariff_usd=0.090,
    ),
    SolarPlant(
        id="PLANT-03",
        name="Dubai MBR Solar Park (Phase III)",
        latitude=24.75,
        longitude=55.36,
        capacity_kwp=5000.0,
        current_soiling_ratio=0.22,
        washing_cost_usd=4200.0,
        electricity_tariff_usd=0.065,
    ),
]


def evaluate_portfolio(plants: List[SolarPlant] = DEFAULT_PORTFOLIO) -> pd.DataFrame:
    """
    Tüm santralleri tara, ensemble yağış riskini ve beklenen net kazancı
    hesaplayarak açgözlü (greedy) öncelik sırasına diz.
    """
    records = []

    for plant in plants:
        # 1. Hava durumu ve yağış riski
        _, rain_prob = get_rain_risk(plant.latitude, plant.longitude)

        # 2. Fiziksel teorik üretim tahmini (günlük MWh)
        df_pv = simulate_clear_sky_production(
            plant.latitude, plant.longitude, peak_power_kw=plant.capacity_kwp
        )
        daily_mwh = df_pv["clean_power_kw"].sum() / 1000.0

        # 3. Finansal analiz
        econ = CleaningEconomics(
            electricity_tariff_usd_per_kwh=plant.electricity_tariff_usd,
            washing_cost_usd=plant.washing_cost_usd,
            daily_production_mwh=daily_mwh,
            current_soiling_ratio=plant.current_soiling_ratio,
        )
        roi = calculate_cleaning_roi(rain_probability_pct=rain_prob, economics=econ)

        records.append({
            "Saha Kodu": plant.id,
            "Santral Adı": plant.name,
            "Kapasite (kWp)": plant.capacity_kwp,
            "Mevcut Toz (%)": int(plant.current_soiling_ratio * 100),
            "7G Yağış Olasılığı (%)": rain_prob,
            "Günlük Kayıp ($)": roi["daily_saved_value_usd"],
            "Beklenen Net Kazanç ($)": roi["expected_net_gain_usd"],
            "Karar": "YIKA" if roi["should_wash"] else "BEKLE",
            "Öncelik Skoru": roi["expected_net_gain_usd"] / plant.washing_cost_usd,
        })

    df = pd.DataFrame(records)
    # En yüksek net getiri ve öncelik skoruna göre sırala
    return df.sort_values(by="Öncelik Skoru", ascending=False).reset_index(drop=True)