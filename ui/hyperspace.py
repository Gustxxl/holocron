import curses
import locale
import math
import random
import time

from ui.interface import haptic

FPS = 30
STARS = 220
ASPECT = 2.0
DEPTH = 26.0
RING_FREQ = 0.55
RING_SPEED = 1.3
STRIPES = 6.0
SWIRL = 0.15
RAMP = ' .·:-=+*x#%@'
MIN_W, MIN_H = 40, 12
TIMING = {'cruise': 0.6, 'charge': 1.8, 'entry': 1.2, 'exit': 0.7}
NEXT = {'cruise': 'charge', 'charge': 'entry', 'entry': 'tunnel'}


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _lerp(a, b, t):
    return a + (b - a) * t


def _ein(t):
    return t * t


def _eout(t):
    return 1.0 - (1.0 - t) * (1.0 - t)


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _bell(x, c, width):
    d = (x - c) / width
    return math.exp(-d * d)


def _level(b):
    return 3 if b > 0.85 else 2 if b > 0.62 else 1 if b > 0.40 else 0


def _palette():
    try:
        curses.start_color()
        curses.use_default_colors()
        for i, c in enumerate((curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_WHITE), 1):
            curses.init_pair(i, c, -1)
        p = curses.color_pair
        return p(1), p(2), p(2) | curses.A_BOLD, p(3) | curses.A_BOLD
    except curses.error:
        return curses.A_DIM, curses.A_NORMAL, curses.A_BOLD, curses.A_BOLD


def _tunnel(w, h, cx, cy):
    maxr = min(w, h * ASPECT) * 0.5
    glow = maxr * 0.16
    cells = []
    for y in range(h - 1):
        for x in range(w):
            dx, dy = x - cx, (y - cy) * ASPECT
            r = math.hypot(dx, dy) or 0.0001
            cells.append((y, x, DEPTH / r, math.atan2(dy, dx) * STRIPES,
                          _clamp(r / maxr), math.exp(-(r * r) / (2 * glow * glow))))
    return cells


class _Star:
    __slots__ = ('a', 'r', 'speed', 'light')

    def __init__(self):
        self.spawn(True)

    def spawn(self, spread=False):
        self.a = random.uniform(0.0, math.tau)
        self.r = random.uniform(0.02, 1.35) if spread else random.uniform(0.02, 0.06)
        self.speed = random.uniform(0.75, 1.25)
        self.light = random.uniform(0.45, 1.0)


class _Screen:
    def __init__(self, scr):
        self.scr = scr
        self.attrs = _palette()
        self.resize()

    def resize(self):
        self.h, self.w = self.scr.getmaxyx()
        self.cx, self.cy = self.w / 2.0, self.h / 2.0
        self.rx, self.ry = self.w * 0.55, self.h * 0.55
        self.cells = _tunnel(self.w, self.h, self.cx, self.cy)

    def put(self, y, x, ch, attr):
        if 0 <= x < self.w and 0 <= y < self.h - 1:
            try:
                self.scr.addstr(int(y), int(x), ch, attr)
            except curses.error:
                pass


def _line(s, x0, y0, x1, y1, ch, attr):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        s.put(y0, x0, ch, attr)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_tunnel(s, depth, swirl, mix):
    sin, attrs = math.sin, s.attrs
    for y, x, d, spoke, shade, glow in s.cells:
        val = 0.5 + 0.5 * (0.6 * sin(d * RING_FREQ + depth * RING_SPEED) + 0.5 * sin(spoke + swirl)) / 1.1
        b = _clamp((val * shade + glow * 0.85) * mix)
        if b >= 0.10:
            s.put(y, x, RAMP[int(min(b, 0.999) * len(RAMP))], attrs[_level(b)])


def _draw_stars(s, stars, warp, streak, alpha, dt):
    for st in stars:
        r0 = st.r
        st.r += (0.12 + st.r) * warp * st.speed * 1.8 * dt
        if st.r > 1.35:
            st.spawn()
            continue
        back = min(max(0.0, st.r - streak * st.speed), r0)
        ca, sa = math.cos(st.a), math.sin(st.a)
        x1, y1 = round(s.cx + ca * st.r * s.rx), round(s.cy + sa * st.r * s.ry)
        x0, y0 = round(s.cx + ca * back * s.rx), round(s.cy + sa * back * s.ry)
        b = _clamp((min(st.r, 1.0) * st.light + warp * 0.15) * alpha)
        if b < 0.06:
            continue
        if streak > 0.02 and abs(x1 - x0) + abs(y1 - y0) >= 2:
            tail = '·' if b < 0.4 else ':' if b < 0.7 else '+'
            _line(s, x0, y0, x1, y1, tail, s.attrs[1 if b > 0.6 else 0])
        head = '+' if b < 0.4 else '*' if b < 0.7 else '#' if b < 0.9 else '@'
        s.put(y1, x1, head, s.attrs[_level(b)])


