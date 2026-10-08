"""geometry.py - জ্যামিতি ও বন্টনের হিসাব (কোনো Kivy লাগে না)।
বাহু থেকে জমি আঁকা, ক্ষেত্রফল, রেখা কাটা ও দিক অনুযায়ী বন্টন।"""
import math

SQFT_PER_SHATAK = 435.6
MAX_PLOTS = 40  # একবারে সর্বোচ্চ প্লট সংখ্যা (হ্যাং এড়াতে)

# বাহুর দিক-ভিত্তিক নাম (ডায়াগ্রামে P1-P2 ওপরে = উত্তর)
SIDE_NAME = {1: "North 1", 2: "East 2", 3: "South 3", 4: "West 4"}

# প্রতিটি প্লটের জন্য আলাদা হালকা রঙ (ডায়াগ্রাম ও PDF)
PLOT_COLORS = [
    (0.78, 0.93, 0.84), (1.00, 0.89, 0.74), (0.80, 0.86, 0.98),
    (0.98, 0.82, 0.88), (0.93, 0.93, 0.74), (0.80, 0.94, 0.95),
]


# ==========================================
# 1. Math & Geometry Validation Engine (Circle-Circle Intersection)
# ==========================================
def circle_intersection(c1, r1, c2, r2):
    """দুটি বৃত্তের ছেদবিন্দু (Circle-Circle Intersection) বের করার নির্ভুল ভেক্টর জ্যামিতি পদ্ধতি"""
    x1, y1 = c1
    x2, y2 = c2
    d = math.hypot(x2 - x1, y2 - y1)
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        raise ValueError(f"Geometry error: Circles do not intersect (d={d:.2f}, r1={r1}, r2={r2})")
    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h_sq = r1**2 - a**2
    h = math.sqrt(max(0.0, h_sq))
    x2_mid = x1 + a * (x2 - x1) / d
    y2_mid = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)
    return (x2_mid + rx, y2_mid + ry), (x2_mid - rx, y2_mid - ry)


def get_diagonal_bounds(s1, s2, s3, s4, diag_type="Pt 1-3"):
    s1, s2, s3, s4 = float(s1), float(s2), float(s3), float(s4)
    if diag_type == "Pt 1-3":
        min_d = max(abs(s1 - s2), abs(s3 - s4))
        max_d = min(s1 + s2, s3 + s4)
    else:  # "Pt 2-4"
        min_d = max(abs(s1 - s4), abs(s2 - s3))
        max_d = min(s1 + s4, s2 + s3)
    return min_d, max_d


def calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type="Pt 1-3"):
    d_val = float(diag_val)
    s1, s2, s3, s4 = float(s1), float(s2), float(s3), float(s4)

    min_allowed, max_allowed = get_diagonal_bounds(s1, s2, s3, s4, diag_type)

    if not (min_allowed <= d_val <= max_allowed):
        raise ValueError(
            f"Input diagonal is geometrically impossible!\n"
            f"The {diag_type} diagonal value must be between "
            f"{min_allowed:.2f} ft and {max_allowed:.2f} ft based on the sides."
        )

    if diag_type == "Pt 1-3":
        p1 = (0.0, 0.0)
        p2 = (s1, 0.0)
        
        pt3_a, pt3_b = circle_intersection(p1, d_val, p2, s2)
        p3 = pt3_a if pt3_a[1] < pt3_b[1] else pt3_b

        pt4_a, pt4_b = circle_intersection(p1, s4, p3, s3)
        
        best_p4 = None
        max_a = -1
        for cand in [pt4_a, pt4_b]:
            pts = [p1, p2, p3, cand]
            area = polygon_area(pts)
            if area > max_a:
                max_a = area
                best_p4 = cand
        p4 = best_p4

        return [p1, p2, p3, p4]

    else:  # "Pt 2-4"
        p1 = (0.0, 0.0)
        p2 = (s1, 0.0)
        
        pt4_a, pt4_b = circle_intersection(p1, s4, p2, d_val)
        p4 = pt4_a if pt4_a[1] < pt4_b[1] else pt4_b

        pt3_a, pt3_b = circle_intersection(p2, s2, p4, s3)
        
        best_p3 = None
        max_a = -1
        for cand in [pt3_a, pt3_b]:
            pts = [p1, p2, cand, p4]
            area = polygon_area(pts)
            if area > max_a:
                max_a = area
                best_p3 = cand
        p3 = best_p3

        return [p1, p2, p3, p4]


