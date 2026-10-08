# ⚡ SolarClever Core: Enterprise PV Soiling & Decision Support System

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://solarclever-engine.streamlit.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Canlı Dağıtım URL'i:** [https://solarclever-engine.streamlit.app/](https://solarclever-engine.streamlit.app/)

**SolarClever**, açık meteoroloji ve uydu atmosfer verilerini kullanarak güneş enerjisi santrallerinde (GES) optik sensör donanım maliyeti gerektirmeden tozlanma (soiling) kaynaklı üretim kayıplarını tahmin eden ve holding düzeyinde saha yıkama lojistiğini optimize eden bir Karar Destek Sistemidir (KDS).

---

## 📌 Problem & Motivasyon

Güneş santrallerinde fotovoltaik panel yüzeylerinde biriken toz ve aerosol tabakası, yıllık enerji üretiminde bölgeye bağlı olarak **%5 ila %30** arasında kayba neden olur. 

* **Gereksiz Yıkama:** Temizlik yapıldıktan 1-2 gün sonra yağmur yağması durumunda yüksek su ve operasyonel işçilik maliyeti israf edilir.
* **Geciken Müdahale:** Tozlanma doyum noktasına ulaştığında her gün megavat-saat (MWh) bazında finansal kayıp yaşanır.
* **Sınırlı Filo Yönetimi:** Çok sahalı holdinglerde temizlik ekipleri sınırlıdır; hangi sahanın en yüksek net finansal getiri sağlayacağına karar verilmesi gerekir.

SolarClever, belirsizlik farkındalıklı (uncertainty-aware) karar motoruyla bu süreci tamamen otomatikleştirir.

---

## 🏗️ Sistem Mimarisi
+------------------------------------+
   |       Açık Veri Kaynakları         |
   |  - Open-Meteo GFS 30-Üyeli Topluluk|
   |  - CAMS PM10 / PM2.5 Aerosol       |
   +-----------------+------------------+
                     |
                     v
+----------------------------------------------+
|              Fiziksel & Çevresel Modeller    |
|  * pvlib: Clear-Sky Ineichen Radyasyon Modeli|
|  * Modifiye Kimber Toz Birikim Dinamiği      |
+---------------------+------------------------+
|
v
+----------------------------------------------+
|           Finansal Karar Motoru              |
|  * Beklenen Değer Analizi (E[ROI])           |
|  * Portföy Düzeyi Açgözlü Sıralama (Greedy)  |
+---------------------+------------------------+
|
v
+------------------------------------+
|       Operasyonel Dashboard        |
|  - Coğrafi GIS Saha İzleme         |
|  - NREL RdTools Doğrulama Kıyası   |
|  - Finansal What-If Simülatörü     |
+--------------------+---------------+
---

## 🔬 Bilimsel & Matematiksel Altyapı

1. Fotovoltaik Üretim Hesabı (pvlib)
Santralin berrak gökyüzü koşullarındaki teorik güç çıkışı Ineichen modeliyle hesaplanır:

$$P_{clean}(t) = GHI(t) \cdot A \cdot \eta \cdot PR$$

* $GHI(t)$: Global Yatay Işınım ($W/m^2$)
* $A$: Toplam modül yüzey alanı ($m^2$)
* $\eta$: Panel verimlilik katsayısı
* $PR$: Performans oranı (Performance Ratio)

### 2. Kimber Tozlanma Oranı
Partikül madde (PM10) yoğunluğu ve yağışsız geçen gün sayısına bağlı birikim:

$$S(t) = \min\left(0.35, \, d_{dry} \cdot r_{base} \cdot f_{aerosol}\right)$$

$$f_{aerosol} = \max\left(0.8, \, \frac{PM_{10}}{30}\right)$$

### 3. Yıkama Karar Fonksiyonu
Meteorolojik yağış olasılığı ($P_{rain}$) ve beklenen net marjinal getiri analizi:

$$E[Gain] = (1 - P_{rain}) \cdot (\Delta E \cdot Tariff) - Cost_{wash}$$

$$\text{Karar} = \begin{cases} \text{YIKA}, & E[Gain] > 0 \\ \text{BEKLE}, & E[Gain] \le 0 \end{cases}$$

## 📊 Dashboard Sekmeleri & Fonksiyonlar

1. **Portföy & Coğrafi İzleme:**
   - Harita katmanı üzerinde aktif santrallerin gerçek zamanlı izlenmesi.
   - Sınırlı yıkama filosu için net kazanç ve öncelik skoruna göre sıralama.
   - Dinamik saha ekleme ve anlık simülasyon.
2. **Tek Saha Fiziksel Analiz:**
   - Seçilen santralin saatlik Clear-Sky üretim profili.
   - 7 günlük meteoroloji ensemble modellerinden gelen çoklu yağış senaryoları.
3. **Bilimsel Doğrulama (Benchmark):**
   - NREL `RdTools` algoritması zemin gerçeği ile Kimber model tahmininin 90 günlük kıyası.
   - Performans metrikleri: $R^2$, $RMSE$, $MAE$ ve Yanlılık (Bias).
4. **What-If Finansal Simülatör:**
   - Elektrik tarifesi ($/kWh) ve yıkama maliyeti parametrelerine göre duyarlılık matrisi.

---

## 🛠️ Yerel Kurulum (Local Setup)

Projeyi yerel ortamda çalıştırmak için:

```bash
# 1. Repoyu klonlayın
git clone https://github.com/halukbakircii-creator/solarclever.git
cd solarclever

# 2. Gerekli kütüphaneleri yükleyin
pip install -r requirements.txt

# 3. Testleri çalıştırın
python -m pytest

# 4. Uygulamayı başlatın
streamlit run app.py
