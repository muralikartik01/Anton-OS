import os
import re
import sys
import time

# ── Palette: "Monochrome Ink & Electric Lime-Yellow" ──────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CURSOR_HOME = "\033[H"
CLEAR_ALL = "\033[2J\033[H"

def fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"
def bg(r, g, b): return f"\033[48;2;{r};{g};{b}m"

C_LOGO       = fg(245, 246, 248)   # Pure Monochrome White (Logo)
C_TEXT       = fg(236, 238, 242)   # Crisp Off-White
C_SUBTEXT    = fg(152, 158, 172)   # Cool Mist Gray
C_MUTED      = fg(94, 100, 114)    # Slate Gray
C_BORDER     = fg(54, 58, 68)      # Graphite Hairline

C_LIME       = fg(212, 244, 88)    # Signature Electric Lime-Yellow
C_LIME_SOFT  = fg(188, 224, 72)    # Secondary Lime
C_MINT       = fg(110, 231, 183)   # Success / Add
C_CORAL      = fg(248, 113, 113)   # Delete / Alert
C_ICE        = fg(147, 197, 253)   # Paths / Info

BG_CARD      = bg(22, 24, 29)
BG_LIME_PILL = bg(38, 46, 22)
BG_ROW_SEL   = bg(30, 34, 26)
BG_ADD       = bg(20, 42, 34)
BG_DEL       = bg(48, 22, 28)

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

def vlen(s: str) -> int:
    return len(ANSI_RE.sub("", s))

def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - vlen(s))

# Enable ANSI escape processing on Windows terminals
if os.name == "nt":
    os.system("")

def read_key() -> str:
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}.get(ch2, "")
        if ch in (b"\r", b"\n"):
            return "ENTER"
        if ch == b"\x1b":
            return "ESC"
        if ch == b"\x03":
            raise KeyboardInterrupt
        return ch.decode("utf-8", errors="ignore").lower()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "UP"
                if seq == "[B":
                    return "DOWN"
                return "ESC"
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ── Realistic Anatomically-Inspired Blink Geometry Engine ──────────────────────
def in_tri(px, py, ax, ay, bx, by, cx, cy):
    v0x, v0y = cx - ax, cy - ay
    v1x, v1y = bx - ax, by - ay
    v2x, v2y = px - ax, py - ay
    dot00 = v0x * v0x + v0y * v0y
    dot01 = v0x * v1x + v0y * v1y
    dot02 = v0x * v2x + v0y * v2y
    dot11 = v1x * v1x + v1y * v1y
    dot12 = v1x * v2x + v1y * v2y
    denom = dot00 * dot11 - dot01 * dot01
    if denom == 0:
        return False
    inv = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv
    v = (dot00 * dot12 - dot01 * dot02) * inv
    return (u >= 0) and (v >= 0) and (u + v <= 1)

def is_eye_pixel(x, y, openness=1.0, pupil_dx=0.0):
    """
    openness: 1.0 = fully open, 0.0 = closed horizontal slit.
    The eyelids slide vertically toward y=0 and clip the pupil cleanly.
    """
    # Closed slit state
    if openness <= 0.06:
        # Thin sleek tapered horizontal line when shut
        half_thickness = 0.045 * max(0.0, 1.0 - (abs(x) / 0.96) ** 2)
        return abs(y) <= half_thickness

    # Vertical shift of upper and lower eyelids as they close toward y = 0
    close_amount = 1.0 - openness
    top_drop = close_amount * 0.56     # Upper lid travels ~65% of the distance (natural anatomy)
    bot_rise = close_amount * 0.42     # Lower lid travels ~35% of the distance

    # Aperture bounds for clipping the pupil
    aperture_top = -0.46 + top_drop
    aperture_bot = 0.46 - bot_rise

    # 1. Stationary Pupil (clipped by the closing eyelids)
    if (x - pupil_dx) ** 2 + y ** 2 <= 0.34 ** 2:
        if aperture_top <= y <= aperture_bot:
            return True

    # 2. Top Angular Eyelid (slides down + flattens slightly as it closes)
    ty = y - top_drop
    flat_top = 1.0 - (close_amount * 0.45)
    top = [
        (-0.98, 0.18 * flat_top),
        (-0.42, -0.52 * flat_top),
        (0.15, -0.88 * flat_top),
        (0.85, -0.28 * flat_top),
        (0.15, -0.52 * flat_top),
    ]
    if (in_tri(x, ty, *top[0], *top[1], *top[4]) or
        in_tri(x, ty, *top[1], *top[2], *top[4]) or
        in_tri(x, ty, *top[2], *top[3], *top[4])):
        return True

    # 3. Bottom Angular Eyelid (slides up + flattens slightly as it closes)
    by = y + bot_rise
    bot = [
        (0.98, -0.14 * flat_top),
        (0.42, 0.56 * flat_top),
        (-0.14, 0.90 * flat_top),
        (-0.82, 0.30 * flat_top),
        (-0.14, 0.54 * flat_top),
    ]
    if (in_tri(x, by, *bot[0], *bot[1], *bot[4]) or
        in_tri(x, by, *bot[1], *bot[2], *bot[4]) or
        in_tri(x, by, *bot[2], *bot[3], *bot[4])):
        return True

    return False

