"""map_widget.py - ম্যাপ আঁকা, জুম ও টাচের উইজেট।"""
from kivy.uix.stencilview import StencilView
from kivy.graphics import (
    Color, Line, Rectangle, Ellipse, RoundedRectangle, Quad,
    PushMatrix, PopMatrix, Rotate,
)
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp, sp
from kivy.clock import Clock

from geometry import PLOT_COLORS, dist
from labels_export import build_label_specs, LABEL_BASE_SIZE, LABEL_COLORS


# ==========================================
# 3. Interactive Map Canvas Component
# ==========================================
class MapCanvasWidget(StencilView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pts = []
        self.div_lines = []
        self.partition_segments = []
        self.sub_edge_segments = []
        self.plot_polys = []
        self.extra_diags = []
        self.diag_val = 0.0
        self.diag_type = "Pt 1-3"
        self.part_area = 0.0
        self.sides = []
        self.is_vertical = True

        self.zoom_scale = 1.0
        self.min_zoom = 0.4
        self.max_zoom = 4.5

        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_touch_pos = None
        self.bind(size=self.trigger_redraw, pos=self.trigger_redraw)

    def draw_map(self, pts, sides, diag_val=0.0, diag_type="Pt 1-3", div_lines=None, part_area=0.0,
                 is_vertical=True, partition_segments=None, sub_edge_segments=None, plot_polys=None,
                 extra_diags=None):
        self.pts = pts
        self.sides = sides
        self.diag_val = diag_val
        self.diag_type = diag_type
        self.div_lines = div_lines if div_lines else []
        self.partition_segments = partition_segments if partition_segments else []
        self.sub_edge_segments = sub_edge_segments if sub_edge_segments else []
        self.plot_polys = plot_polys if plot_polys else []
        self.extra_diags = extra_diags if extra_diags else []
        self.part_area = part_area
        self.is_vertical = is_vertical
        self.trigger_redraw()

    def clear_canvas(self):
        self.pts, self.sides, self.div_lines = [], [], []
        self.partition_segments, self.sub_edge_segments, self.plot_polys = [], [], []
        self.extra_diags = []
        self.diag_val = 0.0
        self.part_area = 0.0
        self.zoom_scale = 1.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.canvas.clear()

    def zoom_in(self, *args):
        new_scale = self.zoom_scale * 1.25
        if new_scale <= self.max_zoom:
            self.zoom_scale = new_scale
            self.trigger_redraw()

    def zoom_out(self, *args):
        new_scale = self.zoom_scale / 1.25
        if new_scale >= self.min_zoom:
            self.zoom_scale = new_scale
            self.trigger_redraw()

    def reset_zoom(self, *args):
        self.zoom_scale = 1.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.trigger_redraw()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.last_touch_pos = touch.pos
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self.last_touch_pos:
            dx = touch.x - self.last_touch_pos[0]
            dy = touch.y - self.last_touch_pos[1]
            self.pan_x += dx
            self.pan_y += dy
            self.last_touch_pos = touch.pos
            self.trigger_redraw()
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.last_touch_pos = None
            return True
        return super().on_touch_up(touch)

    def trigger_redraw(self, *args):
        Clock.unschedule(self.redraw)
        Clock.schedule_once(self.redraw, 0.05)

    # ---- text helpers ----
    def _font_px(self, kind):
        return sp(LABEL_BASE_SIZE[kind] * (0.6 + 0.4 * self.zoom_scale))

    def _texture(self, text, kind):
        core_lbl = CoreLabel(text=str(text), font_size=self._font_px(kind), bold=True)
        core_lbl.refresh()
        return core_lbl.texture

    def _measure(self, text, kind):
        try:
            return self._texture(text, kind).size
        except Exception:
            return (dp(30), dp(12))

    def draw_spec(self, spec):
        try:
            tex = self._texture(spec["text"], spec["kind"])
            w, h = tex.size
            cx, cy = spec["center"]
            PushMatrix()
            Rotate(angle=spec["angle"], origin=(cx, cy))
            if spec["bg"]:
                Color(1, 1, 1, 0.92)
                RoundedRectangle(pos=(cx - w / 2 - dp(3), cy - h / 2 - dp(1)),
                                 size=(w + dp(6), h + dp(2)), radius=[dp(3)])
            Color(*LABEL_COLORS[spec["kind"]])
            Rectangle(texture=tex, pos=(cx - w / 2, cy - h / 2), size=(w, h))
            PopMatrix()
        except Exception:
            pass

    def redraw(self, dt=None):
        self.canvas.clear()
        if not self.pts or len(self.pts) < 4:
            return

        try:
            with self.canvas:
                Color(0.99, 0.99, 1, 1)
                Rectangle(pos=self.pos, size=self.size)

                Color(0.55, 0.70, 0.85, 1)
                Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)

                xs, ys = [p[0] for p in self.pts], [p[1] for p in self.pts]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                w_data, h_data = max(1e-4, max_x - min_x), max(1e-4, max_y - min_y)
                padding_x, padding_y = dp(70), dp(55)

                if self.width <= 2 * padding_x or self.height <= 2 * padding_y:
                    return

                base_scale = min(
                    (self.width - 2 * padding_x) / w_data,
                    (self.height - 2 * padding_y) / h_data,
                )
                scale = base_scale * self.zoom_scale

                cx_screen = self.x + self.width / 2 + self.pan_x
                cy_screen = self.y + self.height / 2 + self.pan_y
                cx_data, cy_data = (min_x + max_x) / 2, (min_y + max_y) / 2

                def to_screen(pt):
                    return (cx_screen + (pt[0] - cx_data) * scale,
                            cy_screen + (pt[1] - cy_data) * scale)

                screen_pts = [to_screen(p) for p in self.pts]

                # ---- plot fills ----
                polys = self.plot_polys if self.plot_polys else [self.pts]
                for i, poly in enumerate(polys):
                    col = PLOT_COLORS[i % len(PLOT_COLORS)]
                    Color(col[0], col[1], col[2], 1)
                    flat = []
                    for p in poly:
                        sp_ = to_screen(p)
                        flat.extend([sp_[0], sp_[1]])
                    try:
                        Quad(points=flat)
                    except Exception:
                        pass

                # ---- diagonal ----
                if self.diag_val > 0:
                    Color(0.95, 0.50, 0.10, 0.45)
                    if self.diag_type == "Pt 1-3":
                        Line(points=[screen_pts[0][0], screen_pts[0][1], screen_pts[2][0], screen_pts[2][1]],
                             width=1.1, dash_length=dp(5), dash_offset=dp(3))
                    else:
                        Line(points=[screen_pts[1][0], screen_pts[1][1], screen_pts[3][0], screen_pts[3][1]],
                             width=1.1, dash_length=dp(5), dash_offset=dp(3))

                # ---- partition lines ----
                part_screen = []
                Color(*LABEL_COLORS["cut"][:3], 1)
                for seg in self.partition_segments:
                    sp1, sp2 = to_screen(seg[0]), to_screen(seg[1])
                    Line(points=[sp1[0], sp1[1], sp2[0], sp2[1]], width=dp(1.6))
                    part_screen.append((sp1, sp2, dist(seg[0], seg[1])))

                # ---- selected plot diagonals ----
                diag_screen = []
                for dp1, dp2 in self.extra_diags:
                    q1, q2 = to_screen(dp1), to_screen(dp2)
                    Color(*LABEL_COLORS["diag"])
                    Line(points=[q1[0], q1[1], q2[0], q2[1]], width=dp(1.8),
                         dash_length=dp(7), dash_offset=dp(4))
                    diag_screen.append((q1, q2, dist(dp1, dp2)))

                # ---- boundary ----
                Color(0.0, 0.42, 0.40, 1)
                flat_pts = []
                for sp_pt in screen_pts:
                    flat_pts.extend([sp_pt[0], sp_pt[1]])
                flat_pts.extend([screen_pts[0][0], screen_pts[0][1]])
                Line(points=flat_pts, width=dp(2))

                offset_factor = 0.7 + 0.3 * self.zoom_scale
                Color(0.0, 0.55, 0.45, 1)
                dot_size = dp(8) * min(2.5, max(0.8, offset_factor))
                for sp_pt in screen_pts:
                    Ellipse(pos=(sp_pt[0] - dot_size / 2, sp_pt[1] - dot_size / 2), size=(dot_size, dot_size))

                # ---- labels ----
                sub_screen = []
                for p1, p2, _pos in self.sub_edge_segments:
                    sub_screen.append((to_screen(p1), to_screen(p2), dist(p1, p2)))

                specs = build_label_specs(
                    screen_pts, self.sides, part_screen, sub_screen,
                    self._measure, dp(1) * offset_factor, diag_screen
                )
                for spec in specs:
                    self.draw_spec(spec)

        except Exception as e:
            print("Redraw Exception Handled:", e)


