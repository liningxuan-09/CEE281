"""Export a saved run: CSV/JSON tables, static figures and an offline HTML report.

Called only after the user explicitly asks to save (``run_demo.py --save``).
Every figure is drawn from data the model already recorded; nothing here
re-runs or alters the simulation.

Figures written to the output directory
---------------------------------------
trajectories.png       Time-space diagram (mainline + ramp lane), colored by speed
merge_speed.png        Mainline-origin speed near the merge vs. an upstream reference
ramp_queue.png         Vehicles on the ramp and in the external ramp queue
merge_events.png       Speed of each accepted merge and the follower's braking request
merge_attempts.png     Outcome of every per-step merge check
trip_delay.png         Trip delay of each completed vehicle by origin
cumulative_counts.png  Cumulative arrivals and detector counts (N-curves)
"""
from pathlib import Path
import base64
import csv
import html
import json
import math

import numpy as np

# Matplotlib is imported lazily inside _plt() so that importing this module
# (for example from make_gif.py for the shared color scale) stays cheap.

# --------------------------------------------------------------------------
# Shared visual style. Every figure, the GIF and the HTML replay use the same
# ink colors and the same speed color scale so they read as one system.
# --------------------------------------------------------------------------
INK = '#0b0b0b'          # primary text
INK_2 = '#52514e'        # secondary text (subtitles, notes)
MUTED = '#898781'        # axis ticks and labels
GRID = '#e1e0d9'         # hairline gridlines
AXIS = '#c3c2b7'         # baselines
SURFACE = '#fcfcfb'      # chart background
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#6250d6']  # fixed categorical order
ZONE = '#f2f1ec'         # shaded merge zone / demand window

# Speed scale (km/h): congested traffic is dark red and stands out; free flow
# fades to a pale gray-blue. Lightness changes monotonically, so the scale is
# still readable in grayscale and for color-vision deficiencies.
SPEED_STOPS = [(0.0, '#7f1d1d'), (0.35, '#d1462f'), (0.65, '#f0a46e'), (1.0, '#c3d3e6')]
SPEED_MAX_KMH = 120.0

DPI = 160


def _hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def speed_rgb(kmh):
    """Map a speed in km/h onto the shared speed scale; returns an (r, g, b) tuple."""
    f = max(0.0, min(1.0, kmh / SPEED_MAX_KMH))
    for (f0, c0), (f1, c1) in zip(SPEED_STOPS[:-1], SPEED_STOPS[1:]):
        if f <= f1:
            w = (f - f0) / (f1 - f0)
            return tuple(int(round(a + (b - a) * w)) for a, b in zip(_hex_rgb(c0), _hex_rgb(c1)))
    return _hex_rgb(SPEED_STOPS[-1][1])


