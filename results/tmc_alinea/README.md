# ALINEA ramp metering

Same [baseline](../baseline/README.md), comparing no control and all-human ALINEA on seeds 101–120.

## Controller

- D2400 occupancy (100 m before the lane end) every 30 s; target 14%; gain 70 veh/h per percentage point; release bounds 200–900 veh/h.
- Signal: one vehicle per 2 s green, cycle `3600/r` s; rests in green at 900 veh/h. Ramp storage: 28 vehicles; queue override off.
- Missing reports hold the last rate; after 60 s, use 400 veh/h (below the 450 veh/h ramp peak, so the meter keeps metering and the queue grows by at most 50 veh/h). Queue estimates use cumulative ramp counts; the advisory forecast has a 60 s horizon.

## Core results

| Measure, 20-seed mean | No control | ALINEA |
|---|---:|---:|
| Total delay (veh·h) | 17.1 | 16.6 |
| Mainline delay (veh·h) | 11.4 | 9.8 |
| Ramp delay (veh·h) | 5.7 | 6.8 |
| Hard-braking merges per run | 32.1 | 10.0 |
| Lane-end stops per run | 4.3 | 1.6 |
| Seeds exceeding 28-vehicle storage | 1/20 | 7/20 |

Mainline delay falls 14% (−1.6 veh·h, 95% interval −2.4 to −0.7), and ramp waiting offsets most of the saving. The paired total-delay change is −0.5 veh·h (95% interval −1.8 to +0.6). A 30 s report delay raises total delay 11% above no control (+2.0 veh·h, interval +0.2 to +3.6); 2% missed passages, occupancy noise and a 5 min outage leave total delay within −1.0 to +0.3 veh·h of no control, with intervals that include zero. Forecast MAE is 3.6 vehicles versus 3.3 for persistence.

**Detector and target, checked with the current settings** (13 development seeds, no control): 70% of the merges happen before 2.4 km (median 2.11 km). At D2400 flow peaks at about 2,130 veh/h for 14–20% occupancy and falls to about 1,730 veh/h above 24%; D2600 never exceeds 17% and stays in free flow. With the detector at 2.6 km ALINEA restricts the ramp in 26% of peak cycles instead of 33% and saves no mainline delay.

## Reproduction

Run from the project root:

```bash
sh results/tmc_alinea/eval_seeds_101-120/run.sh
python3 -B seed_figure.py
```

`eval_seeds_101-120/comparison.json` contains all cases and paired intervals. `seed9/` is a single-seed demo (replay page and figures). See [demand sensitivity](demand/README.md) for changed demand.
