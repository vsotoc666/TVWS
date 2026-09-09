# Diagrama y Arquitectura del Enlace TVWS (Versión 5.1 - Ajuste Discone)

Arquitectura final hiper-optimizada. Todo el sistema utiliza el estándar SMA con cables LMR-200/LMR-100. Se incluye la corrección del adaptador específico para acoplarse directamente a la base de la antena Discone Tram 1411.

---

## 1. NODO GATEWAY (Base con Fibra)

```mermaid
graph LR
    classDef puerto fill:#3b82f6,stroke:#1e3a8a,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef equipo fill:#f1f5f9,stroke:#64748b,stroke-width:2px,color:#000000;
    classDef antena fill:#fecaca,stroke:#dc2626,stroke-width:4px,color:#000000,font-weight:bold;
    classDef lna fill:#d9f99d,stroke:#4d7c0f,stroke-width:3px,color:#000000,font-weight:bold;
    classDef pasamuros fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#ffffff,font-weight:bold;

    %% --------------------------------
    %% RUTA 1: TRANSMISIÓN (TX1)
    %% --------------------------------
    SDR_TX1("SDR: Puerto TX1<br/>SMA Hembra"):::puerto
    ATT1["Atenuador en línea<br/>SMA Hembra <--> SMA Macho"]:::equipo
    PA1["Amplificador 2W<br/>SMA Hembra <--> SMA Hembra"]:::equipo
    PM_TX1["Pasamuros Pared<br/>SMA Hembra <--> SMA Hembra"]:::pasamuros
    ANT_TX1((("📡 ANTENA 1: LPDA TX<br/>SMA Hembra (PCB)"))):::antena

    SDR_TX1 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> ATT1
    ATT1 -- "DIRECTO" --> PA1
    PA1 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> PM_TX1
    PM_TX1 -- "Cable LMR-200 (12ft / 3.6m)<br/>SMA Macho <--> SMA Macho" --> ANT_TX1

    %% --------------------------------
    %% RUTA 2: RECEPCIÓN (RX1)
    %% --------------------------------
    ANT_RX1((("📡 ANTENA 2: LPDA RX<br/>SMA Hembra (PCB)"))):::antena
    LNA1["LNA Nooelec<br/>SMA Hembra <--> SMA Hembra"]:::lna
    PM_RX1["Pasamuros Pared<br/>SMA Hembra <--> SMA Hembra"]:::pasamuros
    SDR_RX1("SDR: Puerto RX1<br/>SMA Hembra"):::puerto
    
    ANT_RX1 -- "Pigtail flexible (30cm)<br/>SMA Macho <--> SMA Macho" --> LNA1
    LNA1 -- "Cable LMR-200 (12ft / 3.6m)<br/>SMA Macho <--> SMA Macho" --> PM_RX1
    PM_RX1 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> SDR_RX1

    %% --------------------------------
    %% RUTA 3: SENSADO (RX2)
    %% --------------------------------
    ANT_SENS((("📡 ANTENA 3: DISCONE<br/>Base SO-239 (UHF Hembra)"))):::antena
    ADAPT_DISC["Adaptador<br/>PL-259 Macho <--> SMA Hembra"]:::equipo
    PM_RX2["Pasamuros Pared<br/>SMA Hembra <--> SMA Hembra"]:::pasamuros
    SDR_RX2("SDR: Puerto RX2<br/>SMA Hembra"):::puerto
    
    ANT_SENS -- "DIRECTO" --> ADAPT_DISC
    ADAPT_DISC -- "Cable LMR-200 (12ft / 3.6m)<br/>SMA Macho <--> SMA Macho" --> PM_RX2
    PM_RX2 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> SDR_RX2
```

---

## 2. NODO CLIENTE (Zona Rural)

```mermaid
graph LR
    classDef puerto fill:#3b82f6,stroke:#1e3a8a,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef equipo fill:#f1f5f9,stroke:#64748b,stroke-width:2px,color:#000000;
    classDef antena fill:#fecaca,stroke:#dc2626,stroke-width:4px,color:#000000,font-weight:bold;
    classDef lna fill:#d9f99d,stroke:#4d7c0f,stroke-width:3px,color:#000000,font-weight:bold;
    classDef pasamuros fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#ffffff,font-weight:bold;

    %% --------------------------------
    %% RUTA 1: TRANSMISIÓN (TX1)
    %% --------------------------------
    SDR_TX2("SDR: Puerto TX1<br/>SMA Hembra"):::puerto
    ATT2["Atenuador en línea<br/>SMA Hembra <--> SMA Macho"]:::equipo
    PA2["Amplificador 2W<br/>SMA Hembra <--> SMA Hembra"]:::equipo
    PM_TX2["Pasamuros Pared<br/>SMA Hembra <--> SMA Hembra"]:::pasamuros
    ANT_TX2((("📡 ANTENA 1: LPDA TX<br/>SMA Hembra (PCB)"))):::antena

    SDR_TX2 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> ATT2
    ATT2 -- "DIRECTO" --> PA2
    PA2 -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> PM_TX2
    PM_TX2 -- "Cable LMR-200 (12ft / 3.6m)<br/>SMA Macho <--> SMA Macho" --> ANT_TX2

    %% --------------------------------
    %% RUTA 2: RECEPCIÓN (RX1)
    %% --------------------------------
    ANT_RX2((("📡 ANTENA 2: LPDA RX<br/>SMA Hembra (PCB)"))):::antena
    LNA2["LNA Nooelec<br/>SMA Hembra <--> SMA Hembra"]:::lna
    PM_RX2_CLI["Pasamuros Pared<br/>SMA Hembra <--> SMA Hembra"]:::pasamuros
    SDR_RX2_CLI("SDR: Puerto RX1<br/>SMA Hembra"):::puerto

    ANT_RX2 -- "Pigtail flexible (30cm)<br/>SMA Macho <--> SMA Macho" --> LNA2
    LNA2 -- "Cable LMR-200 (12ft / 3.6m)<br/>SMA Macho <--> SMA Macho" --> PM_RX2_CLI
    PM_RX2_CLI -- "Pigtail LMR-100 (50cm)<br/>SMA Macho <--> SMA Macho" --> SDR_RX2_CLI
```