def _plt():
    """Import Matplotlib with a file-only backend and apply the shared style."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'font.family': 'sans-serif',
        'font.sans-serif': ['Helvetica Neue', 'Helvetica', 'Arial', 'DejaVu Sans'],
        'font.size': 10.5, 'axes.titlesize': 12, 'axes.labelsize': 10.5,
        'axes.labelcolor': INK_2, 'text.color': INK,
        'xtick.color': MUTED, 'ytick.color': MUTED,
        'xtick.labelcolor': INK_2, 'ytick.labelcolor': INK_2,
        'axes.edgecolor': AXIS, 'axes.linewidth': 0.8,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
        'axes.axisbelow': True, 'legend.frameon': False, 'legend.fontsize': 9.5,
        'lines.linewidth': 2.0, 'lines.solid_capstyle': 'round',
    })
    return plt


def _speed_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list('speed', SPEED_STOPS)


def _header(fig, title, subtitle):
    """Left-aligned title and one-line explanation above the plotting area."""
    fig.text(0.012, 0.985, title, ha='left', va='top', fontsize=14, fontweight='bold', color=INK)
    fig.text(0.012, 0.935, subtitle, ha='left', va='top', fontsize=10, color=INK_2)


def _profile_text(prof):
    return ' -> '.join(f"{r:.0f}" for _, _, r in prof)


def demand_label(c):
    """One-line description of the demand, including the peak when there is one."""
    end = c['demand_end'] / 60
    if c.get('main_profile') or c.get('ramp_profile'):
        mp, rp = c.get('main_profile'), c.get('ramp_profile')
        parts = []
        if mp:
            parts.append(f"mainline {_profile_text(mp)} veh/h")
        if rp:
            mins = ' / '.join(f"{(b - a) / 60:.0f}" for a, b, _ in rp)
            parts.append(f"ramp {_profile_text(rp)} veh/h ({mins} min)")
        return ', '.join(parts) + f"; demand ends at {end:.0f} min"
    base = f"{c.get('main_rate', 0):.0f} mainline + {c.get('ramp_rate', 0):.0f} ramp veh/h"
    if c.get('peak_end', 0) > 0:
        pk = min(c['peak_end'], c['demand_end']) / 60
        return (f"peak {c['peak_main_rate']:.0f} + {c['peak_ramp_rate']:.0f} veh/h for {pk:.0f} min, "
                f"then {base} until {end:.0f} min")
    return f"{base} for {end:.0f} min"


def _demand_window(ax, config, label=True, r=None):
    """Shade the demand period (peak darker) and, if a run is given, mark when the network empties."""
    if r is not None:
        _cleared_marker(ax, r, label)
    end = config['demand_end'] / 60
    ax.axvspan(0, end, color=ZONE, lw=0, zorder=0)
    if config.get('peak_end', 0) > 0:
        pk = min(config['peak_end'], config['demand_end']) / 60
        ax.axvspan(0, pk, color='#e9e7df', lw=0, zorder=0)
        if label:
            ax.text(pk, 1.0, '  peak ends', transform=ax.get_xaxis_transform(),
                    ha='left', va='top', fontsize=8.5, color=MUTED)
    if label:
        ax.text(end, 1.0, 'demand ends  ', transform=ax.get_xaxis_transform(),
                ha='right', va='top', fontsize=8.5, color=MUTED)


def clear_time(r):
    """Time (s) the last vehicle exits, or None if vehicles remain at the end of the run."""
    m = r['summary']
    left = m['remaining_on_road'] + m['remaining_main_external'] + m['remaining_ramp_external']
    if left or not r['trips']:
        return None
    return max(z['exit_s'] for z in r['trips'])


def view_end(r):
    """Right edge of time axes in minutes: one minute after the network empties.

    The model keeps running to `duration` so the arrival cohort can clear; the
    empty tail after the last exit carries no information and is not plotted."""
    duration = r['summary']['config']['duration']
    t = clear_time(r)
    if t is None:
        return duration / 60
    return min(duration, math.ceil((t + 60) / 60) * 60) / 60


def _cleared_marker(ax, r, label=True):
    """Mark the moment the last vehicle leaves the network."""
    t = clear_time(r)
    if t is None:
        return
    ax.axvline(t / 60, color=MUTED, lw=1, ls=(0, (1, 2)))
    if label:
        ax.text(t / 60, 0.03, ' network empty', transform=ax.get_xaxis_transform(), rotation=90,
                ha='right', va='bottom', fontsize=8.5, color=MUTED)


def _legend(ax, **kw):
    """Draw a legend only when something is labeled (an empty run has no series)."""
    if ax.get_legend_handles_labels()[0]:
        ax.legend(**kw)


def _save(fig, path):
    fig.savefig(path, dpi=DPI)
    import matplotlib.pyplot as plt
    plt.close(fig)


def _segments(rows, lane):
    """Build one line segment per consecutive pair of 1 s samples of a vehicle."""
    rows = [r for r in rows if r['lane'] == lane]
    if not rows:
        return np.empty((0, 2, 2)), np.empty(0)
    vid = np.array([r['id'] for r in rows])
    t = np.array([r['t_s'] for r in rows]) / 60
    x = np.array([r['x_km'] for r in rows])
    v = np.array([r['v_kmh'] for r in rows])
    order = np.lexsort((t, vid))
    vid, t, x, v = vid[order], t[order], x[order], v[order]
    link = (vid[1:] == vid[:-1]) & (np.diff(t) <= 1.01 / 60)
    seg = np.stack([np.c_[t[:-1], x[:-1]], np.c_[t[1:], x[1:]]], axis=1)[link]
    return seg, ((v[:-1] + v[1:]) / 2)[link]


# --------------------------------------------------------------------------
# Geometry helpers. Two model generations exist in results/:
#   explicit ramp lane (runs 1-2): ramp_start, merge_start, merge_end
#   point merge (runs 3-4):        merge_x
#   merge zone (runs 5-7):         merge_x, zone_length
#   acceleration lane (current):   merge_x, acc_length (ramp vehicles simulated on lane 1)
# --------------------------------------------------------------------------
def geometry(c):
    """Return merge point (m), merge zone (lo, hi) in m and whether a ramp lane is simulated."""
    if 'merge_x' in c:
        lo = c['merge_x'] - c.get('acc_length', c.get('zone_length', 0.0))
        return c['merge_x'], (lo, c['merge_x']), False
    return c['merge_end'], (c['merge_start'], c['merge_end']), True


def sections(c):
    """Three fixed road sections relative to the merge point: upstream, approach, downstream."""
    m = geometry(c)[0]
    end = c.get('road_end', m + 700)
    return [('Upstream', max(0, m - 1500), max(0, m - 1000)), ('Approach', m - 500, m),
            ('Downstream', m + 200, min(m + 700, end))]


def _mark_merge(ax, c, km_axis='y'):
    m, (lo, hi), _ = geometry(c)
    if hi > lo:
        ax.axhspan(lo / 1000, hi / 1000, color='#2a78d6', alpha=0.08, lw=0)
    else:
        ax.axhline(m / 1000, color='#2a78d6', lw=1, alpha=0.6)


# --------------------------------------------------------------------------
# Individual figures
# --------------------------------------------------------------------------
def fig_trajectories(r, path):
    """Time-space diagram of the mainline (plus the ramp lane when it is simulated)."""
    plt = _plt()
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    c = r['summary']['config']
    m, (lo, hi), ramp_lane = geometry(c)
    cmap, norm = _speed_cmap(), Normalize(0, SPEED_MAX_KMH)
    if ramp_lane:
        fig, (top, bottom) = plt.subplots(
            2, 1, figsize=(11, 7.2), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.15], hspace=0.12))
        axes = ((top, 0), (bottom, 1))
        note = 'flat dark lines on the ramp are vehicles waiting to merge'
    else:
        fig, top = plt.subplots(figsize=(11, 6.2))
        bottom, axes = top, ((top, 0),)
        note = ('ramp vehicles appear where they leave the acceleration lane (shaded); a dark band growing upstream is a queue'
                if 'acc_length' in c else
                'ramp vehicles appear where they merge (shaded merge zone); a dark band growing upstream is a queue'
                if hi > lo else 'ramp vehicles appear at the merge point; a dark band growing upstream is a queue')
    fig.subplots_adjust(left=0.07, right=0.9, top=0.87 if ramp_lane else 0.85, bottom=0.08 if ramp_lane else 0.1)
    _header(fig, 'Vehicle trajectories',
            f"One line per vehicle, colored by speed; {note}.\n"
            f"Seed {c['seed']}, dt = {c['dt']} s; demand: {demand_label(c)}.")
    for ax, lane in axes:
        seg, v = _segments(r['trajectories'], lane)
        lc = LineCollection(seg, cmap=cmap, norm=norm, linewidths=0.7 if lane == 0 else 0.9)
        lc.set_array(v)
        ax.add_collection(lc)
        _mark_merge(ax, c)
        ax.axvline(c['demand_end'] / 60, color=MUTED, lw=1, ls=(0, (4, 3)))
        _cleared_marker(ax, r, label=ax is top)
        ax.grid(axis='x', visible=False)
    top.set_ylim(0, c['road_end'] / 1000)
    top.set_ylabel('Mainline position (km)')
    top.text(0.003, hi / 1000 + 0.03, 'acceleration lane' if 'acc_length' in c else 'merge zone' if ramp_lane else 'merge point', color='#1c5cab',
             fontsize=8.5, transform=top.get_yaxis_transform())
    top.text(c['demand_end'] / 60, c['road_end'] / 1000, 'demand ends  ', ha='right', va='top',
             fontsize=8.5, color=MUTED)
    if ramp_lane:
        bottom.set_ylim(c['ramp_start'] / 1000, c['merge_end'] / 1000)
        bottom.set_ylabel('Ramp (km)')
    bottom.set_xlim(0, view_end(r))
    bottom.set_xlabel('Simulation time (min)')
    cax = fig.add_axes([0.915, 0.08 if ramp_lane else 0.1, 0.014, 0.79 if ramp_lane else 0.75])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    cb.set_label('Speed (km/h)', color=INK_2)
    cb.outline.set_visible(False)
    _save(fig, path)


def fig_speed_heatmap(r, path):
    """Mean mainline speed in 30 s x 100 m cells: the standard picture of a bottleneck."""
    plt = _plt()
    from matplotlib.colors import Normalize
    c = r['summary']['config']
    m = geometry(c)[0]
    tb, xb = 30.0, 100.0
    nt, nx = int(math.ceil(view_end(r) * 60 / tb)), int(math.ceil(c['road_end'] / xb))
    sums, cnt = np.zeros((nx, nt)), np.zeros((nx, nt))
    for z in r['trajectories']:
        if z['lane'] != 0:
            continue
        i, j = int(z['x_km'] * 1000 // xb), int(z['t_s'] // tb)
        if i < nx and j < nt:
            sums[i, j] += z['v_kmh']
            cnt[i, j] += 1
    speed = np.where(cnt > 0, sums / np.maximum(cnt, 1), np.nan)
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(left=0.07, right=0.9, top=0.84, bottom=0.11)
    _header(fig, 'Mainline speed map',
            'Mean speed on the mainline in 30 s x 100 m cells (white = no vehicles).\n'
            'A red region that ends at the merge, with faster cells downstream, marks a bottleneck.')
    im = ax.imshow(speed, origin='lower', aspect='auto', cmap=_speed_cmap(), norm=Normalize(0, SPEED_MAX_KMH),
                   extent=[0, nt * tb / 60, 0, nx * xb / 1000], interpolation='nearest')
    ax.axhline(m / 1000, color=INK, lw=1, ls=(0, (4, 3)))
    ax.text(0.003, m / 1000 + 0.03, 'merge', transform=ax.get_yaxis_transform(), fontsize=8.5, color=INK)
    ax.axvline(c['demand_end'] / 60, color=MUTED, lw=1, ls=(0, (4, 3)))
    ax.grid(False)
    ax.set_xlim(0, view_end(r))
    ax.set_ylim(0, c['road_end'] / 1000)
    ax.set_xlabel('Simulation time (min)')
    ax.set_ylabel('Position (km)')
    cax = fig.add_axes([0.915, 0.11, 0.014, 0.73])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label('Speed (km/h)', color=INK_2)
    cb.outline.set_visible(False)
    _save(fig, path)


def _binned_speed(rows, lo_m, hi_m, bin_s):
    """Mean speed of all mainline vehicles inside [lo, hi) m, per time bin."""
    sums, counts = {}, {}
    for z in rows:
        if z['lane'] == 0 and lo_m <= z['x_km'] * 1000 < hi_m:
            b = int(z['t_s'] // bin_s)
            sums[b] = sums.get(b, 0.0) + z['v_kmh']
            counts[b] = counts.get(b, 0) + 1
    keys = sorted(sums)
    return [(k * bin_s + bin_s / 2) / 60 for k in keys], [sums[k] / counts[k] for k in keys]


def fig_merge_speed(r, path):
    """Mainline speed upstream of, approaching, and downstream of the merge."""
    plt = _plt()
    c = r['summary']['config']
    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.13)
    _header(fig, 'Mainline speed by section',
            'Mean speed of vehicles on the mainline, 30 s bins (gaps = no vehicles). Slow approach with '
            'fast downstream traffic = queue at the merge.')
    _demand_window(ax, c, r=r)
    for (name, lo, hi), col in zip(sections(c), SERIES):
        t, v = _binned_speed(r['trajectories'], lo, hi, 30)
        t, v = np.array(t), np.array(v, dtype=float)
        if len(t):
            gaps = np.where(np.diff(t) > 0.6)[0] + 1
            t, v = np.insert(t, gaps, np.nan), np.insert(v, gaps, np.nan)
        ax.plot(t, v, color=col, label=f'{name} {lo / 1000:.1f}-{hi / 1000:.1f} km')
    ax.axhline(c['v0'] * 3.6, color=MUTED, lw=1, ls=(0, (4, 3)))
    ax.text(view_end(r), c['v0'] * 3.6, 'desired speed v0 ', ha='right', va='bottom',
            fontsize=8.5, color=MUTED)
    ax.set_xlim(0, view_end(r))
    ax.set_ylim(0, SPEED_MAX_KMH * 1.12)
    ax.set_xlabel('Simulation time (min)')
    ax.set_ylabel('Speed (km/h)')
    _legend(ax, loc='lower left', ncol=3)
    _save(fig, path)


def fig_merge_events(r, path):
    """Each accepted merge: merging speed, and the new follower's requested acceleration."""
    plt = _plt()
    c = r['summary']['config']
    acc = [e for e in r['events'] if e['result'] == 'accepted']
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True,
                                 gridspec_kw=dict(hspace=0.18))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.86, bottom=0.09)
    _header(fig, 'Accepted merges',
            'One marker per merge. Lower panel: requested IDM acceleration of the mainline vehicle '
            'that ends up directly behind the merging vehicle.')
    for ax in (a1, a2):
        _demand_window(ax, c, label=ax is a1, r=r)
    recorded = any('rear_origin' in e for e in acc)
    if recorded:
        groups = [('Follower is a mainline vehicle', lambda e: e.get('rear_origin') == 0, SERIES[0], 'o'),
                  ('Follower is a ramp vehicle', lambda e: e.get('rear_origin') == 1, SERIES[2], 's'),
                  ('No follower', lambda e: e.get('rear_origin') is None, MUTED, 'D')]
    else:  # older runs did not record the follower
        groups = [('Accepted merge', lambda e: True, SERIES[0], 'o')]
        a2.text(0.5, 0.5, 'Follower response was not recorded by this model version',
                transform=a2.transAxes, ha='center', va='center', fontsize=10, color=INK_2)
    for label, test, col, m in groups:
        sel = [e for e in acc if test(e)]
        if not sel:
            continue
        a1.scatter([e['t'] / 60 for e in sel], [e['v'] * 3.6 for e in sel], s=30, color=col,
                   marker=m, edgecolor=SURFACE, linewidth=1, label=f'{label} ({len(sel)})', zorder=3)
        with_rear = [e for e in sel if e.get('rear_acc_after_mps2') is not None]
        a2.scatter([e['t'] / 60 for e in with_rear], [e['rear_acc_after_mps2'] for e in with_rear],
                   s=30, color=col, marker=m, edgecolor=SURFACE, linewidth=1, zorder=3)
    a1.set_ylabel('Merge speed (km/h)')
    a1.set_ylim(0, SPEED_MAX_KMH)
    _legend(a1, loc='upper right', ncol=3)
    a2.axhline(0, color=AXIS, lw=1)
    # Run 1-2 accepted merges against an IDM braking limit; run 3 onward uses b_ins on a
    # kinematic deceleration, so the line shows the physical braking bound instead.
    if 'merge_brake' in c:
        limit, label = c['merge_brake'], f"acceptance limit -{c['merge_brake']} m/s² "
    else:
        limit, label = -c['amin'], f"physical braking limit {c['amin']} m/s² "
    a2.axhline(-limit, color='#d03b3b', lw=1, ls=(0, (4, 3)))
    a2.text(view_end(r), -limit, label, ha='right', va='bottom', fontsize=8.5, color='#d03b3b')
    lows = [e['rear_acc_after_mps2'] for e in acc if e.get('rear_acc_after_mps2') is not None]
    a2.set_ylim(min([-limit - 0.5] + [x - 0.3 for x in lows]), c['a'] + 0.3)
    a2.set_ylabel('Follower acceleration\nafter merge (m/s²)')
    a2.set_xlabel('Simulation time (min)')
    a2.set_xlim(0, view_end(r))
    _save(fig, path)


