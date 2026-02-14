# Optimizer (Engineer Mode) — Functional Specification

## 1) Purpose
Optimizer is an on-demand process assistant for Engineer Mode. It recommends safe and cost-aware adjustments to **power** and **gas** knobs in order to hit a selected color target within tolerance.

It does **not** auto-apply changes and does **not** lock UI controls. It only runs when the user clicks **Run**.

---

## 2) Scope and Constraints

### Editable knobs (and only these)
- Power: `cX.pwr`
- Main gases: `cX.m1g`, `cX.m2g`, `cX.m3g`
- Segment gases: `cX.s1g` ... `cX.s11g`

### Non-editable variables
- Any non-knob parameter (e.g., line speed) is read-only context.

### Optimization modes
- **SAFE (default):** prioritize small deltas and strict limits.
- **AGGRESSIVE:** allow larger deltas if required to reach tolerance.

---

## 3) User Inputs

### A. Context selectors
- Product (required)
- Day (optional)
- Plate (optional)
- Scope:
  1. one-shot per plate
  2. average per plate
  3. subset of plates/day

### B. Target selector
- Target type:
  - Profile (positions)
  - Summary (`mean`, `std`, `range`, etc.)
- Channel: `L`, `a`, `b`
- Device: `RG` (extensible)
- Any dataset column matching the selected target family is valid.

### C. Tolerances (manual, per product)
- Setpoint + tolerance bands
- Precision: 1 decimal
- For profile targets:
  - per-position tolerance, or
  - global band
- For summary targets:
  - scalar tolerance

### D. Active knobs
- User selects which knobs are active (checkboxes)
- Per-knob boundaries: min / max / step

---

## 4) Automatic Relevance Detection

### 4.1 Active/used compartments
A compartment is considered **used** if data indicates real process usage in the selected subset, e.g. `cX.pwr` is present and non-null/non-zero/variable.

### 4.2 Available knobs
Infer directly from column presence:
- `cX.pwr` => power knob available
- `cX.m1g..m3g` => main gas knobs available
- `cX.s1g..s11g` => segment gas knobs available

### 4.3 Available targets
Any existing target column for the chosen target family (e.g. `*_RG_*`) is selectable.

---

## 5) Runtime Flow

## Step 1 — Dataset build
- Filter by product and optional day/plate/scope.
- Construct:
  - `X`: selected feature groups + candidate knobs
  - `y`: selected target
- If insufficient rows:
  - suggest widening date range,
  - suggest summary target (e.g., mean),
  - suggest reduced knob granularity (e.g., pwr + main gases only).

## Step 2 — Model train (on demand)
Trigger on **Run**:
- Option A: train a fresh model
- Option B: use latest existing model

Minimum quality gate:
- train/validation sanity metric is logged and shown.

Model role in optimizer:
- simulator (`knob deltas` -> `predicted target`).

## Step 3 — Baseline
Compute current expected output before changes:
- Profile target: full vector
- Summary target: scalar

Also compute uncertainty estimate:
- simple spread/statistical band from filtered data.

UI:
- baseline profile line
- tolerance band overlay

## Step 4 — Objective composition
Composite objective:
1. Reach tolerance (high penalty outside band)
2. Keep deltas small (stability)
3. Minimize operating cost (energy + gas)
4. Optional stability penalties (if available): arc-rate, sigma, etc.

## Step 5 — Hard constraints
- Only modify allowed knobs.
- Respect per-knob bounds.
- Optional axis control: allow-only power / allow-only gas / both.
- Unused compartments cannot be modified.

## Step 6 — Candidate search
- Start from current settings.
- Generate delta candidates:
  - prioritize top knobs by feature importance / sensitivity,
  - expand search breadth if tolerance is not met.
- Keep top `N` scored candidates (default: 20).

Candidate score combines:
- tolerance violation penalty
- delta magnitude penalty
- cost penalty
- optional process instability penalty

## Step 7 — Return recommendations
Return top 3 solutions with:
- knob delta list
- predicted result (profile + summary)
- confidence/risk indicator
- cost impact (`per plate`, `per day`, `per month`)

---

## 6) UI/Visualization

### Chart 1 — Actual vs Predicted Profile
- Line 1: baseline/actual
- Line 2: predicted after selected solution
- Tolerance band
- Tooltip per position: actual, predicted, delta

### Chart 2 — Knob Delta View
- Bar/table view of modified knobs only
- Group by compartment (`c4`, `c5`, `c7`, ...)
- Show absolute and/or percentage delta

### Chart 3 — Cost & Savings
Cards:
- €/plate
- €/day
- €/month

Breakdown:
- energy cost (kWh)
- gas cost (main + segment)

Inputs:
- `price_kWh`
- gas pricing map (per channel or per gas family)

---

## 7) Apply & Verify (Feedback Loop)

## 7.1 Operator workflow
After choosing a solution and applying in production:
- mark **Applied**
- select plate ID / time window / day
- optionally record actual applied deltas (if partial or modified)

System fetches:
- realized process values
- realized color output

Then compares:
- predicted vs realized profile
- predicted vs realized summary metrics

## 7.2 Root-cause hints for mismatch
Possible explanations:
- applied deltas differ from proposal
- extrapolation outside historical domain (high risk)
- process drift/instability during run (vacuum, sigma voltage, arc-rate)
- changed active compartment pattern
- hidden/unmeasured variables

## 7.3 Learning path
Store experiment triplets:
- proposed -> applied -> realized

On next retraining:
- include these records,
- optionally increase penalties for regions with recurrent model error.

---

## 8) Control Behavior
- Runs only on explicit **Run** action.
- Modes:
  - `Run with train` (train + optimize)
  - `Optimize using existing model`
  - `SAFE / AGGRESSIVE` toggle
- Never blocks operators; advisory-only.

---

## 9) Engineer-Facing Final Output Template
Each run must produce a compact, executable summary:

1. **Goal:** selected target + tolerance
2. **Current:** baseline (numeric + profile view)
3. **Best action:** knob deltas
4. **Expected result:** predicted profile + summary
5. **Cost impact:** €/plate, €/day, €/month
6. **Risk:** low/medium/high + reason
7. **Apply & verify:** plate selector + prediction vs reality comparison

---

## 10) Acceptance Criteria
- User can select any supported target column and define tolerances.
- Optimizer modifies only power/gas knobs and respects bounds.
- Top 3 recommendations are returned with predicted impact + cost + risk.
- Profile chart overlays baseline, prediction, and tolerance band.
- Apply/verify flow exists and logs proposed/applied/realized triplets.
- SAFE is default mode; AGGRESSIVE is available.
- Optimizer is manual-run only.
