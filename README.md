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
  # opțional: --cache-dir /date/output/.merge_cache --no-cache-read --no-cache-write --no-ml-ready
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

Notă: în merge-ul final, grosimea și viteza de proces sunt păstrate ca **o singură coloană globală** (`glassThickness_mm`, `nomProcessSpeed_mm`, `actProcessSpeed_mm`), nu pe fiecare compartiment/catod.
Target-urile pe compartiment sunt minimizate: `cX.actTargetMaterial2`/`cX.kwh2` se păstrează doar pentru compartimentele care au efectiv target2 nenul.

Dacă într-un batch nu există niciun compartiment cu material real, output-ul process păstrează doar coloanele globale (fără `cX.*`).

Target-urile per compartiment sunt expuse explicit ca `cX.actTargetMaterial1` și `cX.actTargetMaterial2` (iar `actTargetMaterial2` apare doar unde există real).

Debitele de material/main gas sunt disponibile per compartiment și ca `cX.mainGas1`, `cX.mainGas2`, `cX.mainGas3` (plus alias-urile legacy `cX.m1g`, `cX.m2g`, `cX.m3g`).

Valorile numerice process sunt rotunjite la max. 2 zecimale, cu excepția `actVacuumPressure` (păstrată la precizie completă).

Implicit, exportul final din merger aplică și un pas **ML-ready**: adaugă `dayOfWeek`, `month`, `weekOfYear`, normalizează tipurile cheie și ordonează stabil coloanele (poți dezactiva cu `--no-ml-ready` sau debifând checkbox-ul din UI).


## Cache pentru volume mari
- `optoplex_process_merger_ui.py` salvează cache per fișier în `<output_dir>/.merge_cache` pentru parsing color/process.
- `process_pipeline_glassfile_to_parquet.py` salvează cache per fișier în `<output_dir>/.process_cache`.
- Pentru control granular folosește `--cache-dir`, `--no-cache-read`, `--no-cache-write` (CLI) sau opțiunile din UI (Use cache / Save cache + folder).
