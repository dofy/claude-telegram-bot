"""Centralized color palette for the admin UI.

All color values used by panels and plugin UIs are defined here.
To change the overall look, edit ONLY this file.
"""

# ── Mode ─────────────────────────────────────────────────────────────────────

DARK_MODE = False

# ── Core ──────────────────────────────────────────────────────────────────────

ACCENT = "#dc2626"          # red-600, primary accent
ICON_MUTED = "#6b7280"      # gray-500, muted icons

# ── Quasar props shortcuts ────────────────────────────────────────────────────

SWITCH = "dense color=red"
BTN_PRIMARY = "color=red"
BTN_FLAT_PRIMARY = "flat color=red"
BTN_DANGER = "color=grey"
BTN_FLAT_DANGER = "flat dense round size=sm color=grey"

# ── Dashboard stat cards (tailwind color name, used as bg-{C}-900/20 etc.) ───

STAT_UPTIME = "red"
STAT_MESSAGES = "slate"
STAT_CLAUDE = "red"
STAT_AVG = "slate"
STAT_SESSIONS = "red"

# ── Scheduler badges (Quasar color names) ─────────────────────────────────────

TASK_TYPE_COLORS = {"once": "red", "interval": "red", "daily": "red"}
TASK_MODE_COLORS = {"remind": "red", "ask": "red"}

# ── Plugin list ───────────────────────────────────────────────────────────────

BADGE_CORE = "red"

# ── Login ─────────────────────────────────────────────────────────────────────

LOGIN_ICON_CLS = "text-red-600"

# ── Header ────────────────────────────────────────────────────────────────────

HEADER_CLASSES = "items-center bg-white border-b border-gray-200 px-4"
HEADER_TITLE_CLS = "text-sm font-bold ml-1 text-gray-800"

# ── hljs style (light) ───────────────────────────────────────────────────────

HLJS_CSS_URL = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css"

CODE_BG = "#f6f8fa"
CODE_FG = "#24292e"

# ── Extra CSS injected into theme ─────────────────────────────────────────────

_MONO = "'JetBrains Mono','Fira Code','Cascadia Code','SF Mono','Consolas','Menlo',monospace"
INPUT_PROPS = "outlined dense"

EXTRA_CSS = (
    f"body,.q-btn,.q-card,.q-field,.q-tab-panel,.q-badge,.q-table,"
    f"input,textarea,select,label,span,p,div,h1,h2,h3,h4,h5,h6"
    f"{{font-family:{_MONO}!important}}"
    f".material-icons,.material-symbols-outlined,.q-icon"
    f"{{font-family:'Material Icons'!important}}"
    f"body{{background:#f5f5f5!important}}"
    f".q-header{{box-shadow:0 1px 3px rgba(0,0,0,.08)!important}}"
    f".q-card{{background:#fff!important;border:1px solid #e5e7eb!important;"
    f"box-shadow:0 1px 2px rgba(0,0,0,.04)!important}}"
    f"pre code.hljs{{background:{CODE_BG}!important;color:{CODE_FG}!important}}"
    f"pre{{background:{CODE_BG}!important}}"
    f".hljs{{background:{CODE_BG}!important;color:{CODE_FG}!important}}"
    f".q-field--outlined .q-field__control{{background:#fafafa!important}}"
)