def render_eye_block(w=32, h=15, openness=1.0, pupil_dx=0.0):
    ph = h * 2
    lines = []
    for r in range(h):
        row = ""
        yt = ((r * 2) / (ph - 1)) * 2 - 1
        yb = ((r * 2 + 1) / (ph - 1)) * 2 - 1
        for c in range(w):
            x = (c / (w - 1)) * 2 - 1
            t_on = is_eye_pixel(x, yt, openness, pupil_dx)
            b_on = is_eye_pixel(x, yb, openness, pupil_dx)
            if t_on and b_on:
                row += f"{C_LOGO}█{RESET}"
            elif t_on:
                row += f"{C_LOGO}▀{RESET}"
            elif b_on:
                row += f"{C_LOGO}▄{RESET}"
            else:
                row += " "
        lines.append(row)
    return lines

# ── Smooth 60fps Blink & Wake-Up Animation ─────────────────────────────────────
def play_blink_sequence(cycles=2):
    """Plays realistic fast-close / eased-open blinks with zero flicker."""
    # Eased blink curve: quick snap shut (3 frames), brief hold, smooth elastic open (5 frames)
    blink_curve = [
        (1.00, 0.045),
        (0.68, 0.022),
        (0.28, 0.020),
        (0.00, 0.055),  # Eyelids fully closed
        (0.22, 0.022),
        (0.55, 0.024),
        (0.84, 0.026),
        (1.00, 0.040),
    ]

    sys.stdout.write(HIDE_CURSOR + CLEAR_ALL)
    sys.stdout.flush()
    try:
        for cycle in range(cycles):
            for openness, dt in blink_curve:
                frame_lines = ["\n\n"]
                for line in render_eye_block(w=34, h=16, openness=openness):
                    frame_lines.append(f"                         {line}")
                frame_lines.append(f"\n                         {C_LIME}●{RESET} {C_MUTED}anton-os runtime active{RESET}   ")
                sys.stdout.write(CURSOR_HOME + "\n".join(frame_lines))
                sys.stdout.flush()
                time.sleep(dt)
            if cycle < cycles - 1:
                time.sleep(0.32)  # Natural pause between double-blink
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

def play_opening_animation():
    sys.stdout.write(HIDE_CURSOR + CLEAR_ALL)
    sys.stdout.flush()
    try:
        # 1. Wake up from closed slit -> open -> double-blink -> glance -> settle
        timeline = [
            (0.00,  0.00, "initializing kernel...", 0.18),
            (0.20,  0.00, "initializing kernel...", 0.03),
            (0.55,  0.00, "loading neural runtime...", 0.03),
            (0.88,  0.00, "loading neural runtime...", 0.03),
            (1.00,  0.00, "calibrating vision...", 0.24),
            # Natural double-blink
            (0.60,  0.00, "calibrating vision...", 0.02),
            (0.00,  0.00, "calibrating vision...", 0.05),
            (0.45,  0.00, "calibrating vision...", 0.02),
            (1.00,  0.00, "scanning workspace...", 0.16),
            # Subtle pupil scan left -> right -> center
            (1.00, -0.08, "scanning workspace...", 0.13),
            (1.00,  0.08, "scanning workspace...", 0.13),
            (1.00,  0.00, "ready.", 0.14),
        ]

        for openness, dx, status, delay in timeline:
            buf = ["\n\n"]
            for line in render_eye_block(w=34, h=16, openness=openness, pupil_dx=dx):
                buf.append(f"                         {line}")
            buf.append(f"\n                         {C_LIME}●{RESET} {C_MUTED}{status:<28}{RESET}")
            sys.stdout.write(CURSOR_HOME + "\n".join(buf))
            sys.stdout.flush()
            time.sleep(delay)

        # 2. Typewriter brand reveal
        title = "A N T O N   O S"
        eye_static = [f"                         {l}" for l in render_eye_block(w=34, h=16, openness=1.0)]
        for i in range(1, len(title) + 1):
            cursor = f"{C_LIME}█{RESET}" if i < len(title) else " "
            buf = ["\n\n"] + eye_static + [
                f"\n                        {BOLD}{C_TEXT}{title[:i]}{RESET}{cursor}              ",
                f"                    {C_MUTED}Autonomous Engineering SDK v1.4.2{RESET}   ",
            ]
            sys.stdout.write(CURSOR_HOME + "\n".join(buf))
            sys.stdout.flush()
            time.sleep(0.028)
        time.sleep(0.35)
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