def fig_trip_delay(r, path):
    """Delay of every completed trip against its scheduled arrival time."""
    plt = _plt()
    c = r['summary']['config']
    basis = ('free-flow time of an unimpeded vehicle' if 'free_flow_time_main_s' in r['summary']
             else 'distance / v0')
    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.13)
    _header(fig, 'Trip delay by arrival time',
            f'Delay = exit time - scheduled arrival - {basis}. Includes waiting in queues.')
    _demand_window(ax, c, r=r)
    for origin, label, col, m in ((0, 'Mainline origin', SERIES[0], 'o'), (1, 'Ramp origin', SERIES[1], 's')):
        trips = [z for z in r['trips'] if z['origin'] == origin]
        if not trips:
            continue
        mean = np.mean([z['delay_s'] for z in trips])
        ax.scatter([z['scheduled_s'] / 60 for z in trips], [z['delay_s'] for z in trips], s=18, color=col,
                   marker=m, edgecolor=SURFACE, linewidth=0.6, zorder=3,
                   label=f'{label}: n = {len(trips)}, mean {mean:.0f} s')
    ax.set_xlim(0, view_end(r))
    ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
    ax.set_xlabel('Scheduled arrival time (min)')
    ax.set_ylabel('Trip delay (s)')
    _legend(ax, loc='center right')
    _save(fig, path)


# Figures kept for teaching: where/when traffic slows, why (merges force braking), and who
# pays the delay (mainline vs. ramp).
FIGURES = [
    ('speed_heatmap.png', fig_speed_heatmap),
    ('trajectories.png', fig_trajectories),
    ('merge_speed.png', fig_merge_speed),
    ('merge_events.png', fig_merge_events),
    ('trip_delay.png', fig_trip_delay),
]


# --------------------------------------------------------------------------
# Traffic management centre (only for runs with ramp control)
# --------------------------------------------------------------------------
MODE_COLORS = {'hold': '#f0a46e', 'fallback': '#d1462f', 'override': '#6250d6'}


def controlled(c):
    """True when the run had a ramp meter (ALINEA or a fixed rate)."""
    return c.get('ramp_control') is not None or bool(c.get('ramp_release_rate'))


def tmc_geometry(c):
    xs = c['merge_x'] - c['acc_length']
    meter = xs if c.get('meter_x') is None else c['meter_x']
    dets = sorted(d for d in c['detectors'] if 0 < d < c['road_end'])
    return xs, meter, dets


def detector_rows(r):
    """One row per detector: position, what it measures, its role, and statistics of the reports
    the controller received over the evaluation window."""
    s, c = r['summary'], r['summary']['config']
    xs, meter, dets = tmc_geometry(c)
    t0, t1 = s['measurement_window_s']
    reports = r.get('reports', [])
    rows = []

    def window(sid):
        rep = [z for z in reports if z['sensor_id'] == sid and t0 <= z['interval_start_s'] < t1]
        return rep, [z for z in rep if z['quality_flag'] == 'ok'], len(rep) * c['report_interval'] / 3600

    for d in dets:
        sid = f'D{int(round(d)):04d}'
        rep, ok, hours = window(sid)
        spd = [z['mean_speed_mps'] for z in ok if z['mean_speed_mps'] is not None]
        where = ('inside the merge area' if xs <= d <= c['merge_x'] else
                 'downstream of the merge' if d > c['merge_x'] else 'upstream of the merge')
        rows.append(dict(
            id=sid, pos=f'{d / 1000:.1f} km mainline ({where})', measures='count, occupancy, speed',
            role='ALINEA input (occupancy)' if abs(d - c.get('alinea_detector', -1)) < 1e-6 else 'recorded only',
            flow=f"{sum(z['count'] for z in ok) / hours:,.0f} veh/h" if hours and ok else 'n/a',
            occ=(f"{100 * np.mean([z['occupancy'] for z in ok]):.1f}% (max {100 * max(z['occupancy'] for z in ok):.0f}%)"
                 if ok else 'n/a'),
            speed=f"{3.6 * np.mean(spd):.0f} km/h" if spd else 'n/a'))
    for sid, pos, role in (('RAMP_IN', 'ramp queue tail (arrivals)', 'queue estimate'),
                           ('RAMP_OUT', f'stop line, {meter / 1000:.1f} km (passages)', 'queue estimate')):
        rep, ok, hours = window(sid)
        rows.append(dict(id=sid, pos=pos, measures='count', role=role,
                         flow=f"{sum(z['count'] for z in ok) / hours:,.0f} veh/h" if hours and ok else 'n/a',
                         occ='–', speed='–'))
    return rows


