# CEE281 Freeway On-Ramp Simulation

Python microscopic simulation comparing ALINEA ramp metering and adaptive cruise control (ACC) at a freeway merge. Human drivers use IDM+CAH; ACC uses onboard measurements without V2V communication.

## Quick start

Python 3.10+ with NumPy, Matplotlib and Pillow. Run commands from the project root.

```bash
python3 -m pip install -r requirements.txt
python3 -B -m unittest test_model test_io
python3 -B run_demo.py --seed 110
python3 -B run_demo.py --seed 110 --save --gif --output results/demo_seed110
```

Open the exported `classroom_demo.html` for the replay and figures. Saving requires `--save`; existing output folders are not overwritten. Add `--control alinea` or `--acc-share 0.5` for the intervention examples. Use `--help` for other options.

## Model and evaluation

| Item | Setting |
|---|---|
| Geometry | One 2 km mainline lane; 200 m ramp road; 450 m acceleration lane from 1.05 to 1.50 km; no advance mainline yielding |
| Demand | Independent Poisson arrivals: mainline 1,700 veh/h for 40 min; ramp 100 / 450 / 0 veh/h over 0–5 / 5–35 / 35–40 min |
| Human drivers | IDM+CAH: desired speed 120 km/h, time gap 1.2 s, acceleration/deceleration parameters 2.0 m/s², standstill gap 2 m, length 5 m, CAH weight 0.99 |
| ACC | `u = k_p[s − (η + hv)] − k_v(v − v_leader)`; `k_p = 0.0131 s⁻²`, `η = 7.5699 m`, `h = 1.27 s`, `k_v = 0.80 s⁻¹`; HDV behavior on the ramp and driver takeover during strong braking |
| Runs | dt = 0.1 s; duration 60 min; development seeds 1–4; paired evaluation seeds 101–120 |
| Measures | Delay includes entry waiting and all trips; congestion uses 30 s bins below 40 km/h on 1.0–1.5 km during minutes 5–40 |

A is 0% ACC with an unmetered ramp; B25/B50/B75 equip 25/50/75% of both streams. Arrival times are identical within each seed and ACC assignments are nested. Comparisons use paired changes and 95% bootstrap intervals.

## Reproduce figures and tables

```bash
sh make_figures.sh
python3 -B report_sync_figures.py
```

The first command redraws result summaries. The second writes the report illustrations to `report/figures/`: seed 110 trajectories over 0–45 min and 0–2 km, a shared 0–120 km/h color scale and identical baseline panels, plus the matching arrivals and controller trace. It caches three trajectory records in `results/report_seed110/` and checks recovered runs against saved evaluation metrics. Seed 9 exports are separate demonstration runs.

Each experiment README below gives its rerun commands. `comparison.json` stores per-seed results, case means and paired changes; `run.sh` reproduces the comparisons. Numerical tables use all 20 evaluation seeds.

| Study | Settings and commands |
|---|---|
| Baseline and Poisson arrival check | [baseline](results/baseline/README.md) |
| ALINEA and detector defects | [tmc_alinea](results/tmc_alinea/README.md) |
| ALINEA demand sensitivity | [tmc_alinea/demand](results/tmc_alinea/demand/README.md) |
| Main ACC share study | [acc_main](results/acc_main/README.md) |
| Speed-gain ablation | [acc_ablation_kv](results/acc_ablation_kv/README.md) |
| Time-gap ablation | [acc_ablation_h](results/acc_ablation_h/README.md) |
| ACC sensor delay | [acc_sensor_delay](results/acc_sensor_delay/README.md) |
| ACC demand sensitivity | [acc_demand](results/acc_demand/README.md) |

Deterministic platoon and discharge checks: `python3 -B acc_mechanism.py`. If the local report source is present, build it with `cd report && xelatex mid_report_updated.tex && xelatex mid_report_updated.tex`.

## Key files and limitations

| File | Purpose |
|---|---|
| `model.py` | Configuration, driving laws, merging, detectors, controllers and delay accounting |
| `run_demo.py`, `present.py` | Run and export individual scenarios |
| `tmc_compare.py`, `tmc_demand.py`, `acc_compare.py` | Paired experiments and summaries |
| `acc_figures.py`, `report_sync_figures.py`, `make_figures.sh` | Reproduce figures |
| `test_model.py`, `test_io.py`, `validate.py` | Implementation and time-step checks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Equations, units and simulation order |

The model checks vehicle conservation, within-step clearance and delay accounting. It is not calibrated to a field site. HDVs are homogeneous, lane changes are instantaneous, and merge thresholds and takeover are project rules. ACC sensing delay is tested; sensor noise and actuator lag are not. Gipps and queue-storage control remain future work.

## Model sources

- Treiber, Hennecke and Helbing (2000), *Congested traffic states in empirical observations and microscopic simulations*. [DOI](https://doi.org/10.1103/PhysRevE.62.1805).
- Kesting, Treiber and Helbing (2010), *Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity* (CAH). [DOI](https://doi.org/10.1098/rsta.2010.0084).
- Gunter et al. (2020), *Model-based string stability of adaptive cruise control systems using field data*. [DOI](https://doi.org/10.1109/TIV.2019.2955368).
- Papageorgiou, Hadj-Salem and Blosseville (1991), *ALINEA: A local feedback control law for on-ramp metering*, TRR 1320, 58–64.
- Treiber and Kesting (2013), *Traffic Flow Dynamics: Data, Models and Simulation*.

AI tools assisted with code, figures and documentation.