# ── Main Dashboard & Interactive Loop ──────────────────────────────────────────
def render_header(model="anton-sonnet-4.6", mode="AGENT", tokens_used=14.2, tokens_max=200.0):
    box_w = 86
    eye = render_eye_block(w=28, h=13, openness=1.0)
    cwd = os.path.basename(os.getcwd()) or "anton-os"

    ratio = min(1.0, tokens_used / tokens_max)
    filled = max(1, int(ratio * 10))
    bar = f"{C_LIME}{'▰' * filled}{C_BORDER}{'▱' * (10 - filled)}{RESET}"

    mode_badge = (
        f"{BG_LIME_PILL}{C_LIME}{BOLD} ● {mode} {RESET}"
        if mode == "AGENT"
        else f"{BG_CARD}{C_ICE}{BOLD} ◈ {mode} {RESET}"
    )

    info = [
        f"{BOLD}{C_TEXT}ANTON OS{RESET}  {C_MUTED}v1.4.2{RESET}   {mode_badge}",
        f"{C_SUBTEXT}Autonomous Engineering Environment & SDK{RESET}",
        f"{C_BORDER}{'─' * 46}{RESET}",
        f"{C_MUTED}Model     {RESET} {C_TEXT}{model}{RESET} {C_LIME_SOFT}✦ thinking{RESET}",
        f"{C_MUTED}Workspace {RESET} {C_ICE}~/{cwd}{RESET} {C_MUTED}(git: {C_MINT}main{C_MUTED}){RESET}",
        f"{C_MUTED}Context   {RESET} {bar}  {C_TEXT}{tokens_used:.1f}k{C_MUTED}/{tokens_max:.0f}k{RESET}",
        f"{C_MUTED}Servers   {RESET} {C_MINT}●{C_SUBTEXT} filesystem  {C_MINT}●{C_SUBTEXT} github  {C_MINT}●{C_SUBTEXT} postgres{RESET}",
        f"{C_BORDER}{'─' * 46}{RESET}",
        f"{C_LIME}/blink{C_MUTED} replay blink  {C_LIME}/plan{C_MUTED} mode    {C_LIME}/model{C_MUTED} switch{RESET}",
        f"{C_LIME}/demo{C_MUTED} preview task   {C_LIME}/clear{C_MUTED} reset  {C_LIME}/exit{C_MUTED} quit{RESET}",
        "",
        "",
        "",
    ]

    print(f"\n  {C_BORDER}╭{'─' * box_w}╮{RESET}")
    print(f"  {C_BORDER}│{' ' * box_w}│{RESET}")
    for l_line, r_line in zip(eye, info):
        content = f"   {l_line}     {r_line}"
        print(f"  {C_BORDER}│{RESET}{pad(content, box_w)}{C_BORDER}│{RESET}")
    print(f"  {C_BORDER}│{' ' * box_w}│{RESET}")
    print(f"  {C_BORDER}╰{'─' * box_w}╯{RESET}\n")

def main():
    play_opening_animation()
    model = "anton-sonnet-4.6"
    mode = "AGENT"
    tokens = 14.2

    sys.stdout.write(CLEAR_ALL)
    sys.stdout.flush()
    render_header(model=model, mode=mode, tokens_used=tokens)

    while True:
        try:
            box_w = 86
            print(f"  {C_BORDER}╭{'─' * box_w}╮{RESET}")
            prompt = input(f"  {C_BORDER}│{RESET} {C_LIME}❯{RESET} ").strip()
            print(f"  {C_BORDER}╰{'─' * box_w}╯{RESET}\n")

            if not prompt:
                continue
            if prompt in ("/exit", "/quit"):
                print(f"  {C_MUTED}Session saved. Goodbye.{RESET}\n")
                break
            elif prompt == "/blink":
                play_blink_sequence(cycles=2)
                sys.stdout.write(CLEAR_ALL)
                sys.stdout.flush()
                render_header(model=model, mode=mode, tokens_used=tokens)
            elif prompt == "/clear":
                sys.stdout.write(CLEAR_ALL)
                sys.stdout.flush()
                render_header(model=model, mode=mode, tokens_used=tokens)
            elif prompt == "/plan":
                mode = "PLAN" if mode == "AGENT" else "AGENT"
                print(f"  {C_ICE}◈{RESET} Switched mode to {BOLD}{C_TEXT}{mode}{RESET}\n")
            elif prompt == "/model":
                model = "anton-opus-4.6" if model == "anton-sonnet-4.6" else "anton-sonnet-4.6"
                print(f"  {C_LIME}✦{RESET} Switched model to {BOLD}{C_TEXT}{model}{RESET}\n")
            else:
                print(f"  {C_LIME}✦{RESET} {BOLD}{C_TEXT}Anton{RESET} {C_SUBTEXT}received:{RESET} {C_TEXT}{prompt}{RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {C_MUTED}Interrupted.{RESET}\n")
            break

if __name__ == "__main__":
    main()