def fig_detector_layout(r, path):
    """Schematic of the corridor with the detectors, the ramp counters and the stop line."""
    plt = _plt()
    c = r['summary']['config']
    xs, meter, dets = tmc_geometry(c)
    L, m = c['road_end'] / 1000, c['merge_x'] / 1000
    xr = (xs - c['ramp_length']) / 1000
    fig, ax = plt.subplots(figsize=(11, 3.4))
    fig.subplots_adjust(left=0.03, right=0.97, top=0.78, bottom=0.16)
    _header(fig, 'Detectors and ramp meter',
            'Point detectors report every %.0f s; the controller sees only these reports. Green = ALINEA input.'
            % c['report_interval'])
    ax.grid(False)
    for sp in ('left', 'top', 'right'):
        ax.spines[sp].set_visible(False)
    ax.set_yticks([])
    road = '#d9dce3'
    ax.plot([0, L], [0, 0], color=road, lw=14, solid_capstyle='butt', zorder=1)
    ax.plot([xs / 1000, m], [-0.32, -0.32], color=road, lw=10, solid_capstyle='butt', zorder=1)
    ax.plot([xr, xs / 1000], [-0.9, -0.32], color=road, lw=10, solid_capstyle='butt', zorder=1)
    ax.text(0.01, 0.12, 'mainline', fontsize=9, color=INK_2, va='bottom')
    ax.text((xs / 1000 + m) / 2, -0.47, f"acceleration lane {c['acc_length']:.0f} m", fontsize=8.5,
            color=INK_2, ha='center', va='top')
    ax.text(xr - 0.015, -0.9, f"ramp {c['ramp_length']:.0f} m", fontsize=8.5, color=INK_2, ha='right', va='center')
    ax.plot([m, m], [-0.45, 0.12], color=SERIES[0], lw=1.2)
    ax.text(m + 0.01, -0.36, 'lane end', fontsize=8.5, color=SERIES[0], va='center')
    for d in dets:
        main_in = abs(d - c.get('alinea_detector', -1)) < 1e-6 and c.get('ramp_control') == 'alinea'
        col = '#1a9a5c' if main_in else INK_2
        ax.plot([d / 1000] * 2, [-0.1, 0.1], color=col, lw=3.5 if main_in else 2.2, zorder=3)
        ax.text(d / 1000, 0.18, f'D{int(round(d)):04d}' + ('\nALINEA input' if main_in else ''), ha='center',
                va='bottom', fontsize=9, color=col, fontweight='bold' if main_in else 'normal')
    ax.plot([xr], [-0.9], marker='s', ms=7, color=SERIES[1], zorder=4)
    ax.text(xr, -1.05, 'RAMP_IN\n(queue tail)', ha='center', va='top', fontsize=8.5, color=SERIES[1])
    ym = -0.32 - (xs - meter) / c['ramp_length'] * 0.58
    ax.plot([meter / 1000], [ym], marker='s', ms=7, color=SERIES[1], zorder=4)
    ax.plot([meter / 1000 - 0.012, meter / 1000 + 0.012], [ym - 0.12, ym + 0.12], color=INK, lw=2.5, zorder=4)
    ax.text(meter / 1000 - 0.03, ym - 0.16, 'RAMP_OUT + stop line\n(signal, one car per green)', ha='right',
            va='top', fontsize=8.5, color=SERIES[1])
    ax.set_xlim(-0.02, L + 0.02)
    ax.set_ylim(-1.5, 0.65)
    ax.set_xticks(np.arange(0, L + 0.01, 0.25))
    ax.set_xlabel('Position along the mainline (km)')
    _save(fig, path)


