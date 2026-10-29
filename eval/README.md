# eval/ — set de evaluación (QA)

| Archivo | Qué es |
|---|---|
| `ground_truth.json` | Conteos únicos etiquetados a mano |
| `LABELING.md` | Protocolo (ffmpeg + inspección visual) |
| `score.py` | Métricas offline vs `result.json` / `summary.json` |
| `fixtures/` | `result.json` **MOCK** para pytest (no son corridas reales) |
| `tests/test_score.py` | pytest offline |
| `LICENSES.md` | Licencias de `data/` con flags |
| `GAPS.md` | Qué falta (tránsito / multitudes) |

```bash
# tests (sin API)
pytest eval/tests -q

# score contra corridas locales ya guardadas
python eval/score.py --outputs outputs/real
```

No llama a Meta ni Baseten. No imprime claves.
