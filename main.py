"""main.py - মূল অ্যাপ (স্ক্রিন বানানো ও সব বাটনের কাজ)। এই ফাইলটাই চালাতে হবে।"""
import math
import os
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.utils import platform

# Android Runtime Permission Request
if platform == 'android':
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE
        ])
    except Exception as e:
        print("Android permission error:", e)

from geometry import (
    SQFT_PER_SHATAK, MAX_PLOTS, SIDE_NAME, PLOT_COLORS,
    dist, polygon_area, get_diagonal_bounds, calculate_quadrilateral,
    divide_polygon_directional,
)
from adjuster import MultiCutAdjuster
from labels_export import export_to_dxf, export_to_pdf
from map_widget import MapCanvasWidget
from ui_parts import (
    C_PRIMARY, C_GREEN, C_ORANGE, C_PURPLE, C_RED, C_BLUE, C_TEAL, C_TEXT,
    Card, RoundedButton, RoundedSpinner, left_label, auto_height_label,
)


# ==========================================
# 4b. Main Application Interface
# ==========================================
class SSRKLandApp(App):
    ADJ_STEP = 0.5  # + / - বাটনে প্রতিবার কত ফুট কম-বেশি হবে
    DEFAULT_ADJ_MSG = "Divide a plot first to enable side adjustment."

    # ---------- small UI factories ----------
    def make_card(self, accent):
        card = Card(bg=(1, 1, 1, 1), border=accent, orientation="vertical",
                    padding=dp(8), spacing=dp(5), size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))
        return card

    def section_header(self, card, text, color):
        hdr = Card(bg=color, radius=10, size_hint_y=None, height=dp(32),
                   padding=[dp(12), 0, dp(12), 0])
        lbl = left_label(text, color=(1, 1, 1, 1), size=14, bold=True)
        hdr.add_widget(lbl)
        card.add_widget(hdr)

    def field(self, inp, color, size_hint_x=1):
        box = Card(bg=(0.985, 0.99, 1, 1), border=color, radius=10, size_hint_x=size_hint_x,
                   padding=[dp(2), dp(2), dp(2), dp(2)])
        box.add_widget(inp)
        return box

    def create_input(self, default_val, bound=True):
        inp = TextInput(
            text=default_val, multiline=False, input_filter="float",
            background_normal="", background_active="", background_color=(0, 0, 0, 0),
            foreground_color=C_TEXT, cursor_color=C_PRIMARY, font_size=sp(15),
            padding=[dp(10), dp(8), dp(10), dp(4)]
        )
        if bound:
            inp.bind(text=self.on_side_input_change)
        return inp

    # ---------- build ----------
    def build(self):
        self.title = "Surveyor Juel - Land Divider"
        self.last_partition_info = ""
        self.adjuster = None
        self.adj_ctx = {}
        self.adj_k = 0
        self._adj_lock = False
        self._adj_event = None
        self._area_event = None

        root_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(4))
        main_layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(14), size_hint_y=None)
        main_layout.bind(minimum_height=main_layout.setter("height"))

        # ---------- Header ----------
        header = Card(bg=C_PRIMARY, radius=18, orientation="vertical", size_hint_y=None,
                      height=dp(68), padding=[dp(12), dp(6), dp(12), dp(6)], spacing=dp(1))
        header.add_widget(Label(
            text="[b]Surveyor Juel[/b]", markup=True, color=(1, 1, 1, 1), font_size=sp(25)
        ))
        header.add_widget(Label(
            text="Land Divider  •  Measurement  •  Report",
            color=(1.0, 0.86, 0.42, 1), font_size=sp(12)
        ))
        main_layout.add_widget(header)

        # ---------- 1. Boundary ----------
        card1 = self.make_card(C_BLUE)
        self.section_header(card1, "1   Boundary Sides & Diagonal", C_BLUE)

        grid_inputs = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                                 row_default_height=dp(38), row_force_default=True)
        grid_inputs.bind(minimum_height=grid_inputs.setter("height"))

        side_specs = [
            ("North 1 (Pt 1-2):", "165", C_GREEN, "txt_s1"),
            ("East 2 (Pt 2-3):", "97", C_ORANGE, "txt_s2"),
            ("South 3 (Pt 3-4):", "122", C_PURPLE, "txt_s3"),
            ("West 4 (Pt 4-1):", "96", C_RED, "txt_s4"),
        ]
        for text, default, col, attr in side_specs:
            grid_inputs.add_widget(left_label(text, color=col, size=14, bold=True))
            inp = self.create_input(default)
            setattr(self, attr, inp)
            grid_inputs.add_widget(self.field(inp, col))
        card1.add_widget(grid_inputs)

        diag_box = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(38))
        self.spn_diag_type = RoundedSpinner(
            text="Pt 1-3", values=("Pt 1-3", "Pt 2-4"),
            size_hint_x=0.4, font_size=sp(14), bg=C_TEAL
        )
        self.spn_diag_type.bind(text=self.on_side_input_change)
        diag_box.add_widget(self.spn_diag_type)
        self.txt_diag = self.create_input("172.45")
        diag_box.add_widget(self.field(self.txt_diag, C_TEAL, size_hint_x=0.6))
        card1.add_widget(diag_box)

        self.lbl_ref_bounds = auto_height_label(
            "Reference Diagonal Limits: --", color=C_BLUE, size=12, bold=True, min_h=26)
        card1.add_widget(self.lbl_ref_bounds)

        act_box = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42))
        btn_calc = RoundedButton(text="Generate Land Map", bg=C_GREEN, size_hint_x=0.68, font_size=sp(15))
        btn_calc.bind(on_press=self.on_calculate)
        act_box.add_widget(btn_calc)
        btn_reset = RoundedButton(text="Reset", bg=C_RED, size_hint_x=0.32, font_size=sp(14))
        btn_reset.bind(on_press=self.on_reset)
        act_box.add_widget(btn_reset)
        card1.add_widget(act_box)
        main_layout.add_widget(card1)

        # ---------- Total area banner ----------
        banner = Card(bg=(0.88, 0.97, 0.91, 1), border=C_GREEN, radius=14,
                      size_hint_y=None, height=dp(48), padding=[dp(8), 0, dp(8), 0])
        self.lbl_area = Label(
            text="Total Area: 0.00 sq.ft (0.00 Shatak)", color=(0.0, 0.40, 0.25, 1),
            bold=True, font_size=sp(15)
        )
        banner.add_widget(self.lbl_area)
        main_layout.add_widget(banner)

        # ---------- Map ----------
        map_card = Card(bg=(1, 1, 1, 1), border=C_PRIMARY, radius=14,
                        size_hint_y=None, height=dp(430), padding=dp(4))
        map_container = FloatLayout()
        self.map_widget = MapCanvasWidget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        map_container.add_widget(self.map_widget)

        zoom_box = BoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint=(None, None), size=(dp(42), dp(138)),
            pos_hint={"right": 0.98, "y": 0.03}
        )
        for txt, handler, col in (("+", self.map_widget.zoom_in, (0.04, 0.38, 0.55, 0.92)),
                                  ("R", self.map_widget.reset_zoom, (0.96, 0.50, 0.10, 0.92)),
                                  ("-", self.map_widget.zoom_out, (0.04, 0.38, 0.55, 0.92))):
            b = RoundedButton(text=txt, bg=col, radius=10, font_size=sp(18))
            b.bind(on_press=handler)
            zoom_box.add_widget(b)
        map_container.add_widget(zoom_box)
        map_card.add_widget(map_container)
        main_layout.add_widget(map_card)

        # ---------- 2. Partition ----------
        card2 = self.make_card(C_PURPLE)
        self.section_header(card2, "2   Partition Settings", C_PURPLE)

        opt_grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                              row_default_height=dp(38), row_force_default=True)
        opt_grid.bind(minimum_height=opt_grid.setter("height"))

        opt_grid.add_widget(left_label("Mode:", size=14, bold=True, color=C_PURPLE))
        self.spn_mode = RoundedSpinner(
            text="By Shatak", values=("By Shatak", "By Sq.Ft", "Equal Division"),
            bg=C_PURPLE, font_size=sp(14)
        )
        opt_grid.add_widget(self.spn_mode)
        self.spn_mode.bind(text=self.on_mode_change)

        opt_grid.add_widget(left_label("Parts (plots):", size=14, bold=True, color=C_BLUE))
        self.txt_parts = self.create_input("1", bound=False)
        opt_grid.add_widget(self.field(self.txt_parts, C_BLUE))

        self.lbl_value = left_label("Value (Shatak):", size=14, bold=True, color=C_ORANGE)
        opt_grid.add_widget(self.lbl_value)
        self.txt_part_val = self.create_input("1", bound=False)
        self.box_part_val = self.field(self.txt_part_val, C_ORANGE)
        opt_grid.add_widget(self.box_part_val)

        opt_grid.add_widget(left_label("Direction:", size=14, bold=True, color=C_BLUE))
        self.spn_dir = RoundedSpinner(
            text="West to East", values=("West to East", "East to West", "North to South", "South to North"),
            bg=C_BLUE, font_size=sp(14)
        )
        opt_grid.add_widget(self.spn_dir)

        opt_grid.add_widget(left_label("Cut Line:", size=14, bold=True, color=C_TEAL))
        self.spn_cutstyle = RoundedSpinner(
            text="Parallel to Start Edge", values=("Parallel to Start Edge", "Straight (Map Axis)"),
            bg=C_TEAL, font_size=sp(13)
        )
        opt_grid.add_widget(self.spn_cutstyle)
        card2.add_widget(opt_grid)

        btn_box = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(42))
        btn_divide = RoundedButton(text="Divide Plot", bg=C_GREEN, font_size=sp(14), size_hint_x=0.36)
        btn_divide.bind(on_press=self.on_divide)
        btn_box.add_widget(btn_divide)
        btn_export = RoundedButton(text="Export CAD", bg=C_BLUE, font_size=sp(13), size_hint_x=0.32)
        btn_export.bind(on_press=self.on_export_cad)
        btn_box.add_widget(btn_export)
        btn_pdf = RoundedButton(text="Export PDF", bg=C_ORANGE, font_size=sp(13), size_hint_x=0.32)
        btn_pdf.bind(on_press=self.on_export_pdf)
        btn_box.add_widget(btn_pdf)
        main_layout.add_widget(card2)
        card2b = self.make_card(C_GREEN)
        card2b.add_widget(btn_box)
        main_layout.add_widget(card2b)

        # ---------- 3. Adjust ----------
        card3 = self.make_card(C_ORANGE)
        self.section_header(card3, "3   Adjust Adjacent Sides (Area fixed)", C_ORANGE)

        self.lbl_adj_ref = auto_height_label(self.DEFAULT_ADJ_MSG, color=C_BLUE, size=12, bold=True, min_h=40)
        card3.add_widget(self.lbl_adj_ref)

        cut_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(36))
        cut_row.add_widget(left_label("Adjust plot:", size=13, bold=True, color=C_PURPLE))
        self.spn_cut = RoundedSpinner(text="Plot 1", values=("Plot 1",), bg=C_PURPLE, font_size=sp(14))
        self.spn_cut.bind(text=self.on_cut_select)
        cut_row.add_widget(self.spn_cut)
        card3.add_widget(cut_row)

        def make_adj_row(which, color):
            row = BoxLayout(orientation="horizontal", spacing=dp(5), size_hint_y=None, height=dp(40))
            name_lbl = left_label("-- --", size=12, bold=True, color=color)
            name_lbl.size_hint_x = 0.30
            btn_minus = RoundedButton(text="-", size_hint_x=0.13, font_size=sp(20), bg=C_RED, radius=10)
            inp = self.create_input("", bound=False)
            inp.bind(text=partial(self.on_adj_text, which))
            box = self.field(inp, color, size_hint_x=0.44)
            btn_plus = RoundedButton(text="+", size_hint_x=0.13, font_size=sp(20), bg=C_GREEN, radius=10)
            btn_minus.bind(on_press=partial(self.on_adj_step, which, -self.ADJ_STEP))
            btn_plus.bind(on_press=partial(self.on_adj_step, which, self.ADJ_STEP))
            for w in (name_lbl, btn_minus, box, btn_plus):
                row.add_widget(w)
            return row, name_lbl, inp, btn_minus, btn_plus

        row_a, self.lbl_adj_a_name, self.txt_adj_a, self.btn_adj_a_minus, self.btn_adj_a_plus = make_adj_row("a", C_GREEN)
        row_b, self.lbl_adj_b_name, self.txt_adj_b, self.btn_adj_b_minus, self.btn_adj_b_plus = make_adj_row("b", C_PURPLE)
        card3.add_widget(row_a)
        card3.add_widget(row_b)

        main_layout.add_widget(card3)

        # ---------- 4. Change Plot Area (আলাদা বক্স) ----------
        card_area = self.make_card(C_RED)
        self.section_header(card_area, "4   Change Plot Area", C_RED)
        area_pick = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(36))
        area_pick.add_widget(left_label("Area of plot:", size=13, bold=True, color=C_RED))
        self.spn_area_plot = RoundedSpinner(text="Plot 1", values=("Plot 1",), bg=C_RED, font_size=sp(14))
        self.spn_area_plot.bind(text=self.on_area_plot_select)
        area_pick.add_widget(self.spn_area_plot)
        card_area.add_widget(area_pick)

        def make_area_row(label, color, unit):
            row = BoxLayout(orientation="horizontal", spacing=dp(5), size_hint_y=None, height=dp(40))
            lbl = left_label(label, size=12, bold=True, color=color)
            lbl.size_hint_x = 0.30
            btn_m = RoundedButton(text="-", size_hint_x=0.13, font_size=sp(20), bg=C_RED, radius=10)
            inp = self.create_input("", bound=False)
            inp.bind(text=partial(self.on_area_text, unit))
            box = self.field(inp, color, size_hint_x=0.44)
            btn_p = RoundedButton(text="+", size_hint_x=0.13, font_size=sp(20), bg=C_GREEN, radius=10)
            btn_m.bind(on_press=partial(self.on_area_step, unit, -1))
            btn_p.bind(on_press=partial(self.on_area_step, unit, 1))
            for w in (lbl, btn_m, box, btn_p):
                row.add_widget(w)
            return row, inp, btn_m, btn_p

        row_sq, self.txt_area_sqft, self.btn_sq_m, self.btn_sq_p = make_area_row("Sq.Ft", C_ORANGE, "sqft")
        row_sh, self.txt_area_shatak, self.btn_sh_m, self.btn_sh_p = make_area_row("Shatak", C_TEAL, "shatak")
        card_area.add_widget(row_sq)
        card_area.add_widget(row_sh)
        main_layout.add_widget(card_area)

        # ---- 4. Plot Diagonal ----
        card4 = self.make_card(C_TEAL)
        self.section_header(card4, "5   Plot Diagonal (draw & measure)", C_TEAL)
        pd_grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                             row_default_height=dp(36), row_force_default=True)
        pd_grid.bind(minimum_height=pd_grid.setter("height"))
        pd_grid.add_widget(left_label("Select plot:", size=13, bold=True, color=C_TEAL))
        self.spn_pd_plot = RoundedSpinner(text="Off", values=("Off",), bg=C_TEAL, font_size=sp(14))
        self.spn_pd_plot.bind(text=self.on_pd_change)
        pd_grid.add_widget(self.spn_pd_plot)
        pd_grid.add_widget(left_label("Diagonal:", size=13, bold=True, color=C_ORANGE))
        self.spn_pd_type = RoundedSpinner(text="NW-SE", values=("NW-SE", "NE-SW", "Both"),
                                          bg=C_ORANGE, font_size=sp(14))
        self.spn_pd_type.bind(text=self.on_pd_change)
        pd_grid.add_widget(self.spn_pd_type)
        card4.add_widget(pd_grid)
        self.lbl_pd_info = auto_height_label("Divide a plot, then select a plot to see its diagonal.",
                                             color=C_BLUE, size=12, bold=True, min_h=26)
        card4.add_widget(self.lbl_pd_info)
        main_layout.add_widget(card4)
        self.set_adjust_enabled(False)

        # ---------- Output ----------
        out_card = Card(bg=(1.0, 0.98, 0.88, 1), border=(0.95, 0.75, 0.2, 1), radius=14,
                        orientation="vertical", padding=dp(8), spacing=dp(3), size_hint_y=None)
        out_card.bind(minimum_height=out_card.setter("height"))
        out_card.add_widget(left_label("Summary", size=13, bold=True, color=C_ORANGE))
        out_card.children[0].size_hint_y = None
        out_card.children[0].height = dp(22)
        self.lbl_output = auto_height_label("Calculation summary...", color=C_TEXT, size=13, min_h=40)
        out_card.add_widget(self.lbl_output)
        self.plot_boxes = BoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
        self.plot_boxes.bind(minimum_height=self.plot_boxes.setter("height"))
        self.plot_boxes.height = 0
        out_card.add_widget(self.plot_boxes)
        main_layout.add_widget(out_card)

        # ---------- Footer ----------
        developer_info_text = (
            "[b][color=FFD54F]Developed by[/color][/b]\n"
            "[b][color=FFFFFF]Md: Juel Badsha[/color][/b]\n"
            "[color=B2EBF2]Address: Amrulbari polipara, Thana: Badargonj, Zilla: Rangpur, Bangladesh[/color]\n"
            "[b][color=FFAB91]Mobile no: +8801744431272[/color][/b]"
        )
        footer = Card(bg=C_PRIMARY, radius=16, size_hint_y=None, height=dp(120), padding=dp(10))
        dev_label = Label(text=developer_info_text, markup=True, halign="center", valign="middle",
                          font_size=sp(13))
        dev_label.bind(size=dev_label.setter("text_size"))
        footer.add_widget(dev_label)
        main_layout.add_widget(footer)

        root_scroll.add_widget(main_layout)
        self.on_side_input_change()
        return root_scroll

    def on_side_input_change(self, *args):
        try:
            s1 = float(self.txt_s1.text) if self.txt_s1.text.strip() else 0.0
            s2 = float(self.txt_s2.text) if self.txt_s2.text.strip() else 0.0
            s3 = float(self.txt_s3.text) if self.txt_s3.text.strip() else 0.0
            s4 = float(self.txt_s4.text) if self.txt_s4.text.strip() else 0.0

            if s1 <= 0 or s2 <= 0 or s3 <= 0 or s4 <= 0:
                self.lbl_ref_bounds.text = "Reference Diagonal Limits: Please enter valid positive numbers"
                self.lbl_ref_bounds.color = (0.8, 0.3, 0.0, 1)
                return

            diag_type = self.spn_diag_type.text
            min_d, max_d = get_diagonal_bounds(s1, s2, s3, s4, diag_type)
            self.lbl_ref_bounds.text = f"Allowed {diag_type} Diagonal: {min_d:.2f} ft to {max_d:.2f} ft"
            self.lbl_ref_bounds.color = (0.0, 0.5, 0.2, 1)
        except Exception:
            self.lbl_ref_bounds.text = "Reference Diagonal Limits: Incomplete or invalid inputs"
            self.lbl_ref_bounds.color = (0.8, 0.3, 0.0, 1)

    def get_inputs(self):
        try:
            s1_text = self.txt_s1.text.strip()
            s2_text = self.txt_s2.text.strip()
            s3_text = self.txt_s3.text.strip()
            s4_text = self.txt_s4.text.strip()
            diag_text = self.txt_diag.text.strip()

            if not all([s1_text, s2_text, s3_text, s4_text, diag_text]):
                raise ValueError("All side and diagonal fields must be filled.")

            s1 = float(s1_text)
            s2 = float(s2_text)
            s3 = float(s3_text)
            s4 = float(s4_text)
            diag_val = float(diag_text)

            if any(v <= 0 for v in [s1, s2, s3, s4, diag_val]):
                raise ValueError("All dimensions must be greater than zero.")

            diag_type = self.spn_diag_type.text
            return s1, s2, s3, s4, diag_val, diag_type
        except ValueError as ve:
            self.lbl_output.text = f"Input Error: {str(ve)}"
            return None
        except Exception as e:
            self.lbl_output.text = f"Input Error: Please check your entered values ({str(e)})"
            return None

    def on_calculate(self, instance):
        vals = self.get_inputs()
        if not vals:
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
            area = polygon_area(pts)
            shatak = area / SQFT_PER_SHATAK

            self.last_partition_info = ""
            self.clear_adjust()
            self.lbl_area.text = f"Total Area: {area:.2f} sq.ft ({shatak:.2f} Shatak)"
            self.map_widget.draw_map(pts, [s1, s2, s3, s4], diag_val=diag_val, diag_type=diag_type)
            self.lbl_output.text = f"Success! Land Boundary Created.\nUsing Diagonal: {diag_type}\nTotal Area: {area:.2f} sq.ft | {shatak:.2f} Shatak"
        except ValueError as ve:
            self.lbl_output.text = f"Geometry Limit Error:\n{str(ve)}"
        except Exception as e:
            self.lbl_output.text = f"Calculation Error: {str(e)}"

    def on_mode_change(self, instance, text):
        if text == "By Shatak":
            self.lbl_value.text = "Value (Shatak):"
        elif text == "By Sq.Ft":
            self.lbl_value.text = "Value (Sq.Ft):"
        else:
            self.lbl_value.text = "Value (not used):"
        self.txt_part_val.disabled = (text == "Equal Division")
        self.box_part_val.opacity = 0.45 if text == "Equal Division" else 1.0

    def read_division_params(self, pts):
        """Mode/Parts/Value ঘর থেকে বন্টনের তথ্য পড়ে।
        ফেরত: (target_sqft, num_parts, max_cuts, error_text)
        - Equal Division: Parts = সমান প্লট সংখ্যা (Value লাগে না)
        - By Shatak / By Sq.Ft: Value = প্রতিটি প্লটের ক্ষেত্রফল, Parts = ঐ মাপের কয়টি প্লট
          (শেষে বাকি জমি আলাদা একটি প্লট)। Parts ফাঁকা বা 0 হলে জমি শেষ না হওয়া পর্যন্ত কাটে।"""
        mode = self.spn_mode.text
        total = polygon_area(pts)
        parts_text = self.txt_parts.text.strip()
        try:
            parts = int(float(parts_text)) if parts_text else 0
        except ValueError:
            return 0, 1, 0, "Error: Please enter a valid number in the Parts box."
        if parts < 0:
            return 0, 1, 0, "Error: Parts cannot be negative."

        if mode == "Equal Division":
            if parts < 1:
                return 0, 1, 0, "Error: Please enter the number of parts (plots)."
            if parts > MAX_PLOTS:
                return 0, 1, 0, f"Error: Maximum {MAX_PLOTS} parts allowed (you entered {parts})."
            return 0, parts, 0, ""

        vtext = self.txt_part_val.text.strip()
        try:
            val = float(vtext)
        except ValueError:
            return 0, 1, 0, "Error: Please enter a valid number in the Value box."
        if val <= 0:
            return 0, 1, 0, "Error: Value must be greater than 0."
        target = val * SQFT_PER_SHATAK if mode == "By Shatak" else val
        unit = "Shatak" if mode == "By Shatak" else "sq.ft"
        fit = total / target
        shown = fit if mode == "By Shatak" else fit
        if parts:
            if parts * target > total + 0.5:
                return 0, 1, 0, (f"Error: {parts} plots of {val:g} {unit} need {parts * target:.2f} sq.ft, "
                                 f"but the land is {total:.2f} sq.ft. Maximum {int(fit)} plots possible.")
            if parts + 1 > MAX_PLOTS:
                return 0, 1, 0, f"Error: Maximum {MAX_PLOTS - 1} plots at a time (you entered {parts})."
            return target, 1, parts, ""
        if int(math.ceil(fit)) > MAX_PLOTS:
            need = total / MAX_PLOTS
            need_txt = f"{need / SQFT_PER_SHATAK:.2f} Shatak" if mode == "By Shatak" else f"{need:.0f} sq.ft"
            return 0, 1, 0, (f"Error: This would make {int(math.ceil(fit))} plots (max {MAX_PLOTS}). "
                             f"Enter at least {need_txt} or set Parts.")
        return target, 1, 0, ""

    def on_reset(self, instance):
        self.txt_s1.text = ""
        self.txt_s2.text = ""
        self.txt_s3.text = ""
        self.txt_s4.text = ""
        self.txt_diag.text = ""
        self.txt_part_val.text = "1"
        self.txt_parts.text = "1"
        self.last_partition_info = ""
        self.clear_adjust()
        self.lbl_area.text = "Total Area: 0.00 sq.ft (0.00 Shatak)"
        self.lbl_output.text = "Fields and map have been reset."
        self.lbl_ref_bounds.text = "Reference Diagonal Limits: --"
        self.map_widget.clear_canvas()

    def on_divide(self, instance):
        if not self.map_widget.pts or len(self.map_widget.pts) < 4:
            self.lbl_output.text = "Error: Please click 'Generate Land Map' first before dividing plot!"
            return

        vals = self.get_inputs()
        if not vals:
            return

        s1, s2, s3, s4, diag_val, diag_type = vals
        try:
            pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
            mode = self.spn_mode.text
            direction = self.spn_dir.text

            target_sqft, num_parts, max_cuts, err = self.read_division_params(pts)
            if err:
                self.lbl_output.text = err
                self.clear_adjust()
                return

            div_lines, part_area, is_vertical, partition_segments, sub_edge_segments = divide_polygon_directional(
                pts, num_parts, target_sqft, direction, max_cuts
            )

            if isinstance(is_vertical, str):
                self.lbl_output.text = is_vertical
                self.clear_adjust()
                return

            # ---- Adjustable mode (By Shatak / By Sq.Ft / Equal Division) ----
            if div_lines:
                equal = (mode == "Equal Division")
                targets = [k * part_area for k in range(1, len(div_lines) + 1)]
                adj = MultiCutAdjuster(pts, direction, targets)
                if adj.ok and adj.init_from_lines(div_lines, parallel=(self.spn_cutstyle.text == "Parallel to Start Edge")):
                    self.adj_ctx = {
                        "pts": pts, "sides": [s1, s2, s3, s4],
                        "diag_val": diag_val, "diag_type": diag_type,
                        "direction": direction, "total_area": polygon_area(pts),
                        "equal": equal, "part_area": part_area,
                    }
                    self.setup_adjust(adj)
                    self.render_adjusted()
                    return

            self.clear_adjust("Side adjustment is not available for this division.")

            self.map_widget.draw_map(
                pts, [s1, s2, s3, s4],
                diag_val=diag_val, diag_type=diag_type,
                div_lines=div_lines, part_area=part_area,
                is_vertical=is_vertical, partition_segments=partition_segments,
                sub_edge_segments=sub_edge_segments
            )

            shatak_val = part_area / SQFT_PER_SHATAK
            out_text = f"Direction: {direction}\n"
            out_text += f"Plot Area: {part_area:.2f} sq.ft ({shatak_val:.2f} Shatak)\n"
            out_text += f"Total Plots: {len(div_lines) + 1}"

            self.last_partition_info = out_text
            self.lbl_output.text = f"Partition Summary:\n{out_text}"
        except Exception as e:
            self.lbl_output.text = f"Divide Error: {str(e)}"

    # ==========================================
    # Adjacent-side adjustment (all plot areas fixed)
    # ==========================================
    def set_adjust_enabled(self, enabled):
        for w in (self.txt_adj_a, self.txt_adj_b, self.spn_cut, self.spn_pd_plot, self.spn_pd_type,
                  self.spn_area_plot, self.txt_area_sqft, self.txt_area_shatak,
                  self.btn_sq_m, self.btn_sq_p, self.btn_sh_m, self.btn_sh_p,
                  self.btn_adj_a_minus, self.btn_adj_a_plus,
                  self.btn_adj_b_minus, self.btn_adj_b_plus):
            w.disabled = not enabled

    def clear_adjust(self, message=None):
        self.adjuster = None
        self.adj_ctx = {}
        self.adj_k = 0
        if self._adj_event is not None:
            self._adj_event.cancel()
            self._adj_event = None
        if self._area_event is not None:
            self._area_event.cancel()
            self._area_event = None
        self._adj_lock = True
        self.txt_adj_a.text = ""
        self.txt_adj_b.text = ""
        self.txt_area_sqft.text = ""
        self.txt_area_shatak.text = ""
        self.spn_area_plot.values = ("Plot 1",)
        self.spn_area_plot.text = "Plot 1"
        self.spn_cut.values = ("Plot 1",)
        self.spn_cut.text = "Plot 1"
        self.spn_pd_plot.values = ("Off",)
        self.spn_pd_plot.text = "Off"
        self.lbl_pd_info.text = "Divide a plot, then select a plot to see its diagonal."
        self._adj_lock = False
        self.lbl_adj_a_name.text = "-- --"
        self.lbl_adj_b_name.text = "-- --"
        self.lbl_adj_ref.text = message or self.DEFAULT_ADJ_MSG
        self.lbl_adj_ref.color = C_BLUE
        self.set_adjust_enabled(False)
        self.clear_plot_boxes()

    def clear_plot_boxes(self):
        if hasattr(self, "plot_boxes"):
            self.plot_boxes.clear_widgets()
            self.plot_boxes.height = 0

    def show_plot_boxes(self, plots):
        """প্রতিটি প্লট আলাদা রঙিন বক্সে (ডায়াগ্রামের রঙের সাথে মিল রেখে) দেখায়।"""
        self.plot_boxes.clear_widgets()
        for i, info in enumerate(plots):
            col = PLOT_COLORS[i % len(PLOT_COLORS)]
            dark = (col[0] * 0.55, col[1] * 0.55, col[2] * 0.55, 1)
            box = Card(bg=(col[0], col[1], col[2], 1), border=dark, radius=12,
                       orientation="vertical", padding=[dp(10), dp(5), dp(10), dp(5)],
                       spacing=dp(0), size_hint_y=None)
            box.bind(minimum_height=box.setter("height"))
            box.add_widget(auto_height_label(info["title"], color=dark, size=15, bold=True, min_h=22))
            box.add_widget(auto_height_label(info["line1"], color=C_TEXT, size=13, min_h=18))
            box.add_widget(auto_height_label(info["line2"], color=C_TEXT, size=13, min_h=18))
            if info.get("line3"):
                box.add_widget(auto_height_label(info["line3"], color=(0.75, 0.15, 0.02, 1),
                                                 size=13, bold=True, min_h=18))
            self.plot_boxes.add_widget(box)

    def setup_adjust(self, adj):
        self.adjuster = adj
        self.adj_k = 0
        self.set_adjust_enabled(True)
        c0 = adj.c0
        self.lbl_adj_a_name.text = f"{SIDE_NAME[c0.side_a_no]}\n(from P{c0.ia0 + 1})"
        self.lbl_adj_b_name.text = f"{SIDE_NAME[c0.side_b_no]}\n(from P{c0.ib0 + 1})"
        self._adj_lock = True
        self.spn_cut.values = tuple(f"Plot {i + 1}" for i in range(adj.n))
        self.spn_cut.text = "Plot 1"
        self.spn_area_plot.values = tuple(f"Plot {i + 1}" for i in range(adj.n + 1))
        self.spn_area_plot.text = "Plot 1"
        self.spn_pd_plot.values = ("Off",) + tuple(f"Plot {i + 1}" for i in range(adj.n + 1))
        self.spn_pd_plot.text = "Off"
        self.lbl_pd_info.text = "Select a plot to draw its diagonal on the map."
        self._adj_lock = False
        self.refresh_adjust_fields()
        self.refresh_area_fields()

    def area_plot_index(self):
        try:
            return int(self.spn_area_plot.text.split()[1]) - 1
        except Exception:
            return 0

    def refresh_area_fields(self):
        adj = self.adjuster
        if adj is None:
            return
        i = min(self.area_plot_index(), adj.n)
        a = adj.plot_areas_now()[i]
        self._adj_lock = True
        self.txt_area_sqft.text = f"{a:.2f}"
        self.txt_area_shatak.text = f"{a / SQFT_PER_SHATAK:.2f}"
        self._adj_lock = False

    def on_area_plot_select(self, instance, text):
        if self._adj_lock or self.adjuster is None:
            return
        self.refresh_area_fields()

    def on_area_text(self, unit, instance, value):
        if self._adj_lock or self.adjuster is None:
            return
        if self._area_event is not None:
            self._area_event.cancel()
        self._area_event = Clock.schedule_once(partial(self.apply_area, unit), 0.8)

    def on_area_step(self, unit, sign, *args):
        adj = self.adjuster
        if adj is None:
            return
        if self._area_event is not None:
            self._area_event.cancel()
            self._area_event = None
        box = self.txt_area_sqft if unit == "sqft" else self.txt_area_shatak
        try:
            cur = float(box.text)
        except ValueError:
            return
        step = 10.0 if unit == "sqft" else 0.05
        self._adj_lock = True
        box.text = f"{max(0.0, cur + sign * step):.2f}"
        self._adj_lock = False
        self.apply_area(unit)

    def apply_area(self, unit, *args):
        adj = self.adjuster
        if adj is None:
            return
        i = min(self.area_plot_index(), adj.n)
        box = self.txt_area_sqft if unit == "sqft" else self.txt_area_shatak
        try:
            v = float(box.text.strip())
        except ValueError:
            self.lbl_output.text = "Area Error: Please enter a valid number."
            return
        new_area = v if unit == "sqft" else v * SQFT_PER_SHATAK
        ok, msg = adj.set_plot_area(i, new_area)
        if not ok:
            self.lbl_output.text = f"Area Error: {msg}"
            self.refresh_area_fields()
            return
        self.adj_ctx["custom"] = True
        self.refresh_adjust_fields()
        self.render_adjusted()

    def refresh_adjust_fields(self):
        adj = self.adjuster
        if adj is None:
            return
        k = self.adj_k
        x, y = adj.xy[k]
        pxa, pxb = self.prev_xy(k)
        self._adj_lock = True
        self.txt_adj_a.text = f"{x - pxa:.2f}"
        self.txt_adj_b.text = f"{y - pxb:.2f}"
        self._adj_lock = False
        self.update_ref_text()

    def prev_xy(self, k):
        """আগের প্লটের শেষ (cumulative) অবস্থান; Plot 1 এর জন্য (0, 0)।"""
        if k > 0 and self.adjuster is not None:
            return self.adjuster.xy[k - 1][0], self.adjuster.xy[k - 1][1]
        return 0.0, 0.0

    def update_ref_text(self):
        adj = self.adjuster
        if adj is None:
            return
        k = self.adj_k
        c0 = adj.c0
        pxa, pxb = self.prev_xy(k)
        a_lo, a_hi = adj.bounds(k, "a")
        b_lo, b_hi = adj.bounds(k, "b")
        a_lo, a_hi, b_lo, b_hi = a_lo - pxa, a_hi - pxa, b_lo - pxb, b_hi - pxb
        pa = self.adj_ctx["part_area"]
        if self.adj_ctx.get("custom"):
            ar = adj.plot_areas_now()
            head = (f"Plot {k + 1}: {ar[k]:.2f} sq.ft ({ar[k] / SQFT_PER_SHATAK:.2f} Shatak) | "
                    f"Plot {k + 2}: {ar[k + 1]:.2f} sq.ft ({ar[k + 1] / SQFT_PER_SHATAK:.2f} Shatak) "
                    f"- sides of Plot {k + 1}")
        elif self.adj_ctx["equal"]:
            head = (f"Boundary between Plot {k + 1} and Plot {k + 2}: all {adj.n + 1} plots "
                    f"stay equal ({pa:.2f} sq.ft each)")
        else:
            head = (f"Plot {k + 1} fixed area: {pa:.2f} sq.ft ({pa / SQFT_PER_SHATAK:.2f} Shatak) "
                    f"- adjusting Plot {k + 1} sides (boundary with Plot {k + 2})")
        self.lbl_adj_ref.text = (
            f"{head}\n"
            f"Plot {k + 1} {SIDE_NAME[c0.side_a_no]} allowed: {a_lo:.2f} to {a_hi:.2f} ft\n"
            f"Plot {k + 1} {SIDE_NAME[c0.side_b_no]} allowed: {b_lo:.2f} to {b_hi:.2f} ft"
        )
        self.lbl_adj_ref.color = (0.0, 0.5, 0.2, 1)

    def on_cut_select(self, instance, text):
        if self._adj_lock or self.adjuster is None:
            return
        try:
            k = int(text.split()[1]) - 1
        except Exception:
            return
        if 0 <= k < self.adjuster.n:
            self.adj_k = k
            self.refresh_adjust_fields()

    def on_pd_change(self, instance, value):
        if self._adj_lock or self.adjuster is None:
            return
        self.render_adjusted()

    @staticmethod
    def plot_corner_map(poly, vertical):
        """প্লটের চার কোণাকে NW/NE/SW/SE নাম দেয় (poly = [A1, A2, B2, B1])।"""
        pa0, pa1, pb1, pb0 = poly
        if vertical:
            na = sorted([pa0, pa1], key=lambda p: p[0])
            nb = sorted([pb0, pb1], key=lambda p: p[0])
            return {"NW": na[0], "NE": na[1], "SW": nb[0], "SE": nb[1]}
        wa = sorted([pa0, pa1], key=lambda p: -p[1])
        eb = sorted([pb0, pb1], key=lambda p: -p[1])
        return {"NW": wa[0], "SW": wa[1], "NE": eb[0], "SE": eb[1]}

    def on_adj_text(self, which, instance, value):
        if self._adj_lock or self.adjuster is None:
            return
        if self._adj_event is not None:
            self._adj_event.cancel()
        self._adj_event = Clock.schedule_once(partial(self.apply_adjust, which), 0.6)

    def on_adj_step(self, which, delta, *args):
        adj = self.adjuster
        if adj is None:
            return
        if self._adj_event is not None:
            self._adj_event.cancel()
            self._adj_event = None
        box = self.txt_adj_a if which == "a" else self.txt_adj_b
        off = self.prev_xy(self.adj_k)[0 if which == "a" else 1]
        lo, hi = adj.bounds(self.adj_k, which)
        lo, hi = lo - off, hi - off
        try:
            cur = float(box.text)
        except ValueError:
            cur = lo
        new_val = min(hi, max(lo, cur + delta))
        self._adj_lock = True
        box.text = f"{new_val:.2f}"
        self._adj_lock = False
        self.apply_adjust(which)

    def apply_adjust(self, which, *args):
        adj = self.adjuster
        if adj is None:
            return
        k = self.adj_k
        c0 = adj.c0
        src = self.txt_adj_a if which == "a" else self.txt_adj_b
        dst = self.txt_adj_b if which == "a" else self.txt_adj_a
        side_no = SIDE_NAME[c0.side_a_no if which == "a" else c0.side_b_no]
        pxa, pxb = self.prev_xy(k)
        off_src, off_dst = (pxa, pxb) if which == "a" else (pxb, pxa)
        lo, hi = adj.bounds(k, which)
        lo, hi = lo - off_src, hi - off_src

        try:
            v = float(src.text.strip())
        except ValueError:
            self.lbl_output.text = f"Adjust Error: Please enter a valid number for {side_no}."
            return

        if v < lo - 0.005 or v > hi + 0.005:
            self.lbl_output.text = (
                f"Adjust Error: {side_no} must be between {lo:.2f} and {hi:.2f} ft "
                f"to keep the plot area fixed."
            )
            return

        v = min(hi, max(lo, v)) + off_src          # cumulative মান
        other = adj.cuts[k].solve(which, v)
        if other is None:
            self.lbl_output.text = f"Adjust Error: {side_no} = {v - off_src:.2f} ft is not possible for this area."
            return

        self._adj_lock = True
        dst.text = f"{other - off_dst:.2f}"
        self._adj_lock = False

        adj.xy[k] = [v, other] if which == "a" else [other, v]
        self.update_ref_text()
        self.render_adjusted()

    def render_adjusted(self):
        adj = self.adjuster
        ctx = self.adj_ctx
        if adj is None or not ctx:
            return
        g = adj.geometry()
        c0 = adj.c0

        # ---- নির্বাচিত প্লটের কর্ণ ----
        extra_diags = []
        diag_notes = []
        sel = self.spn_pd_plot.text
        if sel.startswith("Plot"):
            try:
                pi = int(sel.split()[1]) - 1
                cm = self.plot_corner_map(g["plot_polys"][pi], adj.is_vertical)
                kind = self.spn_pd_type.text
                combos = [("NW", "SE"), ("NE", "SW")] if kind == "Both" else [tuple(kind.split("-"))]
                for u_, v_ in combos:
                    p_, q_ = cm[u_], cm[v_]
                    extra_diags.append((p_, q_))
                    diag_notes.append((pi, f"{u_}-{v_}", dist(p_, q_)))
            except Exception:
                extra_diags, diag_notes = [], []
        if diag_notes:
            self.lbl_pd_info.text = "\n".join(
                f"Plot {pi + 1} diagonal {nm}: {ln:.2f} ft" for pi, nm, ln in diag_notes)
        elif sel.startswith("Plot"):
            self.lbl_pd_info.text = "Diagonal not available for this plot."
        else:
            self.lbl_pd_info.text = "Select a plot to draw its diagonal on the map."

        self.map_widget.draw_map(
            ctx["pts"], ctx["sides"],
            diag_val=ctx["diag_val"], diag_type=ctx["diag_type"],
            div_lines=[], part_area=ctx["part_area"],
            is_vertical=adj.is_vertical,
            partition_segments=g["partition_segments"],
            sub_edge_segments=g["sub_edge_segments"],
            plot_polys=g["plot_polys"],
            extra_diags=extra_diags,
        )

        pa = ctx["part_area"]
        sh = SQFT_PER_SHATAK
        a_no, b_no = c0.side_a_no, c0.side_b_no
        total_plots = adj.n + 1

        # ---- প্রতিটি প্লটের তথ্য ----
        plots = []
        pdf_lines = [f"Direction: {ctx['direction']}", f"Total Plots: {total_plots}"]
        for i, poly in enumerate(g["plot_polys"]):
            area_i = g["plot_areas"][i]
            side_a = dist(poly[0], poly[1])      # A বাহুর অংশ
            end_ln = dist(poly[1], poly[2])      # পরের রেখা / শেষ বাহু
            side_b = dist(poly[2], poly[3])      # B বাহুর অংশ
            start_ln = dist(poly[3], poly[0])    # আগের রেখা / শুরুর বাহু
            start_name = "Start Side" if i == 0 else f"Line with Plot {i}"
            end_name = "Far Side" if i == total_plots - 1 else f"Line with Plot {i + 2}"
            tag = " (Remaining)" if (not ctx["equal"] and not ctx.get("custom") and i == total_plots - 1) else ""
            plots.append({
                "title": f"Plot {i + 1}{tag}  -  {area_i:.2f} sq.ft ({area_i / sh:.2f} Shatak)",
                "line1": f"{SIDE_NAME[a_no]}: {side_a:.2f} ft   |   {SIDE_NAME[b_no]}: {side_b:.2f} ft",
                "line2": f"{start_name}: {start_ln:.2f} ft   |   {end_name}: {end_ln:.2f} ft",
            })
            notes_i = [f"{nm}: {ln:.2f} ft" for pi, nm, ln in diag_notes if pi == i]
            if notes_i:
                plots[-1]["line3"] = "Diagonal " + "   |   ".join(notes_i)
            pdf_lines.append(
                f"Plot {i + 1}{tag}: {area_i:.2f} sq.ft ({area_i / sh:.2f} Shatak) | "
                f"{SIDE_NAME[a_no]}: {side_a:.2f} ft | {SIDE_NAME[b_no]}: {side_b:.2f} ft"
            )
            for pi, nm, ln in diag_notes:
                if pi == i:
                    pdf_lines.append(f"   Plot {i + 1} diagonal {nm}: {ln:.2f} ft")

        head = f"Direction: {ctx['direction']}\nTotal Plots: {total_plots}"
        if ctx["equal"] and not ctx.get("custom"):
            head += f"  (each {pa:.2f} sq.ft | {pa / sh:.2f} Shatak)"
        self.lbl_output.text = head
        self.last_partition_info = "\n".join(pdf_lines)
        self.show_plot_boxes(plots)
        self.refresh_area_fields()

    # ==========================================
    # Save dialog / exports
    # ==========================================
    def open_save_dialog(self, default_filename, on_save_callback):
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))

        if platform == 'android':
            start_path = '/storage/emulated/0'
            root_path = '/storage/emulated/0'
            if not os.path.exists(start_path):
                start_path = os.path.expanduser('~')
                root_path = '/'
        else:
            start_path = os.path.expanduser('~')
            if os.path.exists(os.path.join(start_path, 'Downloads')):
                start_path = os.path.join(start_path, 'Downloads')
            root_path = '/'

        file_chooser = FileChooserListView(
            path=start_path,
            rootpath=root_path,
            dirselect=True,
            size_hint=(1, 0.75)
        )
        content.add_widget(file_chooser)

        fn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(5))
        fn_layout.add_widget(Label(text="File Name:", size_hint_x=0.3, color=(1, 1, 1, 1), bold=True))
        txt_filename = TextInput(text=default_filename, multiline=False, size_hint_x=0.7)
        fn_layout.add_widget(txt_filename)
        content.add_widget(fn_layout)

        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(10))
        btn_cancel = RoundedButton(text="Cancel", bg=C_RED)
        btn_save = RoundedButton(text="Save", bg=C_GREEN)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
        content.add_widget(btn_layout)

        popup = Popup(
            title="Choose Directory & Name File",
            content=content,
            size_hint=(0.95, 0.95),
            auto_dismiss=False
        )

        def save_action(instance):
            selected_dir = file_chooser.path
            if file_chooser.selection and os.path.isdir(file_chooser.selection[0]):
                selected_dir = file_chooser.selection[0]

            filename = txt_filename.text.strip()
            if filename:
                full_path = os.path.join(selected_dir, filename)
                popup.dismiss()
                on_save_callback(full_path)
            else:
                self.lbl_output.text = "Error: Please enter a valid file name."

        btn_save.bind(on_press=save_action)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    def on_export_cad(self, instance):
        if not self.map_widget.pts or len(self.map_widget.pts) < 4:
            self.lbl_output.text = "Error: Please click 'Generate Land Map' first before exporting CAD!"
            return

        vals = self.get_inputs()
        if not vals:
            return

        def do_cad_export(full_path):
            s1, s2, s3, s4, diag_val, diag_type = vals
            try:
                pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)
                direction = self.spn_dir.text
                mode = self.spn_mode.text

                if self.adjuster is not None:
                    # স্ক্রিনে যে (অ্যাডজাস্টকৃত) বন্টন রেখাগুলো দেখা যাচ্ছে সেগুলোই এক্সপোর্ট হবে
                    partition_segments = list(self.map_widget.partition_segments)
                else:
                    try:
                        target_sqft, num_parts, max_cuts, err = self.read_division_params(pts)
                        if err:
                            raise ValueError(err)
                        _, _, _, partition_segments, _ = divide_polygon_directional(
                            pts, num_parts, target_sqft, direction, max_cuts)
                    except Exception:
                        partition_segments = []

                filePath = export_to_dxf(pts, partition_segments, full_path)
                self.lbl_output.text = f"CAD Export Successful!\nSaved File Path:\n{filePath}"
            except Exception as e:
                self.lbl_output.text = f"Export Error: {str(e)}"

        self.open_save_dialog("land_map.dxf", do_cad_export)

    def on_export_pdf(self, instance):
        if not self.map_widget.pts or len(self.map_widget.pts) < 4:
            self.lbl_output.text = "Error: Please click 'Generate Land Map' first before exporting PDF!"
            return

        vals = self.get_inputs()
        if not vals:
            return

        def do_pdf_export(full_path):
            s1, s2, s3, s4, diag_val, diag_type = vals
            try:
                pts = calculate_quadrilateral(s1, s2, s3, s4, diag_val, diag_type)

                pdf_path = export_to_pdf(
                    pts=pts,
                    sides=[s1, s2, s3, s4],
                    diag_val=diag_val,
                    diag_type=diag_type,
                    full_filepath=full_path,
                    part_summary_text=self.last_partition_info,
                    partition_segments=self.map_widget.partition_segments,
                    sub_edge_segments=self.map_widget.sub_edge_segments,
                    is_vertical=self.map_widget.is_vertical,
                    plot_polys=self.map_widget.plot_polys,
                    extra_diags=self.map_widget.extra_diags,
                )
                self.lbl_output.text = f"PDF Export Successful!\nSaved PDF File Path:\n{pdf_path}"
            except Exception as e:
                self.lbl_output.text = f"PDF Export Error: {str(e)}"

        self.open_save_dialog("land_report.pdf", do_pdf_export)


# ==========================================
# 5. Program Entry Point
# ==========================================
if __name__ == "__main__":
    SSRKLandApp().run()

