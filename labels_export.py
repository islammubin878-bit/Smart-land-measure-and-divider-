"""labels_export.py - লেবেল বসানোর নিয়ম এবং DXF / PDF এক্সপোর্ট।"""
import math
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth

from geometry import SQFT_PER_SHATAK, PLOT_COLORS, dist, polygon_area
from ui_parts import C_PRIMARY


# ==========================================
# 1c. Label Layout Engine (ডায়াগ্রাম ও PDF দুটোতেই একই নিয়মে লেবেল বসায়)
# ==========================================
LABEL_BASE_SIZE = {"side": 10.5, "sub": 9.0, "cut": 9.0, "pt": 10.0, "diag": 9.5}
LABEL_COLORS = {
    "side": (0.78, 0.10, 0.15, 1),   # মূল বাহু - গাঢ় লাল (বাইরে)
    "sub": (0.05, 0.33, 0.80, 1),    # বন্টনকৃত অংশ - নীল (ভেতরে)
    "cut": (0.50, 0.10, 0.65, 1),    # বন্টন রেখা - বেগুনি
    "pt": (0.0, 0.35, 0.25, 1),      # P1..P4
    "diag": (0.85, 0.20, 0.05, 1),   # প্লটের কর্ণ - কমলা-লাল
}


def label_angle(dx, dy):
    """বাহুর দিক অনুযায়ী লেখা হরাইজন্টাল / ভার্টিকাল / ঢালু - স্বয়ংক্রিয়ভাবে ঠিক করে।"""
    a = math.degrees(math.atan2(dy, dx))
    if a > 90:
        a -= 180
    elif a < -90:
        a += 180
    aa = abs(a)
    if aa < 20:
        return 0.0
    if aa > 70:
        return 90.0
    return a


def build_label_specs(spts, sides, part_segs, sub_segs, measure, u, diag_segs=None):
    """
    spts      : চারটি কোণার স্ক্রিন/পেজ পয়েন্ট
    sides     : মূল চার বাহুর দৈর্ঘ্য
    part_segs : [(p, q, length)] বন্টন রেখা
    sub_segs  : [(p, q, length)] বন্টনকৃত বাহুর টুকরো
    measure   : (text, kind) -> (width, height)
    u         : অফসেট ইউনিট (dp বা pt)
    মূল বাহুর মান = বাহুর বাইরে একটু দূরে; টুকরোর মান = লাইনের ভেতরে।
    """
    specs = []
    n = len(spts)
    cx = sum(p[0] for p in spts) / n
    cy = sum(p[1] for p in spts) / n

    def place(p, q, text, kind, mode, dist_units, bg=False, t=0.5):
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        tx, ty = dx / length, dy / length
        ang = label_angle(dx, dy)
        th = math.radians(ang)
        ux, uy = math.cos(th), math.sin(th)
        vx, vy = -uy, ux
        mx, my = p[0] + dx * t, p[1] + dy * t
        nx, ny = -ty, tx
        if nx * (mx - cx) + ny * (my - cy) < 0:
            nx, ny = -nx, -ny
        w, h = measure(text, kind)
        if mode == "center":
            center = (mx, my)
        else:
            half = abs(nx * ux + ny * uy) * w / 2.0 + abs(nx * vx + ny * vy) * h / 2.0
            sign = 1.0 if mode == "out" else -1.0
            d = dist_units * u + half
            center = (mx + sign * nx * d, my + sign * ny * d)
        specs.append({"text": text, "center": center, "angle": ang, "kind": kind, "bg": bg})

    for i in range(n):
        place(spts[i], spts[(i + 1) % n], f"{sides[i]:.1f}'", "side", "out", 9)

    # বন্টনকৃত বাহুর টুকরোর মান: বাহুর ঠিক মাঝখানে, রেখার উপর সাদা ব্যাকগ্রাউন্ডে
    for p, q, ln in sub_segs:
        place(p, q, f"{ln:.1f}'", "sub", "center", 0, bg=True)

    for p, q, ln in part_segs:
        place(p, q, f"{ln:.1f}'", "cut", "center", 0, bg=True)

    # দুই কর্ণ একসাথে থাকলে মান দুটো আলাদা জায়গায় বসে (মাঝখানে ওভারল্যাপ এড়াতে)
    diag_list = list(diag_segs or [])
    for i, (p, q, ln) in enumerate(diag_list):
        t = 0.5 if len(diag_list) == 1 else (0.28 if i == 0 else 0.72)
        place(p, q, f"{ln:.1f}'", "diag", "center", 0, bg=True, t=t)

    for i, v in enumerate(spts):
        dxv, dyv = v[0] - cx, v[1] - cy
        ln = math.hypot(dxv, dyv) or 1.0
        w, h = measure(f"P{i + 1}", "pt")
        d = 7 * u + 0.5 * math.hypot(w, h)
        specs.append({
            "text": f"P{i + 1}", "center": (v[0] + dxv / ln * d, v[1] + dyv / ln * d),
            "angle": 0.0, "kind": "pt", "bg": False,
        })
    return specs


