"""Placement and routing plan for the V3 turnstile feed (pure geometry, board-centred mm, KiCad y down).

Three MHC0410L03 hybrids sit on the board diagonals with their output side facing out. Every corner is 45 degrees.
UHF_A carries the quarter-wave delay as a one-sided serpentine east of centre; its run length is solved so that
len(UHF_A) - len(UHF_B) is exactly a quarter guided wavelength.
Sense: the feed phase lags north, east, south, west, which is clockwise seen from F.Cu (the inner face) and
counter-clockwise seen from B.Cu (the outer face with the USB ports): right-hand circular out of the outer face.
"""
import math

F_MHZ = 437.0
E_EFF = 3.32  # JLC04161H-7628, 0.3424 mm trace over 0.2104 mm prepreg, 0.4 mm coplanar gap (RF review 2026-11-14)
QUARTER = 299792.458 / F_MHZ / math.sqrt(E_EFF) / 4  # mm
WIDTH = 0.3424

# centre, KiCad orientation. Centres are chosen so the four element feeds come out the same length.
HYBRIDS = {"U301": ((19.215, 19.349), 225), "U302": ((19.215, -19.349), 135), "U303": ((-19.444, 19.444), 315)}
ELEMENTS = {"AE1": (26.5, 0.0), "AE2": (-0.002, -26.955), "AE3": (-26.5, 0.0), "AE4": (0.0, 26.5)}  # pad centres, from the turnstile
RF1_OUT = 3.1  # MMCX centre this far along x and y from U301 pin 2
RF1_ROT = 45


def leg(ref, pin, which):
    """Point 0.3 mm inside the end of a terminal leg and the unit direction a track leaves it in. which: 'v' (long side) or 'h' (short side)."""
    (cx, cy), rot = HYBRIDS[ref]
    sx, sy = {"1": (-1, -1), "2": (1, -1), "3": (1, 1), "4": (-1, 1)}[pin]
    lx, ly, dx, dy = (sx * 5.01, sy * 4.245, 0, sy) if which == "v" else (sx * 6.91, sy * 2.345, sx, 0)  # 0.3 mm inside the land
    a = math.radians(rot)
    r = lambda x, y: (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))
    px, py = r(lx, ly)
    return (cx + px, cy + py), r(dx, dy)


def go(p, d, n):
    return (p[0] + d[0] * n, p[1] + d[1] * n)


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def chamfer(pts, c=0.6):
    """Replace each 90 degree corner with a 45 degree chamfer of leg c."""
    out = [pts[0]]
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        u = ((b[0] - a[0]), (b[1] - a[1]))
        w = ((d[0] - b[0]), (d[1] - b[1]))
        lu, lw = math.hypot(*u), math.hypot(*w)
        if abs(u[0] * w[0] + u[1] * w[1]) < 1e-6 * lu * lw:
            out += [(b[0] - u[0] / lu * c, b[1] - u[1] / lu * c), (b[0] + w[0] / lw * c, b[1] + w[1] / lw * c)]
        else:
            out.append(b)
    out.append(pts[-1])
    return out


def element_feed(ref, pin, el, axis):
    """Out of the short-side leg on its diagonal, then straight along one axis to the element pad centre."""
    p, d = leg(ref, pin, "h")
    ex, ey = ELEMENTS[el]
    n = abs(ex - p[0]) if axis == "y" else abs(ey - p[1])
    q = go(p, d, n * math.sqrt(2))
    assert abs((q[0] - ex) if axis == "y" else (q[1] - ey)) < 1e-6, (ref, pin, q)
    return [p, q, (ex, ey)]


def uhf_b():
    """U301 pin 3 straight west to U303 pin 2."""
    p, d = leg("U301", "3", "v")
    e, de = leg("U303", "2", "v")
    s = 0.7
    a = go(p, d, s * math.sqrt(2))
    f = go(e, de, (e[1] - a[1]) * math.sqrt(2))
    return [p, a, f, e]


def uhf_a(target):
    """U301 pin 4 north through the serpentine, out of its west end, north again and into U302 pin 2."""
    p, d = leg("U301", "4", "v")
    e, de = leg("U302", "2", "v")
    a = go(p, d, 0.5 * math.sqrt(2))
    x0, runs, pitch, y0 = a[0], 7, 2.0, 11.0  # odd, so the last run ends at the west end; clear of R302 to the north
    ys = [y0 - i * pitch for i in range(runs)]

    def path(h):
        pts = [p, a]
        for i, y in enumerate(ys):
            pts += [(x0, y), (x0 - h, y)] if i % 2 == 0 else [(x0 - h, y), (x0, y)]
        k = e[0] - (x0 - h)
        return chamfer(pts + [go(e, de, k * math.sqrt(2)), e])

    lo, hi = 2.0, 16.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if length(path(mid)) < target else (lo, mid)
    return path((lo + hi) / 2)


def term(ref, pin):
    """Short diagonal from the isolated port towards its load: (track points, unit direction). The track ends on pad 1."""
    p, d = leg(ref, pin, "v")
    return [p, go(p, d, 2.0)], d


def plan():
    b = uhf_b()
    nets = {
        "/RF/UHF_B": b,
        "/RF/UHF_A": uhf_a(length(b) + QUARTER),
        "/RF/UHF_0": element_feed("U302", "3", "AE2", "x"),
        "/RF/UHF_90": element_feed("U302", "4", "AE1", "y"),
        "/RF/UHF_180": element_feed("U303", "3", "AE4", "x"),
        "/RF/UHF_270": element_feed("U303", "4", "AE3", "y"),
    }
    p, d = leg("U301", "2", "v")
    nets["/UHF"] = [p, go(p, d, RF1_OUT * math.sqrt(2))]
    return nets


LOADS = {"R301": ("U301", "1"), "R302": ("U302", "1"), "R303": ("U303", "1")}

if __name__ == "__main__":
    for n, pts in plan().items():
        print(f"{n:13s} {length(pts):8.3f} mm  {len(pts) - 1} segments")
    n = plan()
    print(f"quarter wave {QUARTER:.3f} mm, A - B = {length(n['/RF/UHF_A']) - length(n['/RF/UHF_B']):.3f} mm")
    print("leg U301.2", leg("U301", "2", "v"))