def _bloom(s, radius, power):
    if power <= 0.04 or radius < 1:
        return
    r = int(radius)
    for dy in range(-r, r + 1):
        for dx in range(-2 * r, 2 * r + 1):
            dist = math.hypot(dx * 0.5, dy) / r
            v = (1.0 - dist) * power
            if dist > 1.0 or v < 0.12:
                continue
            ch = '@' if v > 0.85 else '#' if v > 0.6 else '+' if v > 0.38 else ':' if v > 0.22 else '·'
            s.put(s.cy + dy, s.cx + dx, ch, s.attrs[3 if v > 0.6 else 2 if v > 0.38 else 1 if v > 0.22 else 0])


def _too_small(s):
    s.scr.erase()
    msg = 'Make the window larger.'[:max(0, s.w - 1)]
    try:
        s.scr.addstr(s.h // 2, max(0, (s.w - len(msg)) // 2), msg, curses.A_DIM)
    except curses.error:
        pass
    s.scr.refresh()
    time.sleep(1.0 / FPS)


def _state(phase, p, t, start):
    if phase == 'cruise':
        return 0.06, 0.006, 0.0, 0.0
    if phase == 'charge':
        return _lerp(0.06, 0.22, _smooth(p)), _lerp(0.006, 0.10, _ein(p)), 0.0, 0.0
    if phase == 'entry':
        return (_lerp(0.22, 0.70, _eout(p)), _lerp(0.10, 0.45, _eout(p)),
                _ein(_clamp((p - 0.4) / 0.6)), 0.55 * _bell(p, 0.5, 0.13))
    if phase == 'tunnel':
        return 0.42 + 0.05 * math.sin(t * 0.8), 0.42, 1.0, 0.0
    warp, streak, mix = start
    return (_lerp(warp, 0.03, _eout(_clamp(p / 0.30))),
            _lerp(streak, 0.015, _eout(_clamp(p / 0.22))),
            _lerp(mix, 0.0, _eout(_clamp(p / 0.32))),
            max(mix, 0.3) * _bell(p, 0.34, 0.09))


def _run(scr):
    curses.curs_set(0)
    curses.flushinp()
    scr.nodelay(True)
    s = _Screen(scr)
    stars = [_Star() for _ in range(STARS)]
    phase, t, start, jumped = 'cruise', 0.0, None, False
    state = _state(phase, 0.0, 0.0, None)
    depth = swirl = 0.0
    last = time.monotonic()
    while True:
        key = scr.getch()
        if (s.h, s.w) != scr.getmaxyx():
            s.resize()
        if s.w < MIN_W or s.h < MIN_H:
            if key not in (-1, curses.KEY_RESIZE):
                return
            _too_small(s)
            last = time.monotonic()
            continue
        if key not in (-1, curses.KEY_RESIZE) and phase != 'exit':
            phase, t, start = 'exit', 0.0, state[:3]
            haptic('click')
        now = time.monotonic()
        dt, last = min(0.05, now - last), now
        t += dt
        if phase in NEXT and t >= TIMING[phase]:
            phase, t = NEXT[phase], 0.0
        if phase == 'exit' and t >= TIMING['exit']:
            return
        p = _clamp(t / TIMING.get(phase, 1.0))
        state = _state(phase, p, t, start)
        warp, streak, mix, flash = state
        if phase == 'entry' and p >= 0.5 and not jumped:
            jumped = True
            haptic('click')
        depth += warp * 1.3 * dt
        swirl += SWIRL * dt

        scr.erase()
        if mix > 0.02:
            _draw_tunnel(s, depth, swirl, mix)
        if mix < 0.98:
            _draw_stars(s, stars, warp, streak, 1.0 - mix, dt)
        if flash > 0.04:
            grow = 0.06 + 0.10 * p if phase == 'entry' else 0.05 + 0.24 * _eout(_clamp(p / 0.45))
            _bloom(s, min(s.w, s.h) * grow, flash)
        if phase == 'tunnel':
            try:
                scr.addstr(s.h - 1, 2, '[any key] return'[:max(0, s.w - 3)], curses.A_DIM)
            except curses.error:
                pass
        scr.refresh()
        time.sleep(max(0.0, 1.0 / FPS - (time.monotonic() - now)))


def hyperspace():
    locale.setlocale(locale.LC_ALL, '')
    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
