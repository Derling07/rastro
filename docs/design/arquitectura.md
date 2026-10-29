# Rastro · Arquitectura (NOVA, propuesta visual basada en `plan_rastro.md`)

```mermaid
flowchart LR
  subgraph Usuario
    U[Persona en el campo<br/>guardaparque / técnico]
  end
  subgraph Web["Web · Next.js en Vercel (FRONT)"]
    W1[Subir video y elegir paquete]
    W2[Panel: video anotado, contador, alertas, voz, reporte]
  end
  subgraph Datos["Supabase Free (CORE)"]
    DB[(runs · events · alerts · reports)]
    ST[(Storage: video difuminado)]
  end
  subgraph Worker["Worker Python + ffmpeg (ORION) · PC o GitHub Actions"]
    K[Cortar en trozos 60 s con 2 s de traslape]
    R[Unir pistas por IoU + re-entradas]
    M[Motor de reglas determinista<br/>conteos, cruces, densidad]
    X[Difuminar caras y placas]
    O[outputs/run_id/result.json]
  end
  subgraph Meta["Meta Model API"]
    SAM[SAM 3.1 · seguimiento en video]
    VT[Voice Transcribe · nota de voz]
  end
  subgraph Agente["Agente · Muse Spark Open en Baseten"]
    A[Herramientas: get_counts, get_events,<br/>verify_frame, raise_alert, write_report]
  end
  P[(Paquete JSON<br/>fauna · tránsito · multitudes)]

  U --> W1 --> K
  P --> K
  P --> M
  K --> SAM --> R --> M --> X --> O
  U -- nota de voz --> VT --> A
  M --> A --> O
  O --> DB
  X --> ST
  DB --> W2
  ST --> W2
```

Notas:
- Los números salen del motor de reglas, no del LLM; el agente solo verifica, alerta y redacta.
- El cambio de paquete en el panel lee corridas ya hechas; no recalcula en vivo.
