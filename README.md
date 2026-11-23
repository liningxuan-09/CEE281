# CEE281 Freeway On-Ramp Simulation

Python microscopic simulation comparing ALINEA ramp metering and adaptive cruise control (ACC) at a freeway merge. Human drivers use IDM+CAH (Gipps in a sensitivity check); ACC uses onboard measurements without V2V communication.

## Quick start

Python 3.10+ with NumPy, Matplotlib and Pillow. Run commands from the project root.

```bash
python3 -m pip install -r requirements.txt
python3 -B -m unittest test_model test_io
python3 -B run_demo.py
python3 -B run_demo.py --save --gif --output results/demo
```

Both use the demonstration seed 9 (`--seed N` for another). Open the exported `classroom_demo.html` for the replay and figures. Saving requires `--save`; existing output folders are not overwritten. Add `--control alinea` or `--acc-share 0.5` for the intervention examples. Use `--help` for other options.

## Model and evaluation

| Item | Setting |
|---|---|
| Geometry | One 3 km mainline lane; 200 m ramp road; 450 m acceleration lane from 2.05 to 2.50 km; no advance mainline yielding |
| Demand | Independent Poisson arrivals: mainline 1,700 veh/h for 40 min; ramp 100 / 450 / 0 veh/h over 0–5 / 5–35 / 35–40 min |
| Human drivers | IDM+CAH: desired speed 120 km/h, time gap 1.2 s, acceleration/deceleration parameters 2.0 m/s², standstill gap 2 m, length 5 m, CAH weight 0.99 |
| ACC | `u = k_p[s − (η + hv)] − k_v(v − v_leader)`; `k_p = 0.0131 s⁻²`, `η = 7.5699 m`, `h = 1.27 s`, `k_v = 0.80 s⁻¹`; HDV behavior on the ramp and driver takeover during strong braking |
| Runs | dt = 0.1 s; duration 60 min; development seeds 1–4; paired evaluation seeds 101–120 |
| Measures | Delay includes entry waiting and all trips; congestion uses 30 s bins below 40 km/h on 2.0–2.5 km during minutes 5–40 |

A is 0% ACC with an unmetered ramp; B25/B50/B75 equip 25/50/75% of both streams. Arrival times are identical within each seed and ACC assignments are nested. Comparisons use paired changes and 95% bootstrap intervals.

## Reproduce figures and tables

```bash
sh make_figures.sh
```

This redraws the 20-seed summary figures in each study folder and the trajectory figures in [results/figures](results/figures/README.md).

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
| Second human-driver model (Gipps) | [human_model_gipps](results/human_model_gipps/README.md) |
| Time-step sensitivity | [time_step](results/time_step/README.md) |

Deterministic platoon and discharge checks for the ACC: `python3 -B acc_mechanism.py`.

## Key files and limitations

| File | Purpose |
|---|---|
| `model.py` | Configuration, driving laws, merging, detectors, controllers and delay accounting |
| `run_demo.py`, `present.py` | Run and export individual scenarios |
| `tmc_compare.py`, `tmc_demand.py`, `acc_compare.py`, `gipps_compare.py`, `dt_check.py` | Paired experiments and summaries |
| `acc_figures.py`, `final_figures.py`, `make_figures.sh` | Reproduce figures |
| `test_model.py`, `test_io.py`, `feasibility.py` | Implementation tests and the baseline feasibility check |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Equations, units and simulation order |

The model checks vehicle conservation, within-step clearance and delay accounting. The mainline is 2.05 km long before the acceleration lane so that queues stay on the road in the main cases; with the earlier 1.05 km they reached the entrance and hid the ACC effect on total delay. It is not calibrated to a field site. HDVs are homogeneous, lane changes are instantaneous, and merge thresholds and takeover are project rules. ACC sensing delay is tested; sensor noise and actuator lag are not. Total delay is insensitive to the time step, but the split between mainline and ramp delay in the uncontrolled case is not ([time_step](results/time_step/README.md)). The Gipps check uses simplified Gipps dynamics. The ramp queue is reported against the 28-vehicle storage but not controlled.

## Model sources

- Treiber, Hennecke and Helbing (2000), *Congested traffic states in empirical observations and microscopic simulations*. [DOI](https://doi.org/10.1103/PhysRevE.62.1805).
- Kesting, Treiber and Helbing (2010), *Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity* (CAH). [DOI](https://doi.org/10.1098/rsta.2010.0084).
- Gipps (1981), *A behavioural car-following model for computer simulation*. [DOI](https://doi.org/10.1016/0191-2615(81)90037-0).
- Gunter et al. (2020), *Model-based string stability of adaptive cruise control systems using field data*. [DOI](https://doi.org/10.1109/TIV.2019.2955368).
- Papageorgiou, Hadj-Salem and Blosseville (1991), *ALINEA: A local feedback control law for on-ramp metering*, TRR 1320, 58–64.
- Gunter et al. (2021), *Are commercially implemented adaptive cruise control systems string stable?* (sensor delay). [DOI](https://doi.org/10.1109/TITS.2020.3000682).
- Klein, Mills and Gibson (2006), *Traffic Detector Handbook*, 3rd ed., vol. I, FHWA-HRT-06-108 (count, occupancy and speed measurement).
- Treiber and Helbing (2002), *Reconstructing the spatio-temporal traffic dynamics from stationary detector data*, Cooperative Transportation Dynamics 1, 3.1–3.24 (estimation and forecasting).
- Treiber and Kesting (2013), *Traffic Flow Dynamics: Data, Models and Simulation*.

AI tools assisted with code, figures and documentation.
