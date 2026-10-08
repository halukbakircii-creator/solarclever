from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CleaningEconomics:
    """Temizlik ve elektrik satış parametrelerini tutan veri sınıfı."""
    electricity_tariff_usd_per_kwh: float = 0.08   # kWh başına satış fiyatı ($)
    washing_cost_usd: float = 1200.0               # 1 MW saha yıkama maliyeti ($)
    daily_production_mwh: float = 5.0              # Günlük ortalama üretim (MWh)
    current_soiling_ratio: float = 0.08            # Mevcut toz kaybı (%8)
    recovery_efficiency: float = 0.85              # Yıkama sonrası geri kazanım (%85)


def calculate_cleaning_roi(
    rain_probability_pct: float,
    days_until_rain: int = 4,
    economics: CleaningEconomics = CleaningEconomics(),
) -> Dict[str, Any]:
    """
    Belirsizlik farkındalıklı beklenen kazanç ve yıkama kararı hesaplar.
    """
    # 1. Günlük kurtarılabilecek enerji (kWh)
    daily_energy_kwh = economics.daily_production_mwh * 1000.0
    recoverable_daily_kwh = (
        daily_energy_kwh * economics.current_soiling_ratio * economics.recovery_efficiency
    )
    daily_saved_value_usd = (
        recoverable_daily_kwh * economics.electricity_tariff_usd_per_kwh
    )

    # 2. Senaryo Analizi:
    # Eğer yağış gelirse panelleri bedava temizler.
    # Bu nedenle yıkamanın kazandıracağı süre = bir sonraki yağışa kadar olan gün sayısıdır.
    revenue_before_rain = daily_saved_value_usd * days_until_rain
    net_gain_immediate_wash = revenue_before_rain - economics.washing_cost_usd

    # 3. Beklenen Değer (Expected Value) ve Karar Kuralı
    # Yağış olasılığı yüksekse (%60+) ve net kazanç maliyeti kurtarmıyorsa bekle.
    should_wash_now = (
        rain_probability_pct < 50.0 and net_gain_immediate_wash > 0
    ) or (net_gain_immediate_wash > (economics.washing_cost_usd * 0.5))

    reason = (
        "Yıkama maliyeti kurtarılan enerjiden yüksek ve yakın vadede yağış ihtimali var. Beklemek daha karlı."
        if not should_wash_now
        else "Tozlanma kaybı yıkama maliyetini aştı. Sahayı hemen yıkamak net kazanç sağlar."
    )

    return {
        "should_wash": should_wash_now,
        "daily_saved_value_usd": round(daily_saved_value_usd, 2),
        "expected_net_gain_usd": round(net_gain_immediate_wash, 2),
        "rain_risk_pct": rain_probability_pct,
        "recommendation_text": reason,
    }


if __name__ == "__main__":
    # Test: %20 yağış ihtimali olan bir senaryo testi
    SAMPLE_RAIN_PROB = 20.0
    result = calculate_cleaning_roi(SAMPLE_RAIN_PROB)

    print("\n--- Karar Destek Çıktısı ---")
    print(f"Hemen Yıkama Önerisi: {'EVET' if result['should_wash'] else 'HAYIR'}")
    print(f"Günlük Kurtarılan Değer: ${result['daily_saved_value_usd']}")
    print(f"Beklenen Net Kazanç/Fark: ${result['expected_net_gain_usd']}")
    print(f"Açıklama: {result['recommendation_text']}")