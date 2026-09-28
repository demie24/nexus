# NEXUS Virtual Industrial Environment & Factory Simulator

Dokumen ini memperincikan seni bina, model matematik-fizik, sistem suntikan senario, dan protokol pengangkutan telemetri bagi **NEXUS Virtual Industrial Environment**.

---

## 1. Topologi Kilang Maya (Virtual Factory Topology)

Simulator ini direka secara berpandukan konfigurasi (*configuration-driven*) dengan topologi kilang industri modular:

```text
FACTORY_01 (NEXUS Virtual Industrial Plant)
│
├── LINE_01 (Primary Machining Line)
│   ├── M01: CNC Milling Center (15 kW, 1500 RPM, 70°C nominal)
│   ├── M02: Precision Lathe Unit (12 kW, 1800 RPM, 62°C nominal)
│   └── M03: Precision Surface Grinder (18.5 kW, 3000 RPM, 74°C nominal)
│
└── LINE_02 (Assembly & Packaging Line)
    ├── M04: Robotic Arc Welder (24 kW, Statik / 0 RPM, 78°C nominal)
    ├── M05: Hydraulic Stamping Press (38 kW, 750 RPM, 150 bar, 71°C nominal)
    └── M06: High-Speed Packaging Unit (8.5 kW, 1200 RPM, 54°C nominal)
```