# ==========================================
# 2. File Export Utilities (DXF & PDF)
# ==========================================
def export_to_dxf(pts, partition_segments, full_filepath):
    dxf_content = ["0", "SECTION", "2", "ENTITIES"]
    n = len(pts)
    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        dxf_content.extend([
            "0", "LINE", "8", "BOUNDARY",
            "10", str(p1[0]), "20", str(p1[1]), "30", "0.0",
            "11", str(p2[0]), "21", str(p2[1]), "31", "0.0"
        ])

    for seg in partition_segments:
        p_start, p_end = seg[0], seg[1]
        dxf_content.extend([
            "0", "LINE", "8", "PARTITIONS",
            "10", str(p_start[0]), "20", str(p_start[1]), "30", "0.0",
            "11", str(p_end[0]), "21", str(p_end[1]), "31", "0.0"
        ])

    dxf_content.extend(["0", "ENDSEC", "0", "EOF"])
    with open(full_filepath, "w") as f:
        f.write("\n".join(dxf_content))
    return os.path.abspath(full_filepath)


def export_to_pdf(pts, sides, diag_val, diag_type, full_filepath, part_summary_text="",
                  partition_segments=None, sub_edge_segments=None, is_vertical=True, plot_polys=None,
                  extra_diags=None):
    c = canvas.Canvas(full_filepath, pagesize=letter)
    width, height = letter

    # ---- Header band ----
    c.setFillColorRGB(*C_PRIMARY[:3])
    c.rect(0, height - 66, width, 66, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 36, "Surveyor Juel - Land Measurement Report")
    c.setFillColorRGB(1.0, 0.85, 0.4)
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 54, "Land Divider  |  Measurement  |  Report")

    text_object = c.beginText(50, height - 92)
    text_object.setFont("Helvetica-Bold", 11)
    text_object.setFillColorRGB(0.04, 0.38, 0.55)
    text_object.textLine("--- Boundary & Area Summary ---")
    text_object.setFont("Helvetica", 9.5)
    text_object.setFillColorRGB(0.1, 0.1, 0.1)

    total_area = polygon_area(pts)
    shatak = total_area / SQFT_PER_SHATAK
    text_object.textLine(f"North 1 (P1-P2): {sides[0]:.2f} ft   |   East 2 (P2-P3): {sides[1]:.2f} ft")
    text_object.textLine(f"South 3 (P3-P4): {sides[2]:.2f} ft   |   West 4 (P4-P1): {sides[3]:.2f} ft")
    text_object.textLine(f"Diagonal ({diag_type}): {diag_val:.2f} ft")
    text_object.setFont("Helvetica-Bold", 10)
    text_object.textLine(f"Total Area: {total_area:.2f} sq.ft ({shatak:.2f} Shatak)")
    text_object.textLine("")

    if part_summary_text:
        text_object.setFont("Helvetica-Bold", 11)
        text_object.setFillColorRGB(0.52, 0.28, 0.78)
        text_object.textLine("--- Partition Summary ---")
        text_object.setFont("Helvetica", 9.5)
        text_object.setFillColorRGB(0.1, 0.1, 0.1)
        lines = part_summary_text.split("\n")
        max_lines = 14
        if len(lines) > max_lines:
            extra = len(lines) - (max_lines - 1)
            lines = lines[:max_lines - 1] + [f"... (+{extra} more lines)"]
        for line in lines:
            text_object.textLine(line)

    c.drawText(text_object)

    title_y = text_object.getY() - 18
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.04, 0.38, 0.55)
    c.drawString(50, title_y, "--- Graphic Plot Map (With All Dimension Values) ---")

    map_box_w = 500.0
    map_box_h = max(200.0, min(330.0, title_y - 20 - 75))
    map_center_x = width / 2
    map_center_y = title_y - 12 - map_box_h / 2

    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w_data, h_data = max(1e-4, max_x - min_x), max(1e-4, max_y - min_y)
    scale = min((map_box_w - 150) / w_data, (map_box_h - 100) / h_data)
    cx_data, cy_data = (min_x + max_x) / 2, (min_y + max_y) / 2

    def to_pdf_coord(pt):
        return (map_center_x + (pt[0] - cx_data) * scale,
                map_center_y + (pt[1] - cy_data) * scale)

    pdf_pts = [to_pdf_coord(p) for p in pts]

    # ---- Fill plots ----
    polys = plot_polys if plot_polys else [pts]
    for i, poly in enumerate(polys):
        col = PLOT_COLORS[i % len(PLOT_COLORS)]
        c.setFillColorRGB(*col)
        path = c.beginPath()
        pp = [to_pdf_coord(p) for p in poly]
        path.moveTo(*pp[0])
        for q in pp[1:]:
            path.lineTo(*q)
        path.close()
        c.drawPath(path, fill=1, stroke=0)

    # ---- Diagonal ----
    if diag_val > 0:
        c.setStrokeColorRGB(0.95, 0.55, 0.15)
        c.setLineWidth(0.8)
        c.setDash(3, 3)
        if diag_type == "Pt 1-3":
            c.line(pdf_pts[0][0], pdf_pts[0][1], pdf_pts[2][0], pdf_pts[2][1])
        else:
            c.line(pdf_pts[1][0], pdf_pts[1][1], pdf_pts[3][0], pdf_pts[3][1])
        c.setDash()

    # ---- Partition lines ----
    part_screen = []
    if partition_segments:
        c.setStrokeColorRGB(*LABEL_COLORS["cut"][:3])
        c.setLineWidth(1.6)
        for seg in partition_segments:
            sp1, sp2 = to_pdf_coord(seg[0]), to_pdf_coord(seg[1])
            c.line(sp1[0], sp1[1], sp2[0], sp2[1])
            part_screen.append((sp1, sp2, dist(seg[0], seg[1])))

    sub_screen = []
    for p1, p2, _pos in (sub_edge_segments or []):
        sub_screen.append((to_pdf_coord(p1), to_pdf_coord(p2), dist(p1, p2)))

    diag_screen = []
    if extra_diags:
        c.setStrokeColorRGB(*LABEL_COLORS["diag"][:3])
        c.setLineWidth(1.4)
        c.setDash(5, 3)
        for p1, p2 in extra_diags:
            q1, q2 = to_pdf_coord(p1), to_pdf_coord(p2)
            c.line(q1[0], q1[1], q2[0], q2[1])
            diag_screen.append((q1, q2, dist(p1, p2)))
        c.setDash()

    # ---- Boundary ----
    c.setStrokeColorRGB(0.0, 0.42, 0.40)
    c.setLineWidth(2.2)
    n = len(pdf_pts)
    for i in range(n):
        p1, p2 = pdf_pts[i], pdf_pts[(i + 1) % n]
        c.line(p1[0], p1[1], p2[0], p2[1])
    c.setFillColorRGB(0.0, 0.5, 0.4)
    for p in pdf_pts:
        c.circle(p[0], p[1], 3, fill=1, stroke=0)

    # ---- Labels ----
    def measure(text, kind):
        size = LABEL_BASE_SIZE[kind]
        return stringWidth(text, "Helvetica-Bold", size), size

    specs = build_label_specs(pdf_pts, sides, part_screen, sub_screen, measure, 1.0, diag_screen)
    for spec in specs:
        size = LABEL_BASE_SIZE[spec["kind"]]
        w, h = measure(spec["text"], spec["kind"])
        cxs, cys = spec["center"]
        c.saveState()
        c.translate(cxs, cys)
        c.rotate(spec["angle"])
        if spec["bg"]:
            c.setFillColorRGB(1, 1, 1)
            c.roundRect(-w / 2 - 2, -h / 2 - 1, w + 4, h + 3, 2, fill=1, stroke=0)
        col = LABEL_COLORS[spec["kind"]]
        c.setFillColorRGB(*col[:3])
        c.setFont("Helvetica-Bold", size)
        c.drawCentredString(0, -size * 0.33, spec["text"])
        c.restoreState()

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, 40, "Developed by: Md. Juel Badsha | Mobile: +8801744431272")
    c.drawRightString(width - 50, 40, "Surveyor Juel Land App")

    c.save()
    return os.path.abspath(full_filepath)