def polygon_area(pts):
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def divide_polygon_directional(pts, num_parts, target_area_sqft, direction, max_cuts=0):
    total_area = polygon_area(pts)

    if target_area_sqft >= total_area and target_area_sqft > 0:
        return [], 0, "Specified plot area cannot be equal to or greater than total area!", [], []

    is_vertical = direction in ["West to East", "East to West"]
    reverse_order = direction in ["East to West", "North to South"]

    idx = 0 if is_vertical else 1
    vals = [p[idx] for p in pts]
    min_v, max_v = min(vals), max(vals)

    def area_upto(V):
        poly = list(pts)
        clipped = []
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            p1_in = p1[idx] <= V
            p2_in = p2[idx] <= V

            if p1_in and p2_in:
                clipped.append(p2)
            elif p1_in and not p2_in:
                t = (V - p1[idx]) / (p2[idx] - p1[idx]) if p2[idx] != p1[idx] else 0
                clipped.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
            elif not p1_in and p2_in:
                t = (V - p1[idx]) / (p2[idx] - p1[idx]) if p2[idx] != p1[idx] else 0
                clipped.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
                clipped.append(p2)
        return polygon_area(clipped) if len(clipped) >= 3 else 0.0

    div_lines = []
    targets_to_find = []

    if target_area_sqft > 0:
        part_area = target_area_sqft
        # একই ক্ষেত্রফলের প্লট বারবার কাটা হয়, যতক্ষণ জমি থাকে (শেষে অবশিষ্ট প্লট)
        k = 1
        while k * part_area < total_area - 0.5 and k < MAX_PLOTS and (not max_cuts or k <= max_cuts):
            cum = k * part_area
            targets_to_find.append((total_area - cum) if reverse_order else cum)
            k += 1
    else:
        part_area = total_area / max(1, num_parts)
        for k in range(1, num_parts):
            target = (total_area - (k * part_area)) if reverse_order else (k * part_area)
            targets_to_find.append(target)

    for target in targets_to_find:
        if target <= 0 or target >= total_area:
            continue
        low, high = min_v, max_v
        for _ in range(80):
            mid = (low + high) / 2.0
            if area_upto(mid) < target:
                low = mid
            else:
                high = mid
        div_lines.append((low + high) / 2.0)

    partition_segments = []
    sub_edge_segments = []

    span_x = max(p[0] for p in pts) - min(p[0] for p in pts)
    span_y = max(p[1] for p in pts) - min(p[1] for p in pts)
    pad = max(span_x, span_y) * 3.0

    min_x, max_x = min(p[0] for p in pts) - pad, max(p[0] for p in pts) + pad
    min_y, max_y = min(p[1] for p in pts) - pad, max(p[1] for p in pts) + pad

    n = len(pts)

    for div_v in div_lines:
        p_a, p_b = ((div_v, min_y), (div_v, max_y)) if is_vertical else ((min_x, div_v), (max_x, div_v))
        intersections = []
        for i in range(n):
            pt_int = line_intersection(p_a, p_b, pts[i], pts[(i + 1) % n])
            if pt_int:
                intersections.append((pt_int, i))

        if len(intersections) >= 2:
            intersections.sort(key=lambda item: item[0][1] if is_vertical else item[0][0])
            p_start, p_end = intersections[0][0], intersections[1][0]
            partition_segments.append((p_start, p_end))

    if is_vertical:
        bottom_pts = [pts[0]]
        top_pts = [pts[3]]

        for div_v in div_lines:
            p_a, p_b = (div_v, min_y), (div_v, max_y)

            int_bot = line_intersection(p_a, p_b, pts[0], pts[1])
            if int_bot:
                bottom_pts.append(int_bot)

            int_top = line_intersection(p_a, p_b, pts[3], pts[2])
            if int_top:
                top_pts.append(int_top)

        bottom_pts.append(pts[1])
        top_pts.append(pts[2])

        bottom_pts.sort(key=lambda p: dist(pts[0], p))
        for i in range(len(bottom_pts) - 1):
            if dist(bottom_pts[i], bottom_pts[i + 1]) > 0.01:
                sub_edge_segments.append((bottom_pts[i], bottom_pts[i + 1], "bottom"))

        top_pts.sort(key=lambda p: dist(pts[3], p))
        for i in range(len(top_pts) - 1):
            if dist(top_pts[i], top_pts[i + 1]) > 0.01:
                sub_edge_segments.append((top_pts[i], top_pts[i + 1], "top"))

    else:
        left_pts = [pts[3]]
        right_pts = [pts[2]]

        for div_v in div_lines:
            p_a, p_b = (min_x, div_v), (max_x, div_v)

            int_left = line_intersection(p_a, p_b, pts[3], pts[0])
            if int_left:
                left_pts.append(int_left)

            int_right = line_intersection(p_a, p_b, pts[2], pts[1])
            if int_right:
                right_pts.append(int_right)

        left_pts.append(pts[0])
        right_pts.append(pts[1])

        left_pts.sort(key=lambda p: dist(pts[3], p))
        for i in range(len(left_pts) - 1):
            if dist(left_pts[i], left_pts[i + 1]) > 0.01:
                sub_edge_segments.append((left_pts[i], left_pts[i + 1], "left"))

        right_pts.sort(key=lambda p: dist(pts[2], p))
        for i in range(len(right_pts) - 1):
            if dist(right_pts[i], right_pts[i + 1]) > 0.01:
                sub_edge_segments.append((right_pts[i], right_pts[i + 1], "right"))

    return div_lines, part_area, is_vertical, partition_segments, sub_edge_segments


