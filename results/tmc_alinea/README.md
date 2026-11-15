# ALINEA ramp metering

Same [baseline](../baseline/README.md), comparing no control and all-human ALINEA on seeds 101–120.

## Controller

- D1400 occupancy every 30 s; target 14%; gain 70 veh/h per percentage point; release bounds 200–900 veh/h.
- Signal: one vehicle per 2 s green, cycle `3600/r` s; rests in green at 900 veh/h. Ramp storage: 28 vehicles; queue override off.
- Missing reports hold the last rate; after 60 s, use 500 veh/h. Queue estimates use cumulative ramp counts; the advisory forecast has a 60 s horizon.

## Core results

| Measure, 20-seed mean | No control | ALINEA |
|---|---:|---:|
| Total delay (veh·h) | 14.9 | 15.6 |
| Mainline delay (veh·h) | 9.9 | 8.2 |
| Ramp delay (veh·h) | 5.0 | 7.4 |
| Hard-braking merges per run | 30.4 | 9.9 |
| Lane-end stops per run | 3.8 | 2.1 |
| Seeds exceeding 28-vehicle storage | 0/20 | 9/20 |

Mainline delay falls 17%, but ramp waiting offsets the saving. The paired total-delay change is +0.8 veh·h (95% interval −0.1 to +1.6). A 30 s report delay raises total delay 13% above no control; 2% missed passages, occupancy noise and a 5 min outage have smaller effects. Forecast MAE is 3.8 vehicles versus 3.4 for persistence.

## Reproduction

Run from the project root:

```bash
sh results/tmc_alinea/eval_seeds_101-120/run.sh
python3 -B seed_figure.py
```

`eval_seeds_101-120/comparison.json` contains all cases and paired intervals. Current report examples use seed 110 via `report_sync_figures.py`; `seed9/` is a separate demo. See [demand sensitivity](demand/README.md) for changed demand.
