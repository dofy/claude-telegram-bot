"""Centralized color palette for the admin UI.

All color values used by panels and plugin UIs are defined here.
To change the overall look, edit ONLY this file.
"""

# ── Core ──────────────────────────────────────────────────────────────────────

ACCENT = "#22c55e"          # terminal green (green-500)
ICON_MUTED = "#4ade80"      # lighter green (green-400) for icons

# ── Quasar props shortcuts ────────────────────────────────────────────────────

SWITCH = "dense color=green"
BTN_PRIMARY = "color=green"
BTN_FLAT_PRIMARY = "flat color=green"
BTN_DANGER = "color=grey"
BTN_FLAT_DANGER = "flat dense round size=sm color=grey"

# ── Dashboard stat cards (tailwind color name, used as bg-{C}-900/20 etc.) ───

STAT_UPTIME = "green"
STAT_MESSAGES = "green"
STAT_CLAUDE = "green"
STAT_AVG = "green"
STAT_SESSIONS = "green"

# ── Scheduler badges (Quasar color names) ─────────────────────────────────────

TASK_TYPE_COLORS = {"once": "green", "interval": "green", "daily": "green"}
TASK_MODE_COLORS = {"remind": "green", "ask": "light-green"}

# ── Plugin list ───────────────────────────────────────────────────────────────

BADGE_CORE = "green"

# ── Login ─────────────────────────────────────────────────────────────────────

LOGIN_ICON_CLS = "text-green-500"

# ── Extra CSS injected into theme ─────────────────────────────────────────────

_MONO = "'JetBrains Mono','Fira Code','Cascadia Code','SF Mono','Consolas','Menlo',monospace"
EXTRA_CSS = (
    f"body,.q-btn,.q-card,.q-field,.q-tab-panel,.q-badge,.q-table,"
    f"input,textarea,select,label,span,p,div,h1,h2,h3,h4,h5,h6"
    f"{{font-family:{_MONO}!important}}"
    f".material-icons,.material-symbols-outlined,.q-icon"
    f"{{font-family:'Material Icons'!important}}"
)
