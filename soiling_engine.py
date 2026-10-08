from dataclasses import dataclass
from typing import Dict, Any
import requests
import pandas as pd

AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


@dataclass
class EnvironmentalMetrics:
    latitude: float
    longitude: float
    pm10_avg_ug_m3: float
    pm2_5_avg_ug_m3: float
    dry_days_count: int
    daily_soiling_rate: float
    accumulated_soiling_ratio: float


def fetch_air_quality_data(lat: float, lon: float, past_days: int = 14) -> dict:
    """
    Open-Meteo Air Quality API üzerinden sahanın son dönem PM10 ve PM2.5 
    aerosol kirlilik verilerini çeker.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["pm10", "pm2_5"],
        "past_days": past_days,
        "forecast_days": 1,
    }
    response = requests.get(AIR_QUALITY_API_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def calculate_kimber_soiling(
    lat: float,
    lon: float,
    dry_days_since_last_cleaning: int = 21,
    base_soiling_rate_per_day: float = 0.002,  # Literatür taban kirlenme oranı (%0.2 / gün)
) -> EnvironmentalMetrics:
    """
    Kimber Soiling Model uyarlaması:
    Partikül madde (PM10/PM2.5) yoğunluğuna göre günlük kirlenme eğimini (slope) dinamik ölçekler.
    """
    try:
        raw_data = fetch_air_quality_data(lat, lon)
        hourly = raw_data.get("hourly", {})
        
        pm10_series = pd.Series(hourly.get("pm10", [25.0])).dropna()
        pm2_5_series = pd.Series(hourly.get("pm2_5", [15.0])).dropna()
        
        pm10_mean = float(pm10_series.mean()) if not pm10_series.empty else 25.0
        pm2_5_mean = float(pm2_5_series.mean()) if not pm2_5_series.empty else 15.0
    except Exception:
        # API kesintisi durumunda kurak bölge ortalaması
        pm10_mean = 35.0
        pm2_5_mean = 20.0

    # PM10 kirlilik çarpanı: 40 ug/m3 üzeri havada birikim hızlanır (Kimber Slope Faktörü)
    pollution_factor = max(0.8, min(pm10_mean / 30.0, 3.0))
    dynamic_daily_rate = base_soiling_rate_per_day * pollution_factor

    # Yağışsız geçen gün boyunca kümülatif kayıp (Maksimum doyum sınırı: %35)
    total_loss_ratio = min(0.35, dynamic_daily_rate * dry_days_since_last_cleaning)

    return EnvironmentalMetrics(
        latitude=lat,
        longitude=lon,
        pm10_avg_ug_m3=round(pm10_mean, 1),
        pm2_5_avg_ug_m3=round(pm2_5_mean, 1),
        dry_days_count=dry_days_since_last_cleaning,
        daily_soiling_rate=round(dynamic_daily_rate, 4),
        accumulated_soiling_ratio=round(total_loss_ratio, 4),
    )


if __name__ == "__main__":
    # Test: Konya Karapınar ve Dubai MBR kirlilik kıyaslaması
    print("--- 1. Konya Karapınar Aerosol & Soiling Analizi ---")
    metrics_tr = calculate_kimber_soiling(37.71, 33.55, dry_days_since_last_cleaning=25)
    print(f"PM10 Seviyesi: {metrics_tr.pm10_avg_ug_m3} µg/m³")
    print(f"Günlük Kirlenme Hızı: %{metrics_tr.daily_soiling_rate * 100:.2f} / gün")
    print(f"25 Günlük Tahmini Tozlanma Kaybı: %{metrics_tr.accumulated_soiling_ratio * 100:.1f}\n")

    print("--- 2. Dubai MBR Çöl Sahası Analizi ---")
    metrics_dxb = calculate_kimber_soiling(24.75, 55.36, dry_days_since_last_cleaning=25)
    print(f"PM10 Seviyesi: {metrics_dxb.pm10_avg_ug_m3} µg/m³")
    print(f"Günlük Kirlenme Hızı: %{metrics_dxb.daily_soiling_rate * 100:.2f} / gün")
    print(f"25 Günlük Tahmini Tozlanma Kaybı: %{metrics_dxb.accumulated_soiling_ratio * 100:.1f}")