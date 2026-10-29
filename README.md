# Rastro

**Un solo motor** que sigue cosas en video sin contarlas dos veces, junta eso con notas de voz y deja que un agente escriba el reporte y lance alertas.

Cada sector es un **paquete JSON**. Si cambiás el paquete, el motor cuenta otra cosa sin tocar código.

> Meta Global AI Developer Hackathon 2026 — track Indie.  
> Todo el código de este repo se escribió durante el evento (a partir del 26 oct 2026).

## Demo en una frase

Conteo ingenuo: **11** apariciones. Rastro: **3** individuos. Mismo video.

## Paquetes del demo

| Paquete | Qué cuenta | Estado |
|---|---|---|
| `packs/fauna.json` | Coyotes / animales / persona en cámaras trampa | Motor listo (SAM en mock hasta tener `META_API_KEY`) |
| `packs/transito.json` | Giros en intersección | Pendiente (31 oct) |
| `packs/multitudes.json` | Densidad de personas | Pendiente (1 nov) |

## Cómo usa los modelos de Meta

| Modelo | Para qué | Dónde corre hoy |
|---|---|---|
| **SAM 3.1** | Seguir objetos en video | Meta Model API (`$META_API_KEY`) — cliente **verificado** oct 2026; mock sin clave |
| **Muse Voice Transcribe 1.0** | Notas de campo → texto con hablante | Meta Model API — cliente listo, modo mock |
| **Muse Spark Open** | Agente de reporte / alertas / verify_frame | Baseten (`$BASETEN_API_KEY`, modelo `meta-models/muse-spark-open-1026`) — **probado** |

## Arranque rápido

```bash
cd rastro
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# o: pip install -r requirements.txt && export PYTHONPATH=worker

# Probar Baseten (necesita BASETEN_API_KEY)
rastro probe-baseten

# Correr fauna con SAM simulado (no gasta créditos de Meta)
rastro run --pack fauna --video data/lila/coyote/DSCF0104.MP4 --mock-sam --hour 22

# Tests
pytest -q
```

## Estructura

```
rastro/
  packs/          fauna.json (+ tránsito/multitudes después)
  worker/rastro/  motor Python (SAM, voice, spark, tracking, rules, CLI)
  data/lila/      clips CDLA de Seattle(ish) Camera Traps (gitignored)
  tests/          pytest del conteo y las reglas
  DATA.md         fuente + licencia de cada clip
```

## Privacidad

- Sin reconocimiento facial.
- El paquete declara qué se difumina (`face`, `license plate`).
- Solo se guardan agregados y, si aplica, clips ya difuminados.

## Licencia

- **Código:** Apache-2.0 (propuesta; Derling todavía la confirma).
- **Datos LILA:** CDLA-Permissive — ver `DATA.md`.

## Qué falta (plan)

1. ~~Créditos / `META_API_KEY` → probar SAM~~ **Hecho**: SAM 3.1 + Voice verificados; ver `outputs/real/EVAL.md` (local, no en git).
2. Remuestreo ffmpeg (bajar a 10 fps, trozos de 60 s con traslape).
3. Difuminado real de caras antes de guardar.
4. Web Next.js + Supabase.
5. Paquetes tránsito y multitudes.
