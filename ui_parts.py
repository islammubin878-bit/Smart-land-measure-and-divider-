"""ui_parts.py - থিমের রঙ এবং স্টাইল করা ছোট UI উপাদান (Card, Button, Spinner, Label)।"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.core.window import Window
from kivy.metrics import dp, sp

# ---------- Theme ----------
C_BG = (0.92, 0.95, 0.99, 1)
C_PRIMARY = (0.04, 0.38, 0.55, 1)
C_GREEN = (0.10, 0.60, 0.40, 1)
C_ORANGE = (0.96, 0.50, 0.10, 1)
C_PURPLE = (0.52, 0.28, 0.78, 1)
C_RED = (0.86, 0.24, 0.28, 1)
C_BLUE = (0.16, 0.45, 0.85, 1)
C_TEAL = (0.05, 0.62, 0.65, 1)
C_TEXT = (0.12, 0.17, 0.25, 1)

Window.clearcolor = C_BG


# ==========================================
# 4a. Styled UI Components
# ==========================================
class Card(BoxLayout):
    """গোল কোণাযুক্ত রঙিন কার্ড"""

    def __init__(self, bg=(1, 1, 1, 1), border=None, radius=14, **kwargs):
        super().__init__(**kwargs)
        self._radius = dp(radius)
        self._border = None
        with self.canvas.before:
            Color(*bg)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
            if border:
                Color(*border)
                self._border = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius),
                    width=dp(1.3)
                )
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size
        if self._border is not None:
            self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


def attach_round_bg(w, bg, radius):
    with w.canvas.before:
        w._bg_color = Color(*bg)
        w._bg_rect = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])

    def upd(*a):
        w._bg_rect.pos = w.pos
        w._bg_rect.size = w.size

    def restyle(*a):
        if w.disabled:
            w._bg_color.rgba = (bg[0], bg[1], bg[2], 0.40)
        elif w.state == "down":
            w._bg_color.rgba = (bg[0] * 0.72, bg[1] * 0.72, bg[2] * 0.72, bg[3])
        else:
            w._bg_color.rgba = bg

    w.bind(pos=upd, size=upd, state=restyle, disabled=restyle)
    restyle()


class RoundedButton(Button):
    def __init__(self, bg=(0.1, 0.5, 0.4, 1), radius=12, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs["background_color"] = (0, 0, 0, 0)
        kwargs.setdefault("color", (1, 1, 1, 1))
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)
        attach_round_bg(self, bg, radius)


class ColorOption(SpinnerOption):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0.96, 0.94, 1.0, 1)
        self.color = C_TEXT
        self.font_size = sp(14)


class RoundedSpinner(Spinner):
    def __init__(self, bg=(0.5, 0.3, 0.8, 1), radius=12, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs["background_color"] = (0, 0, 0, 0)
        kwargs.setdefault("color", (1, 1, 1, 1))
        kwargs.setdefault("bold", True)
        kwargs["option_cls"] = ColorOption
        super().__init__(**kwargs)
        attach_round_bg(self, bg, radius)


def left_label(text, color=C_TEXT, size=13, bold=False, markup=False):
    lbl = Label(text=text, color=color, font_size=sp(size), bold=bold,
                halign="left", valign="middle", markup=markup)
    lbl.bind(size=lbl.setter("text_size"))
    return lbl


def auto_height_label(text, color=C_TEXT, size=13, bold=False, min_h=30, markup=False):
    lbl = Label(text=text, color=color, font_size=sp(size), bold=bold, markup=markup,
                halign="left", valign="top", size_hint_y=None, height=dp(min_h))
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    lbl.bind(texture_size=lambda inst, s: setattr(inst, "height", max(dp(min_h), s[1] + dp(3))))
    return lbl