Setiap mesin ditakrifkan melalui objek `MachineSpec` dalam [`services/simulation/config.py`](file:///home/demie/nexus/services/simulation/config.py) tanpa sebarang nilai *hardcoded* dalam enjin fizik teras.

---

## 2. Model Fizik & Gandingan Parameter (Coupled Dynamics)

Simulator **tidak menggunakan nilai rawak bebas**, sebaliknya mensimulasikan hukum pemuliharaan dan hubungan gandingan antara parameter:

### 2.1 Keseimbangan Termal (Thermal Dynamics)
Suhu dalaman mesin dikira melalui persamaan pemindahan haba urutan pertama (*first-order thermal lag*):

$$\frac{dT}{dt} = \frac{1}{\tau} \left( T_{\text{target}} - T \right)$$

Di mana:
$$T_{\text{target}} = \frac{T_{\text{nominal}} \cdot (\text{load})^{1.3} \cdot (1 + 0.35 \cdot \text{bearing\_wear})}{\max(0.15, 1.0 - 0.75 \cdot \text{cooling\_degrad})}$$

### 2.2 Getaran Mekanikal (Vibration Dynamics)
Getaran nominal meningkat mengikut bebanan operasi, dan meningkat secara kuadratik apabila berlaku kerosakan galas (*bearing wear*):

$$V_{\text{true}} = V_{\text{nominal}} \cdot (0.85 + 0.30 \cdot \text{load}) + 8.5 \cdot (\text{bearing\_degrad})^2$$

### 2.3 Elektrik & Penggunaan Kuasa
Arus 3-fasa dan kuasa aktif:

$$I_{\text{true}} = I_{\text{base}} \cdot \text{load} \cdot (1.0 + 0.22 \cdot \text{bearing\_degrad})$$
$$P_{\text{kW}} = \frac{\sqrt{3} \cdot V \cdot I \cdot \cos(\phi)}{1000}$$

### 2.4 Kecekapan & Kadar Pengeluaran
Kecekapan merosot secara automatik sekiranya berlaku degradasi mekanikal, termal, atau bebanan lampau:

$$\text{Efficiency} = \max\left(0, 100 - 28 \cdot \text{wear}_{\text{bearing}} - 20 \cdot \text{wear}_{\text{cooling}} - 25 \cdot \max(0, \text{load} - 1.0)\right)$$

### 2.5 Hingar Sensor Terkawal (Sensor Noise)
Setiap parameter sensor ditambah dengan hingar Gaussian bertaburan normal:

$$X_{\text{meas}} = X_{\text{true}} + \text{Bias}_{\text{sensor}} + \mathcal{N}(0, \sigma^2)$$

---

## 3. Sistem Kitaran Hayat Senario Kegagalan (Scenario Engine)

Simulator menyediakan 5 senario rujukan:

| Senario | Jenis | Corak Telemetri | Tujuan Pengujian |
| :--- | :--- | :--- | :--- |
| **Scenario A** | `normal` | Semua telemetri berada dalam julat nominal | Baseline dan operasi stabil |
| **Scenario B** | `bearing_degradation` | Getaran ↑↑, Suhu ↑, Kecekapan ↓, Health Score ↓, Kebarangkalian Kegagalan ↑ | Pengesanan anomali mekanikal & RCA |
| **Scenario C** | `cooling_degradation` | Suhu ↑↑ (thermal lag), Kecekapan ↓ perlahan | Anomali termal & pengudaraan |
| **Scenario D** | `overload` | Beban 1.35x, Arus ↑↑, Kuasa ↑↑, Suhu ↑ | Ujian kapasiti elektrik & pemotongan beban |
| **Scenario E** | `sensor_anomaly` | Nilai getaran/suhu melonjak secara tiba-tiba tanpa kerosakan fizikal | Ujian ketahanan terhadap *false-positive* |

Setiap senario melalui kitaran hayat formal:
$$\text{PENDING} \longrightarrow \text{ACTIVE} \longrightarrow \text{ESCALATING} \longrightarrow \text{RECOVERING} \longrightarrow \text{COMPLETED}$$

---

## 4. Jam Simulasi & Penyeragaman Masa (Simulation Clock)

Simulator dilengkapi `SimulationClock` yang menyokong dua mod:
1. **Mod Jam Dinding Terlaras (*Time Dilation*):** Nisbah masa maya kepada masa sebenar (cth. `time_scale=10.0` bermakna 1 saat dunia sebenar bersamaan 10 saat masa simulasi kilang).
2. **Mod Langkah Terkawal (*Stepped Tick*):** Membolehkan ujian unit dan batch simulation melangkah $N$ saat secara diskret tanpa perlu menunggu masa sebenar.

---

## 5. Kepelbagaian Pengangkutan Telemetri (Transports Layer)

Data telemetri yang dijana disiarkan secara serentak ke 3 lapisan:
1. **In-Memory Ring Buffer:** Menyimpan 500 paket telemetri terkini bagi akses serta-merta tanpa overhead I/O.
2. **PostgreSQL Database:** Menyimpan telemetri ke jadual `telemetry` dan mengemas kini keadaan Digital Twin dalam jadual `machine_states`.
3. **Eclipse Mosquitto MQTT:** Menerbitkan mesej JSON ke topik hierarki industri:
   ```text
   nexus/factory/{factory_id}/line/{line_id}/machine/{machine_id}/telemetry
   ```
   Contoh topik sebenar:
   `nexus/factory/FACTORY_01/line/LINE_01/machine/M03/telemetry`

---

## 6. Arahan Penggunaan Antara Muka CLI (`nexus-sim`)

Simulator boleh dikawal terus menggunakan CLI:

### 6.1 Memulakan Penstriman Telemetri Berterusan
```bash
# Menstrim telemetri setiap 1 saat dengan pecutan masa 5x ke memori, database & MQTT
python -m apps.simulator.cli start --interval 1.0 --time-scale 5.0 --transports memory,db,mqtt
```

### 6.2 Menjalankan Senario Tertentu
```bash
# Memicu kerosakan galas pada mesin M03
python -m apps.simulator.cli scenario bearing_degradation --machine M03 --severity 0.85

# Memicu masalah sistem penyejuk pada mesin M01
python -m apps.simulator.cli scenario cooling_degradation --machine M01 --severity 0.90

# Memicu lonjakan sensor palsu (sensor anomaly) pada mesin M02
python -m apps.simulator.cli scenario sensor_anomaly --machine M02
```

### 6.3 Melangkah Secara Manual (Stepped Mode)
```bash
python -m apps.simulator.cli step --count 10 --dt 2.0
```

### 6.4 Mengukur Prestasi & Throughput (Benchmark)
```bash
python -m apps.simulator.cli benchmark --ticks 500
```

---

## 7. Keputusan Ujian & Penanda Aras Prestasi

* **Throughput:** > **51,000 bingkai telemetri sesaat** pada pemproses AMD Ryzen 5 (melepasi syarat minimum 10 Hz sebanyak **856 kali ganda**).
* **Kebolehulangan (Determinisme):** 100% data telemetri adalah seiras apabila menggunakan `seed` yang sama.
* **Integriti Data:** Menghasilkan telemetri patuh skema dengan penandaan `provenance = OBSERVED`.
