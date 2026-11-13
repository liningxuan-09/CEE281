"""Optional replay GIF built from a saved run's recorded frames.

The GIF never reruns the traffic model: every position and speed comes from the
one-second frames stored in ``with_ramp_raw.json``. Usage::

    python3 -B make_gif.py results/<saved_run>

Layout (top to bottom): title and clock, the whole corridor, a zoomed view of
the merge area where individual vehicles are visible, live counters, and a time
bar marking the demand period.

Ramp vehicles are drawn entering at the start of the drawn ramp and driving to
the merge point. The model itself treats the ramp as a FIFO queue (the
acceleration lane is abstracted), so this approach is reconstructed for display:
each vehicle reaches its place in the queue exactly at its scheduled ramp
arrival time and leaves the ramp exactly when the model inserts it.
"""
import argparse
import bisect
import json
import math
from pathlib import Path

from PIL import GifImagePlugin, Image, ImageDraw, ImageFont
from PIL._binary import o16le as o16

from present import INK, INK_2, MUTED, GRID, AXIS, SURFACE, SPEED_MAX_KMH, speed_rgb, view_end

W, H = 1200, 640          # output size in pixels
SS = 2                    # supersampling factor for smooth edges
FRAME_STEP = 5            # use one recorded frame per 5 simulated seconds
FRAME_MS = 125            # 5 s / 0.125 s = 40x real time
END_HOLD_MS = 2000        # pause on the last frame before the GIF loops
ROAD = '#e8eaee'
CAR_EDGE = '#8d8c86'   # thin outline so pale free-flow cars stay visible
LANE_MARK = '#ffffff'
ZOOM_ACCENT = '#2a78d6'
GREEN, RED = '#1a9a5c', '#d03b3b'
RAMP_SPEED = 20.0         # m/s at which drawn ramp vehicles enter the ramp (72 km/h)
RAMP_BRAKE = 2.0          # m/s^2 used to stop at the back of the drawn ramp queue
QUEUE_SPACING = 7.0       # m per waiting vehicle (length + standstill gap)
RAMP_DX, RAMP_DY = 260, 150   # drawn ramp: entrance offset (px) left of and below the merge point
SMOOTH_MIN_SPEED = 8.0    # m/s; a head vehicle whose no-stop drive would be slower waits in the queue instead

_FONT_CANDIDATES = {
    False: ['/System/Library/Fonts/Supplemental/Arial.ttf', '/Library/Fonts/Arial.ttf',
            'C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
    True: ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/Library/Fonts/Arial Bold.ttf',
           'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
}
_font_cache = {}


def font(size, bold=False):
    """Return a TrueType font at the supersampled size, portable across macOS/Windows/Linux."""
    key = (size, bold)
    if key not in _font_cache:
        paths = list(_FONT_CANDIDATES[bold])
        try:  # Matplotlib always ships DejaVu Sans; use it if no system font is found.
            from matplotlib import font_manager
            paths.append(font_manager.findfont('DejaVu Sans:bold' if bold else 'DejaVu Sans'))
        except Exception:
            pass
        for p in paths:
            try:
                _font_cache[key] = ImageFont.truetype(p, size * SS)
                break
            except OSError:
                continue
        else:
            _font_cache[key] = ImageFont.load_default(size=size * SS)
    return _font_cache[key]


class Canvas:
    """Thin wrapper so drawing code can use 1x coordinates on a supersampled image."""

    def __init__(self):
        self.im = Image.new('RGB', (W * SS, H * SS), SURFACE)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, box, fill=None, outline=None, width=1, radius=0):
        box = [v * SS for v in box]
        if radius:
            self.d.rounded_rectangle(box, radius * SS, fill=fill, outline=outline, width=int(round(width * SS)))
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=int(round(width * SS)))

    def line(self, pts, fill, width=1):
        self.d.line([v * SS for v in pts], fill=fill, width=int(width * SS), joint='curve')

    def poly(self, pts, fill, outline=None, width=1):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill, outline=outline, width=int(width * SS))

    def circle(self, x, y, r, fill):
        self.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=fill)

    def text(self, x, y, s, size=14, bold=False, fill=INK, anchor='la'):
        self.d.text((x * SS, y * SS), s, font=font(size, bold), fill=fill, anchor=anchor)

    def dashed(self, x0, x1, y, fill, dash=10, gap=8, width=2):
        x = x0
        while x < x1:
            self.line((x, y, min(x + dash, x1), y), fill, width)
            x += dash + gap

    def finish(self):
        return self.im.resize((W, H), Image.LANCZOS)


def hexrgb(kmh):
    return '#%02x%02x%02x' % speed_rgb(kmh)


def mmss(t):
    return f'{int(t // 60):02d}:{int(t % 60):02d}'


def draw_frame(frame, log, cfg, t_end=None, ramp=None):
    t, cars, main_ext, ramp_ext = frame
    t_end = t_end or cfg['duration']
    cv = Canvas()
    demand = t < cfg['demand_end']

    # ---- Header ---------------------------------------------------------
    cv.text(32, 24, 'All-HDV freeway with an on-ramp', 24, True)
    sub = (f"IDM car following  ·  no yielding  ·  seed {cfg['seed']}  ·  replay at 40x real time"
           if cfg.get('zone_length', 0) > 0 and not cfg.get('yield_enabled', False)
           else f"IDM car following  ·  seed {cfg['seed']}  ·  replay at 40x real time")
    cv.text(32, 58, sub, 14, fill=INK_2)
    cv.text(W - 32, 22, mmss(t), 34, True, anchor='ra')
    empty = not cars and not main_ext and not ramp_ext and not demand
    badge = ('Demand active' if demand else
             f"Network empty (run continues to {cfg['duration'] / 60:.0f} min)" if empty else 'Demand ended, clearing')
    cv.text(W - 32, 66, badge, 14, fill=ZOOM_ACCENT if demand else MUTED, anchor='ra')

    if cfg.get('zone_length', 0) > 0:
        _draw_zone(cv, cfg, t, cars, ramp_ext, ramp)
    elif 'merge_x' in cfg:
        _draw_point(cv, cfg, t, cars, ramp_ext, ramp)
    else:
        _draw_lane(cv, cfg, t, cars)

    # ---- Counters -------------------------------------------------------
    on_main = sum(1 for c in cars if c[3] == 0)
    on_ramp = sum(1 for c in cars if c[3] == 1)
    merged = log.get('merges', '–') if log else '–'
    gone = log.get('exited', '–') if log else '–'
    if 'merge_x' in cfg:
        slow = sum(1 for c in cars if c[2] < 30)
        ramp_label = 'Waiting to merge' if cfg.get('zone_length', 0) > 0 else f"Ramp queue (storage {cfg['ramp_storage']})"
        tiles = [('On mainline', on_main), ('Slower than 30 km/h', slow),
                 (ramp_label, ramp_ext), ('Mainline entry queue', main_ext),
                 ('Merges so far', merged), ('Exited so far', gone)]
    else:
        tiles = [('On mainline', on_main), ('On ramp', f"{on_ramp} / {cfg['ramp_storage']}"),
                 ('Ramp queue (outside)', ramp_ext), ('Mainline queue (outside)', main_ext),
                 ('Merges so far', merged), ('Exited so far', gone)]
    tw = (W - 64 - 10 * (len(tiles) - 1)) / len(tiles)
    for i, (label, value) in enumerate(tiles):
        x = 32 + i * (tw + 10)
        cv.rect((x, 464, x + tw, 530), fill='#ffffff', outline=GRID, radius=8)
        cv.text(x + 12, 474, label, 12, fill=INK_2)
        cv.text(x + 12, 494, str(value), 22, True)

    # ---- Speed legend and time bar ---------------------------------------
    lx, ly = 32, 556
    cv.text(lx, ly, 'Speed', 12, True, fill=INK_2)
    for i in range(200):
        cv.rect((lx + 50 + i, ly + 1, lx + 51 + i, ly + 13), fill=hexrgb(SPEED_MAX_KMH * i / 199))
    cv.text(lx + 50, ly + 17, '0', 11, fill=MUTED)
    cv.text(lx + 250, ly + 17, f'{SPEED_MAX_KMH:.0f} km/h', 11, fill=MUTED, anchor='ra')
    cv.rect((lx + 300, ly, lx + 318, ly + 14), fill=hexrgb(110), outline=CAR_EDGE, width=1, radius=3)
    cv.text(lx + 326, ly, 'mainline origin', 12, fill=INK_2)
    cv.rect((lx + 440, ly, lx + 458, ly + 14), fill=hexrgb(110), outline=INK, width=2, radius=3)
    cv.text(lx + 466, ly, 'ramp origin (thick outline)', 12, fill=INK_2)
    note = ('Positions to scale; each merge is drawn as a 4 s lane change.' if cfg.get('zone_length', 0) > 0
            else 'Positions to scale; lane changes are instantaneous.')
    cv.text(W - 32, ly, note, 12, fill=MUTED, anchor='ra')
    if ramp is not None and cfg.get('zone_length', 0) > 0:
        cv.text(W - 32, ly + 17, 'Ramp and acceleration-lane motion drawn for illustration; the model places each '
                'ramp vehicle into the gap it takes.', 11, fill=MUTED, anchor='ra')
    elif ramp is not None:
        cv.text(W - 32, ly + 17, 'Ramp approach drawn for illustration; the model treats the ramp as a queue.',
                11, fill=MUTED, anchor='ra')

    bx0, bx1, by = 32, W - 32, 606
    total = t_end
    cv.rect((bx0, by, bx1, by + 8), fill=GRID, radius=4)
    cv.rect((bx0, by, bx0 + (bx1 - bx0) * cfg['demand_end'] / total, by + 8), fill='#c6d9f1', radius=4)
    cv.rect((bx0, by, bx0 + (bx1 - bx0) * t / total, by + 8), fill=ZOOM_ACCENT, radius=4)
    cv.text(bx0, by + 12, '0 min', 11, fill=MUTED)
    cv.text(bx0 + (bx1 - bx0) * cfg['demand_end'] / total, by + 12, 'demand ends', 11, fill=MUTED, anchor='ma')
    cv.text(bx1, by + 12, mmss(t_end), 11, fill=MUTED, anchor='ra')
    return cv.finish()


