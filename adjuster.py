"""adjuster.py - নির্দিষ্ট ক্ষেত্রফল ঠিক রেখে পাশের বাহু অ্যাডজাস্ট করার ইঞ্জিন।"""
import math

from geometry import SQFT_PER_SHATAK, dist, polygon_area, divide_polygon_directional


# ==========================================
# 1b. Adjustable Cut Engine (fixed area, adjustable adjacent sides)
# ==========================================
class AdjustableCut:
    """
    বন্টনকৃত প্লটের শুরুর বাহু (Start Side) সংলগ্ন দুই বাহুর (A ও B) কাটা অংশের দৈর্ঘ্য
    কম-বেশি করলেও প্লটের ক্ষেত্রফল (target) একই থাকে।
    A বা B এর একটির মান দিলে অপরটি স্বয়ংক্রিয়ভাবে হিসাব হয়।
    প্লট = [a0, Qa, Qb, b0]  (Qa: A বাহুর উপর a0 থেকে x দূরত্বে, Qb: B বাহুর উপর b0 থেকে y দূরত্বে)
    """
    EPS = 1e-6

    def __init__(self, pts, direction, target_area):
        self.pts = pts
        self.direction = direction
        self.target = float(target_area)
        self.is_vertical = direction in ("West to East", "East to West")

        if self.is_vertical:
            # কাটা হয় Side 1 (P1-P2) ও Side 3 (P4-P3) এর উপর
            cands = [
                ((0, 1, 3, 2), (pts[0][0] + pts[3][0]) / 2.0),  # শুরুর বাহু P1-P4 (পশ্চিম দিক)
                ((1, 0, 2, 3), (pts[1][0] + pts[2][0]) / 2.0),  # শুরুর বাহু P2-P3 (পূর্ব দিক)
            ]
            pick_low = (direction == "West to East")
            self.pos_a, self.pos_b = "bottom", "top"
            self.side_a_no, self.side_b_no = 1, 3
        else:
            # কাটা হয় Side 4 (P4-P1) ও Side 2 (P3-P2) এর উপর
            cands = [
                ((0, 3, 1, 2), (pts[0][1] + pts[1][1]) / 2.0),  # শুরুর বাহু P1-P2
                ((3, 0, 2, 1), (pts[3][1] + pts[2][1]) / 2.0),  # শুরুর বাহু P4-P3
            ]
            pick_low = (direction == "South to North")
            self.pos_a, self.pos_b = "left", "right"
            self.side_a_no, self.side_b_no = 4, 2

        chooser = min if pick_low else max
        idxs = chooser(cands, key=lambda c: c[1])[0]
        self.ia0, self.ia1, self.ib0, self.ib1 = idxs
        self.a0, self.a1 = pts[self.ia0], pts[self.ia1]
        self.b0, self.b1 = pts[self.ib0], pts[self.ib1]
        self.La = dist(self.a0, self.a1)
        self.Lb = dist(self.b0, self.b1)

        self.range_a = self._calc_range("a")
        self.range_b = self._calc_range("b")
        self.ok = (
            self.target > 0
            and self.range_a[0] <= self.range_a[1] + 1e-9
            and self.range_b[0] <= self.range_b[1] + 1e-9
        )

    # ---- basic geometry ----
    @staticmethod
    def _lerp(p0, p1, t):
        return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)

    def point_a(self, x):
        return self._lerp(self.a0, self.a1, x / self.La if self.La > 0 else 0.0)

    def point_b(self, y):
        return self._lerp(self.b0, self.b1, y / self.Lb if self.Lb > 0 else 0.0)

    def poly(self, x, y):
        return [self.a0, self.point_a(x), self.point_b(y), self.b0]

    def area(self, x, y):
        return polygon_area(self.poly(x, y))

    def _area_of(self, which, v, other):
        return self.area(v, other) if which == "a" else self.area(other, v)

    @staticmethod
    def _bisect(fn, target, lo, hi):
        for _ in range(90):
            mid = (lo + hi) / 2.0
            if fn(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    # ---- feasible range & solving ----
    def _calc_range(self, which):
        T = self.target
        L = self.La if which == "a" else self.Lb
        L_other = self.Lb if which == "a" else self.La

        # সর্বনিম্ন মান: অপর বাহু সর্বোচ্চ ধরলেও ক্ষেত্রফল T এর কম হলে চলবে না
        if self._area_of(which, 0.0, L_other) >= T - self.EPS:
            lo = 0.0
        else:
            lo = self._bisect(lambda v: self._area_of(which, v, L_other), T, 0.0, L)

        # সর্বোচ্চ মান: অপর বাহু ০ ধরলেও ক্ষেত্রফল T এর বেশি হলে চলবে না
        if self._area_of(which, L, 0.0) <= T + self.EPS:
            hi = L
        else:
            hi = self._bisect(lambda v: self._area_of(which, v, 0.0), T, 0.0, L)
        return lo, hi

    def solve(self, which, v):
        """which = 'a' বা 'b' এর মান v দিলে অপর বাহুর মান বের করে (ক্ষেত্রফল ঠিক রেখে)।"""
        T = self.target
        L_other = self.Lb if which == "a" else self.La
        if self._area_of(which, v, 0.0) > T + self.EPS:
            return None
        if self._area_of(which, v, L_other) < T - self.EPS:
            return None
        return self._bisect(lambda o: self._area_of(which, v, o), T, 0.0, L_other)

    def default_from_line(self, line_v):
        """সরল (straight) বন্টন রেখা থেকে A ও B এর প্রাথমিক মান।"""
        idx = 0 if self.is_vertical else 1
        d = self.a1[idx] - self.a0[idx]
        t = 0.0 if abs(d) < 1e-9 else (line_v - self.a0[idx]) / d
        x = min(1.0, max(0.0, t)) * self.La
        lo, hi = self.range_a
        x = min(hi, max(lo, x))
        y = self.solve("a", x)
        return x, y

    def default_parallel(self):
        """শুরুর বাহু (a0-b0) এর সমান্তরাল রেখা দিয়ে কাটলে A ও B এর প্রাথমিক মান।
        শুরুর বাহু থেকে লম্ব-দূরত্ব h এর রেখা A ও B কে x = h/na, y = h/nb দূরত্বে কাটে;
        h এমনভাবে বের করা হয় যাতে ক্ষেত্রফল ঠিক target হয়। সম্ভব না হলে None।"""
        dx, dy = self.b0[0] - self.a0[0], self.b0[1] - self.a0[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-9 or self.La < 1e-9 or self.Lb < 1e-9:
            return None
        nx, ny = -dy / ln, dx / ln
        ax, ay = self.a1[0] - self.a0[0], self.a1[1] - self.a0[1]
        if nx * ax + ny * ay < 0:
            nx, ny = -nx, -ny
        na = (nx * ax + ny * ay) / self.La
        nb = (nx * (self.b1[0] - self.b0[0]) + ny * (self.b1[1] - self.b0[1])) / self.Lb
        if na < 1e-6 or nb < 1e-6:
            return None
        h_max = min(self.La * na, self.Lb * nb)
        if self.area(h_max / na, h_max / nb) >= self.target - self.EPS:
            # সমান্তরাল রেখা এখনও A ও B দুই বাহুর ভেতরেই থাকে
            h = self._bisect(lambda hh: self.area(hh / na, hh / nb), self.target, 0.0, h_max)
            return h / na, h / nb
        # সমান্তরাল রেখা একটি বাহুর শেষ কোণে পৌঁছে গেছে: ঐ কোণকে কেন্দ্র করে রেখা ঘোরে (fan),
        # ফলে রেখাগুলো কখনো একে অপরকে কাটে না।
        if self.Lb * nb <= self.La * na:
            x = self.solve("b", self.Lb)
            return (x, self.Lb) if x is not None else None
        y = self.solve("a", self.La)
        return (self.La, y) if y is not None else None

    # ---- result for drawing / report ----
    def geometry(self, x, y):
        qa, qb = self.point_a(x), self.point_b(y)
        sub_edges = []
        for p0, pq, p1, pos in ((self.a0, qa, self.a1, self.pos_a), (self.b0, qb, self.b1, self.pos_b)):
            if dist(p0, pq) > 0.01:
                sub_edges.append((p0, pq, pos))
            if dist(pq, p1) > 0.01:
                sub_edges.append((pq, p1, pos))
        return {
            "qa": qa, "qb": qb,
            "partition_segments": [(qa, qb)],
            "sub_edge_segments": sub_edges,
            "cut_len": dist(qa, qb),
            "start_len": dist(self.a0, self.b0),
            "area": self.area(x, y),
        }



class MultiCutAdjuster:
    """
    একাধিক বন্টন রেখা (cut) একসাথে পরিচালনা করে।
    প্রতিটি cut-এর ক্ষেত্রফল (শুরুর বাহু থেকে ক্রমযোগ) ঠিক থাকে, তাই
    একটি cut কম-বেশি করলেও সব প্লটের ক্ষেত্রফল অপরিবর্তিত থাকে।
    পাশের cut এর সাথে যেন ক্রস না করে, সেজন্য রেঞ্জ প্রতিবেশী cut দিয়ে সীমাবদ্ধ।
    """

    def __init__(self, pts, direction, targets):
        self.pts = pts
        self.direction = direction
        self.total_area = polygon_area(pts)
        self.cuts = [AdjustableCut(pts, direction, t) for t in targets]
        self.n = len(self.cuts)
        c0 = self.cuts[0]
        self.c0 = c0
        self.is_vertical = c0.is_vertical
        self.La, self.Lb = c0.La, c0.Lb
        self.ok = self.n > 0 and all(c.ok for c in self.cuts)
        self.xy = []
        self.parallel = False

    def init_from_lines(self, div_lines, parallel=False):
        self.xy = []
        self.parallel = parallel
        if len(div_lines) != self.n:
            return False
        for c, v in zip(self.cuts, div_lines):
            res = c.default_parallel() if parallel else None
            if res is None:
                res = c.default_from_line(v)
            x, y = res
            if y is None:
                return False
            self.xy.append([x, y])
        return True

    def neighbors(self, k):
        lo = tuple(self.xy[k - 1]) if k > 0 else (0.0, 0.0)
        hi = tuple(self.xy[k + 1]) if k < self.n - 1 else (self.La, self.Lb)
        return lo, hi

    def bounds(self, k, which):
        c = self.cuts[k]
        (xl, yl), (xu, yu) = self.neighbors(k)
        ra, rb = c.range_a, c.range_b

        def clamp(v, r):
            return min(r[1], max(r[0], v))

        if which == "a":
            lo, hi = max(ra[0], xl), min(ra[1], xu)
            t = c.solve("b", clamp(yu, rb))
            if t is not None:
                lo = max(lo, t)
            t = c.solve("b", clamp(yl, rb))
            if t is not None:
                hi = min(hi, t)
        else:
            lo, hi = max(rb[0], yl), min(rb[1], yu)
            t = c.solve("a", clamp(xu, ra))
            if t is not None:
                lo = max(lo, t)
            t = c.solve("a", clamp(xl, ra))
            if t is not None:
                hi = min(hi, t)
        if lo > hi:
            lo = hi = (lo + hi) / 2.0
        return lo, hi

    def plot_areas_now(self):
        T = [c.target for c in self.cuts]
        edges = [0.0] + T + [self.total_area]
        return [edges[i + 1] - edges[i] for i in range(self.n + 1)]

    def set_plot_area(self, i, new_area, min_area=1.0):
        """i নম্বর প্লটের ক্ষেত্রফল new_area করে।
        - শেষ প্লটের আগের যেকোনো প্লট বদলালে তার পরের সব রেখা সমান পরিমাণ সরে যায়; তাই
          মাঝের প্লটগুলোর ক্ষেত্রফল ঠিক থাকে এবং কম-বেশি হয় শেষের অবশিষ্ট জমি (Remaining) থেকে।
        - শেষ প্লট বদলালে তার আগের প্লট (Plot n) বাকি পরিবর্তন শুষে নেয়।
        ফেরত: (ok, message)"""
        n = self.n
        areas = self.plot_areas_now()
        T = [c.target for c in self.cuts]
        if i < n:
            shift = list(range(i, n))
            delta = new_area - areas[i]
            a_hi = areas[i] + areas[n] - min_area
        else:
            shift = [n - 1]
            delta = (self.total_area - new_area) - T[n - 1]
            a_hi = areas[n] + areas[n - 1] - min_area
        newT = list(T)
        for j in shift:
            newT[j] = T[j] + delta
        edges = [0.0] + newT + [self.total_area]
        if new_area < min_area - 1e-6 or any(edges[m + 1] - edges[m] < min_area - 1e-6 for m in range(n + 1)):
            who = "remaining land" if i < n else f"Plot {n}"
            return False, (f"Plot {i + 1} area must be between {min_area:.2f} and {a_hi:.2f} sq.ft "
                           f"({min_area / SQFT_PER_SHATAK:.2f} to {a_hi / SQFT_PER_SHATAK:.2f} Shatak), "
                           f"because the {who} must stay at least {min_area:.0f} sq.ft.")

        saved = {j: (self.cuts[j].target, self.cuts[j].range_a, self.cuts[j].range_b, list(self.xy[j]))
                 for j in shift}

        def restore():
            for j, (t, ra, rb, xy) in saved.items():
                self.cuts[j].target, self.cuts[j].range_a, self.cuts[j].range_b = t, ra, rb
                self.xy[j] = xy

        order = sorted(shift, reverse=(delta > 0))   # বাড়লে শেষ রেখা আগে সরাই, কমলে প্রথমটা আগে
        for j in order:
            c = self.cuts[j]
            c.target = newT[j]
            c.range_a = c._calc_range("a")
            c.range_b = c._calc_range("b")
            lines = divide_polygon_directional(self.pts, 1, newT[j], self.direction)[0]
            if not lines:
                restore()
                return False, "This area is not possible."
            res = c.default_parallel() if getattr(self, "parallel", False) else None
            x, y = res if res is not None else c.default_from_line(lines[0])
            if y is None:
                restore()
                return False, "This area is not possible for this plot shape."
            self.xy[j] = [x, y]
            lo, hi = self.bounds(j, "a")
            x2 = min(hi, max(lo, x))
            if abs(x2 - x) > 1e-9:
                y2 = c.solve("a", x2)
                if y2 is None:
                    restore()
                    return False, "This area is not possible without overlapping the neighbouring plot."
                self.xy[j] = [x2, y2]
        return True, ""

    def geometry(self):
        c0 = self.c0
        qas = [c.point_a(x) for c, (x, y) in zip(self.cuts, self.xy)]
        qbs = [c.point_b(y) for c, (x, y) in zip(self.cuts, self.xy)]
        part_segs = list(zip(qas, qbs))

        sub = []
        for mids, p0, p1, pos in ((qas, c0.a0, c0.a1, c0.pos_a), (qbs, c0.b0, c0.b1, c0.pos_b)):
            chain = [p0] + mids + [p1]
            for u, v in zip(chain, chain[1:]):
                if dist(u, v) > 0.01:
                    sub.append((u, v, pos))

        ca = [c0.a0] + qas + [c0.a1]
        cb = [c0.b0] + qbs + [c0.b1]
        polys = [[ca[i], ca[i + 1], cb[i + 1], cb[i]] for i in range(self.n + 1)]
        plot_areas = [polygon_area(p) for p in polys]

        return {
            "partition_segments": part_segs,
            "sub_edge_segments": sub,
            "plot_polys": polys,
            "plot_areas": plot_areas,
            "cut_lens": [dist(p, q) for p, q in part_segs],
            "start_len": dist(c0.a0, c0.b0),
        }


