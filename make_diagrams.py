"""
Generate high-quality UI mockup diagrams for the README.
Uses Pillow to draw pixel-perfect representations of each screen.
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = "docs/screenshots"
os.makedirs(OUT, exist_ok=True)

# ── colour palette ────────────────────────────────────────────────────────────
BG        = (240, 240, 240)
WHITE     = (255, 255, 255)
DARK      = (45,  45,  45)
PANEL_BG  = (250, 250, 250)
HEADER_BG = (60,  60,  60)
HEADER_FG = (220, 220, 220)
ACCENT    = (66, 133, 244)
GREEN     = (52, 168,  83)
ORANGE    = (251, 140,  0)
RED       = (234,  67,  53)
PURPLE    = (103,  58, 183)
BORDER    = (200, 200, 200)
TEXT      = (30,  30,  30)
MUTED     = (120, 120, 120)
LIGHT_BLUE= (232, 240, 254)
VIEWER_BG = (28,  28,  35)
GRID_LINE = (40,  40,  50)
AXIS_R    = (220,  60,  60)
AXIS_G    = (60,  200,  60)
AXIS_B    = (60, 100, 220)

try:
    FONT_SM  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",  12)
    FONT_MD  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",  14)
    FONT_LG  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",  18)
    FONT_XL  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",  24)
    FONT_BD  = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 14)
    FONT_BDL = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 18)
    FONT_MONO= ImageFont.truetype("C:/Windows/Fonts/consola.ttf",  11)
except Exception:
    FONT_SM = FONT_MD = FONT_LG = FONT_XL = FONT_BD = FONT_BDL = FONT_MONO = \
        ImageFont.load_default()


def rect(d, xy, fill, outline=None, radius=4):
    d.rounded_rectangle(xy, radius=radius, fill=fill,
                         outline=outline or fill, width=1)


def text_c(d, xy, txt, font, fill=TEXT):
    """Center text at xy."""
    bb = d.textbbox((0, 0), txt, font=font)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    d.text((xy[0]-w//2, xy[1]-h//2), txt, font=font, fill=fill)


def shadow_rect(img, d, xy, fill, radius=6):
    """Draw a rectangle with a subtle drop shadow."""
    sx, sy, ex, ey = xy
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((sx+3, sy+3, ex+3, ey+3), radius=radius,
                          fill=(0, 0, 0, 40))
    img.paste(shadow, mask=shadow)
    rect(d, xy, fill, BORDER, radius)


# ═══════════════════════════════════════════════════════════════════════════════
# Diagram 1 — Main Window (loaded state)
# ═══════════════════════════════════════════════════════════════════════════════
def make_main_window():
    W, H = 1280, 740
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    # ── Title bar ──────────────────────────────────────────────────────────────
    rect(d, (0, 0, W, 32), HEADER_BG)
    d.text((12, 8), "CAD2URDF — CAD to ROS 2 URDF Converter", font=FONT_MD, fill=HEADER_FG)
    for i, x in enumerate([W-90, W-60, W-30]):
        rect(d, (x, 6, x+24, 26), (80, 80, 80), radius=3)
    d.text((W-85, 10), "─", font=FONT_SM, fill=HEADER_FG)
    d.text((W-55, 10), "□", font=FONT_SM, fill=HEADER_FG)
    d.text((W-26, 10), "✕", font=FONT_SM, fill=HEADER_FG)

    # ── Menu bar ──────────────────────────────────────────────────────────────
    rect(d, (0, 32, W, 54), WHITE)
    for label, x in [("File", 12), ("Help", 56)]:
        d.text((x, 38), label, font=FONT_MD, fill=TEXT)
    d.line([(0, 54), (W, 54)], fill=BORDER, width=1)

    # ── Left panel: Assembly Tree ──────────────────────────────────────────────
    LW = 230
    rect(d, (0, 54, LW, H-28), WHITE, BORDER, radius=0)
    rect(d, (0, 54, LW, 76), (235, 235, 235), radius=0)
    d.text((8, 60), "Part / Assembly", font=FONT_BD, fill=TEXT)
    d.text((165, 60), "Idx", font=FONT_BD, fill=MUTED)
    d.line([(0, 76), (LW, 76)], fill=BORDER)

    parts = [
        ("🔧 base_link",       "0", True),
        ("  └─ upper_arm",     "1", False),
        ("      └─ forearm",   "2", False),
        ("           └─ wrist","3", False),
        ("               └─ gripper_L","4", False),
        ("               └─ gripper_R","5", False),
    ]
    for i, (name, idx, sel) in enumerate(parts):
        y = 80 + i * 24
        if sel:
            rect(d, (0, y-2, LW, y+20), LIGHT_BLUE, radius=0)
        d.text((8, y), name, font=FONT_SM, fill=ACCENT if sel else TEXT)
        d.text((168, y), idx, font=FONT_SM, fill=MUTED)

    d.line([(0, H-28), (LW, H-28)], fill=BORDER)
    d.text((8, H-22), "6 parts loaded", font=FONT_SM, fill=MUTED)

    # ── Center: 3D Viewer ─────────────────────────────────────────────────────
    VX, VY, VW, VH = LW+4, 58, 1280-340-LW-4, H-90
    rect(d, (VX, VY, VX+VW, VY+VH), VIEWER_BG, (50,50,60), radius=6)

    # Grid floor
    for gx in range(VX+20, VX+VW, 40):
        d.line([(gx, VY+VH-80), (VX+VW//2, VY+VH-20)], fill=GRID_LINE, width=1)
    for gz in range(0, 8):
        x0 = VX+20 + gz*40
        x1 = VX+VW-20 - gz*30
        y0 = VY+VH-80 + gz*8
        d.line([(x0, y0), (x1, y0)], fill=GRID_LINE, width=1)

    # Robot arm silhouette (stylised)
    cx, cy = VX + VW//2, VY + VH//2 + 40

    # Base (box)
    d.rounded_rectangle((cx-45, cy+20, cx+45, cy+70), radius=4,
                         fill=(70,130,180), outline=(100,160,210))
    text_c(d, (cx, cy+45), "base_link", FONT_SM, (200,225,255))

    # Arm segments
    segs = [
        ((cx-8, cy-60, cx+8, cy+22),  (65,105,180), "upper_arm"),
        ((cx+8, cy-110, cx+30, cy-55),(70,110,175), "forearm"),
        ((cx+32, cy-145, cx+55, cy-108),(75,115,170), "wrist"),
    ]
    for bbox, col, lbl in segs:
        x0,y0,x1,y1 = bbox
        d.rounded_rectangle((x0,y0,x1,y1), radius=3,
                             fill=col, outline=(120,160,220))

    # Gripper fingers
    for dx in [-14, 6]:
        d.rounded_rectangle((cx+50+dx, cy-175, cx+58+dx, cy-148),
                             radius=2, fill=(80,120,190),
                             outline=(120,160,220))

    # Joint markers (red/orange dots)
    joints_pts = [(cx, cy+22), (cx, cy-60), (cx+20, cy-108), (cx+47, cy-146)]
    for px, py in joints_pts:
        d.ellipse((px-6, py-6, px+6, py+6), fill=RED, outline=WHITE)

    # Axis arrows (bottom-left)
    ax, ay = VX+30, VY+VH-40
    d.line([(ax, ay), (ax+40, ay)],  fill=AXIS_R, width=2)
    d.text((ax+42, ay-6), "X", font=FONT_SM, fill=AXIS_R)
    d.line([(ax, ay), (ax, ay-40)],  fill=AXIS_G, width=2)
    d.text((ax-14, ay-52), "Z", font=FONT_SM, fill=AXIS_G)
    d.line([(ax, ay), (ax-25, ay+20)], fill=AXIS_B, width=2)
    d.text((ax-38, ay+18), "Y", font=FONT_SM, fill=AXIS_B)

    # Viewer label
    d.text((VX+6, VY+6), "3D Preview", font=FONT_SM, fill=(120,120,130))

    # Joint legend
    legend_x = VX + VW - 145
    for i, (col, lbl) in enumerate([(RED, "Revolute joint"),
                                      (ORANGE, "Fixed joint")]):
        ly = VY + 12 + i*20
        d.ellipse((legend_x, ly, legend_x+12, ly+12), fill=col)
        d.text((legend_x+16, ly-1), lbl, font=FONT_SM, fill=(180,180,200))

    # ── Right panel: Tabs ─────────────────────────────────────────────────────
    RX = VX + VW + 4
    RW = W - RX
    rect(d, (RX, 54, W, H-28), PANEL_BG, BORDER, radius=0)

    # Tab bar
    for i, (tab, active) in enumerate([("Links", True), ("Joints", False)]):
        tx = RX + i * (RW//2)
        rect(d, (tx, 54, tx + RW//2, 78),
             WHITE if active else (230,230,230), BORDER, radius=0)
        text_c(d, (tx + RW//4, 66), tab,
               FONT_BD if active else FONT_MD,
               ACCENT if active else MUTED)
    d.line([(RX, 78), (W, 78)], fill=BORDER)

    # Links tab content
    link_data = [
        ("base_link",   "3.925 kg", "steel",    "(50, 50, 25) mm"),
        ("upper_arm",   "1.480 kg", "aluminum", "(50, 50,125) mm"),
        ("forearm",     "0.892 kg", "aluminum", "(30, 30, 80) mm"),
        ("wrist",       "0.341 kg", "abs_plastic","(15,15,40) mm"),
    ]
    y = 84
    for lname, mass, mat, com in link_data:
        rect(d, (RX+6, y, W-6, y+68), WHITE, BORDER, radius=5)
        d.text((RX+12, y+6), lname, font=FONT_BD, fill=TEXT)
        d.text((RX+12, y+24), f"Mass: {mass}", font=FONT_SM, fill=MUTED)
        d.text((RX+12, y+38), f"Material: {mat}", font=FONT_SM, fill=MUTED)
        d.text((RX+12, y+52), f"CoM: {com}", font=FONT_SM, fill=MUTED)
        rect(d, (W-70, y+24, W-10, y+42), LIGHT_BLUE, ACCENT, radius=3)
        text_c(d, (W-40, y+33), mat[:3].upper(), FONT_SM, ACCENT)
        y += 76

    # ── Status bar ────────────────────────────────────────────────────────────
    rect(d, (0, H-28, W, H), (230,230,230), radius=0)
    d.line([(0, H-28), (W, H-28)], fill=BORDER)
    d.text((8, H-20), "Analysis complete — 6 links, 5 joints detected.", font=FONT_SM, fill=GREEN)
    rect(d, (W-210, H-22, W-10, H-8), ACCENT, radius=3)
    d.text((W-206, H-22), "████████████████████ 100%", font=FONT_SM, fill=WHITE)

    img.save(f"{OUT}/01_main_window.png", optimize=True)
    print(f"  01_main_window.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Diagram 2 — Joints Panel
# ═══════════════════════════════════════════════════════════════════════════════
def make_joints_panel():
    W, H = 780, 680
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    rect(d, (0, 0, W, H), PANEL_BG, BORDER, radius=8)
    rect(d, (0, 0, W, 36), (235, 235, 235), radius=0)
    d.text((12, 10), "Joints Panel — Review & Edit Detected Joints", font=FONT_BD, fill=TEXT)
    d.line([(0, 36), (W, 36)], fill=BORDER)

    joints = [
        {
            "name": "base_to_upper_arm",
            "type": "revolute",
            "parent": "base_link",
            "child":  "upper_arm",
            "conf":   92,
            "axis":   "(0, 0, 1)",
            "origin": "(0.050, 0.050, 0.070)",
            "limits": "-π  →  +π",
            "effort": "150.0 N·m",
            "vel":    "3.14 rad/s",
            "evidence": "Collinear cylinders with matching radii (20.0 mm)",
        },
        {
            "name": "upper_arm_to_forearm",
            "type": "revolute",
            "parent": "upper_arm",
            "child":  "forearm",
            "conf":   88,
            "axis":   "(0, 1, 0)",
            "origin": "(0.050, 0.050, 0.200)",
            "limits": "-1.57  →  +1.57",
            "effort": "120.0 N·m",
            "vel":    "2.50 rad/s",
            "evidence": "Pin-in-hole cylinders: r=12.0mm / 14.0mm, ratio=0.86",
        },
        {
            "name": "forearm_to_wrist",
            "type": "revolute",
            "parent": "forearm",
            "child":  "wrist",
            "conf":   82,
            "axis":   "(0, 0, 1)",
            "origin": "(0.050, 0.050, 0.320)",
            "limits": "-3.14  →  +3.14",
            "effort": "80.0 N·m",
            "vel":    "3.14 rad/s",
            "evidence": "Collinear cylinders with matching radii (8.0 mm)",
        },
    ]

    type_colors = {
        "revolute":  (ACCENT,   LIGHT_BLUE),
        "fixed":     (MUTED,    (240,240,240)),
        "prismatic": (PURPLE,   (243,240,254)),
    }

    y = 46
    for j in joints:
        col_fg, col_bg = type_colors.get(j["type"], (MUTED, (240,240,240)))
        conf = j["conf"]
        bar_w = int((W-24) * conf / 100)

        shadow_rect(img, d, (8, y, W-8, y+148), WHITE, radius=7)

        # Header strip
        rect(d, (8, y, W-8, y+30), col_bg, col_fg, radius=7)
        d.text((16, y+8), j["name"], font=FONT_BD, fill=col_fg)
        rect(d, (W-90, y+6, W-12, y+24), col_fg, radius=3)
        text_c(d, (W-51, y+15), f"{j['type'].upper()}", FONT_SM, WHITE)

        # Confidence bar
        d.text((16, y+36), f"Confidence: {conf}%", font=FONT_SM, fill=MUTED)
        rect(d, (110, y+38, W-16, y+50), (220,220,220), radius=4)
        rect(d, (110, y+38, 110+bar_w-126, y+50), col_fg, radius=4)

        # Details grid
        details = [
            ("Parent → Child", f"{j['parent']}  →  {j['child']}"),
            ("Axis",    j["axis"]),
            ("Origin",  j["origin"]),
            ("Limits",  j["limits"]),
            ("Effort / Vel", f"{j['effort']}  |  {j['vel']}"),
        ]
        for k, (lbl, val) in enumerate(details):
            gx = 16 + (k % 2) * (W//2 - 12)
            gy = y + 58 + (k // 2) * 22
            d.text((gx, gy), f"{lbl}:", font=FONT_SM, fill=MUTED)
            d.text((gx + 110, gy), val, font=FONT_SM, fill=TEXT)

        # Evidence
        d.text((16, y+122), f"Evidence: {j['evidence']}", font=FONT_SM, fill=(100,140,100))

        # Edit dropdown (visual only)
        rect(d, (W-170, y+54, W-16, y+74), WHITE, BORDER, radius=3)
        d.text((W-164, y+59), "Type: revolute ▾", font=FONT_SM, fill=TEXT)

        y += 160

    img.save(f"{OUT}/02_joints_panel.png", optimize=True)
    print(f"  02_joints_panel.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Diagram 3 — Export Dialog
# ═══════════════════════════════════════════════════════════════════════════════
def make_export_dialog():
    W, H = 560, 280
    img = Image.new("RGB", (W, H), (80, 80, 80))
    d   = ImageDraw.Draw(img)

    shadow_rect(img, d, (10, 10, W-10, H-10), WHITE, radius=10)

    # Title bar
    rect(d, (10, 10, W-10, 46), HEADER_BG, radius=10)
    d.text((22, 22), "Export ROS 2 Package", font=FONT_BDL, fill=WHITE)
    rect(d, (W-40, 18, W-16, 38), (100,100,100), radius=4)
    d.text((W-34, 22), "✕", font=FONT_SM, fill=WHITE)

    # Form fields
    y = 60
    for label, value in [
        ("Package name:", "my_robot_arm"),
        ("Output directory:", "C:/Users/ACER/ros2_ws/src"),
    ]:
        d.text((22, y), label, font=FONT_BD, fill=TEXT)
        rect(d, (22, y+20, W-22, y+44), WHITE, BORDER, radius=4)
        d.text((30, y+28), value, font=FONT_MD, fill=TEXT)
        if "directory" in label:
            rect(d, (W-80, y+22, W-24, y+42), (235,235,235), BORDER, radius=4)
            text_c(d, (W-52, y+32), "Browse…", FONT_SM, TEXT)
        y += 64

    # Checkbox
    rect(d, (22, y+4, 38, y+20), WHITE, BORDER, radius=3)
    d.text((26, y+5), "✓", font=FONT_SM, fill=ACCENT)
    d.text((44, y+4), "Open output folder when done", font=FONT_MD, fill=TEXT)

    # Buttons
    rect(d, (W-190, H-52, W-110, H-20), ACCENT, radius=5)
    text_c(d, (W-150, H-36), "Export", FONT_BD, WHITE)
    rect(d, (W-100, H-52, W-22, H-20), (235,235,235), BORDER, radius=5)
    text_c(d, (W-61, H-36), "Cancel", FONT_BD, TEXT)

    img.save(f"{OUT}/03_export_dialog.png", optimize=True)
    print(f"  03_export_dialog.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Diagram 4 — Pipeline Architecture Flow
# ═══════════════════════════════════════════════════════════════════════════════
def make_pipeline():
    W, H = 1100, 300
    img = Image.new("RGB", (W, H), (250, 250, 252))
    d   = ImageDraw.Draw(img)

    steps = [
        ("STEP / IGES\nFile",         (70,130,180),  "📄"),
        ("StepReader\n(XDE / pythonocc)", ACCENT,    "📦"),
        ("TopologyExplorer\n(BRep faces)", (56,142,60), "🔍"),
        ("JointDetector\n(geometry)",   (249,168,37), "🔗"),
        ("InertiaCalc\n(GProp)",        (156,39,176), "⚖"),
        ("MeshExporter\n(DAE + STL)",   (0,150,136),  "🎨"),
        ("URDFGenerator\n(lxml)",       (211,47,47),  "📝"),
        ("ROS 2 Package\n(colcon ready)",(38,166,154),"🚀"),
    ]

    BOX_W, BOX_H = 112, 66
    GAP  = (W - len(steps)*BOX_W) // (len(steps)+1)
    cy   = H // 2

    for i, (label, color, icon) in enumerate(steps):
        bx = GAP + i * (BOX_W + GAP)
        by = cy - BOX_H // 2

        # shadow
        shdw = Image.new("RGBA", img.size, (0,0,0,0))
        sd = ImageDraw.Draw(shdw)
        sd.rounded_rectangle((bx+3,by+3,bx+BOX_W+3,by+BOX_H+3), radius=8, fill=(0,0,0,35))
        img.paste(shdw, mask=shdw)

        # box
        rect(d, (bx, by, bx+BOX_W, by+BOX_H), color, radius=8)

        # icon strip at top
        rect(d, (bx, by, bx+BOX_W, by+22), (*color[:3],), radius=8)
        darker = tuple(max(0,c-40) for c in color)
        rect(d, (bx, by+14, bx+BOX_W, by+22), darker, radius=0)

        lines = label.split("\n")
        text_c(d, (bx+BOX_W//2, by+12), lines[0], FONT_BD, WHITE)
        if len(lines) > 1:
            text_c(d, (bx+BOX_W//2, by+36), lines[1], FONT_SM, WHITE)
        if len(lines) > 2:
            text_c(d, (bx+BOX_W//2, by+52), lines[2], FONT_SM, (220,220,220))

        # arrow to next
        if i < len(steps)-1:
            ax = bx + BOX_W + 4
            d.line([(ax, cy), (ax+GAP-8, cy)], fill=(160,160,160), width=2)
            d.polygon([(ax+GAP-8, cy-5),
                        (ax+GAP+2, cy),
                        (ax+GAP-8, cy+5)], fill=(160,160,160))

    # Label
    d.text((10, 10), "CAD2URDF Processing Pipeline", font=FONT_BDL, fill=(60,60,60))

    img.save(f"{OUT}/04_pipeline.png", optimize=True)
    print(f"  04_pipeline.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Diagram 5 — URDF output preview
# ═══════════════════════════════════════════════════════════════════════════════
def make_urdf_preview():
    W, H = 760, 440
    img = Image.new("RGB", (W, H), (30, 30, 35))
    d   = ImageDraw.Draw(img)

    # Code editor style
    rect(d, (0, 0, W, 32), (40, 40, 46), radius=0)
    rect(d, (8, 6, 26, 26), (220,90,90), radius=12)
    rect(d, (34,6, 52, 26), (220,180,60), radius=12)
    rect(d, (60,6, 78, 26), (80,190,80), radius=12)
    d.text((94, 10), "test_robot.urdf — CAD2URDF", font=FONT_SM, fill=(160,160,170))

    KWRD = (86, 156, 214)   # blue  – XML tags
    STR  = (206, 145, 120)  # amber – attribute values
    ATTR = (156, 220, 254)  # cyan  – attribute names
    CMT  = (106, 153,  85)  # green – comments
    WH   = (212, 212, 212)
    DIM  = (100, 100, 110)

    lines = [
        ('', ''),
        ('  ', CMT,  '<!-- Auto-generated by CAD2URDF -->'),
        ('  ', KWRD, '<robot', ATTR, ' name', WH, '=', STR, '"my_robot_arm"', KWRD, '>'),
        ('', ''),
        ('  ', DIM,  '  <!-- Link 1: base -->'),
        ('  ', KWRD, '  <link', ATTR, ' name', WH, '=', STR, '"base_link"', KWRD, '>'),
        ('  ', WH,   '    <inertial>'),
        ('  ', ATTR, '      <mass',  WH, ' value', WH, '=', STR, '"3.925000"', WH, '/>'),
        ('  ', ATTR, '      <inertia', WH, ' ixx', WH, '=', STR, '"0.00408854"',
                     ATTR, ' iyy', WH, '=', STR, '"0.00408854"',
                     ATTR, ' izz', WH, '=', STR, '"0.00654167"', WH, '/>'),
        ('  ', WH,   '    </inertial>'),
        ('  ', WH,   '    <visual>'),
        ('  ', ATTR, '      <mesh', WH, ' filename', WH, '=',
                     STR, '"package://my_robot_arm/meshes/visual/base_link.dae"', WH, '/>'),
        ('  ', WH,   '    </visual>'),
        ('  ', KWRD, '  </link>'),
        ('', ''),
        ('  ', DIM,  '  <!-- Joint 1: base → upper_arm (REVOLUTE) -->'),
        ('  ', KWRD, '  <joint', ATTR, ' name', WH, '=', STR, '"base_to_upper_arm"',
                     ATTR, ' type', WH, '=', STR, '"revolute"', KWRD, '>'),
        ('  ', ATTR, '    <axis',    WH, ' xyz', WH, '=', STR, '"0.000000 0.000000 1.000000"', WH, '/>'),
        ('  ', ATTR, '    <limit',   WH, ' lower', WH, '=', STR, '"-3.14159"',
                     ATTR, ' upper', WH, '=', STR, '"3.14159"',
                     ATTR, ' effort', WH, '=', STR, '"150.0"',
                     ATTR, ' velocity', WH, '=', STR, '"3.14"', WH, '/>'),
        ('  ', KWRD, '  </joint>'),
        ('', ''),
        ('  ', KWRD, '</robot>'),
    ]

    y = 42
    lnum = 1
    for parts in lines:
        d.text((8, y), f"{lnum:3}", font=FONT_MONO, fill=(80,80,90))
        x = 44
        i = 0
        while i < len(parts):
            if parts[i] == '':
                i += 1
                continue
            if isinstance(parts[i], tuple):  # color
                color = parts[i]; i += 1
                txt = parts[i] if i < len(parts) else ''; i += 1
                d.text((x, y), txt, font=FONT_MONO, fill=color)
                bb = d.textbbox((0,0), txt, font=FONT_MONO)
                x += bb[2]-bb[0]
            else:
                txt = parts[i]; i += 1
                d.text((x, y), txt, font=FONT_MONO, fill=WH)
                bb = d.textbbox((0,0), txt, font=FONT_MONO)
                x += bb[2]-bb[0]
        lnum += 1
        y += 17

    img.save(f"{OUT}/05_urdf_output.png", optimize=True)
    print(f"  05_urdf_output.png")


# ─── Run all ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating diagrams...")
    make_main_window()
    make_joints_panel()
    make_export_dialog()
    make_pipeline()
    make_urdf_preview()
    print(f"\nAll saved to {OUT}/")
