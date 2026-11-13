# baseline: all-HDV freeway, no ramp control

Every vehicle is human-driven (IDM+CAH, a = b = 2.0 m/s², T = 1.2 s), mainline vehicles do not yield, and the ramp has no meter. Mainline 1,700 veh/h for 40 min; ramp 100 → 450 → 0 veh/h (5 / 30 / 5 min); 2 km mainline, 200 m ramp road, 450 m acceleration lane ending at 1.5 km; dt = 0.1 s.

**Why this setting.** With a 300 m lane and 1,700 + 500 veh/h, ramp vehicles that found no gap stopped at the end of the acceleration lane and, because nobody yields, could wait there for minutes while a long queue formed behind them. With the 450 m lane, vehicles behind a stopped one can still merge further upstream, so queues on the acceleration lane stay short. 1,700 + 450 veh/h keeps a clear merge bottleneck in which a few ramp vehicles may wait at the lane end.

| Item | Content |
|---|---|
| `seed9/` | **Use this one to present.** Clear bottleneck: approach 42 km/h vs. 96 km/h upstream, 18 min congested at the merge, slow cells reaching 800 m upstream; no ramp vehicle stops at the lane end. Total delay 60,311 veh·s (mainline 52,918 / ramp 7,393). Full export, GIF and `classroom_demo.html`. |
| `../tmc_alinea/eval_seeds_101-120/` | Case A there: no control on the 20 evaluation seeds. Mean total delay 53,487 veh·s (mainline 35,570 + ramp 17,917); 3.8 ramp vehicles per run wait at the lane end (on 12 of 20 seeds; up to 14 on one seed). |

**Why one seed here and 20 in comparisons.** A seed fixes the random arrival times. One run is enough to show the mechanism; comparisons use the 20 evaluation seeds because single seeds differ a lot.

## Arrival generation check → `arrivals/`

`arrival_check.py` regenerates the arrivals of the 20 evaluation seeds (same random streams as the model,
no simulation; seed 9's mainline arrivals match the saved run exactly) and checks them against the target.
`poisson_arrivals.png` has two panels: (a) cumulative vehicles generated vs. rate × time (seed 9) and
(b) vehicles per 30 s vs. the Poisson distribution. All numbers below are in `arrival_check.json`.

| | Mainline (1,700 veh/h) | Ramp peak (450 veh/h) |
|---|---:|---:|
| Mean headway, generated / target (s) | 2.09 / 2.12 | 7.90 / 8.00 |
| KS test of headways vs. exponential | D = 0.008, p = 0.15 | D = 0.011, p = 0.61 |
| Vehicles per 30 s: mean, variance / mean (Poisson: 1) | 14.36, 0.99 | 3.79, 0.99 |
| Vehicles generated per run, mean / expected | 1,149 / 1,133 | 234 / 233 |

The headways are exponential and the counts per 30 s are Poisson with the target rates; the mainline
generated 1.4% more vehicles than expected on these 20 seeds, which is about two standard errors of
the mean and within random variation. Arrivals that cannot enter at once (the entry needs a safe gap) wait
at the entrance and the wait is counted as delay; no vehicle is dropped (seed 9: 1,168 generated, 1,168 entered).