def fig_tmc_timeline(r, path):
    """Controller trace: occupancy received vs. target, release rate and mode, ramp queue."""
    plt = _plt()
    s, c = r['summary'], r['summary']['config']
    t = r.get('tmc', [])
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.6), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.9, bottom=0.07, hspace=0.18)
    sid = f"{c.get('alinea_detector', 0) / 1000:.1f} km"
    _header(fig, 'What the controller saw and did',
            f'Every {c["report_interval"]:.0f} s: occupancy received from the {sid} detector, the release rate chosen, '
            'and the ramp queue estimated from the counters.')
    xe = view_end(r)
    tm = np.array([z['t_s'] for z in t]) / 60
    for ax in axes:
        _demand_window(ax, c, label=ax is axes[0], r=None)
        ax.set_xlim(0, xe)
    # (a) occupancy
    ax = axes[0]
    occ = np.array([np.nan if z['occupancy'] is None else 100 * z['occupancy'] for z in t], dtype=float)
    occ_t = np.array([np.nan if z.get('occupancy_true') is None else 100 * z['occupancy_true'] for z in t], dtype=float)
    differs = len(t) and np.isfinite(occ).any() and np.nanmax(np.abs(occ - occ_t)) > 1e-9
    if differs:
        ax.plot(tm, occ_t, color=MUTED, lw=1.1, label='true occupancy (scoring only)')
    ax.plot(tm, occ, color=SERIES[0], lw=1.6, marker='o', ms=2.5, label='occupancy received')
    if c.get('ramp_control') == 'alinea':
        ax.axhline(100 * c['alinea_target_occ'], color='#1a9a5c', ls=(0, (4, 3)), lw=1.4,
                   label=f"target o* = {100 * c['alinea_target_occ']:.0f}%")
    ax.set_ylabel(f'Occupancy at {sid} (%)')
    ax.set_ylim(0, max(np.nanmax(np.r_[occ, occ_t, 1.0]) * 1.25, 1.0) if len(t) else 1)
    _legend(ax, loc='upper left', ncol=3)
    # (b) release rate and mode
    ax = axes[1]
    rate = np.array([np.nan if z['rate_veh_h'] is None else z['rate_veh_h'] for z in t], dtype=float)
    start = c.get('rate_max') if c.get('ramp_control') == 'alinea' else c.get('ramp_release_rate')
    ax.step(np.r_[0, tm], np.r_[start, rate], where='post', color=SERIES[0], lw=1.8, label='release rate')
    prof = c['ramp_profile']
    ax.step([a / 60 for a, _, _ in prof] + [prof[-1][1] / 60], [rr for *_, rr in prof] + [prof[-1][2]],
            where='post', color=SERIES[1], lw=1.4, ls=(0, (4, 3)), label='ramp demand')
    for z in t:
        if z['mode'] in MODE_COLORS:
            ax.axvspan((z['t_s'] - c['report_interval']) / 60, z['t_s'] / 60, color=MODE_COLORS[z['mode']],
                       alpha=0.25, lw=0)
    for mode, col in MODE_COLORS.items():
        if any(z['mode'] == mode for z in t):
            ax.fill_between([], [], color=col, alpha=0.25, label=mode)
    if c.get('ramp_control') == 'alinea':
        ax.axhline(c['rate_max'], color=MUTED, lw=0.8)
        ax.text(xe, c['rate_max'], 'maximum: signal rests green ', ha='right', va='bottom', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Rate (veh/h)')
    top = c['rate_max'] if c.get('ramp_control') == 'alinea' else np.nanmax(np.r_[rate, start])
    ax.set_ylim(0, top * 1.15)
    _legend(ax, loc='lower right', ncol=5)
    # (c) queue
    ax = axes[2]
    logs = r.get('logs', [])
    if logs and 'ramp_before_meter' in logs[0]:
        ax.plot([z['t_s'] / 60 for z in logs], [z['ramp_before_meter'] for z in logs], color=MUTED, lw=1.1,
                label='true vehicles before the stop line')
    ax.step(tm, [z['queue_est_veh'] for z in t], where='post', color=SERIES[0], lw=1.6, label='estimate (counters)')
    ax.plot([z['forecast_target_s'] / 60 for z in t], [z['forecast_veh'] for z in t], 'o', ms=2.5,
            color=SERIES[2], label=f"{c['forecast_horizon']:.0f} s forecast (advisory)")
    cap = s.get('ramp_capacity_veh')
    if cap:
        ax.axhline(cap, color=SERIES[3], lw=1, ls=(0, (4, 3)))
        ax.text(xe, cap, f'ramp holds {cap} ', ha='right', va='bottom', fontsize=8.5, color=SERIES[3])
    ax.set_ylabel('Ramp vehicles')
    ax.set_xlabel('Simulation time (min)')
    ax.set_ylim(0, max(ax.get_ylim()[1], (cap or 0) * 1.25))
    _legend(ax, loc='upper left', ncol=3)
    _save(fig, path)


TMC_FIGURES = [('detector_layout.png', fig_detector_layout), ('tmc_timeline.png', fig_tmc_timeline)]


# --------------------------------------------------------------------------
# ACC runs (acc_share > 0): which vehicles are equipped, and a zoomed time-space diagram by type.
# --------------------------------------------------------------------------
def with_acc(c):
    return bool(c.get('acc_share'))


def acc_ids(r):
    """IDs of the ACC-equipped vehicles (the type is stored with each completed trip)."""
    return {z['id'] for z in r.get('trips', []) if z.get('type') == 'ACC'}


def busiest_window(r, width_s=600.0):
    """Start (s) of the width_s window inside the evaluation window in which the mainline is
    slowest over the last 500 m before the end of the acceleration lane (30 s bins)."""
    c = r['summary']['config']
    m, t0, t1 = c['merge_x'], c['eval_start'], c['demand_end']
    nb = int((t1 - t0) // 30)
    sums, cnt = np.zeros(nb), np.zeros(nb)
    for z in r['trajectories']:
        if z['lane'] == 0 and m - 500 <= z['x_km'] * 1000 < m and t0 <= z['t_s'] < t1:
            j = min(int((z['t_s'] - t0) // 30), nb - 1)
            sums[j] += z['v_kmh']
            cnt[j] += 1
    mean = np.where(cnt > 0, sums / np.maximum(cnt, 1), SPEED_MAX_KMH)
    k = max(1, int(width_s // 30))
    scores = [mean[i:i + k].mean() for i in range(max(1, nb - k + 1))]
    return t0 + 30.0 * int(np.argmin(scores))


def fig_acc_trajectories(r, path):
    """Ten minutes of mainline trajectories around the slowest period: by vehicle type, and by speed."""
    plt = _plt()
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from matplotlib.lines import Line2D
    c = r['summary']['config']
    ids = acc_ids(r)
    start = busiest_window(r)
    rows = [z for z in r['trajectories'] if z['lane'] == 0 and start - 2 <= z['t_s'] <= start + 602]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 8.6), sharex=True, gridspec_kw=dict(hspace=0.1))
    fig.subplots_adjust(left=0.07, right=0.9, top=0.87, bottom=0.07)
    _header(fig, 'Trajectories by vehicle type',
            f"Mainline, the 10 minutes with the slowest approach. Top: ACC (blue) and human-driven (orange) vehicles; "
            f"bottom: the same lines colored by speed.\n"
            f"Seed {c['seed']}, {100 * c['acc_share']:.0f}% ACC, dt = {c['dt']} s; demand: {demand_label(c)}.")
    for flag, color in ((False, SERIES[1]), (True, SERIES[0])):
        seg, _ = _segments([z for z in rows if (z['id'] in ids) == flag], 0)
        top.add_collection(LineCollection(seg, colors=color, linewidths=0.8))
    top.legend(handles=[Line2D([], [], color=SERIES[0], lw=1.6, label='ACC'),
                        Line2D([], [], color=SERIES[1], lw=1.6, label='Human-driven')],
               frameon=False, loc='lower right', fontsize=9, labelcolor=INK_2)
    cmap, norm = _speed_cmap(), Normalize(0, SPEED_MAX_KMH)
    seg, v = _segments(rows, 0)
    lc = LineCollection(seg, cmap=cmap, norm=norm, linewidths=0.8)
    lc.set_array(v)
    bottom.add_collection(lc)
    lo = max(0.0, (c['merge_x'] - c['acc_length'] - 700) / 1000)
    hi = min(c['road_end'], c['merge_x'] + 300) / 1000
    for ax in (top, bottom):
        _mark_merge(ax, c)
        ax.set_ylim(lo, hi)
        ax.set_ylabel('Mainline position (km)')
        ax.grid(axis='x', visible=False)
    top.text(0.003, c['merge_x'] / 1000 + 0.02, 'acceleration lane', color='#1c5cab', fontsize=8.5,
             transform=top.get_yaxis_transform())
    bottom.set_xlim(start / 60, start / 60 + 10)
    bottom.set_xlabel('Simulation time (min)')
    pos = bottom.get_position()
    cax = fig.add_axes([0.915, pos.y0, 0.014, pos.height])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    cb.set_label('Speed (km/h)', color=INK_2)
    cb.outline.set_visible(False)
    _save(fig, path)


ACC_FIGURES = [('acc_trajectories.png', fig_acc_trajectories)]


def _stability(c):
    """Left side of the linear string-stability criterion of Gunter et al. (2020); >= 0 is stable."""
    return c['acc_kp'] * c['acc_h'] ** 2 + 2 * c['acc_kv'] * c['acc_h'] - 2


def acc_main(r, embed):
    """Main-page section on the ACC vehicles: the law in one line, what it reads, and trajectories by type."""
    s, c = r['summary'], r['summary']['config']
    crit = _stability(c)
    share_t = 100 * s['acc_takeover_vehicle_s'] / s['acc_mainline_vehicle_s'] if s.get('acc_mainline_vehicle_s') else 0.0
    delay = c.get('acc_sensor_delay') or 0
    facts = [('Equipped', f"{100 * c['acc_share']:.0f}% of both streams ({s['acc_vehicles_main']} mainline, "
                          f"{s['acc_vehicles_ramp']} ramp vehicles)"),
             ('Law', f"u = k_p [s − (η + h v)] − k_v (v − v_leader), k_p = {c['acc_kp']:g} s⁻², "
                     f"k_v = {c['acc_kv']:g} s⁻¹, η = {c['acc_eta']:.2f} m, h = {c['acc_h']:g} s"),
             ('String stability', f"k_p h² + 2 k_v h − 2 = {crit:+.2f} ({'met' if crit >= 0 else 'not met'})"),
             ('Reads', 'own speed, gap and speed of the vehicle directly ahead'
                       + (f', {delay:g} s old' if delay else '')),
             ('Driver takeover', f"{s['acc_takeover_episodes']} episodes, {share_t:.1f}% of ACC time on the mainline")]
    facts_html = ''.join(f'<span><b>{html.escape(a)}:</b> {html.escape(b)}</span>' for a, b in facts)
    return f"""
<section id="acc">
  <h2>ACC vehicles</h2>
  <div class="facts">{facts_html}</div>
  <figure><img src="{embed('acc_trajectories.png')}" alt="Mainline trajectories by vehicle type and by speed"></figure>
</section>"""


def acc_section(r):
    """Appendix block on the ACC vehicles: counts, takeovers, braking and gaps by vehicle type."""
    s = r['summary']
    rows = [('ACC vehicles (mainline / ramp)', f"{s['acc_vehicles_main']} / {s['acc_vehicles_ramp']}"),
            ('ACC time on the mainline', f"{s['acc_mainline_vehicle_s'] / 3600:.1f} veh·h"),
            ('Driver takeovers (episodes / time)',
             f"{s['acc_takeover_episodes']} / {s['acc_takeover_vehicle_s']:.0f} veh·s"),
            ('Merges in front of an ACC follower', f"{s['merges_with_acc_follower']} of {s['merges']}"),
            ('Braking harder than 3 m/s², HDV / ACC',
             f"{s['hard_braking_vehicle_s_hdv']:.0f} / {s['hard_braking_vehicle_s_acc']:.0f} veh·s"),
            ('Smallest net gap behind HDV / ACC follower',
             f"{_fmt(s['min_net_gap_hdv_follower_m'], 2)} / {_fmt(s['min_net_gap_acc_follower_m'], 2)} m"),
            ('Total trip delay, HDV / ACC',
             f"{s['total_delay_hdv_veh_s'] / 3600:.1f} / {s['total_delay_acc_veh_s'] / 3600:.1f} veh·h"),
            ('Discharge at 1.6 km while the bottleneck is active', f"{_fmt(s.get('discharge_flow_active_veh_h'), 0)} veh/h"),
            ('Disturbance ratio (speed SD 300–500 m upstream ÷ at the merge)', _fmt(s.get('disturbance_ratio'), 2))]
    return ('<h2>ACC vehicles</h2><div class="grid2"><div class="group"><h3>By vehicle type</h3><table>'
            + _rows_html(rows) + '</table></div></div>')


def _figure(src, alt, caption):
    return f'<figure><img src="{src}" alt="{html.escape(alt)}"><figcaption>{caption}</figcaption></figure>'


CAPTIONS = {
    'speed_heatmap.png': ('Mainline speed map', '<b>Mainline speed</b> in 30 s × 100 m cells; red is slow. A merge '
                          'bottleneck is a red area that ends at the merge and spreads upstream.'),
    'trip_delay.png': ('Trip delay by arrival time', '<b>Delay of each trip</b> by arrival time, mainline vs. ramp '
                       '(includes waiting before entering the road).'),
    'trajectories.png': ('Time-space diagram', '<b>Trajectories.</b> Flat, dark lines are slow or stopped vehicles.'),
    'merge_speed.png': ('Speed by section', '<b>Speed by section.</b> A slow approach between faster upstream and '
                        'downstream sections is the signature of a merge bottleneck.'),
    'merge_events.png': ('Accepted merges', '<b>Merges.</b> Speed at which each ramp vehicle joins, and how hard the '
                         'mainline vehicle behind it must brake.'),
}


def _rows_html(rows):
    return ''.join(f'<tr><th>{html.escape(a)}</th><td>{html.escape(b)}</td></tr>' for a, b in rows)


def _defects(c):
    out = []
    if c.get('detector_miss_prob'):
        out.append(f"{100 * c['detector_miss_prob']:.0f}% of passages missed")
    if c.get('occupancy_noise_sd'):
        out.append(f"occupancy noise SD {100 * c['occupancy_noise_sd']:.1f} points")
    if c.get('report_delay'):
        out.append(f"reports delayed {c['report_delay']:.0f} s")
    if c.get('report_dropout'):
        out.append('reports lost ' + ', '.join(f'{a:.0f}-{b:.0f} s' for a, b in c['report_dropout']))
    return out


def tmc_main(r, embed):
    """Main-page section on the ramp meter: what it reads, its rule in one line, and the controller trace."""
    c = r['summary']['config']
    xs, meter, dets = tmc_geometry(c)
    if c.get('ramp_control') == 'alinea':
        facts = [('Reads', f"occupancy at {c['alinea_detector'] / 1000:.1f} km, every {c['report_interval']:.0f} s"),
                 ('Rule', f"r ← r + {c['alinea_gain'] / 100:.0f} veh/h per % × ({100 * c['alinea_target_occ']:.0f}% − o), "
                          f"{c['rate_min']:.0f}–{c['rate_max']:.0f} veh/h"),
                 ('Acts', f"signal at {meter / 1000:g} km: green {c['meter_green']:g} s + red ≥ {c['meter_min_red']:g} s, "
                          f"cycle 3600/r = {3600 / c['rate_max']:.0f}–{3600 / c['rate_min']:.0f} s, one car per green; "
                          f"green all the time at {c['rate_max']:.0f} veh/h")]
        title = 'Ramp meter (ALINEA)'
    else:
        facts = [('Acts', f"fixed {c['ramp_release_rate']:.0f} veh/h, one car per green at {meter / 1000:g} km")]
        title = 'Ramp meter (fixed rate)'
    if _defects(c):
        facts.append(('Detector defects', '; '.join(_defects(c))))
    facts_html = ''.join(f'<span><b>{html.escape(a)}:</b> {html.escape(b)}</span>' for a, b in facts)
    return f"""
<section id="tmc">
  <h2>{title}</h2>
  <div class="facts">{facts_html}</div>
  {_figure(embed('tmc_timeline.png'), 'Occupancy, release rate and ramp queue over time',
           '<b>Controller trace.</b> When occupancy (top) is above the target, the release rate (middle) drops '
           'below the ramp demand and vehicles queue at the stop line (bottom).')}
</section>"""


def tmc_section(r, embed):
    """Appendix block on the TMC: layout, detector table, controller design and statistics."""
    s, c = r['summary'], r['summary']['config']
    xs, meter, dets = tmc_geometry(c)
    t = r.get('tmc', [])
    w0, w1 = s['measurement_window_s']
    peak = [z for z in t if w0 <= z['t_s'] < w1]
    ramp_peak = max(rr for *_, rr in c['ramp_profile']) if c['ramp_profile'] else 0
    restrict = 100 * np.mean([z['rate_veh_h'] < ramp_peak for z in peak]) if peak and ramp_peak else None
    det_html = ('<table class="wide"><tr><th>Detector</th><th>Position</th><th>Measures</th><th>Used for</th>'
                '<th>Flow</th><th>Occupancy (mean)</th><th>Speed</th></tr>'
                + ''.join(f"<tr><td><b>{html.escape(d['id'])}</b></td><td>{html.escape(d['pos'])}</td>"
                          f"<td>{html.escape(d['measures'])}</td><td>{html.escape(d['role'])}</td>"
                          f"<td>{html.escape(d['flow'])}</td><td>{html.escape(d['occ'])}</td>"
                          f"<td>{html.escape(d['speed'])}</td></tr>" for d in detector_rows(r)) + '</table>')
    defects = _defects(c)
    if c.get('ramp_control') == 'alinea':
        law = (f"r = clip(r_prev + {c['alinea_gain'] / 100:.0f} veh/h per % × ({100 * c['alinea_target_occ']:.0f}% − o), "
               f"{c['rate_min']:.0f}, {c['rate_max']:.0f}) veh/h")
        design = [('Cycle', f"every {c['report_interval']:.0f} s: observe, estimate, predict, decide, act"),
                  ('Input', f"occupancy at D{int(round(c['alinea_detector'])):04d} ({c['alinea_detector'] / 1000:.1f} km)"),
                  ('Control law (ALINEA)', law),
                  ('Missing report', f"hold the rate; fallback {c['fallback_rate']:.0f} veh/h after "
                                     f"{c['report_stale']:.0f} s without data"),
                  ('Queue override', 'off' if c.get('ramp_storage') is None
                   else f"maximum rate above {c['ramp_storage']} vehicles"),
                  ('Ramp meter', f"stop line at {meter / 1000:.2f} km; each cycle: green {c['meter_green']:g} s (one car), "
                                 f"then red, cycle 3600/r ≥ {c['meter_green'] + c['meter_min_red']:g} s; rests green at the maximum rate"),
                  ('Queue estimate', 'RAMP_IN − RAMP_OUT (cumulative counts)'),
                  ('Forecast', f"{c['forecast_horizon']:.0f} s ahead, Eq. (11); advisory, not used by the controller"),
                  ('Detector defects', '; '.join(defects) if defects else 'none (perfect detectors)')]
    else:
        design = [('Ramp meter', f"fixed {c['ramp_release_rate']:.0f} veh/h, stop line at {meter / 1000:.2f} km"),
                  ('Detector defects', '; '.join(defects) if defects else 'none')]
    m = s.get('tmc_modes', {})
    perf = [('Mean release rate (evaluation window)', f"{_fmt(s.get('mean_release_rate_veh_h'), 0)} veh/h"),
            (f'Cycles restricting the ramp (rate < {ramp_peak:.0f} veh/h)', 'n/a' if restrict is None else f'{restrict:.0f}%'),
            ('Cycles by mode', ', '.join(f'{k} {v}' for k, v in sorted(m.items()))),
            ('Greens used / unused', f"{s.get('ramp_release_slots_used')} / {s.get('ramp_release_slots_lost')}"),
            ('Total delay (mainline / ramp)', f"{s['accumulated_delay_veh_s'] / 3600:,.1f} veh·h "
                                              f"({s['total_delay_main_veh_s'] / 3600:,.1f} / {s['total_delay_ramp_veh_s'] / 3600:,.1f})"),
            ('Ramp vehicles stranded at the lane end', f"{s['stops_at_lane_end']}"),
            ('Max vehicles before the stop line', f"{s.get('max_ramp_queue_veh')} (ramp holds {s.get('ramp_capacity_veh')})"),
            ('Time with vehicles waiting off the ramp', f"{s['ramp_spillback_s'] / 60:.1f} min (max {s['max_ramp_external']} vehicles)")]
    occ_mae = s.get('detector_occupancy_mae')
    obs = [('Count error per 30 s at the ALINEA detector', f"{_fmt(s.get('detector_count_error_veh'), 2)} veh"),
           ('Occupancy error at the ALINEA detector (MAE)', 'n/a' if occ_mae is None else f"{100 * occ_mae:.2f} points"),
           ('Queue estimate error (MAE)', f"{_fmt(s.get('queue_estimate_mae_veh'), 2)} veh"),
           (f"Forecast vs. persistence MAE ({c['forecast_horizon']:.0f} s)",
            f"{_fmt(s.get('forecast_mae_veh'), 2)} / {_fmt(s.get('persistence_mae_veh'), 2)} veh"),
           ('Reports missing', f"{s.get('reports_missing_cycles', 0)} of {s.get('tmc_cycles')} cycles")]
    return f"""
<h2>Detectors and controller</h2>
<figure><img src="{embed('detector_layout.png')}" alt="Detector and ramp meter layout"></figure>
<h3 class="sub">Detectors (statistics over {w0 / 60:.0f}–{w1 / 60:.0f} min, from the reports the controller received)</h3>
{det_html}
<div class="grid2" style="margin-top:18px">
  <div class="group"><h3>Controller design</h3><table>{_rows_html(design)}</table></div>
  <div class="group"><h3>Controller performance</h3><table>{_rows_html(perf)}</table></div>
  <div class="group"><h3>Observation quality (vs. truth)</h3><table>{_rows_html(obs)}</table></div>
</div>"""


def tmc_replay(r):
    """Data for the browser replay: detector positions, stop line, release rate and greens."""
    c = r['summary']['config']
    if not controlled(c):
        return None
    xs, meter, dets = tmc_geometry(c)
    t = sorted(r.get('tmc', []), key=lambda z: z['t_s'])
    alinea = c.get('ramp_control') == 'alinea'
    return dict(detectors=dets, alinea_x=c.get('alinea_detector') if alinea else None, meter_x=meter,
                times=[0.0] + [z['t_s'] for z in t],
                rates=[c['rate_max'] if alinea else c['ramp_release_rate']] + [z['rate_veh_h'] for z in t],
                modes=['alinea' if alinea else 'fixed'] + [z['mode'] for z in t],
                releases=sorted(z['release_s'] for z in r['trips'] if z.get('release_s') is not None),
                rest=c['rate_max'] if alinea else None)


# --------------------------------------------------------------------------
# Tables and HTML report
# --------------------------------------------------------------------------
def csvwrite(path, rows):
    """Export dictionaries with a header; omit a table when there are no records."""
    if not rows:
        return
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _fmt(value, digits=1):
    if value is None:
        return 'n/a'
    if isinstance(value, float):
        return f'{value:,.{digits}f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


def _kpis(s):
    """Four headline numbers at the top of the report; everything else is in the appendix."""
    c = s['config']
    cards = []
    if 'total_delay_main_veh_s' in s:
        cards.append(('Total delay', f"{s['accumulated_delay_veh_s'] / 3600:,.1f} veh·h",
                      f"mainline {s['total_delay_main_veh_s'] / 3600:,.1f} + ramp {s['total_delay_ramp_veh_s'] / 3600:,.1f}"))
    else:
        cards.append(('Mean trip delay', f"{_fmt(s['completed_mean_delay_s'], 0)} s", 'completed trips'))
    cards.append(('Stranded at lane end', _fmt(s.get('stops_at_lane_end')), 'ramp vehicles that had to stop'))
    if s.get('congestion_duration_s') is not None:
        w = s.get('measurement_window_s') or [c['eval_start'], c['demand_end']]
        cards.append(('Congested at the merge', f"{s['congestion_duration_s'] / 60:.1f} min",
                      f"approach below {c['congested_kmh']:.0f} km/h, {w[0] / 60:.0f}–{w[1] / 60:.0f} min"))
    if controlled(c) and s.get('max_ramp_queue_veh') is not None:
        cards.append(('Ramp queue', f"max {s['max_ramp_queue_veh']}",
                      f"{s['ramp_spillback_s'] / 60:.1f} min with cars waiting off the ramp"))
    elif s.get('approach_speed_kmh') is not None:
        cards.append(('Speed at the merge', f"{_fmt(s['approach_speed_kmh'], 0)} km/h",
                      f"last 500 m before it; {_fmt(s['downstream_speed_kmh'], 0)} km/h after it"))
    if with_acc(c):
        cards.append(('ACC vehicles', f"{100 * c['acc_share']:.0f}%",
                      f"{s['acc_takeover_episodes']} driver takeovers"))
    return cards


def _flow_row(s):
    if 'downstream_flow_veh_h' in s:
        w = s['measurement_window_s']
        return (f"Discharge at {s['downstream_detector_km']:g} km, {w[0]:.0f}-{w[1]:.0f} s",
                f"{s['downstream_flow_veh_h']:.0f} veh/h")
    return ('Downstream flow at 2.2 km, 300-900 s', f"{s['downstream_flow_300_900_veh_h']} veh/h")


SUMMARY_ROWS = [
    ('Demand', [('Offered vehicles (mainline / ramp)', lambda s: f"{s['offered_main']} / {s['offered_ramp']}"),
                ('Entered / exited', lambda s: f"{s['entered']} / {s['exited']}"),
                ('Left on road / in queues',
                 lambda s: f"{s['remaining_on_road']} / {s['remaining_main_external'] + s['remaining_ramp_external']}"),
                (None, _flow_row)]),
    ('Merging', [('Accepted merges (during / after demand)',
                  lambda s: f"{s['merges']} ({s.get('merges_during_demand')} / {s.get('merges_after_demand')})"),
                 ('Mean merge speed', lambda s: f"{_fmt(s.get('mean_merge_speed_kmh'))} km/h"),
                 ('Mainline followers braking below -0.1 m/s²',
                  lambda s: f"{s['merges_braking_mainline_follower']} of {s['merges_with_mainline_follower']}"),
                 ('Ramp wait, mean / max', lambda s: f"{_fmt(s['mean_ramp_wait_s'], 0)} / {_fmt(s['max_ramp_wait_s'], 0)} s"),
                 ('Release slots used / lost',
                  lambda s: f"{s['ramp_release_slots_used']:,} / {s['ramp_release_slots_lost']:,}"),
                 ('Max on-ramp vehicles / external queue', lambda s: f"{s['max_ramp_onroad']} / {s['max_ramp_external']}")]),
    ('Bottleneck (evaluation window)', [('Upstream speed (1.5-1.0 km before merge or from the entry)', lambda s: f"{_fmt(s['upstream_speed_kmh'])} km/h"),
                    ('Approach speed (last 500 m before merge)', lambda s: f"{_fmt(s['approach_speed_kmh'])} km/h"),
                    ('Downstream speed (200 m after merge to 700 m or the exit)', lambda s: f"{_fmt(s['downstream_speed_kmh'])} km/h"),
                    ('Speed SD upstream / approach / downstream',
                     lambda s: f"{_fmt(s['upstream_speed_sd_kmh'])} / {_fmt(s['approach_speed_sd_kmh'])} / {_fmt(s['downstream_speed_sd_kmh'])} km/h"),
                    ('Congested time at the merge approach', lambda s: f"{s['congestion_duration_s'] / 60:.1f} min"),
                    ('Longest queue upstream of the merge', lambda s: f"{s['max_queue_extent_m']:.0f} m"
                     + (' (reaches entry)' if s['queue_reaches_entry'] else '')),
                    ('Congested time / longest queue, whole run (reference)',
                     lambda s: f"{s['congestion_duration_full_run_s'] / 60:.1f} min / {s['max_queue_extent_full_run_m']:.0f} m"),
                    ('Ramp queue above storage', lambda s: f"{s['ramp_spillback_s'] / 60:.1f} min"),
                    ('Slowest 30 s x 100 m cell before the merge', lambda s: f"{_fmt(s['pre_merge_min_cell_kmh'])} km/h"),
                    ('Max mainline entry queue', lambda s: f"{s['max_main_external']}")]),
    ('Performance', [('Mean delay of completed trips', lambda s: f"{_fmt(s['completed_mean_delay_s'])} s"),
                     ('Free-flow time mainline / ramp',
                      lambda s: f"{_fmt(s['free_flow_time_main_s'])} / {_fmt(s['free_flow_time_ramp_s'])} s"),
                     ('Total delay (vs. free-flow time, incl. unfinished trips)',
                      lambda s: f"{_fmt(s['accumulated_delay_veh_s'] / 3600, 2)} veh·h"),
                     ('Mainline vehicle-time mean speed', lambda s: f"{_fmt(s['main_vehicle_time_mean_kmh'])} km/h")]),
    ('Checks', [('Minimum net gap', lambda s: f"{_fmt(s['min_net_gap_m'], 2)} m"),
                ('Minimum ramp stop-line clearance', lambda s: f"{_fmt(s['min_ramp_stop_clearance_m'], 2)} m"),
                ('Strongest applied deceleration', lambda s: f"{_fmt(s['min_applied_acceleration_mps2'], 2)} m/s²"),
                ('Clipped braking vehicle-steps', lambda s: f"{s['brake_clipped_vehicle_steps']}"),
                ('Conservation checks passed', lambda s: f"{s['conservation_checks']:,} steps")]),
]

CONFIG_GROUPS = [
    ('Run', ['seed', 'dt', 'duration', 'demand_end', 'eval_start', 'congested_kmh']),
    ('Demand (veh/h)', ['main_profile', 'ramp_profile', 'warmup', 'peak_end', 'peak_main_rate', 'peak_ramp_rate', 'main_rate', 'ramp_rate']),  # older runs
    ('Geometry (m)', ['road_end', 'merge_x', 'ramp_start', 'merge_start', 'merge_end', 'ramp_storage', 'detectors']),
    ('Ramp, acceleration lane and merging', ['ramp_release_rate', 'acc_length', 'ramp_length', 'ramp_v0', 'acc_lane_a',
                                  'b_safe', 'b_safe_end', 'merge_horizon', 'drop_dv', 'align_k', 'end_trigger', 'end_margin',
                                  'force_zone', 'zone_length', 'zone_speed', 'merge_gap_min', 'merge_time_gap',
                                  'T_ins', 'b_ins', 'ramp_free_speed', 'yield_enabled',
                                  'yield_zone', 'T_yield', 's0_yield', 'yield_max_time', 'coop_share',
                                  'green_duration', 'release_period', 'ramp_entry_speed', 'ramp_end_brake',
                                  'merge_brake']),
    ('Mainline entry', ['main_entry_speed', 'entry_brake']),
    ('IDM (+CAH)', ['v0', 'T', 'a', 'b', 's0', 'length', 'delta', 'amin', 'amax', 'cool']),
    ('ACC', ['acc_share', 'acc_kp', 'acc_kv', 'acc_eta', 'acc_h', 'acc_takeover_b', 'acc_sensor_delay',
             'acc_fallback_decel']),
]


def _summary_html(s):
    parts = []
    for group, rows in SUMMARY_ROWS:
        cells = []
        for label, get in rows:
            try:
                value = get(s)
            except (KeyError, TypeError, ZeroDivisionError, ValueError):
                continue   # metric not produced by this model version
            if label is None:
                label, value = value
            cells.append(f'<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>')
        if cells:
            parts.append(f'<div class="group"><h3>{html.escape(group)}</h3><table>{"".join(cells)}</table></div>')
    return ''.join(parts)


def _config_html(config):
    seen, parts = set(), []
    groups = CONFIG_GROUPS + [('Other', [k for k in config if k not in {k for _, ks in CONFIG_GROUPS for k in ks}])]
    for group, keys in groups:
        keys = [k for k in keys if k in config and k not in seen]
        if not keys:
            continue
        seen.update(keys)
        def shown(value):
            return format(value, 'g') if isinstance(value, float) else str(value)
        rows = ''.join(f'<tr><th><code>{html.escape(k)}</code></th><td>{html.escape(shown(config[k]))}</td></tr>'
                       for k in keys)
        parts.append(f'<div class="group"><h3>{html.escape(group)}</h3><table>{rows}</table></div>')
    return ''.join(parts)


def _shown_frames(result):
    """Replay frames up to view_end(): the empty tail after the last exit is dropped."""
    end = view_end(result) * 60 + 1e-6
    return [f for f in result['frames'] if f[0] <= end]


def _counters(result):
    """Cumulative [merges, exited] for each replay frame (logs are taken at the end of that step)."""
    dt = result['summary']['config']['dt']
    logs = {round(z['t_s'] - dt, 3): z for z in result['logs']}
    rows = []
    for frame in result['frames']:
        z = logs.get(round(frame[0], 3))
        rows.append([z['merges'], z['exited']] if z else [None, None])
    return rows


REPLAY_RAMP_M = 300.0   # drawn ramp approach in the HTML replay (m, to scale)


def _zone_replay(result):
    """Drawn ramp motion for the HTML replay of a merge-zone run (None for older models).

    For every shown frame: [[path position in m from the ramp entrance, speed km/h], ...]
    of vehicles on the drawn ramp or acceleration lane, plus each ramp vehicle's merge
    time so the replay can draw the merge as a short lane change. Display only; the
    same reconstruction as the GIF (make_gif.zone_plan)."""
    c = result['summary']['config']
    if c.get('acc_length'):
        # Acceleration-lane model: ramp vehicles are in the frames (lane 1); only merge times are needed.
        return dict(kind='lane', lc_time=3.0,
                    merge_t={str(e['id']): round(e['t'], 2) for e in result['events'] if e.get('result') == 'accepted'})
    if not c.get('zone_length'):
        return None
    from make_gif import zone_plan, _zone_positions, LC_TIME
    plan = zone_plan(result, REPLAY_RAMP_M)
    frames = [[[round(d, 1), round(v * 3.6, 1)] for d, v in _zone_positions(plan, f[0], REPLAY_RAMP_M)]
              for f in _shown_frames(result)]
    return dict(ramp_len=REPLAY_RAMP_M, lc_time=LC_TIME, frames=frames,
                merge_t={str(p['id']): round(p['te'], 2) for p in plan})


def fill_derived(result):
    """Add summary fields that older model versions did not compute, derived from recorded events.

    Nothing is re-simulated: merge counts and speeds come from the stored per-step
    events. Returns the list of fields that were derived."""
    s, c = result['summary'], result['summary']['config']
    accepted = [e for e in result['events'] if e['result'] == 'accepted']
    derived = []
    for key, value in (
            ('merges_during_demand', sum(e['t'] < c['demand_end'] for e in accepted)),
            ('merges_after_demand', sum(e['t'] >= c['demand_end'] for e in accepted)),
            ('mean_merge_speed_kmh', float(np.mean([e['v'] for e in accepted]) * 3.6) if accepted else None)):
        if key not in s:
            s[key] = value
            derived.append(key)
    return derived


def render(results, out, tables=True):
    """Export already computed runs. Call only after the user requests saving.

    tables=False writes only the figures and the HTML report (used by replot.py
    so a re-rendered old run does not duplicate its original CSV/JSON files)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for result in results.values():
        fill_derived(result)

    # Preserve tabular records for independent checks outside the report.
    if tables:
        for name, result in results.items():
            keys = ['trajectories', 'events', 'trips', 'detectors', 'logs']
            if controlled(result['summary']['config']):
                keys += ['reports', 'tmc']          # the observation and control layer exists only with a TMC
            for key in keys:
                # 'detectors' holds true position crossings used for the discharge flow (not TMC detectors).
                csvwrite(out / f"{name}_{'crossings' if key == 'detectors' else key}.csv", result.get(key) or [])
            (out / f'{name}_summary.json').write_text(json.dumps(result['summary'], indent=2), encoding='utf-8')

    ramp = results['with_ramp']
    summary = ramp['summary']
    for filename, draw in FIGURES:
        draw(ramp, out / filename)
    with_tmc = controlled(summary['config']) and bool(ramp.get('tmc'))
    if with_tmc:
        for filename, draw in TMC_FIGURES:
            draw(ramp, out / filename)
    acc_run = with_acc(summary['config'])
    if acc_run:
        for filename, draw in ACC_FIGURES:
            draw(ramp, out / filename)

    def embed(name):
        return 'data:image/png;base64,' + base64.b64encode((out / name).read_bytes()).decode()

    def fig(name, caption=True):
        alt, text = CAPTIONS[name]
        if not caption:     # main page: the figure's own title and subtitle already explain it
            return f'<figure><img src="{embed(name)}" alt="{html.escape(alt)}"></figure>'
        return _figure(embed(name), alt, text)

    # Main page: the problem (speed map), then the controller trace or who pays the delay.
    main_sections = ('<section id="bottleneck"><h2>Where traffic slows</h2>' + fig('speed_heatmap.png', False) + '</section>'
                     + (acc_main(ramp, embed) if acc_run else '')
                     + (tmc_main(ramp, embed) if with_tmc else
                        '<section id="delay"><h2>Who pays the delay</h2>' + fig('trip_delay.png', False) + '</section>'))
    # Appendix (collapsed): every other figure and the full tables.
    details = ('<h2>Traffic and merging</h2><div class="stack">'
               + ''.join(fig(n) for n in ('trajectories.png', 'merge_speed.png', 'merge_events.png')
                         + (('trip_delay.png',) if with_tmc else ()))
               + '</div>'
               + (tmc_section(ramp, embed) if with_tmc else '')
               + (acc_section(ramp) if acc_run else '')
               + '<h2>Run summary</h2><div class="grid2">' + _summary_html(summary) + '</div>'
               + '<h2>Configuration</h2><div class="grid2">' + _config_html(summary['config']) + '</div>'
               + '<h2>Notes</h2><ul class="notes">'
                 '<li>Collision, stop-line and vehicle-conservation checks run inside the model and stop the run on '
                 'failure. They show numerical consistency, not real-world safety.</li>'
                 '<li>One seed cannot judge a controller; compare cases on the 20 evaluation seeds '
                 '(<code>tmc_compare.py</code>).</li></ul>')

    kpis = ''.join(f'<div class="kpi"><div class="kpi-label">{html.escape(a)}</div>'
                   f'<div class="kpi-value">{html.escape(b)}</div><div class="kpi-note">{html.escape(n)}</div></div>'
                   for a, b, n in _kpis(summary))
    c = summary['config']
    templates = Path(__file__).parent / 'templates'
    page = (templates / 'replay.html').read_text(encoding='utf-8')
    replacements = {
        'RUN_LABEL': html.escape(f"Seed {c['seed']} · "
                                 + (f"acceleration lane {c['acc_length']:.0f} m · " if c.get('acc_length') else '')
                                 + demand_label(c)),
        'KPIS': kpis,
        'TITLE': html.escape((f"Freeway on-ramp with {100 * c['acc_share']:.0f}% ACC vehicles"
                              + (' and ALINEA ramp metering' if c.get('ramp_control') == 'alinea'
                                 else ' and a fixed-rate ramp meter' if c.get('ramp_release_rate')
                                 else ', no ramp control')) if acc_run
                             else 'Freeway on-ramp with ALINEA ramp metering' if c.get('ramp_control') == 'alinea'
                             else 'Freeway on-ramp with a fixed-rate ramp meter' if c.get('ramp_release_rate')
                             else 'All-HDV freeway with an on-ramp, no ramp control'),
        'ACC': json.dumps(sorted(acc_ids(ramp)) if acc_run else [], separators=(',', ':')),
        'ACC_HINT': ' Blue outline = ACC vehicle.' if acc_run else '',
        'CAVEAT': html.escape('Simulation (IDM+CAH car following, no yielding); not field data or a calibrated forecast.'
                              + (' The ramp meter uses detector reports only.' if with_tmc else '')
                              + (' ACC vehicles use onboard readings only.' if acc_run else '')),
        'MAIN_SECTIONS': main_sections,
        'DETAILS': details,
        'TMC': json.dumps(tmc_replay(ramp) if with_tmc else None, separators=(',', ':')),
        'DATA': json.dumps({name: _shown_frames(result) for name, result in results.items()}, separators=(',', ':')),
        'CONFIGS': json.dumps({name: result['summary']['config'] for name, result in results.items()}),
        'COUNTERS': json.dumps({name: _counters(result)[:len(_shown_frames(result))]
                                for name, result in results.items()},
                               separators=(',', ':')),
        'SPEED_STOPS': json.dumps(SPEED_STOPS),
        'RAMP': json.dumps(_zone_replay(ramp), separators=(',', ':')),
        'REPLAY_SCRIPT': (templates / 'replay.js').read_text(encoding='utf-8'),
    }
    for key, value in replacements.items():
        page = page.replace('{{' + key + '}}', value)
    (out / 'classroom_demo.html').write_text(page, encoding='utf-8')
    return summary
