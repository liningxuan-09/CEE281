# CEE281 Freeway On-Ramp Simulation

A microscopic traffic simulation of a single-lane freeway with one on-ramp and an acceleration lane, for the CEE281 project "ACC Penetration and Freeway Bottleneck Performance". Vehicles are human-driven (HDV, IDM+CAH) or, at a chosen share, equipped with adaptive cruise control (ACC). A second human-driver model (Gipps) is planned but not implemented yet.

> **Status: baseline, TMC and ACC.** The `Config` defaults (0% ACC) reproduce `results/baseline/`. Detector reports, queue estimate and forecast, and ALINEA ramp metering are in `model.py`; `tmc_compare.py` compares ALINEA with no control on many seeds (`results/tmc_alinea/`). ACC vehicles (`acc_share`) use the Gunter et al. (2020) law with a string-stable k_v = 0.80 (the fitted k_v = 0.2692 is kept as the ablation); `acc_compare.py` compares 0, 25, 50 and 75% ACC on the evaluation seeds. See [ACC study](#acc-study) for the questions, parameter rules and results. [Reproducing the figures and tables](#reproducing-the-figures-and-tables) lists the command behind every result figure and table.

---

## Contents

1. [Quick start](#quick-start)
1. [Reproducing the figures and tables](#reproducing-the-figures-and-tables)
2. [What is simulated](#what-is-simulated)
3. [ACC study](#acc-study)
4. [Running the model](#running-the-model)
5. [Saved outputs](#saved-outputs)
6. [Run log in `results/`](#run-log-in-results)
7. [Project layout](#project-layout)
8. [Checks and validation](#checks-and-validation)
9. [Known limitations](#known-limitations)
10. [References and attribution](#references-and-attribution)

---

## Quick start

```bash
cd ~/Desktop/"CEE281 Project"
python3 -m pip install -r requirements.txt   # numpy, matplotlib, Pillow
python3 -B -m unittest test_model test_io    # 56 tests
python3 -B run_demo.py                       # run once, print a summary, save nothing
python3 -B run_demo.py --save --gif --output results/<descriptive_name>
python3 -B feasibility.py                    # check the baseline on the development seeds
```

Open `results/<run>/classroom_demo.html` in a browser to see everything in one place. `-B` stops Python from writing `__pycache__` folders. The three demonstration pages share one layout: `results/baseline/seed9/` (no control), `results/tmc_alinea/seed9/` (ALINEA) and `results/acc_main/seed9_B50/` (50% ACC; ACC vehicles have a blue outline in the replay).

---

## Reproducing the figures and tables

Python 3.10 with NumPy, Matplotlib and Pillow (`requirements.txt`). All commands run from the project folder.

**Redraw every summary figure from the saved results** (about 1 minute on 4 cores):

```bash
sh make_figures.sh
```

**Rerun the experiments.** The 20-seed comparisons are saved in `results/`; each folder has a `run.sh` that recreates its `comparison.json` (roughly 2 minutes per 5 seeds and case set on 4 cores). Demonstration runs never overwrite an existing folder, so pass a new `--output`.

| Figure or table | Source file(s) | Command |
|---|---|---|
| Road layout and TMC decision trace (seed 9) | `results/tmc_alinea/seed9/detector_layout.png`, `tmc_timeline.png` | `python3 -B run_demo.py --control alinea --save --output results/<new>` |
| Arrival check (Poisson) | `results/baseline/arrivals/` | `python3 -B arrival_check.py` |
| Speed map without control (seed 9) | `results/baseline/seed9/speed_heatmap.png` | `python3 -B run_demo.py --save --output results/<new>` |
| ALINEA vs. no control on 20 seeds, detector defects; seed-by-seed figure | `results/tmc_alinea/eval_seeds_101-120/` | `sh results/tmc_alinea/eval_seeds_101-120/run.sh`, then `python3 -B seed_figure.py` |
| TMC changed-demand test | `results/tmc_alinea/demand/eval_seeds_101-120/` | `sh results/tmc_alinea/demand/run.sh` (ends with `tmc_demand.py`) |
| ACC share study (table and summary figure) | `results/acc_main/eval_seeds_101-120/` | `sh results/acc_main/eval_seeds_101-120/run.sh`, then `python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110` |
| Trajectories A vs. B50 (seed 110) | `results/acc_main/seed110_trajectories.png` | `python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110 --trajectories` |
| k_v ablation | `results/acc_ablation_kv/` | `sh results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/run.sh`, then the `--compare` line in `make_figures.sh` |
| Sensor delay (failure condition) | `results/acc_sensor_delay/` | `sh results/acc_sensor_delay/delay_0.5s/eval_seeds_101-120/run.sh` and `delay_1.0s/...`, then the `--compare` line in `make_figures.sh` |
| h ablation; ACC at ramp peak 350/550 | `results/acc_ablation_h/`, `results/acc_demand/` | the `run.sh` in each subfolder |
| Platoon disturbance and queue discharge tests | `results/acc_main/mechanism_tests.txt` | `python3 -B acc_mechanism.py` |
| Unit tests | – | `python3 -B -m unittest test_model test_io` |

---

## What is simulated

```text
 mainline entry                         acceleration lane            exit
 0 ─────────────────────────────────── 1.2 ════════════ 1.5 ─────────── 2.0 km
                                      /   ramp vehicles change lane here
                    ramp road (200 m)/
            ramp entrance ──────────┘
```

| Item | Default | `Config` field |
|---|---|---|
| Mainline | 1 lane, 0–2 km, free exit | `road_end` |
| Ramp | 200 m ramp road, then a 450 m acceleration lane beside the mainline from 1.05 to 1.5 km | `ramp_length`, `acc_length`, `merge_x` |
| Ramp speed | vehicles enter the ramp at 60 km/h and drive at up to 60 km/h on the ramp road; on the acceleration lane they speed up toward the mainline speed | `ramp_entry_speed`, `ramp_v0`, `acc_lane_a` |
| Demand | Poisson. Mainline 1,700 veh/h for 0–40 min. Ramp 100 veh/h (0–5 min), 450 veh/h (5–35 min), 0 (35–40 min). Run lasts 60 min. A clear merge bottleneck in which only a few ramp vehicles wait at the end of the acceleration lane | `main_profile`, `ramp_profile`, `demand_end`, `duration` |
| Seed | 9 for the demonstration runs; comparisons use the 20 evaluation seeds 101–120 | `seed` |
| Yielding | **none.** Mainline vehicles never open a gap or change lanes | – |
| Ramp control | none; a fixed release rate at the ramp entrance can be switched on for the TMC test | `ramp_release_rate` |
| Car following | IDM+CAH (Kesting, Treiber & Helbing 2010): v0 = 120 km/h, T = 1.2 s, a = 2.0 m/s², b = 2.0 m/s², s0 = 2 m, length 5 m, coolness 0.99 | `v0`, `T`, `a`, `b`, `s0`, `length`, `cool` |
| ACC vehicles | share of both streams (default 0). Each arrival draws one number from its own random stream, so arrivals are identical for every share and assignments are nested | `acc_share` |
| ACC, main controller | Gunter et al. (2020): u = k_p [s − (η + h v)] − k_v (v − v_leader); k_p = 0.0131 s⁻², η = 7.57 m (their fit), h = 1.27 s (project choice: 100% ACC capacity at v0 = IDM capacity), **k_v = 0.80 s⁻¹** (project choice: smallest round value meeting their string-stability criterion k_p h² + 2 k_v h − 2 ≥ 0; their fit 0.2692 fails it). Cruise = the IDM free-road term. Inputs: own speed, gap and speed of the vehicle directly ahead in the same lane. The driver takes over (HDV law) when it brakes harder than 2 m/s² and harder than the ACC. On the ramp road and the acceleration lane ACC vehicles drive and merge like HDVs | `acc_kp`, `acc_kv`, `acc_eta`, `acc_h`, `acc_takeover_b` |
| Physical limits | acceleration clipped to [−4, +2] m/s² | `amin`, `amax` |
| Integration | ballistic update, dt = 0.1 s | `dt` |
| Evaluation window | 300–2400 s | `eval_start`, `demand_end` |

**Why IDM+CAH with a = 2.0 and T = 1.2 s.** With the literature value a = 1.4 m/s², IDM platoons amplify small disturbances below about 60 km/h. The merge then produced stop-and-go waves below 30 km/h, which is not realistic for a single freeway lane at this demand. With a = b = 2.0 m/s², platoons are string-stable at all speeds. CAH stops a follower from emergency braking when a merging vehicle cuts in at a short gap without being slower. Single-lane capacity is about 2,190 veh/h.

**How a ramp vehicle merges** (`merge_test`, `target_speed` in `model.py`)

1. It enters the ramp road at 60 km/h. If the entrance is blocked, it waits in a counted queue.
2. On the acceleration lane it speeds up and lines up with the nearest mainline gap it could reach.
   - Side by side with a mainline car, it pushes ahead if it is in front; otherwise it drops back.
   - It lets a faster car close behind it pass.
3. It changes lane when the gap is acceptable:
   - both net gaps stay above a minimum, also 2 s later at current speeds;
   - neither it nor its new follower would have to brake harder than a budget, judged with IDM+CAH.
   - The budget grows from 2 to 4 m/s², and the minimum gap shrinks, toward the lane end.
4. In the last 60 m, or once it would have to start braking for the lane end, it takes any gap that is physically safe, or one with room to accelerate briskly.
5. If no gap comes, it brakes to a stop at the lane end and waits. On the demonstration seed 9 this never happens; on the evaluation seeds it happens 3.8 times per run on average (see [Known limitations](#known-limitations)).

---

## ACC study

**Main question.** With the same demand and ramp conditions, how does the share of ACC vehicles change total delay, bottleneck discharge and the growth of merge-induced speed disturbances at the on-ramp merge, compared with all-human traffic?

**Ablation (CEE281).** Does string stability decide whether ACC harms the bottleneck? Same control law, spacing, takeover, demand and seeds; only the speed-difference gain differs: k_v = 0.2692 s⁻¹ (Gunter et al. fit, not string stable) versus 0.80 s⁻¹ (main controller).

**Parameter rules (main controller).** Published values come from one vehicle and its test conditions, not from this merge. The control law, k_p = 0.0131 s⁻² and η = 7.57 m are as published; the two parameters tied to the study follow stated rules:

| Parameter | Rule | Value (published) |
|---|---|---|
| h | 100% ACC capacity at v0 equals the IDM capacity, so the ACC share does not act through capacity (the study is not about capacity) | 1.27 s (1.6881 s) |
| k_v | smallest value, rounded up to 0.05, meeting the string-stability criterion k_p h² + 2 k_v h − 2 ≥ 0 (Gunter et al. 2020); only the damping term changes, since meeting it with k_p instead would need 0.82 s⁻², i.e. 8 m/s² for a 10 m gap error | 0.80 s⁻¹ (0.2692 s⁻¹) |

**Results** (20 evaluation seeds 101–120, mean total delay in veh·h; A = 0% ACC = 14.9):

| | B25 | B50 | B75 | Folder |
|---|---:|---:|---:|---|
| Main controller (k_v = 0.80) | 14.5 | 14.5 | 14.0 | `results/acc_main/` |
| Ablation: fitted k_v = 0.2692 | 51.2 | 83.0 | 124.6 | `results/acc_ablation_kv/` |

- **Main question.** With the main controller total delay does not change; the deep queue at the merge almost disappears (congestion 251 s → 12 s per run at B75), shallow slowdowns spread further upstream, delay moves from the ramp to the mainline, and hard braking right after cut-ins becomes more frequent.
- **Ablation.** With the fitted gain (not string stable) the bottleneck collapses at every share: queue discharge falls by up to a third and stop-and-go waves reach the entrance. With k_v = 0.80 it does not (`results/acc_ablation_kv/ablation_kv_comparison.png`). String stability decides the outcome.

**Further tests** (main controller unless noted; same 20 seeds; mean total delay in veh·h, A in brackets):

| Test | B25 | B50 | B75 | Result | Folder |
|---|---:|---:|---:|---|---|
| Ramp peak 350 veh/h (A 8.3) | 8.2 | 8.2 | 7.7 | almost no bottleneck; ACC changes little | `results/acc_demand/` |
| Ramp peak 450 veh/h, main (A 14.9) | 14.5 | 14.5 | 14.0 | unchanged total delay | `results/acc_main/` |
| Ramp peak 550 veh/h (A 32.5) | 26.2 | 24.9 | 24.4 | −19 to −25%: ACC prevents ramp vehicles from stopping at the lane end | `results/acc_demand/` |
| Sensor delay 0.5 s (A 14.9) | 20.4 | 27.5 | 33.4 | string stability lost; up to 2.2 × A | `results/acc_sensor_delay/` |
| Sensor delay 1.0 s (A 14.9) | 31.7 | 54.1 | 77.0 | up to 5.2 × A: **failure condition** | `results/acc_sensor_delay/` |
| Ablation h = 1.69 s, the fitted gap setting (A 14.9) | 19.8 | 29.6 | 41.6 | lane capacity below demand at the entrance; justifies h = 1.27 s | `results/acc_ablation_h/` |

- **Changed demand** (required by the guide): the main controller never raises total delay; its benefit grows with the merge load.
- **Degraded information** (required): a sensor delay of 0.5 s already removes the string stability and doubles delay at B75; string stability must be designed with the delay included.
- **Second ablation (h)**: with the fitted h = 1.69 s the long gaps cut the mainline's capacity below its demand, so delay comes from a queue at the entrance, not from merge disturbances.

## Running the model

Nothing is written to disk unless you ask for it.

| Command | What it does |
|---|---|
| `python3 -B run_demo.py` | Run the default scenario and print the summary JSON. |
| `python3 -B run_demo.py --seed 42 --dt 0.05` | Change the demand seed or the time step (dt must divide 1 s). |
| `python3 -B run_demo.py --save --output results/<descriptive_name>` | Export tables, figures and the HTML report to a new folder. Without `--output`, a timestamped folder is used. Never overwrites an existing folder. |
| `python3 -B run_demo.py --save --gif` | Also export the replay GIF (about 18 MB, adds a minute or two). |
| `python3 -B run_demo.py --save --validate` | Also run the seed and time-step checks and save `validation.json`. |
| `python3 -B validate.py --save FILE.json` | Only the checks: seeds 21/7/42, dt = 0.1/0.05/0.025 s. |
| `python3 -B feasibility.py --save FILE.json` | Bottleneck feasibility check: 13 development seeds plus the selected seed, each with and without ramp demand, and the selected seed again at dt = 0.05 s. |
| `python3 -B run_demo.py --control alinea` | Same scenario with ALINEA ramp metering; the ramp signal runs a 2 s green (one car) then red, cycle 3600/r = 4–18 s (`--target-occ 0.14` changes o*, `--signal 2 2` the green and minimum red, `--rate-max` the maximum rate). |
| `python3 -B run_demo.py --control alinea --miss 0.02 --occ-noise 0.02 --report-delay 30` | Detector defects: missed passages, occupancy noise, delayed reports. |
| `python3 -B run_demo.py --control alinea --dropout 1200 1500` | Lose all detector reports ending between 1200 and 1500 s (tests hold and fallback). |
| `python3 -B tmc_compare.py --seeds 101-110 --save FILE.json` | No control vs. ALINEA vs. ALINEA with lost reports on the same seeds; paired delay differences. `--cases A,A-ALINEA,A-ALINEA-miss2,...` picks cases (detector defects: miss2, noise2, delay30). Changed demand: `A-R350`, `A-R550`, `A-M1500`, `A-M1900` and their `A-ALINEA-...` versions (`results/tmc_alinea/demand/run.sh`). `--merge A.json B.json --save C.json` combines seed ranges. |
| `python3 -B run_demo.py --acc-length 300 [--control alinea]` | Same run with another acceleration lane length (default 450 m; the lane always ends at 1.5 km). |
| `python3 -B run_demo.py --acc-share 0.5 [--acc-controller gunter] [--save --gif --output results/<name>]` | Same scenario with 50% ACC vehicles (both streams); `--acc-controller` picks stable (main, k_v = 0.80, default) or gunter (fitted k_v = 0.2692, the ablation). |
| `python3 -B acc_compare.py --controller stable --seeds 101-105 --save FILE.json` | ACC study: A (0%) vs B25, B50, B75 on the same seeds, with paired changes; `--controller stable|gunter`. Test conditions: `--ramp-peak 550`, `--set acc_sensor_delay=0.5`, `--set acc_h=1.6881`; `--a-from REPORT` reuses case A when only ACC fields change. `--merge A.json B.json --save C.json` combines seed ranges. |
| `python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110` | Summary figure and four-case speed maps for one controller's study. `--compare R1.json R2.json --labels ... --out FILE.png` draws controllers side by side. |
| `python3 -B acc_mechanism.py` | Deterministic platoon-disturbance and queue-discharge tests for the main controller, the fitted gain (k_v ablation), sensor delays of 0.5 and 1.0 s, and h = 1.69 s. |
| `python3 -B make_gif.py results/<run>` | Rebuild the GIF for a saved run. |
| `python3 -B replot.py results/<run>` | Re-render an old run with the current figures, report and GIF into `results/<run>/replot/`. Nothing is re-simulated. |

---

## Saved outputs

All figures share one speed colour scale: dark red is slow, pale blue-gray is free flow. Figures, the HTML replay and the GIF stop one minute after the last vehicle exits ("network empty").

| File | What it shows |
|---|---|
| `classroom_demo.html` | **Start here.** Headline numbers, an interactive replay (whole road plus a zoomed merge area with the ramp and acceleration lane), every figure with a reading guide, the summary and the configuration. |
| `simulation_replay.gif` | Replay for slides. Vehicles are drawn as cars; frames are interpolated so cars never appear to roll backwards. |
| `speed_heatmap.png` | Mean mainline speed by time and position. The bottleneck is the slow region ending at the acceleration lane. |
| `trajectories.png` | One line per mainline vehicle, coloured by speed. |
| `merge_speed.png` | Speed upstream, approaching and downstream of the merge over time. |
| `merge_events.png` | Where and at what speed each merge happened, and the braking it caused behind. |
| `trip_delay.png` | Delay of each completed trip by arrival time and origin. |
| `with_ramp_summary.json` | All scalar metrics and the exact configuration. |
| `with_ramp_{trajectories,events,trips,crossings,logs}.csv` | Raw tables (`crossings` = true position crossings used for the discharge flow, not TMC detectors). |
| `with_ramp_reports.csv` | 30 s detector reports (count, occupancy, speed, quality flag), from the TMC version on. |
| `with_ramp_tmc.csv` | TMC runs only. One row per TMC cycle: measured and true occupancy, estimated and true queue, forecast, previous and new rate, mode, releases. |
| `with_ramp_raw.json` | Everything above in one file; `make_gif.py` and `replot.py` read it. |
| `validation.json` | Only with `--validate` (seed and time-step checks). Not saved for the current default yet. |
| `acc_trajectories.png` | ACC runs only. Ten minutes of mainline trajectories around the slowest period, by vehicle type (ACC blue, human orange) and by speed. |

**Units:** internally m, s and m/s; exported positions in km and speeds in km/h; times and delays in seconds.

---

## Run log in `results/`

```text
results/
├── baseline/            no ramp control, no detectors in the loop
│   ├── seed9/           demonstration seed (clear bottleneck), with GIF and classroom_demo.html
│   └── arrivals/        Poisson arrival check (arrival_check.py)
├── acc_main/            main ACC study (k_v = 0.80): 0, 25, 50, 75% ACC, unmetered ramp (README = prediction, result)
│   ├── seed9_B50/       demonstration run with 50% ACC, same page layout as baseline/seed9 and tmc_alinea/seed9
│   ├── seed110_speed_maps.png, seed110_trajectories.png
│   └── eval_seeds_101-120/  comparison.json, acc_summary.png, parts/, run.sh
├── acc_ablation_kv/     ablation k_v = 0.2692 vs 0.80: ablation_kv_comparison.png, mechanism_tests.txt
│   └── fitted_kv_0.2692/   the run with the fitted gain (same cases and seeds): the collapse and its diagnosis
├── acc_ablation_h/      ablation h = 1.69 vs 1.27 s: ablation_h_comparison.png, h_1.69/
├── acc_demand/          changed demand, ramp peak 350 and 550 veh/h: demand_comparison.png, peak_350/, peak_550/
├── acc_sensor_delay/    degraded information, sensor delay 0.5 and 1.0 s: delay_comparison.png, delay_0.5s/, delay_1.0s/
├── tmc_alinea/          ALINEA ramp metering driven by detector reports
│   ├── seed9/                    same seed with ALINEA (controller trace in classroom_demo.html)
│   ├── eval_seeds_101-120/
│   │   ├── comparison.json        no control vs. ALINEA vs. lost reports vs. detector defects
│   │   ├── parts/part_*.json      the batches it was merged from; run.sh reproduces them
│   │   ├── comparison_console.txt per-seed delay and stops for every case
│   │   └── seed_by_seed.png       paired seed-by-seed figure (seed_figure.py)
│   └── demand/                   changed-demand test: 5 demand combinations, with and without ALINEA
└── dev_history/         earlier model versions (first_model = run 1, merge_zone = run 7) and the old-style ACC replay
```

A seed fixes the random arrivals. Single runs (seed folders) are for checking and showing the model; comparisons between controls use the same 20 evaluation seeds for every case, because one seed can mislead. The source code is the project folder itself; each `with_ramp_summary.json` stores the full configuration.

Routine for the next change: save with `--output results/<case>/seed<N> --gif`, write or update the case README, and run `tmc_compare.py` (or its successor) on the evaluation seeds.

## Project layout

| File | Purpose |
|---|---|
| `model.py` | The simulation: `Config`, IDM and IDM+CAH, ACC (`acc_inputs`, `acc_command`, `driver_takeover`), ballistic motion, within-step collision check, demand, ramp road and acceleration lane, merge rule, detectors, delay accounting and assertions. `run()` returns everything in memory and never writes files. |
| `run_demo.py` | Command-line entry point; decides whether anything is saved. |
| `present.py` | Exports CSV/JSON, figures (Matplotlib) and the HTML report. It can also draw runs from older model versions. |
| `make_gif.py` | Draws the replay GIF from saved frames (Pillow); never reruns the model. |
| `replot.py` | Re-renders a saved run with the current presentation into its `replot/` folder. |
| `templates/replay.html`, `templates/replay.js` | HTML report layout and the browser replay. |
| `validate.py` | Seed and time-step sensitivity. |
| `feasibility.py` | Bottleneck feasibility check with criteria fixed in advance and no-ramp controls. |
| `tmc_compare.py` | TMC test on many seeds: no control vs. ALINEA vs. ALINEA with lost reports, paired by seed. |
| `arrival_check.py` | Checks the generated arrivals (rates, exponential headways, Poisson counts per 30 s) on the evaluation seeds; `results/baseline/arrivals/`. |
| `seed_figure.py` | Seed-by-seed figure of the TMC test (no control vs. ALINEA, paired), `results/tmc_alinea/eval_seeds_101-120/seed_by_seed.png`. |
| `tmc_demand.py` | Changed-demand test of the TMC: summary table and figure from `results/tmc_alinea/demand/eval_seeds_101-120/comparison.json`. |
| `acc_compare.py` | ACC study on many seeds: A vs. B25, B50, B75, paired by seed, for one controller (recorded runs, about 2 min per 5 seeds on 4 cores). |
| `acc_figures.py` | Figures of the ACC study from its `comparison.json` files: summary and speed maps, or two runs side by side (ablation). |
| `acc_mechanism.py` | Deterministic platoon and queue-discharge tests with the model's own laws: main controller, fitted gain (k_v ablation), sensor delay and h = 1.69 s. |
| `test_model.py` | IDM equilibrium, free acceleration, exact stopping, collision detection, free-flow time, IDM+CAH cut-in response, merge rule cases, release without banking, no-yield merging above ramp entry speed, clearance, reproducibility, delay accounting (total = mainline + ramp), bottleneck indicators restricted to the evaluation window; detector occupancy and speed, report format, queue estimate, ALINEA law and bounds, release rate and signal cycle (2 s greens, one car per green, minimum red between greens), rest-in-green commits only vehicles that cannot stop, queue override, hold and fallback on lost reports; ACC onboard inputs, equilibrium gap, Gunter form, cruise = IDM free road, fallback, takeover and handover, cut-in response, mixed platoon braking, 0% ACC = pre-ACC model, nested equipment, ramp ACC vehicles merging like HDVs, all-ACC run; the string-stable default k_v and the failing fitted k_v. |
| `test_io.py` | No files without `--save`; every figure is exported; existing folders are never overwritten. |
| `ARCHITECTURE.md` | Equations, units, assumptions and the per-step order. |
| `make_figures.sh` | Redraws the summary figures from the saved 20-seed results. |

---

## Checks and validation

Every call to `model.run()` enforces the following and raises an error on the first failure:

- Speeds and positions are finite, and no vehicle moves backwards.
- **Within-step clearance:** the minimum gap is checked during each step, on the mainline and the acceleration lane, not only at its end.
- Vehicle conservation holds every step: offered = exited + on road + waiting.
- Every exit has a matching detector passage, and the integrated delay equals the summed trip delays once the network is empty (all delays use the free-flow time of the origin as reference).
- With metering, no ramp vehicle passes the stop line without a green or a commitment made while the meter rested in green.

These are consistency checks for the code. They are not calibration and not a proof of safety.

---

## Known limitations

- Lane changes are instantaneous; the GIF and HTML replay draw them as a 3 s lane change for illustration only.
- No driver heterogeneity or reaction delay; every HDV uses the same parameters.
- Without yielding, a ramp vehicle that stops at the end of the acceleration lane needs a large gap to get in. With the 450 m lane the vehicles behind it can still merge further upstream, so the queue stays short, but stops still happen on some seeds (no control: 3.8 per run on average, up to 14 on one seed; ALINEA: 2.05). With a 300 m lane and 1,700 + 500 veh/h it happened on almost every seed (17.5 per run) and blocked the lane for minutes. The feasibility check (`feasibility.py`) was designed for that earlier setting and has not been rerun.
- The merge thresholds, ramp speeds, a = 2.0 and T = 1.2 s are project choices for a realistic baseline, not calibration to a site.
- Detectors are ideal point detectors unless a defect is switched on. Missed passages, occupancy noise, delayed reports and lost reports are modelled and tested (`results/tmc_alinea/`); speed noise and placement errors are not.
- ACC: a sensor delay of 0.5 s or more removes the main controller's string stability (`results/acc_sensor_delay/`); only delay is modelled, not noise or dropouts. The main controller's k_v = 0.80 is a design value from the string-stability criterion, not a measured setting; it brakes harder at cut-ins than the fitted gains. The Gunter et al. law was fitted to small oscillations at highway speed. ACC readings are exact; the driver takeover is a project rule.
- Not yet modelled: Gipps (planned as the second human-driver model, to check that the ACC effect does not depend on IDM).

---

## References and attribution

- Treiber, M., Hennecke, A. and Helbing, D. (2000). Congested traffic states in empirical observations and microscopic simulations. *Physical Review E*, 62, 1805–1824. https://doi.org/10.1103/PhysRevE.62.1805
- Kesting, A., Treiber, M. and Helbing, D. (2010). Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity. *Philosophical Transactions of the Royal Society A*, 368, 4585–4605. https://doi.org/10.1098/rsta.2010.0084
- Treiber, M. IDM description, including ballistic integration: https://traffic-simulation.de/info/info_IDM.html
- Gunter, G., Janssen, C., Barbour, W., Stern, R. E. and Work, D. B. (2020). Model-based string stability of adaptive cruise control systems using field data. *IEEE Transactions on Intelligent Vehicles*, 5(1), 90–99. https://doi.org/10.1109/TIV.2019.2955368
- Papageorgiou, M., Hadj-Salem, H. and Blosseville, J.-M. (1991). ALINEA: A local feedback control law for on-ramp metering. *Transportation Research Record*, 1320, 58–64.
- Treiber, M. and Kesting, A. (2013). *Traffic Flow Dynamics: Data, Models and Simulation*. Springer.
- Gunter, G. et al. (2021). Are commercially implemented adaptive cruise control systems string stable? *IEEE Transactions on Intelligent Transportation Systems*, 22(11), 6992–7003. https://doi.org/10.1109/TITS.2020.3000682
- Klein, L. A., Mills, M. K. and Gibson, D. R. P. (2006). *Traffic Detector Handbook: Third Edition, Volume I*. FHWA-HRT-06-108.
- Treiber, M. and Helbing, D. (2002). Reconstructing the spatio-temporal traffic dynamics from stationary detector data. *Cooperative Transportation Dynamics*, 1, 3.1–3.24.
- Gipps, P. G. (1981). A behavioural car-following model for computer simulation. *Transportation Research Part B*, 15(2), 105–111 (planned second human-driver model). https://doi.org/10.1016/0191-2615(81)90037-0
- Adebisi, A., Liu, Y., Schroeder, B., Ma, J., Cesme, B., Jia, A. and Morgan, A. (2020). Developing Highway Capacity Manual capacity adjustment factors for connected and automated traffic on freeway segments. *Transportation Research Record*, 2674(10), 401–415. https://doi.org/10.1177/0361198120934797

Code and documentation were prepared with AI assistance. Review the equations, assumptions, event order and tests before using this project for coursework, and report numbers only from your own runs together with their configuration and validation results.
