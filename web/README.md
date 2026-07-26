# User as Code — interactive paper companion

A React website for the paper *User as Code: Executable Memory for Personalized Agents*.
It explains the mechanism and lets you interactively explore the graded cases bundled for
four benchmarks (LOCOMO, LongMemEval, Analytical Inference, Active Service). The LOCOMO
explorer currently contains the legacy 600-question subset, not the full 1,986-question suites.

## Stack
- Vite + React 18
- Tailwind CSS
- Recharts (interactive charts)
- Framer Motion (animation)

## Develop
```bash
npm install
npm run dev        # http://localhost:5173
```

## Build (static)
```bash
npm run build      # → dist/  (fully static, deployable anywhere)
npm run preview
```

## Data
The site is driven by compact JSON bundles in `public/data/`, generated from the raw
experiment results by:

```bash
python3 ../scripts/build_site_data.py
```

This reads `experiments/results/*.json`, the source benchmarks, and the active-service
scenario definitions, and writes:

| file | contents |
|------|----------|
| `locomo.json` | Legacy LOCOMO subset: the first 60 QAs from each of 10 conversations (600 total; not random) × 7 systems, with conversation-evidence context and dual-judge grades |
| `longmemeval.json` | 500 LongMemEval QAs × 7 systems, dual-judge grades |
| `analytical.json` | 100 analytical cases × 5 systems, with executed Python traces |
| `active.json` | 60 Active-Service scenarios with multi-session context + per-system runs |
| `summary.json` | aggregate tables / chart data (from the paper) |

Re-run the script if the underlying results change, then rebuild.

## Each explorer case shows
- **(a)** the benchmark result / gold answer
- **(b)** the context (conversation evidence, seeded sessions, or record set)
- **(c)** each system's response (including UaC's executed code trace)
- **(d)** the grading — dual-judged under Gemini 3 Flash and Claude Opus 4.7 where applicable
