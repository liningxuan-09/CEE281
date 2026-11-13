// Replay of recorded one-second frames. This is a viewer, not a second simulation:
// positions and speeds are drawn exactly as stored, and only playback state changes.
// Frame format: [t_s, [[id, x_m, v_kmh, lane, origin], ...], main_external, ramp_external]
(function () {
    const frames = DATA.with_ramp;
    const cfg = CONFIGS.with_ramp;
    const counters = COUNTERS.with_ramp || [];
    const canvas = document.getElementById('road');
    const ctx = canvas.getContext('2d');
    const slider = document.getElementById('time');
    const button = document.getElementById('play');
    const clock = document.getElementById('clock');
    const W = 1160, H = 560;       // logical drawing size; scaled for HiDPI screens
    const C = { ink: '#0b0b0b', ink2: '#52514e', muted: '#898781', grid: '#e1e0d9', road: '#e8eaee',
                edge: '#8d8c86', accent: '#2a78d6', green: '#1a9a5c', red: '#d03b3b', surface: '#fcfcfb' };
    let playing = false, sim = 0, last = null;
    // Python already dropped the empty tail after the last exit; the bar ends at the last frame.
    const tEnd = frames.length ? frames[frames.length - 1][0] : cfg.duration;

    // Same speed scale as the PNG figures and the GIF (defined once in present.py).
    const stops = SPEED_STOPS.map(([f, h]) => [f, [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16))]);
    function speedColor(kmh) {
        const f = Math.max(0, Math.min(1, kmh / 120));
        for (let i = 1; i < stops.length; i++) {
            if (f <= stops[i][0]) {
                const [f0, c0] = stops[i - 1], [f1, c1] = stops[i], w = (f - f0) / (f1 - f0);
                return `rgb(${c0.map((a, k) => Math.round(a + (c1[k] - a) * w)).join(',')})`;
            }
        }
        return `rgb(${stops[stops.length - 1][1].join(',')})`;
    }

    function resize() {
        const dpr = window.devicePixelRatio || 1;
        canvas.width = W * dpr; canvas.height = H * dpr;
        canvas.style.aspectRatio = `${W} / ${H}`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const mmss = t => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
    function text(s, x, y, size = 13, color = C.ink2, align = 'left', weight = 400) {
        ctx.font = `${weight} ${size}px system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
        ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'top';
        ctx.fillText(s, x, y);
    }
    function roundRect(x, y, w, h, r, fill, stroke, lw) {
        ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.stroke(); }
    }

    // Explicit ramp-lane model (runs 1-2).
    function drawLane(t, cars) {
        // ---- Whole-corridor strip -----------------------------------------
        const L = cfg.road_end, ox0 = 40, ox1 = W - 40, oy = 96;
        const opx = x => ox0 + (ox1 - ox0) * x / L;
        const zlo = cfg.ramp_start - 150, zhi = cfg.merge_end + 250;
        text('Whole corridor', ox0, 66, 12, C.ink2, 'left', 600);
        roundRect(opx(zlo), oy - 14, opx(zhi) - opx(zlo), 36, 4, null, C.accent, 1);
        ctx.lineCap = 'butt';
        ctx.strokeStyle = C.road; ctx.lineWidth = 9;
        ctx.beginPath(); ctx.moveTo(ox0, oy); ctx.lineTo(ox1, oy); ctx.stroke();
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(opx(cfg.ramp_start), oy + 15); ctx.lineTo(opx(cfg.merge_start), oy + 7);
        ctx.lineTo(opx(cfg.merge_end), oy + 7); ctx.stroke();
        for (let km = 0; km <= L / 1000; km++) text(`${km} km`, opx(km * 1000), oy + 26, 11, C.muted, 'center');
        for (const [, x, v, lane] of cars) {
            const y = lane === 0 ? oy : oy + 15 - 8 * Math.min(1, (x - cfg.ramp_start) / (cfg.merge_start - cfg.ramp_start));
            ctx.fillStyle = speedColor(v); ctx.fillRect(opx(x) - 2, y - 4, 3, 8);
            ctx.strokeStyle = C.edge; ctx.lineWidth = 0.5; ctx.strokeRect(opx(x) - 2, y - 4, 3, 8);
        }

        // ---- Zoomed merge area --------------------------------------------
        const zx0 = 40, zx1 = W - 40, my = 228, lh = 34, ay = my + lh, rb = 372;
        const zpx = x => zx0 + (zx1 - zx0) * (x - zlo) / (zhi - zlo);
        const rampY = x => rb + (ay - rb) * Math.min(1, Math.max(0, (x - cfg.ramp_start) / (cfg.merge_start - cfg.ramp_start)));
        text(`Merge area ${(zlo / 1000).toFixed(2)}–${(zhi / 1000).toFixed(2)} km`, zx0, 150, 12, C.ink2, 'left', 600);
        ctx.fillStyle = C.road;
        ctx.fillRect(zx0, my - lh / 2, zx1 - zx0, lh);
        ctx.fillRect(zpx(cfg.merge_start), ay - lh / 2, zpx(cfg.merge_end) - zpx(cfg.merge_start), lh);
        ctx.strokeStyle = C.road; ctx.lineWidth = lh * 0.8;
        ctx.beginPath(); ctx.moveTo(zpx(cfg.ramp_start), rb); ctx.lineTo(zpx(cfg.merge_start), ay); ctx.stroke();
        ctx.setLineDash([10, 8]); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(zpx(cfg.merge_start), my + lh / 2); ctx.lineTo(zpx(cfg.merge_end), my + lh / 2); ctx.stroke();
        ctx.setLineDash([]); ctx.strokeStyle = C.ink;
        ctx.beginPath(); ctx.moveTo(zpx(cfg.merge_end), ay - lh / 2); ctx.lineTo(zpx(cfg.merge_end), ay + lh / 2); ctx.stroke();
        text('merge zone', (zpx(cfg.merge_start) + zpx(cfg.merge_end)) / 2, ay + lh / 2 + 6, 11, C.accent, 'center');
        text('ramp end', zpx(cfg.merge_end) + 4, ay + lh / 2 + 6, 11, C.muted);
        for (let x = Math.ceil(zlo / 100) * 100; x < zhi; x += 100) {
            ctx.strokeStyle = '#c3c2b7'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(zpx(x), my - lh / 2 - 8); ctx.lineTo(zpx(x), my - lh / 2 - 2); ctx.stroke();
            text((x / 1000).toFixed(1), zpx(x), my - lh / 2 - 24, 11, C.muted, 'center');
        }
        // Upstream admission signal: one ramp vehicle may enter per cycle while open.
        const open = t % cfg.release_period < cfg.green_duration;
        ctx.fillStyle = open ? C.green : C.red;
        ctx.beginPath(); ctx.arc(zpx(cfg.ramp_start) + 4, rb + 28, 7, 0, 2 * Math.PI); ctx.fill();
        text(`${cfg.ramp_end_brake === undefined ? 'merge window' : 'ramp admission'} ${open ? 'open' : 'closed'}`, zpx(cfg.ramp_start) + 18, rb + 21, 12);
        const scale = (zx1 - zx0) / (zhi - zlo);
        for (const [, x, v, lane, origin] of cars) {
            if (x < zlo - 10 || x > zhi + 10) continue;
            const len = Math.max(cfg.length * scale, 6), y = lane === 0 ? my : rampY(x);
            roundRect(zpx(x) - len, y - 8, len, 16, 3, speedColor(v), origin === 1 ? C.ink : C.edge, origin === 1 ? 2 : 1);
        }

    }

    // Point-merge model (run 3 onward): ramp is a FIFO queue at the merge point.
    function drawPoint(t, cars, rampQ) {
        const L = cfg.road_end, m = cfg.merge_x, ox0 = 40, ox1 = W - 40, oy = 96;
        const opx = x => ox0 + (ox1 - ox0) * x / L;
        const zlo = Math.max(0, m - 900), zhi = Math.min(L, m + 400);
        text('Whole corridor', ox0, 66, 12, C.ink2, 'left', 600);
        roundRect(opx(zlo), oy - 14, opx(zhi) - opx(zlo), 36, 4, null, C.accent, 1);
        ctx.lineCap = 'butt'; ctx.strokeStyle = C.road; ctx.lineWidth = 9;
        ctx.beginPath(); ctx.moveTo(ox0, oy); ctx.lineTo(ox1, oy); ctx.stroke();
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(opx(m - 160), oy + 15); ctx.lineTo(opx(m), oy + 5); ctx.stroke();
        for (let km = 0; km <= L / 1000; km++) text(`${km} km`, opx(km * 1000), oy + 26, 11, C.muted, 'center');
        for (const [, x, v, , origin] of cars) {
            ctx.fillStyle = speedColor(v); ctx.fillRect(opx(x) - 2, oy - 4, 3, 8);
            ctx.strokeStyle = origin ? C.ink : C.edge; ctx.lineWidth = 0.5; ctx.strokeRect(opx(x) - 2, oy - 4, 3, 8);
        }
        const zx0 = 40, zx1 = W - 40, my = 228, lh = 34;
        const zpx = x => zx0 + (zx1 - zx0) * (x - zlo) / (zhi - zlo);
        text(`Merge area ${(zlo / 1000).toFixed(2)}–${(zhi / 1000).toFixed(2)} km (traffic flows left to right)`,
             zx0, 150, 12, C.ink2, 'left', 600);
        ctx.fillStyle = C.road; ctx.fillRect(zx0, my - lh / 2, zx1 - zx0, lh);
        const mx = zpx(m), sx0 = mx - 240, sy0 = my + 140, sy1 = my + lh / 2 - 2;
        ctx.strokeStyle = C.road; ctx.lineWidth = 24;
        ctx.beginPath(); ctx.moveTo(sx0, sy0); ctx.lineTo(mx, sy1); ctx.stroke();
        ctx.strokeStyle = C.accent; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(mx, my - lh / 2 - 6); ctx.lineTo(mx, my + lh / 2 + 6); ctx.stroke();
        text('merge point', mx + 6, my + lh / 2 + 6, 11, C.accent);
        for (let x = Math.ceil(zlo / 100) * 100; x < zhi; x += 100) {
            ctx.strokeStyle = '#c3c2b7'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(zpx(x), my - lh / 2 - 8); ctx.lineTo(zpx(x), my - lh / 2 - 2); ctx.stroke();
            text((x / 1000).toFixed(1), zpx(x), my - lh / 2 - 24, 11, C.muted, 'center');
        }
        const shown = Math.min(rampQ, 16);
        for (let k = 0; k < shown; k++) {
            const f = (k + 0.6) / 17, qx = mx + (sx0 - mx) * f, qy = sy1 + (sy0 - sy1) * f;
            roundRect(qx - 6, qy - 5, 12, 10, 3, '#e6b8a6', C.ink, 2);
        }
        text(`Ramp queue: ${rampQ} waiting${rampQ > shown ? ` (first ${shown} drawn)` : ''}`,
             sx0 - 10, sy0 + 12, 13, C.ink2, 'center');
        const scale = (zx1 - zx0) / (zhi - zlo);
        for (const [, x, v, , origin] of cars) {
            if (x < zlo - 10 || x > zhi + 10) continue;
            const len = Math.max(cfg.length * scale, 6);
            roundRect(zpx(x) - len, my - 8, len, 16, 3, speedColor(v), origin === 1 ? C.ink : C.edge, origin === 1 ? 2 : 1);
        }
    }

    // Merge-zone model (run 5 onward): ramp vehicles drive down the ramp into an acceleration
    // lane beside the mainline and join it where the model inserted them. The ramp motion and
    // the 4 s lane change are reconstructed for display (see present._zone_replay).
    const Z = (typeof RAMP !== 'undefined' && RAMP) ? RAMP : null;
    const EQUIPPED = (typeof ACC !== 'undefined' && ACC) ? ACC : new Set();   // ids of ACC vehicles (blue outline)
    function drawZone(i, t, cars, rampQ) {
        const L = cfg.road_end, m = cfg.merge_x, zl = cfg.zone_length, xs = m - zl;
        const ox0 = 40, ox1 = W - 40, oy = 96;
        const opx = x => ox0 + (ox1 - ox0) * x / L;
        const zlo = Math.max(0, m - 900), zhi = Math.min(L, m + 400);
        text('Whole corridor', ox0, 66, 12, C.ink2, 'left', 600);
        roundRect(opx(zlo), oy - 14, opx(zhi) - opx(zlo), 36, 4, null, C.accent, 1);
        ctx.lineCap = 'butt'; ctx.strokeStyle = C.road; ctx.lineWidth = 9;
        ctx.beginPath(); ctx.moveTo(ox0, oy); ctx.lineTo(ox1, oy); ctx.stroke();
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(opx(xs - 300), oy + 15); ctx.lineTo(opx(xs), oy + 7); ctx.lineTo(opx(m), oy + 7); ctx.stroke();
        for (let km = 0; km <= L / 1000; km++) text(`${km} km`, opx(km * 1000), oy + 26, 11, C.muted, 'center');
        for (const [, x, v, , origin] of cars) {
            ctx.fillStyle = speedColor(v); ctx.fillRect(opx(x) - 2, oy - 4, 3, 8);
            ctx.strokeStyle = origin ? C.ink : C.edge; ctx.lineWidth = 0.5; ctx.strokeRect(opx(x) - 2, oy - 4, 3, 8);
        }

        const zx0 = 40, zx1 = W - 40, my = 228, lh = 34, ay = my + 34;
        const scale = (zx1 - zx0) / (zhi - zlo);
        const zpx = x => zx0 + (x - zlo) * scale;
        text(`Merge area ${(zlo / 1000).toFixed(2)}–${(zhi / 1000).toFixed(2)} km (traffic flows left to right)`,
             zx0, 150, 12, C.ink2, 'left', 600);
        ctx.fillStyle = C.road; ctx.fillRect(zx0, my - lh / 2, zx1 - zx0, lh);
        // Acceleration lane (= merge zone) with a short taper, and the ramp approach to scale.
        ctx.fillRect(zpx(xs), ay - lh / 2, zpx(m) - zpx(xs), lh);
        ctx.beginPath(); ctx.moveTo(zpx(m), ay - lh / 2); ctx.lineTo(zpx(m) + 40, ay - lh / 2); ctx.lineTo(zpx(m), ay + lh / 2);
        ctx.closePath(); ctx.fill();
        const rampLen = Z ? Z.ramp_len : 300, rpx = rampLen * scale;
        const ang = Math.atan2(116, 260), ux = -Math.cos(ang), uy = Math.sin(ang);   // toward the entrance
        const jx = zpx(xs), jy = ay, ex = jx + ux * rpx, ey = jy + uy * rpx;
        ctx.strokeStyle = C.road; ctx.lineWidth = 26;
        ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(jx + 6, jy); ctx.stroke();
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; ctx.setLineDash([10, 8]);
        ctx.beginPath(); ctx.moveTo(zpx(xs), my + lh / 2); ctx.lineTo(zpx(m), my + lh / 2); ctx.stroke();
        ctx.setLineDash([]);
        text('ramp entrance', ex - 6, ey - 16, 11, C.muted, 'right');
        text(`acceleration lane = merge zone (${Math.round(zl)} m)`, zpx(xs) + 4, ay + lh / 2 + 4, 11, C.accent);
        ctx.strokeStyle = C.accent; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(zpx(m), my - lh / 2 - 6); ctx.lineTo(zpx(m), ay + lh / 2); ctx.stroke();
        text('lane end', zpx(m) + 44, ay - 8, 11, C.accent);
        for (let x = Math.ceil(zlo / 100) * 100; x < zhi; x += 100) {
            ctx.strokeStyle = '#c3c2b7'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(zpx(x), my - lh / 2 - 8); ctx.lineTo(zpx(x), my - lh / 2 - 2); ctx.stroke();
            text((x / 1000).toFixed(1), zpx(x), my - lh / 2 - 24, 11, C.muted, 'center');
        }
        const len = Math.max(cfg.length * scale, 6);
        // Ramp vehicles on the approach (rotated) or in the acceleration lane.
        const drawn = Z ? (Z.frames[i] || []) : [];
        for (const [d, v] of drawn) {
            if (d < 0) continue;
            if (d <= rampLen) {
                const back = (rampLen - d) * scale, fx = jx + ux * back, fy = jy + uy * back;
                ctx.save(); ctx.translate(fx, fy); ctx.rotate(Math.atan2(-uy, -ux));
                roundRect(-len, -7, len, 14, 3, speedColor(v), C.ink, 1); ctx.restore();
            } else {
                roundRect(zpx(xs + d - rampLen) - len, ay - 8, len, 16, 3, speedColor(v), C.ink, 2);
            }
        }
        text(`Waiting to merge: ${rampQ}`, ex, ey + 16, 13, C.ink2, 'center');
        // Mainline vehicles; a ramp vehicle that merged less than lc_time ago is drawn mid lane change.
        for (const [id, x, v, , origin] of cars) {
            if (x < zlo - 10 || x > zhi + 10) continue;
            let y = my;
            const te = Z && origin === 1 ? Z.merge_t[String(id)] : undefined;
            if (te !== undefined && t - te >= 0 && t - te < Z.lc_time) {
                let f = (t - te) / Z.lc_time; f = f * f * (3 - 2 * f);
                y = ay + (my - ay) * f;
            }
            roundRect(zpx(x) - len, y - 8, len, 16, 3, speedColor(v), origin === 1 ? C.ink : C.edge, origin === 1 ? 2 : 1);
        }
    }


    // Acceleration-lane model (run 8 onward): ramp vehicles are real vehicles on lane 1 (the ramp
    // road and the acceleration lane). Positions are interpolated between the one-second records
    // so motion stays smooth (and never seems to roll backward) at any playback speed.
    function carIcon(xFront, y, len, fill, stroke, lw, angle) {
        ctx.save(); ctx.translate(xFront, y); if (angle) ctx.rotate(angle);
        const w = 9;
        roundRect(-len, -w / 2, len, w, 3, fill, stroke, lw);
        if (len >= 8) {
            const g = '#2e3440';
            roundRect(-0.24 * len - Math.max(0.17 * len, 1.6), -w / 2 + 1.3, Math.max(0.17 * len, 1.6), w - 2.6, 1, g);
            roundRect(-len + 0.13 * len, -w / 2 + 1.5, Math.max(0.1 * len, 1.2), w - 3, 1, g);
        }
        ctx.restore();
    }
    function shade(rgb) { return rgb.replace(/\d+/g, n => Math.round(n * 0.62)); }
    function interpCars(i, w) {
        const a = frames[i], b = frames[Math.min(i + 1, frames.length - 1)];
        if (!b || b === a || w <= 0) return a[1];
        const nb = new Map(b[1].map(c => [c[0], c])), na = new Map(a[1].map(c => [c[0], c]));
        const t = a[0] + w, out = [];
        const te = Z && Z.merge_t ? Z.merge_t : {};
        for (const c of a[1]) {
            const n = nb.get(c[0]);
            if (n) {
                const lane = c[3] === n[3] ? n[3] : (t >= (te[String(c[0])] ?? b[0]) ? 0 : 1);
                out.push([c[0], c[1] + (n[1] - c[1]) * w, c[2] + (n[2] - c[2]) * w, lane, c[4]]);
            } else if (c[1] + c[2] / 3.6 * w < cfg.road_end) out.push([c[0], c[1] + c[2] / 3.6 * w, c[2], c[3], c[4]]);
        }
        const xrs = cfg.merge_x - cfg.acc_length - cfg.ramp_length;
        for (const n of b[1]) {
            if (na.has(n[0])) continue;
            const x = n[1] - n[2] / 3.6 * (1 - w);
            if (x >= (n[3] === 1 ? xrs : 0)) out.push([n[0], x, n[2], n[3], n[4]]);
        }
        return out;
    }
    function drawAcc(t, cars, rampQ) {
        const L = cfg.road_end, m = cfg.merge_x, xs = m - cfg.acc_length;
        const ox0 = 40, ox1 = W - 40, oy = 96;
        const opx = x => ox0 + (ox1 - ox0) * x / L;
        const zlo = Math.max(0, xs - 350), zhi = Math.min(L, m + 100);
        const main = cars.filter(c => c[3] === 0), ramp = cars.filter(c => c[3] === 1);
        text('Whole road (color = speed of the nearest car)', ox0, 66, 12, C.ink2, 'left', 600);
        roundRect(opx(zlo), oy - 14, opx(zhi) - opx(zlo), 36, 4, null, C.accent, 1);
        ctx.lineCap = 'butt'; ctx.strokeStyle = C.road; ctx.lineWidth = 10;
        ctx.beginPath(); ctx.moveTo(ox0, oy); ctx.lineTo(ox1, oy); ctx.stroke();
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(opx(xs - cfg.ramp_length), oy + 17); ctx.lineTo(opx(xs), oy + 9); ctx.lineTo(opx(m), oy + 9); ctx.stroke();
        for (let km = 0; km <= L / 1000; km++) text(`${km} km`, opx(km * 1000), oy + 24, 11, C.muted, 'center');
        const pts = main.map(c => [c[1], c[2]]).sort((p, q) => p[0] - q[0]);
        if (pts.length) {
            const nb = Math.floor(L / 20);
            let k = 0;
            for (let b = 0; b < nb; b++) {
                const xc = (b + 0.5) * L / nb;
                while (k + 1 < pts.length && Math.abs(pts[k + 1][0] - xc) <= Math.abs(pts[k][0] - xc)) k++;
                if (Math.abs(pts[k][0] - xc) <= 150) {
                    ctx.fillStyle = speedColor(Math.min(Math.floor(pts[k][1] / 10) * 10 + 5, 120));
                    ctx.fillRect(opx(b * L / nb), oy - 5, opx((b + 1) * L / nb) - opx(b * L / nb) + 0.5, 10);
                }
            }
        }
        const zx0 = 40, zx1 = W - 40, my = 228, lh = 24, ay = my + lh;
        const sc = (zx1 - zx0) / (zhi - zlo), zpx = x => zx0 + (x - zlo) * sc;
        text(`Merge area ${(zlo / 1000).toFixed(2)}–${(zhi / 1000).toFixed(2)} km (traffic flows left to right)`, zx0, 150, 12, C.ink2, 'left', 600);
        ctx.fillStyle = C.road; ctx.fillRect(zx0, my - lh / 2, zx1 - zx0, lh);
        ctx.fillRect(zpx(xs), ay - lh / 2, zpx(m) - zpx(xs), lh);
        ctx.beginPath(); ctx.moveTo(zpx(m), ay - lh / 2); ctx.lineTo(zpx(m) + 36, ay - lh / 2); ctx.lineTo(zpx(m), ay + lh / 2); ctx.closePath(); ctx.fill();
        const ux = -0.894, uy = 0.447, jx = zpx(xs), jy = ay, rl = cfg.ramp_length * sc, ex = jx + ux * rl, ey = jy + uy * rl;
        ctx.strokeStyle = C.road; ctx.lineWidth = lh;
        ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(jx + 2, jy); ctx.stroke();
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5; ctx.setLineDash([8, 7]);
        ctx.beginPath(); ctx.moveTo(zpx(xs), my + lh / 2); ctx.lineTo(zpx(m), my + lh / 2); ctx.stroke(); ctx.setLineDash([]);
        text('ramp entrance', ex - 6, ey - 16, 11, C.muted, 'right');
        text(`acceleration lane (${Math.round(cfg.acc_length)} m)`, zpx(xs) + 4, ay + lh / 2 + 5, 11, C.accent);
        ctx.strokeStyle = C.accent; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(zpx(m), my - lh / 2 - 6); ctx.lineTo(zpx(m), ay + lh / 2 + 2); ctx.stroke();
        text('lane end', zpx(m) + 40, ay - 8, 11, C.accent);
        for (let x = Math.ceil(zlo / 100) * 100; x <= zhi; x += 100) {
            ctx.strokeStyle = '#c3c2b7'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(zpx(x), my - lh / 2 - 7); ctx.lineTo(zpx(x), my - lh / 2 - 2); ctx.stroke();
            text((x / 1000).toFixed(1), zpx(x), my - lh / 2 - 22, 11, C.muted, 'center');
        }
        let meterPx = null;
        if (typeof TMC !== 'undefined' && TMC) {
            // Detectors (loops across the mainline, drawn under the cars) and the ramp stop line.
            TMC.detectors.forEach(d => {
                const hl = TMC.alinea_x !== null && Math.abs(d - TMC.alinea_x) < 1e-6;
                const col = hl ? C.green : C.ink2;
                ctx.fillStyle = col; ctx.fillRect(opx(d) - 1.5, oy - 13, 3, 26);
                if (d >= zlo && d <= zhi) {
                    ctx.fillStyle = col; ctx.globalAlpha = 0.55;
                    ctx.fillRect(zpx(d) - 2, my - lh / 2, 4, lh); ctx.globalAlpha = 1;
                    text(`D${String(Math.round(d)).padStart(4, '0')}${hl ? ' · ALINEA' : ''}`, zpx(d), my - lh / 2 - 36, 11, col, 'center', hl ? 700 : 400);
                }
            });
            const back = (xs - TMC.meter_x) * sc, px = jx + ux * back, py = jy + uy * back;
            ctx.strokeStyle = C.ink; ctx.lineWidth = 3;
            ctx.beginPath(); ctx.moveTo(px + uy * 13, py - ux * 13); ctx.lineTo(px - uy * 13, py + ux * 13); ctx.stroke();
            meterPx = [px, py];
        }
        const CL = 17;
        // Ramp road (slanted) and acceleration lane; icons shortened to the room before the car behind.
        const rs = ramp.slice().sort((p, q) => q[1] - p[1]);
        rs.forEach((c, k) => {
            const len = Math.max(Math.min(CL, k + 1 < rs.length ? (c[1] - rs[k + 1][1]) * sc - 2 : CL), 4);
            const col = speedColor(c[2]);
            if (c[1] < xs) {
                const back = (xs - c[1]) * sc;
                carIcon(jx + ux * back, jy + uy * back, len, col, EQUIPPED.has(c[0]) ? C.accent : C.ink, EQUIPPED.has(c[0]) ? 2 : 1.5, Math.atan2(-uy, -ux));
            } else if (zpx(c[1]) - len >= zx0) carIcon(zpx(c[1]), ay, len, col, EQUIPPED.has(c[0]) ? C.accent : C.ink, EQUIPPED.has(c[0]) ? 2 : 1.5);
        });
        text(`Waiting outside ramp: ${rampQ}`, ex, ey + 16, 13, C.ink2, 'center');
        const shown = main.filter(c => c[1] >= zlo - 30 && c[1] <= zhi + 30).sort((p, q) => q[1] - p[1]);
        shown.forEach((c, k) => {
            const front = zpx(c[1]);
            const len = Math.max(Math.min(CL, k + 1 < shown.length ? front - zpx(shown[k + 1][1]) - 2 : CL), 4);
            if (front - len < zx0 || front > zx1) return;
            let y = my;
            const te = Z && c[4] === 1 ? Z.merge_t[String(c[0])] : undefined;
            if (te !== undefined && t - te >= 0 && t - te < Z.lc_time) {
                let f = (t - te) / Z.lc_time; f = f * f * (3 - 2 * f); y = ay + (my - ay) * f;
            }
            const col = speedColor(c[2]);
            if (EQUIPPED.has(c[0])) carIcon(front, y, len, col, C.accent, 2);
            else carIcon(front, y, len, col, c[4] === 1 ? C.ink : shade(col), c[4] === 1 ? 1.5 : 1);
        });
        if (meterPx) {
            // Ramp signal (green just after a release, or resting green at the maximum rate) and rate.
            let k = 0; while (k + 1 < TMC.times.length && TMC.times[k + 1] <= t + 1e-9) k++;
            let j = -1, lo = 0, hi = TMC.releases.length - 1;
            while (lo <= hi) { const mid = (lo + hi) >> 1; if (TMC.releases[mid] <= t + 1e-9) { j = mid; lo = mid + 1; } else hi = mid - 1; }
            const rest = TMC.rest !== null && TMC.rates[k] >= TMC.rest - 1e-9;
            const green = rest || (j >= 0 && t - TMC.releases[j] < 1.5);
            const [px, py] = meterPx;
            roundRect(px - 24, py + 20, 18, 18, 4, C.ink);
            ctx.fillStyle = green ? C.green : C.red; ctx.beginPath(); ctx.arc(px - 15, py + 29, 6, 0, 2 * Math.PI); ctx.fill();
            const names = { alinea: 'ALINEA', hold: 'hold (report missing)', fallback: 'fallback (no data)', override: 'queue override', fixed: 'fixed rate' };
            text(`Ramp meter: ${Math.round(TMC.rates[k])} veh/h`, jx + 8, jy + 40, 14, C.green, 'left', 700);
            text(`mode: ${names[TMC.modes[k]] || TMC.modes[k]}${rest ? ', resting green' : ''}`, jx + 8, jy + 60, 12, C.ink2);
        }
    }

    function draw() {
        if (!frames.length) { text('No recorded frames.', 20, 20); return; }
        const i = Math.min(frames.length - 1, Math.floor(sim));
        let [t, cars, mainExt, rampExt] = frames[i];
        if (cfg.acc_length) { const w = Math.min(Math.max(sim - i, 0), 1); cars = interpCars(i, w); t = t + w; }
        slider.max = frames.length - 1; slider.value = i;
        clock.textContent = `${mmss(t)} / ${mmss(tEnd)}`;
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = C.surface; ctx.fillRect(0, 0, W, H);

        // ---- Header line --------------------------------------------------
        const demand = t < cfg.demand_end;
        text(mmss(t), 24, 16, 30, C.ink, 'left', 700);
        const empty = !cars.length && !mainExt && !rampExt && !demand;
        text(demand ? 'Demand active' : empty ? `Network empty (run continues to ${Math.round(cfg.duration / 60)} min)` : 'Demand ended, clearing',
             130, 28, 14, demand ? C.accent : C.muted);

        if (cfg.acc_length) drawAcc(t, cars, rampExt);
        else if (cfg.zone_length) drawZone(i, t, cars, rampExt);
        else if (cfg.merge_x !== undefined) drawPoint(t, cars, rampExt); else drawLane(t, cars);

        // ---- Counters ------------------------------------------------------
        const onMain = cars.filter(c => c[3] === 0).length, onRamp = cars.length - onMain;
        const cnt = counters[i] || [null, null];
        const tiles = cfg.merge_x !== undefined
            ? [['On mainline', onMain], ['Slower than 30 km/h', cars.filter(c => c[3] === 0 && c[2] < 30).length],
               ...(cfg.acc_length ? [['On ramp', onRamp], ['Waiting outside ramp', rampExt]]
                   : [[cfg.zone_length ? 'Waiting to merge' : `Ramp queue (storage ${cfg.ramp_storage})`, rampExt], ['Mainline entry queue', mainExt]]),
               ['Merges so far', cnt[0] ?? '–'], ['Exited so far', cnt[1] ?? '–']]
            : [['On mainline', onMain], ['On ramp', `${onRamp} / ${cfg.ramp_storage}`],
               ['Ramp queue (outside)', rampExt], ['Mainline queue (outside)', mainExt],
               ['Merges so far', cnt[0] ?? '–'], ['Exited so far', cnt[1] ?? '–']];
        const tw = (W - 48 - 10 * (tiles.length - 1)) / tiles.length;
        tiles.forEach(([label, value], k) => {
            const x = 24 + k * (tw + 10);
            roundRect(x, 430, tw, 62, 8, '#ffffff', C.grid, 1);
            text(label, x + 12, 440, 12);
            text(String(value), x + 12, 458, 22, C.ink, 'left', 700);
        });

        // ---- Legend and time bar --------------------------------------------
        text('Speed', 24, 508, 12, C.ink2, 'left', 600);
        for (let k = 0; k < 160; k++) { ctx.fillStyle = speedColor(120 * k / 159); ctx.fillRect(70 + k, 509, 1.2, 11); }
        text('0', 70, 523, 11, C.muted); text('120 km/h', 230, 523, 11, C.muted, 'right');
        roundRect(260, 508, 18, 13, 3, speedColor(110), C.edge, 1); text('mainline origin', 284, 507, 12);
        roundRect(390, 508, 18, 13, 3, speedColor(110), C.ink, 2); text('ramp origin', 414, 507, 12);
        const bx0 = 520, bx1 = W - 24, by = 512, frac = x => bx0 + (bx1 - bx0) * Math.min(1, x / tEnd);
        roundRect(bx0, by, bx1 - bx0, 6, 3, C.grid);
        roundRect(bx0, by, frac(cfg.demand_end) - bx0, 6, 3, '#c6d9f1');
        roundRect(bx0, by, Math.max(6, frac(t) - bx0), 6, 3, C.accent);
        text('demand period', bx0, by + 10, 11, C.muted);
        text(mmss(tEnd), bx1, by + 10, 11, C.muted, 'right');
    }

    function toggle() {
        if (sim >= frames.length - 1) sim = 0;
        playing = !playing;
        button.textContent = playing ? 'Pause' : 'Play';
    }
    function jump(seconds) { sim = Math.max(0, Math.min(frames.length - 1, sim + seconds)); draw(); }
    button.onclick = toggle;
    document.getElementById('back').onclick = () => jump(-10);
    document.getElementById('fwd').onclick = () => jump(10);
    slider.oninput = () => { sim = Number(slider.value); draw(); };
    document.addEventListener('keydown', e => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        if (e.code === 'Space') { e.preventDefault(); toggle(); }
        if (e.code === 'ArrowLeft') jump(-10);
        if (e.code === 'ArrowRight') jump(10);
    });
    function tick(ts) {
        if (playing && last !== null) {
            sim += (ts - last) / 1000 * Number(document.getElementById('speed').value);
            if (sim >= frames.length - 1) { sim = frames.length - 1; playing = false; button.textContent = 'Play'; }
            draw();
        }
        last = ts;
        requestAnimationFrame(tick);
    }
    resize();
    window.addEventListener('resize', () => { resize(); draw(); });
    draw();
    requestAnimationFrame(tick);
})();
