# Optoplex + GlassFile Merger

Scriptul `optoplex_process_merger_ui.py` combină output-ul din cele 2 fluxuri într-un singur fișier **wide**:
- color/optoplex (1 rând / zi / placă)
- process/glassFile (pivot pe compartimente)
- merge final pe `(day, plate)`

## UI
```bash
python optoplex_process_merger_ui.py --gui
```

Din UI poți:
- selecta folderul rădăcină pentru Optoplex CSV
- selecta folderul rădăcină pentru `*_glassFile.csv`
- seta fișierul de output
- seta formatul (`parquet`/`csv`)
- seta compresia (`snappy`/`zstd`/`gzip` pentru parquet)
- alege tipul de merge (`inner`/`left`/`outer`)
- activa scanare recursivă
- filtra pe an (ex. `2025`, util pentru structuri `2025/02/02/...`)
- vezi progress bar + status live (scanare / parsing / merge / save)

## CLI (fără UI)
```bash
python optoplex_process_merger_ui.py \
  --optoplex-dir /date/optoplex \
  --process-dir /date/glass \
  --out /date/output/merged_wide.parquet \
  --format parquet \
  --compression snappy \
  --merge-how inner \
  --year 2025
```

## Process pipeline (minimal, ML-ready)
```bash
python process_pipeline_glassfile_to_parquet.py \
  --input /data/glass \
  --output /data/out/process.parquet \
  --keep-material-only \
  --include-seg-gas \
  --include-material-gas
```
