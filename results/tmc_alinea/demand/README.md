# tmc_alinea/demand: changed-demand test

Same road, drivers, detectors and ALINEA (with the signal cycle) as `../`. Only the demand changes, one
demand at a time around the baseline (mainline 1,700 veh/h, ramp peak 450 veh/h). Every combination is
run without control and with ALINEA on the same 20 evaluation seeds (101–120), so within a combination
both cases see identical arrivals.

| Step | Mainline (veh/h, 0–40 min) | Ramp (veh/h): 0–5 / 5–35 / 35–40 min | Question |
|---|---|---|---|
| 1: ramp demand changed | 1,700 | 100 / **350, 450, 550** / 0 | How does the TMC effect change as more ramp vehicles merge? |
| 2: mainline demand changed | **1,500, 1,700, 1,900** | 100 / 450 / 0 | How does the TMC effect change as mainline pressure rises? |

The two steps share the baseline (1,700 + 450), so there are 5 demand combinations × 2 controls = 10
cases (`tmc_compare.py`: `A`, `A-ALINEA`, `A-R350`, `A-ALINEA-R350`, `A-R550`, `A-ALINEA-R550`,
`A-M1500`, `A-ALINEA-M1500`, `A-M1900`, `A-ALINEA-M1900`). Peak demand after the merge is 2,050 / 2,150 /
2,250 veh/h in step 1 and 1,950 / 2,150 / 2,350 veh/h in step 2.

## Development check (seeds 1–4, no control; `dev_check/`)

Run before the evaluation to confirm that the five combinations give clearly different traffic pressure.
Mean total delay (veh·h): mainline 1,500: 4.4; ramp 350: 6.4; baseline: 8.9; ramp 550: 19.8;
mainline 1,900: 43.7. The values were kept as planned.

## Predictions (written before the evaluation runs)

- **Low demand (ramp 350, mainline 1,500):** little or no breakdown without control. ALINEA rests in green
  most of the time, so the two cases are nearly the same; ALINEA should not make things worse.
- **Ramp 550:** without control, more merges, more stops at the lane end and a longer mainline queue.
  ALINEA meters harder; it should still protect the mainline, but the ramp queue grows and overflows the
  ramp road (28 vehicles) on more seeds than at 450. Total delay may or may not improve.
- **Mainline 1,900:** without control, the mainline breaks down early and badly. Mainline 1,900 plus the
  200 veh/h minimum rate is 2,100 veh/h, just under the ~2,190 veh/h single-lane capacity, so ALINEA can in
  principle still hold the mainline, but only by staying near its minimum rate for most of the peak. The
  ramp queue then overflows on almost every seed. This is the case where ALINEA is expected to reach its
  limit: the mainline benefit may shrink and the cost on the ramp becomes large.
- **Trend:** the higher the demand, the larger the mainline benefit of ALINEA in absolute terms and the
  larger the ramp cost; ALINEA does not see the ramp queue, so storage, not the mainline, is the first
  thing to fail.

## Results on the 20 evaluation seeds (101–120)

`eval_seeds_101-120/`: `comparison.json` (per-seed results, from `tmc_compare.py`; `run.sh` reproduces
everything), `summary.md` / `summary.json` and `demand_comparison.png` (from `tmc_demand.py`). Means over
seeds; changes are ALINEA minus no control on the same seeds, with 95% paired bootstrap intervals. The
baseline columns are identical, seed by seed, to `../eval_seeds_101-120/`. Peak demand is given as a share
of the ~2,190 veh/h single-lane capacity. No vehicles are left in the network at the end of any run.

### Step 1: ramp demand changed (mainline 1,700 veh/h)

| | ramp 350 | ramp 450 (baseline) | ramp 550 |
|---|---:|---:|---:|
| Peak demand after the merge (veh/h) | 2,050 (94%) | 2,150 (98%) | 2,250 (103%) |
| Total delay, no control / ALINEA (veh·h) | 8.3 / 8.4 | 14.9 / 15.6 | 32.5 / 29.7 |
| Mainline delay, no control / ALINEA (veh·h) | 7.4 / 6.9 | 9.9 / 8.2 | 14.3 / 9.1 |
| Ramp delay, no control / ALINEA (veh·h) | 0.9 / 1.5 | 5.0 / 7.4 | 18.2 / 20.7 |
| ALINEA − no control: mainline delay [95%] | -0.5 [-0.8, -0.2] (-6%), lower 20/20 | -1.7 [-2.8, -0.7] (-17%), lower 15/20 | -5.2 [-8.2, -3.0] (-37%), lower 19/20 |
| ALINEA − no control: ramp delay [95%] | +0.6 [+0.3, +0.9] (+66%), lower 0/20 | +2.4 [+1.6, +3.3] (+49%), lower 1/20 | +2.4 [+0.1, +4.9] (+13%), lower 7/20 |
| ALINEA − no control: total delay [95%] | +0.1 [-0.1, +0.3] (+1%), lower 4/20 | +0.8 [-0.1, +1.6] (+5%), lower 6/20 | -2.8 [-4.6, -1.1] (-9%), lower 15/20 |
| ALINEA mean release rate (veh/h) | 727 | 532 | 456 |
| Max cars before the stop line, mean / worst: no control | 5.5 / 7 | 6.8 / 9 | 21.1 / 89 |
| Max cars before the stop line, mean / worst: ALINEA | 12.0 / 33 | 29.6 / 60 | 60.9 / 92 |
| Seeds with queue > 28 cars, no control / ALINEA | 0 / 2 | 0 / 9 | 5 / 20 |
| Time with cars waiting off the ramp, no control / ALINEA (min) | 0.6 / 1.3 | 1.1 / 9.7 | 5.5 / 24.0 |
| Stops at the lane end per run, no control / ALINEA | 1.0 / 0.1 | 3.8 / 2.0 | 13.6 / 3.6 |
| Hard braking (> 3 m/s²) after merges per run, no control / ALINEA | 11.4 / 3.6 | 30.4 / 9.9 | 48.1 / 15.7 |
| Discharge flow at 1.6 km, no control / ALINEA (veh/h) | 2,020 / 2,021 | 2,085 / 2,094 | 2,083 / 2,114 |
| Vehicles left at the end, no control / ALINEA | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

