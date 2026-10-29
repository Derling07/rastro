# Rastro · Diseño del panel de la demo (NOVA)

Estado: **propuesta** para FRONT. No toca `src/` ni `packs/`. Datos según `docs/OUTPUT_SCHEMA.md` v1.1.

## 1. Qué tiene que lograr
Una sola pantalla que cuente la historia del guion en 3 minutos: **subir → elegir paquete → ver el video anotado con el contador → nota de voz → reporte y alertas**, y que el **cambio de paquete en vivo** sea el momento memorable.

## 2. Dirección visual: "cámara trampa de noche"
El mundo del producto son cámaras trampa, CCTV y celulares en trípode: imagen infrarroja, sellos de hora quemados en el video, marcas de campo. El panel se ve como un **visor de campo**, no como un SaaS de tarjetas.

| Token | Hex | Uso |
|---|---|---|
| `--ink` | `#0E1512` | fondo (verde muy oscuro, no negro plano) |
| `--panel` | `#17221C` | superficies |
| `--line` | `#2C3B33` | bordes y divisores |
| `--text` | `#E6EDE8` | texto principal |
| `--muted` | `#93A69A` | texto secundario (contraste ≥ 4.5:1 sobre `--panel`) |
| `--pack` | cambia por paquete | acento del paquete activo |

Acento por paquete (lo que cambia en vivo): **fauna `#F2A93B`** (ámbar fósforo), **tránsito `#C8E34A`** (amarillo señal), **multitudes `#5CC8E0`** (cian). Alertas: alta `#FF6B5B`, info usa `--pack`. Máscaras de pista: paleta categórica de 8 colores, siempre con el ID escrito al lado (no depender solo del color).

Tipografía: **Barlow Condensed** (600/700) para números y el contador, como señalética de carretera; **Atkinson Hyperlegible** para todo lo demás. Autoalojadas con `next/font`. Escala: 14 / 16 / 20 / 28 / 44 / 120 px (el 120 es solo el contador).

Principio: lo audaz va en **un solo lugar, el contador "ingenuo vs Rastro"**. Todo lo demás es quieto.

## 3. Pantallas y estados
Ver `panel.html` (maqueta navegable, abrir en el navegador) y `wireframes.md`.

1. **Vacío / subir**: zona de arrastre (MP4/MOV H.264, ≤ 50 MB) + 3 clips de ejemplo precargados (resultados guardados, no gastan créditos).
2. **Configurar**: selector de paquete (3 chips), primer frame con herramienta para dibujar línea o zona (solo tránsito/multitudes), botón "Analizar video".
3. **Procesando**: barra por etapas reales del worker (cortar → SAM por concepto → unir pistas → reglas → agente). Cada etapa marca hecho/fallo. Sin porcentajes inventados.
4. **Resultado** (pantalla principal de la demo):
   - Izquierda: video con cajas/máscaras e ID, sello de hora, línea de tiempo con marcas de eventos (clic = saltar).
   - Derecha arriba: **contador** `90 → 2` (DSCF0112, detecciones crudas → coyotes únicos, medido) (ingenuo tachado, Rastro grande) + desglose por clase.
   - Derecha medio: **alertas** (severidad, mensaje, segundo del video).
   - Derecha abajo: **nota de voz** (reproductor, transcripción por turno con hablante) y **registro del agente** (herramientas que llamó, plegable).
   - Pestaña **Reporte**: resumen, especies/clases, recomendaciones, exportar PDF/CSV.
5. **Error**: formato no aceptado (WebM/VP9) → "Convertí el video a MP4 H.264"; worker apagado → "El procesador no está conectado; podés ver los ejemplos guardados".

## 4. El momento clave: cambiar de paquete en vivo
Secuencia de 900 ms al tocar otro chip (con `prefers-reduced-motion` se reduce a un corte simple):
1. 0–200 ms: el acento `--pack` hace transición de color en todo el panel.
2. 200–500 ms: las máscaras del video se desvanecen y entran las del nuevo paquete.
3. 300–900 ms: los dígitos del contador **ruedan** (tipo odómetro) al nuevo número; las clases se reordenan.
4. Debajo del chip aparece el nombre del archivo: `fauna.json` → `transito.json`. Ese texto es el gancho "mismo motor, otro archivo".

Regla de honestidad: el cambio solo muestra resultados **ya calculados** de una corrida real (`run_id` por paquete). Si no hay corrida, el chip lo dice ("Sin corrida para este video").

## 5. Componentes (para FRONT)
`UploadDrop`, `PackSwitcher`, `FrameDrawTool`, `StageProgress`, `AnnotatedPlayer` (canvas sobre `<video>`), `EventTimeline`, `CountHero` (ingenuo vs único + odómetro), `ClassBreakdown`, `AlertList`, `VoiceNote` (audio + turnos), `AgentLog`, `ReportView`, `ExportButtons`, `EmptyState`, `ErrorBanner`.

## 6. Mapeo de datos (OUTPUT_SCHEMA v1.1)
| UI | Campo |
|---|---|
| Contador | número tachado = detecciones crudas de SAM (campo pendiente en el esquema), número grande = `unique_count`, `by_class`; marca `is_mock` (ejemplo o medido) |
| Video | `artifacts.annotated_video` (ya trae máscaras pintadas). No dibujar cajas encima para no duplicar; `frames[].objects[].bbox` solo para el resaltado al pasar el mouse o al tocar un ID |
| Línea de tiempo | `events[]` + `alerts[].t_s` |
| Alertas | `alerts[].{id, severity, message, t_s}`; clic salta a `t_s` |
| Nota de voz | `voice.turns[].{speaker, start_s, end_s, transcript}`, solo si la nota es pública (`is_public`); si no, mostrar el resumen de `report` |
| Registro del agente | `agent_log[].{step, tool, detail}` |
| Reporte | `report` |
| Costo | `cost_usd` (pie del panel, pequeño) |
| Cambio de paquete | corridas con el mismo `source_video_id`, alternando por `pack.id` |

Datos de ejemplo: `docs/result.example.json` y `outputs/demo-real-coyote` (real). Los `demo-mock-*` se muestran con la marca "ejemplo".

## 7. Accesibilidad y responsive
- Teclado completo: chips con flechas, espacio para pausar, `J/L` para saltar entre eventos. Foco visible con `--pack`.
- Contador con `aria-live="polite"` para que el cambio se anuncie.
- Mobile-first: en < 900 px se apila video → contador → alertas → voz. La demo se graba en escritorio 1440×900.

## 8. Preguntas abiertas
Ninguna: ORION las respondió el 26 oct 2026.
