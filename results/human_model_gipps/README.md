# Human-model check: Gipps drivers instead of IDM

Does the effect of 50% ACC depend on the human-driver model? Cases A (all IDM) and B50 (50% ACC, others IDM) come from the [main study](../acc_main/README.md). This folder adds C (all Gipps) and D (50% ACC, others Gipps) on the same seeds 101–120, demand and ACC controller. In `comparison.json` C is stored as "A" and D as "B50", because the run is `acc_compare.py --set human_model=gipps`.

**Gipps settings.** Gipps's (1981) average values `a_G = 1.7 m/s²`, `b_G = b̂ = −3.4 m/s²`, `s_m = 1.5 m` (effective length 6.5 m), the common desired speed 120 km/h. Project choice: `τ = 0.97 s` instead of 2/3 s, so that the capacity at the desired speed (2,180 veh/h) matches the IDM capacity (2,190 veh/h). The target speed is recomputed every 0.1 s and the acceleration `(v⁺ − v)/τ` is applied, which keeps Gipps's steady-state gap `s_m + 1.5 τ v` but not his exact reaction-delay dynamics. Gipps replaces only the mainline following law; the ramp, the acceleration-lane manoeuvre and the gap-acceptance rule are the same as in A.

**Prediction.** None was recorded before the first run. Development seeds 1–4 were run first and showed the pattern below; the evaluation seeds confirmed it.

## Core results

Means per run over 20 seeds; changes are paired with 95% bootstrap intervals (`summary.md` has all measures).

| Measure | A (IDM) | B50 | C (Gipps) | D | ACC effect, IDM: B50 − A | ACC effect, Gipps: D − C |
|---|---:|---:|---:|---:|---|---|
| Total delay (veh·h) | 17.1 | 14.7 | 6.3 | 6.6 | −2.44 [−3.96, −0.98] | +0.37 [+0.06, +0.71] |
| Mainline delay (veh·h) | 11.4 | 13.4 | 5.6 | 6.2 | +2.05 [+0.54, +3.91] | +0.59 [+0.28, +0.91] |
| Ramp delay (veh·h) | 5.7 | 1.2 | 0.6 | 0.4 | −4.49 [−7.65, −1.92] | −0.21 [−0.29, −0.14] |
| Congested time (min) | 4.0 | 1.5 | 0.8 | 0.0 | −2.58 [−4.35, −0.95] | −0.72 [−1.30, −0.23] |
| Hard braking > 3 m/s² (veh·s) | 39 | 47 | 154 | 124 | +8.4 [−1.0, +18.2] | −30.1 [−37.8, −22.3] |

- **The bottleneck itself depends on the human model.** With Gipps drivers total delay is 63% lower than with IDM and the merge area is congested for 0.8 instead of 4.0 minutes. A Gipps follower brakes hard for a moment when a vehicle merges in front of it (187 of 234 merges per run make the follower brake harder than 3 m/s², against 32 with IDM) and then recovers quickly; hard braking is 4.0 times higher.
- **The components move in the same direction under both models:** mainline delay rises, ramp delay and congested time fall. The sizes are much smaller with Gipps because there is little congestion and almost no ramp delay to remove.
- **Total delay does depend on the human model:** with IDM, 50% ACC reduces it by 14% (interval below zero); with Gipps it raises it by 6% (interval just above zero). The difference between the two effects is +2.8 veh·h [+1.5, +4.2]. The ACC benefit found in the main study comes from relieving ramp vehicles stuck at the merge, which hardly happens with Gipps drivers.
- With Gipps drivers ACC reduces hard braking by 20%; with IDM it does not.

**Limits.** Results are for the 3 km road. The simplified Gipps dynamics needed the same collision-avoidance floor as IDM+CAH. A first variant in which the merging driver also judged gaps with the Gipps law was dropped: far fewer gaps were accepted, about 36 ramp vehicles per run stopped at the lane end on development seeds 1–4, and the evaluation runs stopped on collision-check failures (at least three among seeds 101–115; tested with the earlier 2 km road). The comparison is a sensitivity check, not a validation against data.

## Reproduction

```bash
sh results/human_model_gipps/eval_seeds_101-120/run.sh
python3 -B gipps_compare.py
```