### Step 2: mainline demand changed (ramp peak 450 veh/h)

| | mainline 1500 | mainline 1700 (baseline) | mainline 1900 |
|---|---:|---:|---:|
| Peak demand after the merge (veh/h) | 1,950 (89%) | 2,150 (98%) | 2,350 (107%) |
| Total delay, no control / ALINEA (veh·h) | 5.3 / 5.6 | 14.9 / 15.6 | 53.1 / 43.0 |
| Mainline delay, no control / ALINEA (veh·h) | 4.6 / 4.4 | 9.9 / 8.2 | 27.6 / 15.0 |
| Ramp delay, no control / ALINEA (veh·h) | 0.7 / 1.2 | 5.0 / 7.4 | 25.5 / 28.0 |
| ALINEA − no control: mainline delay [95%] | -0.2 [-0.3, -0.1] (-3%), lower 17/20 | -1.7 [-2.8, -0.7] (-17%), lower 15/20 | -12.6 [-20.7, -5.7] (-46%), lower 16/20 |
| ALINEA − no control: ramp delay [95%] | +0.5 [+0.3, +0.7] (+64%), lower 0/20 | +2.4 [+1.6, +3.3] (+49%), lower 1/20 | +2.5 [-5.0, +10.3] (+10%), lower 9/20 |
| ALINEA − no control: total delay [95%] | +0.3 [+0.2, +0.5] (+6%), lower 1/20 | +0.8 [-0.1, +1.6] (+5%), lower 6/20 | -10.1 [-13.0, -7.5] (-19%), lower 20/20 |
| ALINEA mean release rate (veh/h) | 806 | 532 | 325 |
| Max cars before the stop line, mean / worst: no control | 6.6 / 9 | 6.8 / 9 | 37.6 / 112 |
| Max cars before the stop line, mean / worst: ALINEA | 10.9 / 23 | 29.6 / 60 | 83.1 / 121 |
| Seeds with queue > 28 cars, no control / ALINEA | 0 / 0 | 0 / 9 | 9 / 20 |
| Time with cars waiting off the ramp, no control / ALINEA (min) | 1.1 / 1.4 | 1.1 / 9.7 | 8.2 / 30.0 |
| Stops at the lane end per run, no control / ALINEA | 0.6 / 0.1 | 3.8 / 2.0 | 10.1 / 1.0 |
| Hard braking (> 3 m/s²) after merges per run, no control / ALINEA | 6.3 / 3.6 | 30.4 / 9.9 | 63.8 / 10.2 |
| Discharge flow at 1.6 km, no control / ALINEA (veh/h) | 1,908 / 1,908 | 2,085 / 2,094 | 2,114 / 2,180 |
| Vehicles left at the end, no control / ALINEA | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

## Interpretation

- **Low demand (ramp 350, mainline 1,500).** There is little to fix: ALINEA cuts mainline delay by a few
  percent but adds about as much on the ramp, so total delay is unchanged at ramp 350 and slightly worse
  at mainline 1,500 (+0.3 veh·h, +6%, worse on 19 of 20 seeds). The controller still meters now and then
  (mean rate 730–810 veh/h, not resting in green), so at low demand it costs a little.
- **Baseline (98% of capacity).** As in `../`: mainline −17%, total delay +5% (not significant).
- **High demand (ramp 550, mainline 1,900).** Without control the merge breaks down: many ramp vehicles stop
  at the end of the acceleration lane (13.6 and 10.1 per run), and the discharge flow stays below what the
  merge can pass. ALINEA holds the merge below its critical occupancy, so far fewer vehicles stop at the lane
  end, the discharge flow rises (mainline 1,900: 2,114 → 2,180 veh/h) and **total delay falls: −9% at
  ramp 550 (15/20 seeds), −19% at mainline 1,900 (20/20 seeds).** Ramp delay barely rises, because without
  control the ramp vehicles are already stuck behind the failed merge.
- **The cost is storage.** At both high demands the queue before the stop line exceeds the 28 cars the ramp
  road holds on **20 of 20 seeds**: on average 61 cars at ramp 550 and 83 at mainline 1,900 (worst 121),
  with cars waiting off the ramp for 24–30 min. ALINEA does not see the ramp queue, so nothing stops it from
  growing. In reality this queue would block the street and a queue override would have to release
  vehicles, which removes most of the metering. **This is where ALINEA stops working: not on the mainline,
  but because the ramp cannot store the vehicles it holds back.**
- **Trend.** The higher the demand, the larger the mainline benefit and the larger the ramp queue.
  ALINEA is most useful exactly where it needs the most storage.

### Predictions vs. results

| Prediction | Result |
|---|---|
| Low demand: nearly no difference, ALINEA should not make things worse | Mostly right; at mainline 1,500 ALINEA is slightly but consistently worse (+6%) |
| Ramp 550: mainline protected, overflow on more seeds | Right (mainline −37%; overflow 20/20). Total delay improved (−9%) |
| Mainline 1,900: mainline benefit may shrink, ramp cost large | **Wrong on the mainline**: the benefit is the largest (−46%) and total delay falls 19%; right on the ramp (overflow 20/20, mean 83 cars) |
| Storage, not the mainline, fails first | Right |