def _draw_lane(cv, cfg, t, cars):
    """Corridor strip and zoomed view for the explicit ramp-lane model (runs 1-2)."""
    # ---- Overview of the whole corridor ---------------------------------
    L = cfg['road_end']
    ox0, ox1, oy = 60, W - 60, 128

    def opx(x):
        return ox0 + (ox1 - ox0) * x / L

    zlo, zhi = cfg['ramp_start'] - 150, cfg['merge_end'] + 250
    cv.text(ox0, 96, 'Whole corridor', 13, True, fill=INK_2)
    cv.rect((opx(zlo), oy - 16, opx(zhi), oy + 24), outline=ZOOM_ACCENT, width=1, radius=4)
    cv.text(opx(zhi) + 6, oy + 8, 'zoomed below', 11, fill=ZOOM_ACCENT)
    cv.line((ox0, oy, ox1, oy), ROAD, 10)
    cv.line((opx(cfg['ramp_start']), oy + 16, opx(cfg['merge_start']), oy + 7), ROAD, 6)
    cv.line((opx(cfg['merge_start']), oy + 7, opx(cfg['merge_end']), oy + 7), ROAD, 6)
    for km in range(int(L // 1000) + 1):
        cv.text(opx(km * 1000), oy + 30, f'{km} km', 11, fill=MUTED, anchor='ma')
    for _, x, v, lane, origin in cars:
        if lane == 0:
            cv.rect((opx(x) - 2, oy - 4, opx(x) + 1, oy + 4), fill=hexrgb(v), outline=CAR_EDGE)
        else:
            y = oy + 16 - 9 * min(1, (x - cfg['ramp_start']) / (cfg['merge_start'] - cfg['ramp_start']))
            cv.rect((opx(x) - 2, y - 3, opx(x) + 1, y + 3), fill=hexrgb(v))

    # ---- Zoomed merge area ----------------------------------------------
    zx0, zx1 = 60, W - 60
    my, lane_h = 262, 34          # mainline lane centre and lane width
    ay = my + lane_h               # acceleration lane centre
    rb = 400                       # y of the ramp at its upstream end

    def zpx(x):
        return zx0 + (zx1 - zx0) * (x - zlo) / (zhi - zlo)

    def ramp_y(x):
        f = (x - cfg['ramp_start']) / (cfg['merge_start'] - cfg['ramp_start'])
        return rb + (ay - rb) * min(1.0, max(0.0, f))

    cv.text(zx0, 200, f"Merge area  {zlo / 1000:.2f}-{zhi / 1000:.2f} km", 13, True, fill=INK_2)
    # Road surfaces: mainline, acceleration lane, and the ramp approach.
    cv.rect((zx0, my - lane_h / 2, zx1, my + lane_h / 2), fill=ROAD)
    cv.rect((zpx(cfg['merge_start']), ay - lane_h / 2, zpx(cfg['merge_end']), ay + lane_h / 2), fill=ROAD)
    cv.line((zpx(cfg['ramp_start']), rb, zpx(cfg['merge_start']), ay), ROAD, lane_h * 0.8)
    # Merge zone: dashed line between lanes and a soft label.
    cv.dashed(zpx(cfg['merge_start']), zpx(cfg['merge_end']), my + lane_h / 2, LANE_MARK)
    cv.line((zpx(cfg['merge_end']), ay - lane_h / 2, zpx(cfg['merge_end']), ay + lane_h / 2), INK, 2)
    cv.text((zpx(cfg['merge_start']) + zpx(cfg['merge_end'])) / 2, ay + lane_h / 2 + 8,
            'merge zone', 11, fill=ZOOM_ACCENT, anchor='ma')
    cv.text(zpx(cfg['merge_end']) + 4, ay + lane_h / 2 + 8, 'ramp end', 11, fill=MUTED)
    for x in range(int(zlo // 100 + 1) * 100, int(zhi), 100):
        cv.line((zpx(x), my - lane_h / 2 - 8, zpx(x), my - lane_h / 2 - 2), AXIS, 1)
        cv.text(zpx(x), my - lane_h / 2 - 24, f'{x / 1000:.1f}', 11, fill=MUTED, anchor='ma')
    # Upstream ramp admission signal (one vehicle per cycle while green).
    open_ = (t % cfg['release_period']) < cfg['green_duration']
    sx, sy = zpx(cfg['ramp_start']) + 4, rb + 30
    cv.circle(sx, sy, 7, GREEN if open_ else RED)
    # Run 1 used the window as merge permission; run 2 moved it to ramp admission.
    what = 'ramp admission' if 'ramp_end_brake' in cfg else 'merge window'
    cv.text(sx + 14, sy - 8, f"{what} {'open' if open_ else 'closed'}", 12, fill=INK_2)

    # Vehicles: length to scale, colored by speed; ramp-origin vehicles outlined.
    scale = (zx1 - zx0) / (zhi - zlo)
    half_w = 8
    for _, x, v, lane, origin in cars:
        if not (zlo - 10 <= x <= zhi + 10):
            continue
        front = zpx(x)
        rear = front - max(5 * scale, 6)
        y = my if lane == 0 else ramp_y(x)
        cv.rect((rear, y - half_w, front, y + half_w), fill=hexrgb(v),
                outline=INK if origin == 1 else CAR_EDGE, width=2 if origin == 1 else 1, radius=3)


def _zoom(cfg):
    """Zoomed merge view: (zlo, zhi) in m and its scale in px per m."""
    zlo, zhi = max(0.0, cfg['merge_x'] - 900), min(cfg['road_end'], cfg['merge_x'] + 400)
    return zlo, zhi, (W - 120) / (zhi - zlo)


def _ramp_ends(cfg):
    """Pixel coordinates of the drawn ramp entrance and of its end at the merge point."""
    zlo, zhi, scale = _zoom(cfg)
    my, lane_h = 262, 34
    jx, jy = 60 + (cfg['merge_x'] - zlo) * scale, my + lane_h / 2 - 2
    return jx - RAMP_DX, my + RAMP_DY, jx, jy


def ramp_length_m(cfg):
    """Length of the drawn ramp in m, at the same scale as the zoomed mainline."""
    ex, ey, jx, jy = _ramp_ends(cfg)
    return ((jx - ex) ** 2 + (jy - ey) ** 2) ** 0.5 / _zoom(cfg)[2]


def _hermite(u, T, L, v0, v1):
    """Distance (m) and speed (m/s) at fraction u of a T-second drive over L m from speed v0 to v1."""
    dist = (u ** 3 - 2 * u ** 2 + u) * T * v0 + (-2 * u ** 3 + 3 * u ** 2) * L + (u ** 3 - u ** 2) * T * v1
    speed = ((3 * u ** 2 - 4 * u + 1) * T * v0 + (-6 * u ** 2 + 6 * u) * L + (3 * u ** 2 - 2 * u) * T * v1) / T
    return dist, speed


def ramp_plan(result, ramp_len):
    """Drawn ramp motion for every ramp vehicle (display only; the model treats the ramp as a queue).

    Every vehicle leaves the drawn ramp exactly when the model inserts it (te). A vehicle with
    nobody ahead and only a short wait drives the ramp without stopping, adjusting its speed
    from RAMP_SPEED at the entrance to its insertion speed so that it reaches the merge point
    at te. Any other vehicle cruises at RAMP_SPEED and brakes at RAMP_BRAKE to stop at the
    back of the queue at its scheduled arrival time ta, then waits in the queue."""
    trips = sorted((z for z in result['trips'] if z['origin'] == 1 and z.get('entry_s') is not None),
                   key=lambda z: (z['scheduled_s'], z['id']))
    v_ins = {e['id']: e['v'] for e in result['events'] if e.get('result') == 'accepted'}
    plan = []
    for k, z in enumerate(trips):
        ta, te = z['scheduled_s'], z['entry_s']
        ahead = sum(1 for y in trips[:k] if y['entry_s'] > ta)   # FIFO: earlier arrivals still waiting
        v1 = max(float(v_ins.get(z['id'], RAMP_SPEED)), 0.5)
        if ahead == 0:
            T = 2 * ramp_len / (RAMP_SPEED + v1) + (te - ta)
            slowest = min(_hermite(i / 20, T, ramp_len, RAMP_SPEED, v1)[1] for i in range(21))
            if slowest >= SMOOTH_MIN_SPEED:   # smooth drive without stopping or crawling
                plan.append(dict(ta=ta, te=te, t0=te - T, kind='smooth', T=T, v1=v1))
                continue
        D = ramp_len - ahead * QUEUE_SPACING
        if D <= 0:                       # queue reaches past the drawn ramp: drawn only while waiting
            plan.append(dict(ta=ta, te=te, t0=ta, kind='stop', D=0.0, tc=0.0, v0=0.0))
            continue
        db = RAMP_SPEED ** 2 / (2 * RAMP_BRAKE)
        if D >= db:
            tc, v0 = (D - db) / RAMP_SPEED, RAMP_SPEED
        else:
            tc, v0 = 0.0, (2 * RAMP_BRAKE * D) ** 0.5
        plan.append(dict(ta=ta, te=te, t0=ta - tc - v0 / RAMP_BRAKE, kind='stop', D=D, tc=tc, v0=v0))
    return plan


def _ramp_positions(plan, t, ramp_len):
    """(distance from the merge point in m, speed in m/s) of every vehicle drawn on the ramp at t.

    Vehicles are kept in FIFO order at least QUEUE_SPACING apart, so a waiting vehicle
    queues behind whatever is ahead of it on the drawn ramp."""
    out = []
    for p in plan:                                   # plan is in FIFO order
        if not (p['t0'] <= t < p['te']):
            continue
        s_ = t - p['t0']
        if p['kind'] == 'smooth':
            dist, v = _hermite(min(s_ / p['T'], 1.0), p['T'], ramp_len, RAMP_SPEED, p['v1'])
            d = ramp_len - dist
        elif t >= p['ta']:                           # waiting: wants to be at the merge point
            d, v = 0.0, 0.0
        elif s_ <= p['tc']:
            d, v = ramp_len - p['v0'] * s_, p['v0']
        else:
            s2 = s_ - p['tc']
            d = ramp_len - (p['v0'] * p['tc'] + p['v0'] * s2 - 0.5 * RAMP_BRAKE * s2 ** 2)
            v = max(p['v0'] - RAMP_BRAKE * s2, 0.0)
        if out and d < out[-1][0] + QUEUE_SPACING:   # stay behind the vehicle ahead
            d, v = out[-1][0] + QUEUE_SPACING, min(v, out[-1][1])
        out.append((d, v))
    return out


def _draw_point(cv, cfg, t, cars, ramp_q, ramp=None):
    """Corridor strip and zoomed view for the point-merge model (run 3 onward)."""
    L, m = cfg['road_end'], cfg['merge_x']
    ox0, ox1, oy = 60, W - 60, 128

    def opx(x):
        return ox0 + (ox1 - ox0) * x / L

    zlo, zhi = max(0.0, m - 900), min(L, m + 400)
    cv.text(ox0, 96, 'Whole corridor', 13, True, fill=INK_2)
    cv.rect((opx(zlo), oy - 16, opx(zhi), oy + 24), outline=ZOOM_ACCENT, width=1, radius=4)
    cv.text(opx(zhi) + 6, oy + 8, 'zoomed below', 11, fill=ZOOM_ACCENT)
    cv.line((ox0, oy, ox1, oy), ROAD, 10)
    cv.line((opx(m - 160), oy + 16, opx(m), oy + 5), ROAD, 6)
    for km in range(int(L // 1000) + 1):
        cv.text(opx(km * 1000), oy + 30, f'{km} km', 11, fill=MUTED, anchor='ma')
    for _, x, v, lane, origin in cars:
        cv.rect((opx(x) - 2, oy - 4, opx(x) + 1, oy + 4), fill=hexrgb(v), outline=INK if origin else CAR_EDGE)

    zx0, zx1 = 60, W - 60
    my, lane_h = 262, 34

    def zpx(x):
        return zx0 + (zx1 - zx0) * (x - zlo) / (zhi - zlo)

    scale = (zx1 - zx0) / (zhi - zlo)
    ex, ey, jx, jy = _ramp_ends(cfg)              # ramp entrance and ramp end at the merge point
    ramp_px = ((jx - ex) ** 2 + (jy - ey) ** 2) ** 0.5
    ramp_len = ramp_length_m(cfg)                 # drawn ramp length, same scale as the mainline
    on_ramp = _ramp_positions(ramp, t, ramp_len) if ramp is not None else None
    if on_ramp:
        o0x, o0y, o1x, o1y = opx(m), oy + 5, opx(m - 160), oy + 16
        for d, v in on_ramp:
            f = min(d / ramp_len, 1.0)
            px, py = o0x + (o1x - o0x) * f, o0y + (o1y - o0y) * f
            cv.rect((px - 1, py - 2, px + 2, py + 2), fill=hexrgb(v * 3.6), outline=INK)

    cv.text(zx0, 200, f"Merge area  {zlo / 1000:.2f}-{zhi / 1000:.2f} km  (traffic flows left to right)",
            13, True, fill=INK_2)
    cv.rect((zx0, my - lane_h / 2, zx1, my + lane_h / 2), fill=ROAD)
    # Ramp meeting the mainline at the merge point; the acceleration lane is abstracted.
    mx = zpx(m)
    sx0, sy0 = ex, ey
    cv.line((sx0, sy0, mx, my + lane_h / 2 - 2), ROAD, 26)
    if on_ramp is not None:
        cv.text(sx0 - 6, sy0 - 6, 'ramp entrance', 11, fill=MUTED, anchor='rb')
    cv.line((mx, my - lane_h / 2 - 6, mx, my + lane_h / 2 + 6), ZOOM_ACCENT, 2)
    cv.text(mx + 6, my + lane_h / 2 + 8, 'merge point', 11, fill=ZOOM_ACCENT)
    for x in range(int(zlo // 100 + 1) * 100, int(zhi), 100):
        cv.line((zpx(x), my - lane_h / 2 - 8, zpx(x), my - lane_h / 2 - 2), AXIS, 1)
        cv.text(zpx(x), my - lane_h / 2 - 24, f'{x / 1000:.1f}', 11, fill=MUTED, anchor='ma')
    if on_ramp is None:
        # Older runs without trip records: one marker per waiting vehicle, head nearest the merge.
        shown = min(ramp_q, 16)
        for k in range(shown):
            f = (k + 0.6) / 17
            qx, qy = mx + (sx0 - mx) * f, (my + lane_h / 2 - 2) + (sy0 - (my + lane_h / 2 - 2)) * f
            cv.rect((qx - 6, qy - 5, qx + 6, qy + 5), fill='#e6b8a6', outline=INK, width=2, radius=3)
        more = f'  (first {shown} drawn)' if ramp_q > shown else ''
    else:
        # Vehicles on the drawn ramp, front bumper at distance d from the merge point.
        ux, uy = (sx0 - jx) / ramp_px, (sy0 - jy) / ramp_px     # unit vector toward the entrance
        nx, ny = -uy, ux
        car_px, half = max(cfg['length'] * scale, 4), 7
        hidden = 0
        for d, v in sorted(on_ramp, reverse=True):
            if d > ramp_len:
                hidden += 1
                continue
            fx, fy = jx + ux * d * scale, jy + uy * d * scale
            rx, ry = fx + ux * car_px, fy + uy * car_px
            cv.poly([(fx + nx * half, fy + ny * half), (rx + nx * half, ry + ny * half),
                     (rx - nx * half, ry - ny * half), (fx - nx * half, fy - ny * half)],
                    fill=hexrgb(v * 3.6), outline=INK, width=1)
        more = f'  ({hidden} beyond the drawn ramp)' if hidden else ''
    cv.text(sx0 - 10, sy0 + 12, f'Ramp queue: {ramp_q} waiting{more}', 13, fill=INK_2, anchor='ma')

    for _, x, v, lane, origin in cars:
        if not (zlo - 10 <= x <= zhi + 10):
            continue
        front = zpx(x)
        rear = front - max(cfg['length'] * scale, 6)
        cv.rect((rear, my - 8, front, my + 8), fill=hexrgb(v),
                outline=INK if origin == 1 else CAR_EDGE, width=2 if origin == 1 else 1, radius=3)


# --------------------------------------------------------------------------
# Merge-zone model: ramp vehicles drive down the ramp into an acceleration lane
# that runs beside the mainline over the merge zone, and join the mainline at
# the position and time the model inserted them. The model abstracts this
# approach; it is reconstructed here for display only.
# --------------------------------------------------------------------------
LANE_GAP = 34          # px between the mainline and acceleration-lane centre lines
LC_TIME = 4.0          # s over which a merge is drawn as a lateral lane change
ZONE_FRAME_STEP = 2    # s between GIF frames for the merge-zone model (finer, so lane changes show)
ZONE_FRAME_MS = 50     # 2 s / 0.05 s = 40x real time


def _zone_ends(cfg):
    """Pixel coordinates of the drawn ramp entrance and of the acceleration-lane start."""
    zlo, zhi, scale = _zoom(cfg)
    my = 262
    jx, jy = 60 + (cfg['merge_x'] - cfg['zone_length'] - zlo) * scale, my + LANE_GAP
    return jx - RAMP_DX, jy + RAMP_DY - LANE_GAP, jx, jy


def zone_ramp_length_m(cfg):
    """Length (m) of the drawn ramp approach up to the start of the acceleration lane."""
    ex, ey, jx, jy = _zone_ends(cfg)
    return ((jx - ex) ** 2 + (jy - ey) ** 2) ** 0.5 / _zoom(cfg)[2]


def _lane_profile(T, L, v0, v1):
    """Monotone drive of L m in T s from speed v0 to v1; returns f(s) -> (distance, speed).

    A cubic Hermite curve is used when it stays smooth; otherwise the vehicle slows to a
    common speed (or stops), keeps it, and changes to v1 at a constant rate."""
    if T <= 1e-6:
        return lambda s_: (L, v1)
    samples = [_hermite(i / 40, T, L, v0, v1)[1] for i in range(41)]
    if min(samples) >= 0.4 * min(v0, v1) and max(samples) <= 1.3 * max(v0, v1, L / T):
        return lambda s_: _hermite(min(max(s_ / T, 0.0), 1.0), T, L, v0, v1)
    best = None
    for d in (2.0, 3.0, 4.0, 6.0):
        for i in range(301):
            vc = max(v0, v1, L / T) * 1.2 * i / 300
            t1, t2 = abs(v0 - vc) / d, abs(v1 - vc) / d
            tc = T - t1 - t2
            if tc < 0:
                continue
            dist = (v0 + vc) / 2 * t1 + vc * tc + (vc + v1) / 2 * t2
            err = abs(dist - L)
            if best is None or err < best[0]:
                best = (err, d, vc, t1, tc, t2)
        if best and best[0] < 0.5:
            break
    if best is None or best[0] > 2.0:
        return lambda s_: (L * min(max(s_ / T, 0.0), 1.0), L / T)
    _, d, vc, t1, tc, t2 = best
    a1 = (vc - v0) / t1 if t1 > 0 else 0.0
    a2 = (v1 - vc) / t2 if t2 > 0 else 0.0
    def f(s_):
        s_ = min(max(s_, 0.0), T)
        if s_ <= t1:
            return v0 * s_ + 0.5 * a1 * s_ ** 2, v0 + a1 * s_
        d1 = v0 * t1 + 0.5 * a1 * t1 ** 2
        if s_ <= t1 + tc:
            return d1 + vc * (s_ - t1), vc
        u = s_ - t1 - tc
        return d1 + vc * tc + vc * u + 0.5 * a2 * u ** 2, vc + a2 * u
    return f


def zone_plan(result, ramp_len):
    """Drawn motion of every ramp vehicle: ramp approach at RAMP_SPEED, reaching the start of
    the acceleration lane at its scheduled arrival (as in the model), then along the lane to
    the position and speed at which the model inserted it."""
    cfg = result['summary']['config']
    x_start = cfg['merge_x'] - cfg['zone_length']
    ins = {e['id']: e for e in result['events'] if e.get('result') == 'accepted'}
    trips = sorted((z for z in result['trips'] if z['origin'] == 1 and z['id'] in ins),
                   key=lambda z: (z['scheduled_s'], z['id']))
    plan = []
    for z in trips:
        e = ins[z['id']]
        ta, te = z['scheduled_s'], z['entry_s']
        L = max(e['x'] - x_start, 0.0)
        v1 = max(float(e['v']), 0.0)
        prof = _lane_profile(max(te - ta, 0.0), L, RAMP_SPEED, v1)
        plan.append(dict(id=z['id'], t0=ta - ramp_len / RAMP_SPEED, ta=ta, te=te, L=L, prof=prof))
    return plan


def _zone_positions(plan, t, ramp_len, spacing=QUEUE_SPACING):
    """(path position in m from the ramp entrance, speed in m/s) of every drawn ramp vehicle.
    Positions beyond ramp_len lie in the acceleration lane. FIFO spacing (m) is kept."""
    out = []
    for p in plan:
        if not (p['t0'] <= t < p['te']):
            continue
        if t < p['ta']:
            d, v = RAMP_SPEED * (t - p['t0']), RAMP_SPEED
        else:
            dist, v = p['prof'](t - p['ta'])
            d = ramp_len + dist
        if out and d > out[-1][0] - spacing:
            d, v = out[-1][0] - spacing, min(v, out[-1][1])
        out.append((d, max(v, 0.0)))
    return out


def _draw_zone(cv, cfg, t, cars, ramp_q, ramp=None):
    """Corridor strip and zoomed view for the merge-zone model (no yielding)."""
    L, m, zl = cfg['road_end'], cfg['merge_x'], cfg['zone_length']
    xs = m - zl
    ox0, ox1, oy = 60, W - 60, 128

    def opx(x):
        return ox0 + (ox1 - ox0) * x / L

    zlo, zhi, scale = _zoom(cfg)
    cv.text(ox0, 96, 'Whole corridor', 13, True, fill=INK_2)
    cv.rect((opx(zlo), oy - 16, opx(zhi), oy + 24), outline=ZOOM_ACCENT, width=1, radius=4)
    cv.text(opx(zhi) + 6, oy + 8, 'zoomed below', 11, fill=ZOOM_ACCENT)
    cv.line((ox0, oy, ox1, oy), ROAD, 10)
    cv.line((opx(xs - 300), oy + 16, opx(xs), oy + 7), ROAD, 6)
    cv.line((opx(xs), oy + 7, opx(m), oy + 7), ROAD, 6)
    for km in range(int(L // 1000) + 1):
        cv.text(opx(km * 1000), oy + 30, f'{km} km', 11, fill=MUTED, anchor='ma')
    for _, x, v, lane, origin in cars:
        cv.rect((opx(x) - 2, oy - 4, opx(x) + 1, oy + 4), fill=hexrgb(v), outline=INK if origin else CAR_EDGE)

    zx0, zx1 = 60, W - 60
    my, lane_h = 262, 34
    ay = my + LANE_GAP

    def zpx(x):
        return zx0 + (x - zlo) * scale

    ex, ey, jx, jy = _zone_ends(cfg)
    ramp_px = ((jx - ex) ** 2 + (jy - ey) ** 2) ** 0.5
    ramp_len = zone_ramp_length_m(cfg)
    drawn = _zone_positions(ramp, t, ramp_len) if ramp is not None else []
    # Overview: ramp vehicles as small marks on the drawn ramp/lane.
    for d, v in drawn:
        if d <= ramp_len:
            f = d / ramp_len
            px, py = opx(xs - 300) + (opx(xs) - opx(xs - 300)) * f, oy + 16 - 9 * f
        else:
            px, py = opx(xs + d - ramp_len), oy + 7
        cv.rect((px - 1, py - 2, px + 2, py + 2), fill=hexrgb(v * 3.6), outline=INK)

    cv.text(zx0, 200, f"Merge area  {zlo / 1000:.2f}-{zhi / 1000:.2f} km  (traffic flows left to right)",
            13, True, fill=INK_2)
    # Road surfaces: mainline, acceleration lane with a short taper, ramp approach.
    cv.rect((zx0, my - lane_h / 2, zx1, my + lane_h / 2), fill=ROAD)
    cv.rect((zpx(xs), ay - lane_h / 2, zpx(m), ay + lane_h / 2), fill=ROAD)
    cv.poly([(zpx(m), ay - lane_h / 2), (zpx(m) + 40, ay - lane_h / 2), (zpx(m), ay + lane_h / 2)], fill=ROAD)
    cv.line((ex, ey, jx, jy), ROAD, 26)
    cv.dashed(zpx(xs), zpx(m), my + lane_h / 2, LANE_MARK)
    cv.text(ex - 6, ey - 6, 'ramp entrance', 11, fill=MUTED, anchor='rb')
    cv.text(zpx(xs) + 4, ay + lane_h / 2 + 6, f'acceleration lane = merge zone ({zl:.0f} m)',
            11, fill=ZOOM_ACCENT)
    cv.line((zpx(m), my - lane_h / 2 - 6, zpx(m), ay + lane_h / 2), ZOOM_ACCENT, 2)
    cv.text(zpx(m) + 44, ay - 6, 'lane end', 11, fill=ZOOM_ACCENT)
    for x in range(int(zlo // 100 + 1) * 100, int(zhi), 100):
        cv.line((zpx(x), my - lane_h / 2 - 8, zpx(x), my - lane_h / 2 - 2), AXIS, 1)
        cv.text(zpx(x), my - lane_h / 2 - 24, f'{x / 1000:.1f}', 11, fill=MUTED, anchor='ma')

    # Ramp vehicles: on the approach they are drawn along the ramp, in the lane as boxes.
    ux, uy = (ex - jx) / ramp_px, (ey - jy) / ramp_px          # unit vector toward the entrance
    nx, ny = -uy, ux
    car_px, half = max(cfg['length'] * scale, 6), 7
    for d, v in sorted(drawn, reverse=True):
        if d < 0:
            continue
        if d <= ramp_len:
            back = ramp_len - d                                  # m before the lane start
            fx, fy = jx + ux * back * scale, jy + uy * back * scale
            rx, ry = fx + ux * car_px, fy + uy * car_px
            cv.poly([(fx + nx * half, fy + ny * half), (rx + nx * half, ry + ny * half),
                     (rx - nx * half, ry - ny * half), (fx - nx * half, fy - ny * half)],
                    fill=hexrgb(v * 3.6), outline=INK, width=1)
        else:
            front = zpx(xs + d - ramp_len)
            cv.rect((front - car_px, ay - 8, front, ay + 8), fill=hexrgb(v * 3.6), outline=INK, width=2, radius=3)
    cv.text(ex - 10, ey + 12, f'Waiting to merge: {ramp_q}', 13, fill=INK_2, anchor='ma')

    te = {p['id']: p['te'] for p in ramp} if ramp is not None else {}
    for vid, x, v, lane, origin in cars:
        if not (zlo - 10 <= x <= zhi + 10):
            continue
        front = zpx(x)
        rear = front - car_px
        y = my
        if origin == 1 and vid in te and 0 <= t - te[vid] < LC_TIME:
            f = (t - te[vid]) / LC_TIME
            f = f * f * (3 - 2 * f)                          # smooth start and end of the lane change
            y = ay + (my - ay) * f
        cv.rect((rear, y - 8, front, y + 8), fill=hexrgb(v),
                outline=INK if origin == 1 else CAR_EDGE, width=2 if origin == 1 else 1, radius=3)


# --------------------------------------------------------------------------
# Merge-zone replay with car icons (no yielding).
#
# Frames are drawn every REPLAY_STEP simulated seconds, interpolated between the
# one-second records. A coarser step makes cars appear to roll backward: when a
# car moves more than about half its spacing between two frames, the eye pairs
# it with the car behind (the wagon-wheel effect). At 0.6 s a car moves about a
# fifth of its spacing per frame in every traffic state of these runs.
# --------------------------------------------------------------------------
REPLAY_STEP = 0.6         # simulated s per GIF frame
REPLAY_MS = 20            # ms per GIF frame: 0.6 s / 0.02 s = 30x real time
CAR_PX, CAR_W = 17.0, 9.0 # drawn car length and width (px); about 2x real length so cars stay visible
LANE_PX = 24.0            # drawn lane width (px)
GLASS = '#2e3440'         # windscreen and rear window
RAMP_EDGE = INK           # ramp-origin cars: dark outline
TRANSPARENT = 255         # palette index reserved for "unchanged pixel" in the GIF frames
PALETTE_COLORS = 64       # GIF palette size; fewer colors keep the file smaller


def _zone_view(cfg):
    """Zoomed view geometry for the car-icon replay (all x in px at 1x scale)."""
    xs = cfg['merge_x'] - cfg['zone_length']
    zlo = max(0.0, xs - 350.0)
    zhi = min(cfg['road_end'], cfg['merge_x'] + 100.0)
    scale = (W - 120) / (zhi - zlo)
    my = 240.0
    ay = my + LANE_PX
    jx = 60 + (xs - zlo) * scale
    ex, ey = jx - 300.0, ay + 150.0
    return dict(zlo=zlo, zhi=zhi, scale=scale, my=my, ay=ay, xs=xs, jx=jx, jy=ay, ex=ex, ey=ey,
                ramp_len=((jx - ex) ** 2 + (ay - ey) ** 2) ** 0.5 / scale)


def _shade(rgb, f=0.62):
    return tuple(int(c * f) for c in rgb)


def _car_h(d, x_front, y, length, fill, edge, ew):
    """Top view of a car driving to the right; x_front is the front bumper (px, supersampled)."""
    hw = CAR_W * SS / 2
    x0 = x_front - length
    d.rounded_rectangle((x0, y - hw, x_front, y + hw), radius=3 * SS, fill=fill, outline=edge,
                        width=max(1, int(round(ew * SS))))
    if length >= 8 * SS:
        w1 = x_front - 0.24 * length
        w0 = w1 - max(0.17 * length, 1.6 * SS)
        d.rounded_rectangle((w0, y - hw + 1.25 * SS, w1, y + hw - 1.25 * SS), radius=0.8 * SS, fill=GLASS)
        r0 = x0 + 0.13 * length
        r1 = r0 + max(0.1 * length, 1.2 * SS)
        d.rounded_rectangle((r0, y - hw + 1.45 * SS, r1, y + hw - 1.45 * SS), radius=0.6 * SS, fill=GLASS)


def _car_r(d, fx, fy, ux, uy, length, fill, edge, ew):
    """Car icon along a slanted road. (fx, fy): front bumper (supersampled px);
    (ux, uy): unit vector from the front toward the rear."""
    nx, ny = -uy, ux
    hw = CAR_W * SS / 2

    def pt(a, b):
        return (fx + ux * a + nx * b, fy + uy * a + ny * b)

    d.polygon([pt(0, -hw), pt(length, -hw), pt(length, hw), pt(0, hw)], fill=fill, outline=edge,
              width=max(1, int(round(ew * SS))))
    w0 = 0.24 * length
    w1 = w0 + max(0.17 * length, 1.6 * SS)
    i = 1.25 * SS
    d.polygon([pt(w0, -hw + i), pt(w1, -hw + i), pt(w1, hw - i), pt(w0, hw - i)], fill=GLASS)
    r1 = 0.87 * length
    r0 = r1 - max(0.1 * length, 1.2 * SS)
    i = 1.45 * SS
    d.polygon([pt(r0, -hw + i), pt(r1, -hw + i), pt(r1, hw - i), pt(r0, hw - i)], fill=GLASS)


def _interp_frames(result, step, t_end):
    """Yield (t, cars, main_waiting, ramp_waiting) every `step` s, interpolating the 1 s records.

    A car present in both neighbouring records moves linearly between them; a car that
    enters (at the entrance or by a merge) or leaves during the second is extrapolated
    with its recorded speed, and a merging car is shown only from its merge time on."""
    cfg = result['summary']['config']
    by_t = {int(round(f[0])): f for f in result['frames']}
    last = max(by_t)
    merge_t = {e['id']: e['t'] for e in result['events'] if e.get('result') == 'accepted'}
    k = 0
    while True:
        t = round(k * step, 6)
        if t > t_end + 1e-9 or t > last:
            return
        i = int(math.floor(t + 1e-9))
        w = t - i
        a, b = by_t[i], by_t.get(i + 1)
        if b is None or w < 1e-9:
            yield t, a[1], a[2], a[3]
            k += 1
            continue
        ca = {c[0]: c for c in a[1]}
        cb = {c[0]: c for c in b[1]}
        cars = []
        for vid, c in ca.items():
            n = cb.get(vid)
            if n is not None:
                cars.append([vid, c[1] + (n[1] - c[1]) * w, c[2] + (n[2] - c[2]) * w, c[3], c[4]])
            else:                                     # left the road during this second
                x = c[1] + c[2] / 3.6 * w
                if x < cfg['road_end']:
                    cars.append([vid, x, c[2], c[3], c[4]])
        for vid, n in cb.items():
            if vid in ca:
                continue
            tm = merge_t.get(vid)
            if tm is not None and t < tm:             # merges later in this second
                continue
            x = n[1] - n[2] / 3.6 * (1 - w)
            if tm is None and x < 0:                  # not yet through the entrance
                continue
            cars.append([vid, x, n[2], n[3], n[4]])
        yield t, cars, a[2], a[3]
        k += 1


def _zone_background(cfg, t_end, g):
    """Everything that does not change between frames, drawn once (supersampled)."""
    cv = Canvas()
    L, m, zl = cfg['road_end'], cfg['merge_x'], cfg['zone_length']
    xs = g['xs']
    cv.text(32, 24, 'All-HDV freeway with an on-ramp', 24, True)
    cv.text(32, 58, f"IDM car following  ·  no yielding  ·  seed {cfg['seed']}  ·  "
                    f"replay at {REPLAY_STEP * 1000 / REPLAY_MS:.0f}x real time", 14, fill=INK_2)

    # Whole road: a strip colored by the speed of the nearest car (drawn per frame).
    ox0, ox1, oy = 60, W - 60, 124

    def opx(x):
        return ox0 + (ox1 - ox0) * x / L

    cv.text(ox0, 92, 'Whole road', 13, True, fill=INK_2)
    cv.text(ox0 + 92, 93, '(color = speed of the nearest car)', 12, fill=MUTED)
    cv.line((opx(xs - 300), oy + 17, opx(xs), oy + 9), ROAD, 5)
    cv.line((opx(xs), oy + 9, opx(m), oy + 9), ROAD, 5)
    cv.line((ox0, oy, ox1, oy), ROAD, 10)
    for km in range(int(L // 1000) + 1):
        cv.text(opx(km * 1000), oy + 22, f'{km} km', 11, fill=MUTED, anchor='ma')
    cv.rect((opx(g['zlo']), oy - 12, opx(g['zhi']), oy + 20), outline=ZOOM_ACCENT, width=1, radius=4)
    cv.text(opx(g['zhi']) + 6, oy + 3, 'zoomed below', 11, fill=ZOOM_ACCENT)

    # Zoomed merge area.
    zx0, zx1, my, ay = 60, W - 60, g['my'], g['ay']
    sc, zlo = g['scale'], g['zlo']

    def zpx(x):
        return zx0 + (x - zlo) * sc

    h = LANE_PX / 2
    cv.text(zx0, 176, f"Merge area  {g['zlo'] / 1000:.2f}-{g['zhi'] / 1000:.2f} km  (traffic flows left to right)",
            13, True, fill=INK_2)
    cv.rect((zx0, my - h, zx1, my + h), fill=ROAD)
    cv.rect((zpx(xs), ay - h, zpx(m), ay + h), fill=ROAD)
    cv.poly([(zpx(m), ay - h), (zpx(m) + 36, ay - h), (zpx(m), ay + h)], fill=ROAD)
    cv.line((g['ex'], g['ey'], g['jx'] + 2, g['jy']), ROAD, LANE_PX)
    cv.dashed(zpx(xs), zpx(m), my + h, LANE_MARK, dash=8, gap=7, width=1.5)
    cv.text(g['ex'] - 8, g['ey'] - 4, 'ramp entrance', 11, fill=MUTED, anchor='rb')
    cv.text(zpx(xs) + 4, ay + h + 6, f'acceleration lane = merge zone ({zl:.0f} m)', 11, fill=ZOOM_ACCENT)
    cv.line((zpx(m), my - h - 6, zpx(m), ay + h + 2), ZOOM_ACCENT, 2)
    cv.text(zpx(m) + 40, ay - 7, 'lane end', 11, fill=ZOOM_ACCENT)
    for x in range(int(zlo // 100 + 1) * 100, int(g['zhi']) + 1, 100):
        cv.line((zpx(x), my - h - 7, zpx(x), my - h - 2), AXIS, 1)
        cv.text(zpx(x), my - h - 22, f'{x / 1000:.1f}', 11, fill=MUTED, anchor='ma')

    # Counter tiles (values drawn per frame).
    labels = ['On mainline', 'Slower than 30 km/h', 'Waiting to merge', 'Mainline entry queue',
              'Merges so far', 'Exited so far']
    tw = (W - 64 - 10 * (len(labels) - 1)) / len(labels)
    for i, label in enumerate(labels):
        x = 32 + i * (tw + 10)
        cv.rect((x, 464, x + tw, 530), fill='#ffffff', outline=GRID, radius=8)
        cv.text(x + 12, 474, label, 12, fill=INK_2)

    # Legend.
    lx, ly = 32, 556
    cv.text(lx, ly, 'Speed', 12, True, fill=INK_2)
    for i in range(200):
        cv.rect((lx + 50 + i, ly + 1, lx + 51 + i, ly + 13), fill=hexrgb(SPEED_MAX_KMH * i / 199))
    cv.text(lx + 50, ly + 17, '0', 11, fill=MUTED)
    cv.text(lx + 250, ly + 17, f'{SPEED_MAX_KMH:.0f} km/h', 11, fill=MUTED, anchor='ra')
    pale = speed_rgb(105)
    _car_h(cv.d, (lx + 302 + CAR_PX) * SS, (ly + 7) * SS, CAR_PX * SS, pale, _shade(pale), 1)
    cv.text(lx + 310 + CAR_PX, ly, 'mainline car', 12, fill=INK_2)
    _car_h(cv.d, (lx + 420 + CAR_PX) * SS, (ly + 7) * SS, CAR_PX * SS, pale, RAMP_EDGE, 1.5)
    cv.text(lx + 428 + CAR_PX, ly, 'ramp car (dark outline)', 12, fill=INK_2)
    cv.text(W - 32, ly, 'Positions to scale; cars drawn about 2x real length; merges drawn as 4 s lane changes.',
            11, fill=MUTED, anchor='ra')
    cv.text(W - 32, ly + 17, 'Ramp and acceleration-lane motion drawn for illustration; the model places each '
            'ramp vehicle into the gap it takes.', 11, fill=MUTED, anchor='ra')

    # Time bar background.
    bx0, bx1, by = 32, W - 32, 606
    cv.rect((bx0, by, bx1, by + 8), fill=GRID, radius=4)
    cv.rect((bx0, by, bx0 + (bx1 - bx0) * min(cfg['demand_end'] / t_end, 1), by + 8), fill='#c6d9f1', radius=4)
    cv.text(bx0, by + 12, '0 min', 11, fill=MUTED)
    cv.text(bx0 + (bx1 - bx0) * min(cfg['demand_end'] / t_end, 1), by + 12, 'demand ends', 11, fill=MUTED, anchor='ma')
    cv.text(bx1, by + 12, mmss(t_end), 11, fill=MUTED, anchor='ra')
    return cv.im


_font1_cache = {}


def font1(size, bold=False):
    """Font at output resolution (1x) for text drawn directly on a finished frame."""
    key = (size, bold)
    if key not in _font1_cache:
        f = font(size, bold)
        try:
            _font1_cache[key] = f.font_variant(size=size)
        except AttributeError:
            _font1_cache[key] = ImageFont.load_default(size=size)
    return _font1_cache[key]


_sprites = {}


def _car_sprite(kmh, length, ramp_car, direction=None):
    """Anti-aliased car icon at output resolution, cached; (image, front-bumper offset x, y).

    direction=None: driving to the right; otherwise (ux, uy), the unit vector from the
    front toward the rear of a car on the slanted ramp."""
    key = (int(round(kmh / 2)), int(length), ramp_car, direction)
    hit = _sprites.get(key)
    if hit:
        return hit
    rgb = speed_rgb(key[0] * 2)
    edge = _hex_rgb(RAMP_EDGE) if ramp_car else _shade(rgb)
    ew = 1.5 if ramp_car else 1
    if direction is None:
        w, h = length + 2, CAR_W + 2
        ox, oy = 1 + length, h / 2
    else:
        ux, uy = direction
        nx, ny = -uy, ux
        hw = CAR_W / 2
        xs_ = [ux * a + nx * b for a in (0, length) for b in (-hw, hw)]
        ys_ = [uy * a + ny * b for a in (0, length) for b in (-hw, hw)]
        w, h = math.ceil(max(xs_) - min(xs_)) + 3, math.ceil(max(ys_) - min(ys_)) + 3
        ox, oy = 1.5 - min(xs_), 1.5 - min(ys_)
    im = Image.new('RGBA', (int(w) * SS, int(h) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if direction is None:
        _car_h(d, ox * SS, oy * SS, length * SS, rgb, edge, ew)
    else:
        _car_r(d, ox * SS, oy * SS, ux, uy, length * SS, rgb, edge, ew)
    hit = (im.resize((int(w), int(h)), Image.LANCZOS), ox, oy)
    _sprites[key] = hit
    return hit


def _hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _paste_car(frame, x_front, y, kmh, length, ramp_car, direction=None):
    sp, ox, oy = _car_sprite(kmh, length, ramp_car, direction)
    frame.paste(sp, (int(round(x_front - ox)), int(round(y - oy))), sp)


def _zone_frame(bg, cfg, g, t, cars, main_ext, ramp_ext, log, t_end, ramp, te):
    """One replay frame at output resolution: copy the background, paste cached car icons
    at whole-pixel positions and write the changing numbers."""
    im = bg.copy()
    d = ImageDraw.Draw(im)
    L = cfg['road_end']
    demand = t < cfg['demand_end']
    d.text((W - 32, 22), mmss(t), font=font1(34, True), fill=INK, anchor='ra')
    empty = not cars and not main_ext and not ramp_ext and not demand
    badge = ('Demand active' if demand else
             f"Network empty (run continues to {cfg['duration'] / 60:.0f} min)" if empty else 'Demand ended, clearing')
    d.text((W - 32, 66), badge, font=font1(14), fill=ZOOM_ACCENT if demand else MUTED, anchor='ra')

    # Whole-road strip: each 20 m piece takes the speed of the nearest car within 150 m,
    # in 10 km/h steps (a traffic-map look that changes only when a speed class changes).
    ox0, ox1, oy = 60, W - 60, 124
    main = sorted((c[1], c[2]) for c in cars)
    if main:
        xs_ = [p for p, _ in main]
        nb = int(L // 20)
        for b in range(nb):
            xc = (b + 0.5) * L / nb
            j = bisect.bisect_left(xs_, xc)
            best = min((k for k in (j - 1, j) if 0 <= k < len(main)), key=lambda k: abs(main[k][0] - xc))
            if abs(main[best][0] - xc) <= 150:
                x0 = ox0 + round((ox1 - ox0) * b / nb)
                x1 = ox0 + round((ox1 - ox0) * (b + 1) / nb) - 1
                d.rectangle((x0, oy - 5, x1, oy + 4), fill=speed_rgb(min(main[best][1] // 10 * 10 + 5, SPEED_MAX_KMH)))

    sc, zlo, my, ay = g['scale'], g['zlo'], g['my'], g['ay']
    zx0, zx1 = 60, W - 60

    def zpx(x):
        return zx0 + (x - zlo) * sc

    # Ramp cars: along the slanted ramp, then in the acceleration lane.
    drawn = _zone_positions(ramp, t, g['ramp_len'], spacing=(CAR_PX + 2) / sc) if ramp is not None else []
    rl = g['ramp_len']
    ex, ey, jx, jy = g['ex'], g['ey'], g['jx'], g['jy']
    rpx = ((jx - ex) ** 2 + (jy - ey) ** 2) ** 0.5
    ux, uy = round((ex - jx) / rpx, 4), round((ey - jy) / rpx, 4)
    for dist, v in drawn:
        if dist < 0:
            continue
        if dist <= rl:
            back = (rl - dist) * sc                       # px before the lane start
            _paste_car(im, jx + ux * back, jy + uy * back, v * 3.6, CAR_PX, True, (ux, uy))
        else:
            _paste_car(im, zpx(g['xs'] + dist - rl), ay, v * 3.6, CAR_PX, True)
    d.text((ex - 10, ey + 12), f'Waiting to merge: {ramp_ext}', font=font1(13), fill=INK_2, anchor='ma')

    # Mainline cars, front to back. A car's drawn length is limited by the room to the car
    # behind it, so icons never overlap even though they are drawn longer than real.
    shown = sorted((c for c in cars if zlo - 30 <= c[1] <= g['zhi'] + 30), key=lambda c: -c[1])
    for k, (vid, x, v, lane, origin) in enumerate(shown):
        front = round(zpx(x))
        room = front - round(zpx(shown[k + 1][1])) - 2 if k + 1 < len(shown) else CAR_PX
        length = int(max(min(CAR_PX, room), 4))
        if front - length < zx0 or front > zx1:        # only cars fully inside the drawn road
            continue
        y = my
        if origin == 1 and vid in te and 0 <= t - te[vid] < LC_TIME:
            f = (t - te[vid]) / LC_TIME
            f = f * f * (3 - 2 * f)                       # smooth start and end of the lane change
            y = round(ay + (my - ay) * f)
        _paste_car(im, front, y, v, length, origin == 1)

    # Counter values and elapsed-time bar.
    tiles = [sum(1 for c in cars if c[3] == 0), sum(1 for c in cars if c[2] < 30), ramp_ext, main_ext,
             log.get('merges', '–') if log else '–', log.get('exited', '–') if log else '–']
    tw = (W - 64 - 10 * (len(tiles) - 1)) / len(tiles)
    for i, value in enumerate(tiles):
        d.text((32 + i * (tw + 10) + 12, 494), str(value), font=font1(22, True), fill=INK)
    bx0, bx1, by = 32, W - 32, 606
    d.rounded_rectangle((bx0, by, max(bx0 + 8, bx0 + (bx1 - bx0) * min(t / t_end, 1)), by + 8), 4, fill=ZOOM_ACCENT)
    return im


def _gif_writer(path, palette_rgb):
    """Stream frames into a GIF: global palette, endless loop, one frame at a time."""
    f = open(path, 'wb')
    f.write(b'GIF89a' + o16(W) + o16(H) + bytes([0xF7, 0, 0]) + bytes(palette_rgb))
    f.write(b'!\xff\x0bNETSCAPE2.0\x03\x01' + o16(0) + b'\x00')
    return f


def _make_zone(result, out):
    cfg = result['summary']['config']
    logs = {int(round(z['t_s'] - cfg['dt'])): z for z in result['logs']}
    t_end = view_end(result) * 60
    g = _zone_view(cfg)
    ramp = zone_plan(result, g['ramp_len'])
    te = {p['id']: p['te'] for p in ramp}
    bg = _zone_background(cfg, t_end, g).resize((W, H), Image.LANCZOS)

    def render(fr):
        t, cars, main_ext, ramp_ext = fr
        return _zone_frame(bg, cfg, g, t, cars, main_ext, ramp_ext, logs.get(int(math.floor(t + 1e-9))),
                           t_end, ramp, te)

    # One global palette (PALETTE_COLORS entries) from sample frames plus the speed scale;
    # index 255 is kept free and marks pixels that did not change since the previous frame.
    frames = list(_interp_frames(result, REPLAY_STEP, t_end))
    samples = [render(frames[int(len(frames) * q)]) for q in (0.25, 0.5, 0.8)]
    ref = Image.new('RGB', (W, 3 * H + 120), SURFACE)
    for k, sample in enumerate(samples):
        ref.paste(sample, (0, k * H))
    for i in range(W):
        rgb = speed_rgb(SPEED_MAX_KMH * i / (W - 1))
        ref.paste(rgb, (i, 3 * H, i + 1, 3 * H + 80))
        ref.paste(_shade(rgb), (i, 3 * H + 80, i + 1, 3 * H + 120))
    pal = ref.quantize(colors=PALETTE_COLORS, method=Image.Quantize.MEDIANCUT).getpalette()[:PALETTE_COLORS * 3]
    pal += [0] * (255 * 3 - len(pal)) + [255, 0, 255]
    pal_img = Image.new('P', (1, 1))
    pal_img.putpalette(pal)

    import numpy as np
    f = _gif_writer(out / 'simulation_replay.gif', pal)
    prev = None
    for n, fr in enumerate(frames):
        cur = np.asarray(render(fr).quantize(palette=pal_img, dither=Image.Dither.NONE))
        delay = END_HOLD_MS if n == len(frames) - 1 else REPLAY_MS
        if prev is None:
            box, data = (0, 0, W, H), cur
        else:
            diff = cur != prev
            if diff.any():
                ys, xs = np.nonzero(diff)
                box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
                data = np.where(diff, cur, TRANSPARENT)[box[1]:box[3], box[0]:box[2]]
            else:
                box, data = (0, 0, 1, 1), np.full((1, 1), TRANSPARENT, np.uint8)
        data = np.ascontiguousarray(data, dtype=np.uint8)
        im = Image.frombytes('P', (data.shape[1], data.shape[0]), data.tobytes())
        for chunk in GifImagePlugin.getdata(im, offset=box[:2], duration=delay, disposal=1,
                                            transparency=TRANSPARENT):
            f.write(chunk)
        prev = cur
    f.write(b';')
    f.close()
    return len(frames)


# --------------------------------------------------------------------------
# Explicit acceleration lane: ramp vehicles are simulated on lane 1 (the ramp road and the
# acceleration lane beside the mainline) and change to the mainline when the gap is safe.
# --------------------------------------------------------------------------
LANE_LC_TIME = 3.0        # s over which a merge is drawn as a lateral lane change


def _lane_view(cfg):
    """Zoomed view geometry for the explicit acceleration-lane model (px at 1x scale)."""
    xs = cfg['merge_x'] - cfg['acc_length']
    zlo = max(0.0, xs - 350.0)
    zhi = min(cfg['road_end'], cfg['merge_x'] + 100.0)
    scale = (W - 120) / (zhi - zlo)
    my = 240.0
    ay = my + LANE_PX
    jx = 60 + (xs - zlo) * scale
    ux, uy = -0.894, 0.447                      # from the lane start toward the ramp entrance
    rl = cfg['ramp_length'] * scale             # ramp road drawn to scale
    return dict(zlo=zlo, zhi=zhi, scale=scale, my=my, ay=ay, xs=xs, jx=jx, jy=ay, ux=ux, uy=uy,
                ex=jx + ux * rl, ey=ay + uy * rl)


def _interp_lanes(result, step, t_end):
    """Yield (t, cars, main_waiting, ramp_waiting) every `step` s from the 1 s records.

    Cars are [id, x, v_kmh, lane, origin]; a car present in both neighbouring records moves
    linearly between them, and a car that changes lane during the second takes the mainline
    from its merge time on. Cars entering or leaving during the second are extrapolated."""
    cfg = result['summary']['config']
    by_t = {int(round(f[0])): f for f in result['frames']}
    last = max(by_t)
    te = {e['id']: e['t'] for e in result['events'] if e.get('result') == 'accepted'}
    x_rs = cfg['merge_x'] - cfg['acc_length'] - cfg['ramp_length']
    k = 0
    while True:
        t = round(k * step, 6)
        if t > t_end + 1e-9 or t > last:
            return
        i = int(math.floor(t + 1e-9))
        w = t - i
        a, b = by_t[i], by_t.get(i + 1)
        if b is None or w < 1e-9:
            yield t, a[1], a[2], a[3]
            k += 1
            continue
        ca = {c[0]: c for c in a[1]}
        cb = {c[0]: c for c in b[1]}
        cars = []
        for vid, c in ca.items():
            n = cb.get(vid)
            if n is not None:
                lane = n[3] if c[3] == n[3] else (0 if t >= te.get(vid, i + 1) else 1)
                cars.append([vid, c[1] + (n[1] - c[1]) * w, c[2] + (n[2] - c[2]) * w, lane, c[4]])
            else:                                     # left the road during this second
                x = c[1] + c[2] / 3.6 * w
                if x < cfg['road_end']:
                    cars.append([vid, x, c[2], c[3], c[4]])
        for vid, n in cb.items():
            if vid in ca:
                continue
            x = n[1] - n[2] / 3.6 * (1 - w)
            if x < (x_rs if n[3] == 1 else 0.0):      # not yet through its entrance
                continue
            cars.append([vid, x, n[2], n[3], n[4]])
        yield t, cars, a[2], a[3]
        k += 1


def _lane_background(cfg, t_end, g):
    """Static parts of the explicit-lane replay, drawn once (supersampled)."""
    cv = Canvas()
    L, m = cfg['road_end'], cfg['merge_x']
    xs = g['xs']
    cv.text(32, 24, 'All-HDV freeway with an on-ramp', 24, True)
    # Ramp control badge next to the title, so runs with and without metering are told apart.
    control = _control_label(cfg)
    cv.rect((500, 24, 500 + 11 * len(control) + 28, 54), fill=METER_ON if _metered(cfg) else METER_NONE, radius=15)
    cv.text(514, 30, control, 15, True, fill='#ffffff')
    ramp_txt = ('ramp: ALINEA metering' if cfg.get('ramp_control') == 'alinea' else
                f"ramp: fixed meter {cfg['ramp_release_rate']:.0f} veh/h" if cfg.get('ramp_release_rate') else 'ramp: no metering')
    cv.text(32, 58, f"IDM car following  ·  acceleration lane  ·  no yielding  ·  {ramp_txt}  ·  seed {cfg['seed']}  ·  "
                    f"replay at {REPLAY_STEP * 1000 / REPLAY_MS:.0f}x real time", 14, fill=INK_2)
    if _metered(cfg):
        # Stop line across the ramp at the meter, and a legend for the signal (the legend also puts
        # both signal colours into the GIF palette).
        px, py = _meter_px(cfg, g)
        nx, ny = -g['uy'], g['ux']                 # unit normal of the ramp road
        cv.line((px - nx * 10, py - ny * 10, px + nx * 10, py + ny * 10), INK, 3)
        lx0, ly0 = 64, g['ey'] - 64
        cv.circle(lx0, ly0 + 7, 5, LIGHT_RED)
        cv.text(lx0 + 9, ly0, 'red: wait at stop line', 11, fill=MUTED)
        cv.circle(lx0 + 142, ly0 + 7, 5, LIGHT_GREEN)
        cv.text(lx0 + 151, ly0, 'green: one car goes', 11, fill=MUTED)
    ox0, ox1, oy = 60, W - 60, 124

    def opx(x):
        return ox0 + (ox1 - ox0) * x / L

    cv.text(ox0, 92, 'Whole road', 13, True, fill=INK_2)
    cv.text(ox0 + 92, 93, '(color = speed of the nearest car)', 12, fill=MUTED)
    cv.line((opx(xs - cfg['ramp_length']), oy + 17, opx(xs), oy + 9), ROAD, 5)
    cv.line((opx(xs), oy + 9, opx(m), oy + 9), ROAD, 5)
    cv.line((ox0, oy, ox1, oy), ROAD, 10)
    for km in range(int(L // 1000) + 1):
        cv.text(opx(km * 1000), oy + 22, f'{km} km', 11, fill=MUTED, anchor='ma')
    cv.rect((opx(g['zlo']), oy - 12, opx(g['zhi']), oy + 20), outline=ZOOM_ACCENT, width=1, radius=4)
    cv.text(opx(g['zhi']) + 6, oy + 3, 'zoomed below', 11, fill=ZOOM_ACCENT)

    zx0, zx1, my, ay = 60, W - 60, g['my'], g['ay']
    sc, zlo = g['scale'], g['zlo']

    def zpx(x):
        return zx0 + (x - zlo) * sc

    h = LANE_PX / 2
    cv.text(zx0, 176, f"Merge area  {g['zlo'] / 1000:.2f}-{g['zhi'] / 1000:.2f} km  (traffic flows left to right)",
            13, True, fill=INK_2)
    cv.rect((zx0, my - h, zx1, my + h), fill=ROAD)
    cv.rect((zpx(xs), ay - h, zpx(m), ay + h), fill=ROAD)
    cv.poly([(zpx(m), ay - h), (zpx(m) + 36, ay - h), (zpx(m), ay + h)], fill=ROAD)
    cv.line((g['ex'], g['ey'], g['jx'] + 2, g['jy']), ROAD, LANE_PX)
    cv.dashed(zpx(xs), zpx(m), my + h, LANE_MARK, dash=8, gap=7, width=1.5)
    cv.text(g['ex'] - 8, g['ey'] - 4, 'ramp entrance', 11, fill=MUTED, anchor='rb')
    cv.text(zpx(xs) + 4, ay + h + 6, f"acceleration lane ({cfg['acc_length']:.0f} m)", 11, fill=ZOOM_ACCENT)
    cv.line((zpx(m), my - h - 6, zpx(m), ay + h + 2), ZOOM_ACCENT, 2)
    cv.text(zpx(m) + 40, ay - 7, 'lane end', 11, fill=ZOOM_ACCENT)
    for x in range(int(zlo // 100 + 1) * 100, int(g['zhi']) + 1, 100):
        cv.line((zpx(x), my - h - 7, zpx(x), my - h - 2), AXIS, 1)
        cv.text(zpx(x), my - h - 22, f'{x / 1000:.1f}', 11, fill=MUTED, anchor='ma')

    labels = ['On mainline', 'Slower than 30 km/h', 'On ramp', 'Waiting outside ramp', 'Merges so far', 'Exited so far']
    tw = (W - 64 - 10 * (len(labels) - 1)) / len(labels)
    for i, label in enumerate(labels):
        x = 32 + i * (tw + 10)
        cv.rect((x, 464, x + tw, 530), fill='#ffffff', outline=GRID, radius=8)
        cv.text(x + 12, 474, label, 12, fill=INK_2)

    lx, ly = 32, 556
    cv.text(lx, ly, 'Speed', 12, True, fill=INK_2)
    for i in range(200):
        cv.rect((lx + 50 + i, ly + 1, lx + 51 + i, ly + 13), fill=hexrgb(SPEED_MAX_KMH * i / 199))
    cv.text(lx + 50, ly + 17, '0', 11, fill=MUTED)
    cv.text(lx + 250, ly + 17, f'{SPEED_MAX_KMH:.0f} km/h', 11, fill=MUTED, anchor='ra')
    pale = speed_rgb(105)
    _car_h(cv.d, (lx + 302 + CAR_PX) * SS, (ly + 7) * SS, CAR_PX * SS, pale, _shade(pale), 1)
    cv.text(lx + 310 + CAR_PX, ly, 'mainline car', 12, fill=INK_2)
    _car_h(cv.d, (lx + 420 + CAR_PX) * SS, (ly + 7) * SS, CAR_PX * SS, pale, RAMP_EDGE, 1.5)
    cv.text(lx + 428 + CAR_PX, ly, 'ramp car (dark outline)', 12, fill=INK_2)
    cv.text(W - 32, ly, 'Positions to scale; cars drawn about 2x real length; lane changes drawn over 3 s.',
            11, fill=MUTED, anchor='ra')
    cv.text(W - 32, ly + 17, 'Ramp cars accelerate on the acceleration lane and merge into a safe gap; no vehicle yields.',
            11, fill=MUTED, anchor='ra')

    bx0, bx1, by = 32, W - 32, 606
    cv.rect((bx0, by, bx1, by + 8), fill=GRID, radius=4)
    cv.rect((bx0, by, bx0 + (bx1 - bx0) * min(cfg['demand_end'] / t_end, 1), by + 8), fill='#c6d9f1', radius=4)
    cv.text(bx0, by + 12, '0 min', 11, fill=MUTED)
    cv.text(bx0 + (bx1 - bx0) * min(cfg['demand_end'] / t_end, 1), by + 12, 'demand ends', 11, fill=MUTED, anchor='ma')
    cv.text(bx1, by + 12, mmss(t_end), 11, fill=MUTED, anchor='ra')
    return cv.im


METER_ON, METER_NONE = '#1f7a3a', '#6b7280'
LIGHT_RED, LIGHT_GREEN = '#d0402b', '#2e9e4f'
GREEN_HOLD_S = 1.5          # the drawn signal shows green this long after each release
MODE_TEXT = {'alinea': 'ALINEA', 'override': 'queue override', 'fallback': 'fallback (no data)', 'hold': 'hold (report lost)'}


def _metered(cfg):
    return cfg.get('ramp_control') == 'alinea' or bool(cfg.get('ramp_release_rate'))


def _control_label(cfg):
    if cfg.get('ramp_control') == 'alinea':
        return 'ALINEA RAMP METERING'
    if cfg.get('ramp_release_rate'):
        return 'FIXED RAMP METER'
    return 'NO RAMP CONTROL'


def _meter_px(cfg, g):
    """Drawn position of the meter stop line on the ramp road."""
    xm = cfg.get('meter_x')
    back = 0.0 if xm is None else (g['xs'] - xm) * g['scale']
    return g['jx'] + g['ux'] * back, g['jy'] + g['uy'] * back


def _meter_state(result, cfg):
    """Release rate and TMC mode over time, and ramp release times, for the drawn ramp signal."""
    if not _metered(cfg):
        return None
    cycles = sorted(result.get('tmc') or [], key=lambda z: z['t_s'])
    if cfg.get('ramp_control') == 'alinea':
        times = [0.0] + [z['t_s'] for z in cycles]
        rates = [cfg['rate_max']] + [z['rate_veh_h'] for z in cycles]
        modes = ['alinea'] + [z['mode'] for z in cycles]
    else:
        times, rates, modes = [0.0], [cfg['ramp_release_rate']], ['fixed']
    key = 'release_s' if result['trips'] and 'release_s' in result['trips'][0] else 'entry_s'
    entries = sorted(z[key] for z in result['trips'] if z['origin'] == 1 and z.get(key) is not None)
    rest = cfg['rate_max'] if cfg.get('ramp_control') == 'alinea' else math.inf
    return dict(times=times, rates=rates, modes=modes, entries=entries, rest=rest)


def _draw_meter(d, g, t, meter, cfg):
    """Signal at the stop line (green just after a release, or resting green at the maximum rate)
    and the current release rate."""
    px, py = _meter_px(cfg, g)
    x, y = g['jx'] + 6, g['jy'] + 38
    if meter is None:
        d.text((x, y), 'Ramp meter: off', font=font1(13), fill=MUTED, anchor='la')
        return
    k = max(bisect.bisect_right(meter['times'], t + 1e-9) - 1, 0)
    j = bisect.bisect_right(meter['entries'], t + 1e-9) - 1
    rest = meter['rates'][k] >= meter['rest'] - 1e-9
    green = rest or (j >= 0 and t - meter['entries'][j] < GREEN_HOLD_S)
    sx, sy = px - 14, py + 30
    d.rounded_rectangle((sx - 9, sy - 9, sx + 9, sy + 9), 4, fill=INK)
    d.ellipse((sx - 6, sy - 6, sx + 6, sy + 6), fill=LIGHT_GREEN if green else LIGHT_RED)
    mode = MODE_TEXT.get(meter['modes'][k], meter['modes'][k])
    if rest:
        mode += ', resting green (no restriction)'
    d.text((x, y), f"Ramp meter: {meter['rates'][k]:.0f} veh/h", font=font1(14, True), fill=METER_ON, anchor='la')
    d.text((x, y + 19), f'mode: {mode}', font=font1(12), fill=INK_2, anchor='la')


def _clamped(cars, px):
    """(car, drawn length) front to back; a car's icon is shortened to the room before the car behind."""
    out = []
    for k, z in enumerate(cars):
        room = px(z) - px(cars[k + 1]) - 2 if k + 1 < len(cars) else CAR_PX
        out.append((z, int(max(min(CAR_PX, room), 4))))
    return out


def _lane_frame(bg, cfg, g, t, cars, main_ext, ramp_ext, log, t_end, te, meter=None):
    im = bg.copy()
    d = ImageDraw.Draw(im)
    _draw_meter(d, g, t, meter, cfg)
    L = cfg['road_end']
    demand = t < cfg['demand_end']
    d.text((W - 32, 22), mmss(t), font=font1(34, True), fill=INK, anchor='ra')
    empty = not cars and not main_ext and not ramp_ext and not demand
    badge = ('Demand active' if demand else
             f"Network empty (run continues to {cfg['duration'] / 60:.0f} min)" if empty else 'Demand ended, clearing')
    d.text((W - 32, 66), badge, font=font1(14), fill=ZOOM_ACCENT if demand else MUTED, anchor='ra')
    main = [z for z in cars if z[3] == 0]
    ramp = [z for z in cars if z[3] == 1]

    ox0, ox1, oy = 60, W - 60, 124
    pts = sorted((z[1], z[2]) for z in main)
    if pts:
        xs_ = [p for p, _ in pts]
        nb = int(L // 20)
        for b in range(nb):
            xc = (b + 0.5) * L / nb
            j = bisect.bisect_left(xs_, xc)
            best = min((k for k in (j - 1, j) if 0 <= k < len(pts)), key=lambda k: abs(pts[k][0] - xc))
            if abs(pts[best][0] - xc) <= 150:
                x0 = ox0 + round((ox1 - ox0) * b / nb)
                x1 = ox0 + round((ox1 - ox0) * (b + 1) / nb) - 1
                d.rectangle((x0, oy - 5, x1, oy + 4), fill=speed_rgb(min(pts[best][1] // 10 * 10 + 5, SPEED_MAX_KMH)))

    sc, zlo, my, ay, xs = g['scale'], g['zlo'], g['my'], g['ay'], g['xs']
    zx0, zx1 = 60, W - 60

    def zpx(x):
        return zx0 + (x - zlo) * sc

    # Ramp road (slanted) and acceleration lane; path distance in px is (x difference) * scale.
    for z, length in _clamped(sorted(ramp, key=lambda z: -z[1]), lambda z: z[1] * sc):
        if z[1] < xs:
            back = (xs - z[1]) * sc
            _paste_car(im, g['jx'] + g['ux'] * back, g['jy'] + g['uy'] * back, z[2], length, True, (g['ux'], g['uy']))
        else:
            front = round(zpx(z[1]))
            if zx0 <= front - length:
                _paste_car(im, front, ay, z[2], length, True)
    d.text((g['ex'] - 10, g['ey'] + 12), f'Waiting outside ramp: {ramp_ext}', font=font1(13), fill=INK_2, anchor='ma')

    shown = sorted((z for z in main if zlo - 30 <= z[1] <= g['zhi'] + 30), key=lambda z: -z[1])
    for z, length in _clamped(shown, lambda z: round(zpx(z[1]))):
        vid, x, v, lane, origin = z
        front = round(zpx(x))
        if front - length < zx0 or front > zx1:
            continue
        y = my
        if origin == 1 and vid in te and 0 <= t - te[vid] < LANE_LC_TIME:
            f = (t - te[vid]) / LANE_LC_TIME
            f = f * f * (3 - 2 * f)
            y = round(ay + (my - ay) * f)
        _paste_car(im, front, y, v, length, origin == 1)

    tiles = [len(main), sum(1 for z in main if z[2] < 30), len(ramp), ramp_ext,
             log.get('merges', '–') if log else '–', log.get('exited', '–') if log else '–']
    tw = (W - 64 - 10 * (len(tiles) - 1)) / len(tiles)
    for i, value in enumerate(tiles):
        d.text((32 + i * (tw + 10) + 12, 494), str(value), font=font1(22, True), fill=INK)
    bx0, bx1, by = 32, W - 32, 606
    d.rounded_rectangle((bx0, by, max(bx0 + 8, bx0 + (bx1 - bx0) * min(t / t_end, 1)), by + 8), 4, fill=ZOOM_ACCENT)
    return im


def _make_lane(result, out):
    cfg = result['summary']['config']
    logs = {int(round(z['t_s'] - cfg['dt'])): z for z in result['logs']}
    t_end = view_end(result) * 60
    g = _lane_view(cfg)
    te = {e['id']: e['t'] for e in result['events'] if e.get('result') == 'accepted'}
    bg = _lane_background(cfg, t_end, g).resize((W, H), Image.LANCZOS)
    meter = _meter_state(result, cfg)

    def render(fr):
        t, cars, main_ext, ramp_ext = fr
        return _lane_frame(bg, cfg, g, t, cars, main_ext, ramp_ext, logs.get(int(math.floor(t + 1e-9))), t_end, te, meter)

    _write_gif(out / 'simulation_replay.gif', list(_interp_lanes(result, REPLAY_STEP, t_end)), render)


def _write_gif(path, frames, render):
    """Palette from sample frames, then stream every frame storing only changed pixels."""
    samples = [render(frames[int(len(frames) * q)]) for q in (0.25, 0.5, 0.8)]
    ref = Image.new('RGB', (W, 3 * H + 120), SURFACE)
    for k, sample in enumerate(samples):
        ref.paste(sample, (0, k * H))
    for i in range(W):
        rgb = speed_rgb(SPEED_MAX_KMH * i / (W - 1))
        ref.paste(rgb, (i, 3 * H, i + 1, 3 * H + 80))
        ref.paste(_shade(rgb), (i, 3 * H + 80, i + 1, 3 * H + 120))
    pal = ref.quantize(colors=PALETTE_COLORS, method=Image.Quantize.MEDIANCUT).getpalette()[:PALETTE_COLORS * 3]
    pal += [0] * (255 * 3 - len(pal)) + [255, 0, 255]
    pal_img = Image.new('P', (1, 1))
    pal_img.putpalette(pal)
    import numpy as np
    f = _gif_writer(path, pal)
    prev = None
    for n, fr in enumerate(frames):
        cur = np.asarray(render(fr).quantize(palette=pal_img, dither=Image.Dither.NONE))
        delay = END_HOLD_MS if n == len(frames) - 1 else REPLAY_MS
        if prev is None:
            box, data = (0, 0, W, H), cur
        else:
            diff = cur != prev
            if diff.any():
                ys, xs = np.nonzero(diff)
                box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
                data = np.where(diff, cur, TRANSPARENT)[box[1]:box[3], box[0]:box[2]]
            else:
                box, data = (0, 0, 1, 1), np.full((1, 1), TRANSPARENT, np.uint8)
        data = np.ascontiguousarray(data, dtype=np.uint8)
        im = Image.frombytes('P', (data.shape[1], data.shape[0]), data.tobytes())
        for chunk in GifImagePlugin.getdata(im, offset=box[:2], duration=delay, disposal=1, transparency=TRANSPARENT):
            f.write(chunk)
        prev = cur
    f.write(b';')
    f.close()


def make(out, raw=None):
    """Read an explicitly saved run and export ``simulation_replay.gif`` into ``out``.

    ``raw`` is the run's ``with_ramp_raw.json``; by default it is read from ``out``."""
    out = Path(out)
    result = json.loads(Path(raw or out / 'with_ramp_raw.json').read_text(encoding='utf-8'))
    cfg = result['summary']['config']
    if cfg.get('acc_length', 0) > 0:
        _make_lane(result, out)
        return
    if cfg.get('zone_length', 0) > 0:
        _make_zone(result, out)
        return
    # logs[i] is recorded at the end of the same step whose start is frames[i].
    logs = {round(z['t_s'] - cfg['dt'], 3): z for z in result['logs']}
    # Stop one minute after the last exit (same rule as the figures and HTML replay).
    t_end = view_end(result) * 60
    zone = cfg.get('zone_length', 0) > 0
    step, frame_ms = (ZONE_FRAME_STEP, ZONE_FRAME_MS) if zone else (FRAME_STEP, FRAME_MS)
    frames = [f for f in result['frames'] if f[0] <= t_end + 1e-6][::step]
    if not frames:
        raise ValueError('No recorded frames are available for GIF export.')
    # One shared palette (built from the speed scale plus a sample frame) lets the
    # GIF encoder store only the pixels that change between frames.
    ramp = None
    if cfg.get('zone_length', 0) > 0:
        ramp = zone_plan(result, zone_ramp_length_m(cfg))
    elif 'merge_x' in cfg:
        try:
            ramp = ramp_plan(result, ramp_length_m(cfg))
        except (KeyError, TypeError):
            ramp = None    # older saved runs without trip records keep the plain queue drawing
    sample = draw_frame(frames[len(frames) // 2], logs.get(round(frames[len(frames) // 2][0], 3)), cfg, t_end, ramp)
    swatch = Image.new('RGB', (241, 20))
    for i in range(241):
        swatch.paste(speed_rgb(SPEED_MAX_KMH * i / 240), (i, 0, i + 1, 20))
    ref = Image.new('RGB', (W, H + 20), SURFACE)
    ref.paste(sample, (0, 0))
    ref.paste(swatch, (0, H))
    palette = ref.quantize(colors=160, method=Image.Quantize.MEDIANCUT)
    images = [draw_frame(f, logs.get(round(f[0], 3)), cfg, t_end, ramp).quantize(palette=palette, dither=Image.Dither.NONE)
              for f in frames]
    durations = [frame_ms] * (len(images) - 1) + [END_HOLD_MS]
    images[0].save(out / 'simulation_replay.gif', save_all=True, append_images=images[1:],
                   duration=durations, loop=0, optimize=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path, help='Existing user-saved run directory.')
    make(parser.parse_args().directory)
