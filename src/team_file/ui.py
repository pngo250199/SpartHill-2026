"""Tandem look and feel: CSS plus small HTML builders.

Pure presentation. No database or permission logic lives here; app.py decides what to show
and passes plain values in. Every user-supplied string goes through esc().
"""
from html import escape as esc

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink: #101828;  --muted: #667085;  --line: #E4E7EC;  --canvas: #F6F7F9;  --panel: #FFFFFF;
  --nav: #0E2238;  --nav-text: #C3CFDD;
  --blue: #0055A2; --blue-soft: #EAF2FA;  --gold: #E5A823;
  --ok: #1B7F5F;   --ok-soft: #E6F4EE;  --warn: #B42318;  --warn-soft: #FDECEA;  --amber-soft: #FEF3D7; --amber: #8A5A00;
  --text-2: #344054; --icon: #667085; --hover: #F2F4F7; --active: #EAECF0;
  --chip-plain-bg: #EEF0F3; --chip-plain-fg: #475467; --box-border: #C5CBD3; --tip-bg: #FFFFFF;
  --stu-bg: #CFE0F3; --men-bg: #FBE7B5; --on-ok: #FFFFFF; --on-blue: #FFFFFF;
  --shadow-sm: 0 1px 2px rgba(16,24,40,0.05); --shadow-md: 0 4px 12px rgba(16,24,40,0.12);
  --font: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

.stApp { background: var(--canvas); font-family: var(--font); color: var(--ink); }
.stApp p, .stApp label, .stApp li { font-family: var(--font); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1180px; padding: 1.4rem 2rem 4rem; }
h1, h2, h3, h4 { font-family: var(--font); font-weight: 600; letter-spacing: -0.01em; color: var(--ink); }

/* ---------- sidebar: a floating light panel; collapses to an icon rail ---------- */
section[data-testid="stSidebar"] { background: var(--canvas); border-right: 0; }
section[data-testid="stSidebar"] > div:first-child {
  background: var(--panel); border: 1px solid var(--line); border-radius: 14px; margin: 10px;
  width: calc(100% - 20px) !important; box-sizing: border-box; height: calc(100vh - 20px); box-shadow: var(--shadow-sm); }
section[data-testid="stSidebar"] * { font-family: var(--font); }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important; }
[data-testid="stSidebarResizeHandle"], [data-testid="stSidebarResizer"] { display: none; }
@media (min-width: 900px) {
  [data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] { display: none; }
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.tn-brand) { margin-bottom: 0 !important; }
.tn-brand { display: flex; align-items: center; justify-content: flex-start; padding: 0 2.6rem 0 0.65rem; min-height: 2.2rem; }
.tn-brand b { color: var(--ink); font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }
.tn-brand i { width: 26px; height: 26px; border-radius: 8px; background: var(--blue); display: grid; place-items: center;
  font-style: normal; font-weight: 600; color: #fff; font-size: 0.9rem; flex: none; }
.tn-navhead { font-size: 0.78rem; color: var(--muted); padding: 1rem 0.6rem 0.3rem; }
.tn-sep { height: 1px; background: var(--line); margin: 0.6rem 0.4rem; }
[class*="st-key-nav_"] button, [class*="st-key-navon_"] button {
  width: 100%; justify-content: flex-start; background: transparent !important; border: 0 !important; border-radius: 8px;
  padding: 0.5rem 0.65rem; min-height: 0; color: var(--text-2); font-weight: 500; box-shadow: none; }
[class*="st-key-nav"] button p { font-size: 0.92rem; text-align: left; }
[class*="st-key-nav"] button div { justify-content: flex-start !important; text-align: left; }
[class*="st-key-nav_"] button:hover { background: var(--hover) !important; color: var(--ink); }
[class*="st-key-navon_"] button { background: var(--active) !important; color: var(--ink); font-weight: 600; }
[class*="st-key-nav"] button [data-testid="stIconMaterial"] { color: var(--icon); }
[class*="st-key-navon_"] button [data-testid="stIconMaterial"] { color: var(--ink); }
section[data-testid="stSidebar"] > div:first-child { position: relative; }
[class*="st-key-railtoggle"] { position: absolute; top: 5px; right: 12px; width: auto !important; z-index: 2; }
[class*="st-key-railtoggle"] button { background: transparent !important; border: 0 !important; color: var(--icon); padding: 0.3rem; min-height: 0; box-shadow: none; }
[class*="st-key-railtoggle"] button:hover { background: var(--hover) !important; color: var(--ink); }
.tn-me { display: flex; gap: 0.65rem; align-items: center; padding: 0.9rem 0.4rem 0.6rem; border-top: 1px solid var(--line); margin-top: 1rem; }
.tn-me b { display: block; color: var(--ink); font-size: 0.9rem; font-weight: 600; line-height: 1.2; }
.tn-me small { color: var(--muted); font-size: 0.78rem; }
[class*="st-key-logout"] button div { justify-content: flex-start !important; }
[class*="st-key-logout"] button { border: 0 !important; background: transparent !important; color: var(--icon); justify-content: flex-start; padding: 0.45rem 0.65rem; box-shadow: none; }
[class*="st-key-logout"] button:hover { background: var(--hover) !important; color: var(--warn); }

/* ---------- page header + KPI strip ---------- */
.tn-head { display: flex; flex-wrap: wrap; gap: 1rem; justify-content: space-between; align-items: flex-end; margin-bottom: 1.1rem; }
.tn-head h1 { font-size: 1.65rem; margin: 0; line-height: 1.15; }
.tn-head p { margin: 0.3rem 0 0; color: var(--muted); font-size: 0.95rem; max-width: 60ch; }
.tn-kpis { display: flex; flex-wrap: wrap; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; margin-bottom: 1rem; }
.tn-kpi { flex: 1 1 140px; padding: 0.9rem 1.2rem; border-right: 1px solid var(--line); }
.tn-kpi:last-child { border-right: 0; }
.tn-kpi b { display: block; font-size: 1.55rem; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; }
.tn-kpi span { color: var(--muted); font-size: 0.84rem; }

/* ---------- panels ---------- */
[class*="st-key-card_"] { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 1.1rem 1.25rem !important; margin-bottom: 0.4rem; }
[class*="st-key-card_"] [data-testid="stMarkdownContainer"], [class*="st-key-nav"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.tn-title { font-weight: 600; font-size: 0.98rem; margin: 0 0 0.7rem; }
.tn-title small { color: var(--muted); font-weight: 400; margin-left: 0.4rem; }

.tn-chip { display: inline-block; font-size: 0.78rem; font-weight: 500; padding: 0.15rem 0.6rem; margin: 0 0.3rem 0.3rem 0;
  border-radius: 6px; background: var(--blue-soft); color: var(--blue); }
.tn-chip.ok { background: var(--ok-soft); color: var(--ok); }
.tn-chip.warn { background: var(--warn-soft); color: var(--warn); }
.tn-chip.amber { background: var(--amber-soft); color: var(--amber); }
.tn-chip.plain { background: var(--chip-plain-bg); color: var(--chip-plain-fg); }
.tn-avatar { border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 600; flex: none; object-fit: cover; }

/* ---------- route ---------- */
.tn-route { display: flex; padding: 0.2rem 0 0; }
.tn-stop { flex: 1; text-align: center; position: relative; padding: 0 0.35rem; }
.tn-stop::before { content: ''; position: absolute; top: 11px; left: -50%; width: 100%; height: 2px; background: var(--line); }
.tn-stop:first-child::before { display: none; }
.tn-stop.done::before, .tn-stop.current::before, .tn-stop.flag::before { background: var(--blue); }
.tn-dot { width: 24px; height: 24px; border-radius: 50%; margin: 0 auto 0.5rem; display: grid; place-items: center; position: relative; z-index: 1;
  font-size: 0.74rem; font-weight: 600; background: var(--panel); border: 2px solid var(--line); color: var(--muted); }
.tn-stop.done .tn-dot { background: var(--blue); border-color: var(--blue); color: var(--on-blue); }
.tn-stop.current .tn-dot { background: var(--gold); border-color: var(--gold); color: var(--nav); box-shadow: 0 0 0 4px var(--amber-soft); }
.tn-stop.flag .tn-dot { background: var(--warn-soft); border-color: var(--warn); color: var(--warn); }
.tn-stop .name { font-weight: 500; font-size: 0.85rem; line-height: 1.25; }
.tn-stop .when { font-size: 0.78rem; color: var(--muted); margin-top: 0.1rem; }
.tn-stop.todo .name { color: var(--muted); }
@media (max-width: 760px) {
  .tn-route { flex-direction: column; gap: 0.8rem; }
  .tn-stop { text-align: left; display: flex; gap: 0.7rem; }
  .tn-stop::before { display: none; }
  .tn-dot { margin: 0; }
}

/* ---------- people, rows, bars ---------- */
.tn-person { display: flex; gap: 0.95rem; align-items: flex-start; }
.tn-person h3 { margin: 0; font-size: 1.1rem; }
.tn-person .meta { color: var(--muted); font-size: 0.9rem; margin: 0.1rem 0 0.55rem; }
.tn-why { border-left: 3px solid var(--blue); padding: 0.1rem 0 0.1rem 0.8rem; font-size: 0.9rem; margin-top: 0.7rem; color: var(--text-2); }
.tn-why b { color: var(--ink); font-weight: 600; }
.tn-bar { height: 6px; background: var(--line); border-radius: 99px; overflow: hidden; margin-top: 0.3rem; max-width: 320px; }
.tn-bar > i { display: block; height: 100%; background: var(--blue); }
.tn-row { padding: 0.55rem 0; border-top: 1px solid var(--line); font-size: 0.92rem; display: flex; gap: 0.7rem; align-items: baseline; }
.tn-row:first-child { border-top: 0; padding-top: 0; }
.tn-row .n { color: var(--muted); font-variant-numeric: tabular-nums; min-width: 1.4rem; }
.tn-next { display: flex; gap: 0.85rem; align-items: center; }
.tn-date { width: 52px; text-align: center; border-radius: 8px; overflow: hidden; border: 1px solid var(--line); flex: none; }
.tn-date i { display: block; font-style: normal; background: var(--nav); color: #fff; font-size: 0.7rem; font-weight: 500; padding: 0.12rem 0; }
.tn-date b { display: block; font-size: 1.35rem; font-weight: 600; padding: 0.15rem 0; font-variant-numeric: tabular-nums; }
.tn-attn { display: flex; gap: 0.8rem; align-items: center; padding: 0.6rem 0; border-top: 1px solid var(--line); font-size: 0.93rem; }
.tn-attn:first-child { border-top: 0; padding-top: 0; }
.tn-count { min-width: 2rem; text-align: center; padding: 0.1rem 0.4rem; border-radius: 6px; font-weight: 600; font-variant-numeric: tabular-nums;
  background: var(--warn-soft); color: var(--warn); }
.tn-count.zero { background: var(--ok-soft); color: var(--ok); }
.tn-upd { padding: 0.55rem 0; border-top: 1px solid var(--line); font-size: 0.88rem; }
.tn-upd:first-child { border-top: 0; padding-top: 0; }
.tn-upd small { color: var(--muted); display: block; }
.tn-empty { color: var(--muted); font-size: 0.9rem; }


/* checklist + lesson progress */
.tn-check { display: flex; gap: 0.65rem; align-items: flex-start; padding: 0.5rem 0; border-top: 1px solid var(--line); font-size: 0.92rem; }
.tn-check:first-child { border-top: 0; padding-top: 0; }
.tn-box { width: 18px; height: 18px; border-radius: 5px; border: 2px solid var(--box-border); flex: none; margin-top: 2px; display: grid; place-items: center;
  font-size: 0.7rem; color: #fff; }
.tn-check.done .tn-box { background: var(--ok); border-color: var(--ok); }
.tn-check.done span:last-child { color: var(--muted); text-decoration: line-through; }
.tn-lesson { display: grid; grid-template-columns: minmax(0, 2.2fr) 112px minmax(90px, 1fr) minmax(90px, 1fr); gap: 1rem; align-items: center;
  padding: 0.7rem 0; border-top: 1px solid var(--line); font-size: 0.9rem; }
.tn-lesson:first-child { border-top: 0; padding-top: 0; }
.tn-lesson b { font-weight: 600; display: block; }
.tn-lesson small { color: var(--muted); }
.tn-lesson .lbl { font-size: 0.78rem; color: var(--muted); }
.tn-lesson.future { opacity: 0.65; }
@media (max-width: 760px) { .tn-lesson { grid-template-columns: 1fr 1fr; } }


/* schedule fit grid */
.tn-sched { margin-top: 0.7rem; }
.tn-sched table { border-collapse: separate; border-spacing: 3px; font-size: 0.72rem; color: var(--muted); }
.tn-sched th { font-weight: 500; text-align: center; padding: 0; }
.tn-sched td.t { text-align: right; padding-right: 4px; white-space: nowrap; }
.tn-sched td.c { width: 26px; height: 20px; border-radius: 5px; background: var(--hover); text-align: center; font-size: 0.7rem; }
.tn-sched.compact td.c { width: 20px; height: 15px; }
.tn-sched td.both { background: var(--ok); color: var(--on-ok); }
.tn-sched td.stu { background: var(--stu-bg); color: var(--blue); }
.tn-sched td.men { background: var(--men-bg); color: var(--amber); }
.tn-sched .legend { display: flex; gap: 0.8rem; flex-wrap: wrap; margin-top: 0.4rem; font-size: 0.74rem; color: var(--muted); }
.tn-sched .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }

/* tabs inside a page (for example the session list) */
[data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { font-weight: 500; color: var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--blue); }
[data-baseweb="tab-highlight"] { background: var(--blue); }
.main .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { border-radius: 8px; font-weight: 500; }
"""

AVATAR_COLORS = ["#0055A2", "#1B7F5F", "#5B4B9A", "#A8512D", "#2B7A9B"]


DARK_VARS = """
  --ink: #E7EDF4;  --muted: #9AA9BB;  --line: #2A3A4F;  --canvas: #0E1621;  --panel: #16212F;
  --nav: #0A1420;  --blue: #4A9DEB;  --blue-soft: #172F4A;  --gold: #E5A823;
  --ok: #3FBF98;   --ok-soft: #12332B;  --warn: #F0705F;  --warn-soft: #3A1D1A;  --amber-soft: #3A2F12;  --amber: #F2C25C;
  --text-2: #C3CEDB; --icon: #9AA9BB; --hover: #1F2E41; --active: #27394F;
  --chip-plain-bg: #243244; --chip-plain-fg: #B5C2D2; --box-border: #4B5B70; --tip-bg: #1F2E41;
  --stu-bg: #1D3A5C; --men-bg: #4A3A12; --on-ok: #06241B; --on-blue: #06182B;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.4); --shadow-md: 0 4px 14px rgba(0,0,0,0.5);
"""


THEME_SYNC_JS = """<script>
(function () {
  const p = window.parent, d = p.document;
  const lum = (rgb) => { const m = (rgb.match(/\\d+/g) || [255, 255, 255]).slice(0, 3).map(Number);
                         return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; };
  // Streamlit paints <body> with its own theme background and we never override it, so it tells us
  // which theme Streamlit is really showing (system setting, or a choice saved in the browser).
  const apply = () => d.documentElement.setAttribute(
    "data-tn", lum(p.getComputedStyle(d.body).backgroundColor) < 0.5 ? "dark" : "light");
  if (p.__tnStop) p.__tnStop();
  const mq = p.matchMedia("(prefers-color-scheme: dark)"), onMq = () => setTimeout(apply, 150);
  mq.addEventListener("change", onMq);
  const mo = new p.MutationObserver(apply);
  mo.observe(d.head, { childList: true, subtree: true, characterData: true });
  mo.observe(d.body, { attributes: true });
  const iv = setInterval(apply, 800);
  p.__tnStop = () => { mq.removeEventListener("change", onMq); mo.disconnect(); clearInterval(iv); };
  apply();
})();
</script>"""


def inject():
    """Light palette by default; dark palette whenever Streamlit itself is showing its dark theme.

    The theme is not always the system one: a choice saved in the browser overrides it. So a small
    script reads Streamlit's real theme and sets data-tn on <html>, live. Until it runs, the system
    setting is used.
    """
    st.markdown(f"<style>{CSS}\n:root[data-tn='dark'] {{ {DARK_VARS} }}\n"
                f"@media (prefers-color-scheme: dark) {{ :root:not([data-tn]) {{ {DARK_VARS} }} }}"
                "\n[data-testid='stElementContainer']:has(iframe[srcdoc*='data-tn']) { position: absolute; height: 0; margin: 0; overflow: hidden; }</style>",
                unsafe_allow_html=True)
    if hasattr(st, "iframe"):
        st.iframe(THEME_SYNC_JS, height=1, width=1)
    else:                                   # older Streamlit
        st.components.v1.html(THEME_SYNC_JS, height=0)


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def avatar(name, size=56, photo_uri=None):
    if photo_uri:
        return f'<img class="tn-avatar" src="{photo_uri}" alt="" style="width:{size}px;height:{size}px">'
    color = AVATAR_COLORS[sum(map(ord, name)) % len(AVATAR_COLORS)]
    return (f'<div class="tn-avatar" style="width:{size}px;height:{size}px;background:{color};'
            f'font-size:{size * 0.38:.0f}px">{esc(initials(name))}</div>')


def chip(text, tone=""):
    return f'<span class="tn-chip {tone}">{esc(str(text))}</span>'


def chips(items, tone=""):
    return "".join(chip(i, tone) for i in items)


def card_title(text, note=""):
    small = f"<small>{esc(note)}</small>" if note else ""
    html(f'<div class="tn-title">{esc(text)}{small}</div>')


def brand(rail=False):
    if not rail:
        html('<div class="tn-brand"><b>Tandem</b></div>')


def separator():
    html('<div class="tn-sep"></div>')


def rail_css(labels):
    """Icon-only sidebar: narrow width, text hidden. Each icon shows its name in a small label to its right on hover.

    Streamlit's own tooltip always opens above the button and covers the icon, so these labels are CSS.
    position: fixed lets the label escape the sidebar's scroll clipping; with no top/left set it stays
    beside the icon it belongs to.
    """
    names = {f"nav_{i}": t for i, t in enumerate(labels)} | {f"navon_{i}": t for i, t in enumerate(labels)}
    names |= {"logout": "Log out", "railtoggle": "Expand sidebar"}
    tips = "\n".join(f'.st-key-{k}::after {{ content: "{esc(t)}"; }}' for k, t in names.items())
    st.markdown("""<style>
section[data-testid="stSidebar"] { width: 84px !important; min-width: 84px !important; max-width: 84px !important; }
[class*="st-key-nav"] button p, [class*="st-key-logout"] button p { display: none; }
[class*="st-key-nav"] button, [class*="st-key-logout"] button, [class*="st-key-railtoggle"] button { justify-content: center !important; }
.tn-me { justify-content: center; }
[class*="st-key-railtoggle"] { position: static !important; top: auto; right: auto; width: 100% !important; display: flex; justify-content: center; margin-top: 16px; margin-bottom: -8px; }
[class*="st-key-nav"] button div, [class*="st-key-logout"] button div { justify-content: center !important; }
[class*="st-key-nav"] button [data-testid="stMarkdownContainer"], [class*="st-key-logout"] button [data-testid="stMarkdownContainer"] { display: none !important; }
[class*="st-key-nav"] button, [class*="st-key-logout"] button { gap: 0 !important; }
[class*="st-key-nav"] button [data-testid="stIconMaterial"], [class*="st-key-logout"] button [data-testid="stIconMaterial"] { margin: 0 !important; }
[class*="st-key-railtoggle"] button { width: 100%; padding: 0.5rem 0.65rem; }
[class*="st-key-nav"], [class*="st-key-logout"], [class*="st-key-railtoggle"] { display: flex; align-items: center; }
[class*="st-key-nav"]::after, [class*="st-key-logout"]::after, [class*="st-key-railtoggle"]::after {
  position: fixed; margin-left: 58px; white-space: nowrap; pointer-events: none; opacity: 0; z-index: 99999;
  background: var(--tip-bg); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 0.3rem 0.65rem;
  font-size: 0.85rem; font-weight: 500; box-shadow: var(--shadow-md); transition: opacity 0.12s; }
[class*="st-key-nav"]:hover::after, [class*="st-key-logout"]:hover::after, [class*="st-key-railtoggle"]:hover::after { opacity: 1; }
""" + tips + "</style>", unsafe_allow_html=True)


def nav_heading(text):
    html(f'<div class="tn-navhead">{esc(text)}</div>')


def me_block(name, role, photo_uri=None, rail=False):
    text = "" if rail else f'<div><b>{esc(name)}</b><small>{esc(role)}</small></div>'
    html(f'<div class="tn-me">{avatar(name, 34, photo_uri)}{text}</div>')


def page_header(title, subtitle="", chips_html=""):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    html(f'<div class="tn-head"><div><h1>{esc(title)}</h1>{sub}</div><div>{chips_html}</div></div>')


def kpis(items):
    if items:
        html('<div class="tn-kpis">' + "".join(f'<div class="tn-kpi"><b>{esc(str(v))}</b><span>{esc(k)}</span></div>'
                                              for k, v in items) + '</div>')


def route(stops):
    """stops: list of dicts {name, when, state}; state is done | current | todo | flag."""
    out = []
    for n, s in enumerate(stops, 1):
        mark = "✓" if s["state"] == "done" else "!" if s["state"] == "flag" else n
        out.append(f'<div class="tn-stop {s["state"]}"><div class="tn-dot">{mark}</div>'
                   f'<div><div class="name">{esc(s["name"])}</div><div class="when">{esc(s["when"])}</div></div></div>')
    html(f'<div class="tn-route">{"".join(out)}</div>')


def person(name, meta, tags, why=None, extra="", photo_uri=None):
    why_html = f'<div class="tn-why"><b>Why you were matched.</b> {esc(why)}</div>' if why else ""
    html(f'<div class="tn-person">{avatar(name, 52, photo_uri)}<div style="flex:1;min-width:0">'
         f'<h3>{esc(name)}</h3><div class="meta">{esc(meta)}</div>{chips(tags)}{extra}{why_html}</div></div>')


def numbered(items):
    html("".join(f'<div class="tn-row"><span class="n">{i}</span><span>{esc(t)}</span></div>' for i, t in items))


def checklist(items):
    """items: list of (text, done)."""
    html("".join(f'<div class="tn-check {"done" if d else ""}"><span class="tn-box">{"✓" if d else ""}</span>'
                 f'<span>{esc(t)}</span></div>' for t, d in items))


def lesson_rows(rows):
    """rows: dicts {name, when, status, tone, pre:(done,total), post:(done,total), future}."""
    def bar(label, pair):
        done, total = pair
        pct = int(100 * done / total) if total else 0
        return (f'<div><span class="lbl">{esc(label)} {done}/{total}</span>'
                f'<div class="tn-bar" style="max-width:none"><i style="width:{pct}%"></i></div></div>')
    html("".join(f'<div class="tn-lesson {"future" if r["future"] else ""}"><div><b>{esc(r["name"])}</b>'
                 f'<small>{esc(r["when"])}</small></div>{chip(r["status"], r["tone"])}'
                 f'{bar("Prework", r["pre"])}{bar("Postwork", r["post"])}</div>' for r in rows))


def schedule_grid(student_slots, mentor_slots, days, times, student_name, mentor_name, shared, compact=False):
    """Weekly grid: green where both are free, blue where only the student is, amber where only the mentor is."""
    head = "".join(f"<th>{esc(d)}</th>" for d in days)
    rows = []
    for t in times:
        cells = []
        for d in days:
            slot, st_, mt_ = f"{d} {t}", f"{d} {t}" in student_slots, f"{d} {t}" in mentor_slots
            cls, mark = ("both", "✓") if st_ and mt_ else ("stu", "") if st_ else ("men", "") if mt_ else ("", "")
            tip = (f"{slot}: both free" if st_ and mt_ else f"{slot}: only {student_name}" if st_
                   else f"{slot}: only {mentor_name}" if mt_ else f"{slot}: neither")
            cells.append(f'<td class="c {cls}" title="{esc(tip)}">{mark}</td>')
        rows.append(f'<tr><td class="t">{esc(t[:3] if compact else t)}</td>{"".join(cells)}</tr>')
    tone = "ok" if shared >= 3 else "amber" if shared >= 1 else "warn"
    summary = chip(f"{shared} shared time{'s' if shared != 1 else ''}" if shared else "No shared times", tone)
    legend = ('' if compact else
              f'<div class="legend"><span><i style="background:var(--ok)"></i>Both free</span>'
              f'<span><i style="background:var(--stu-bg)"></i>Only {esc(student_name)}</span>'
              f'<span><i style="background:var(--men-bg)"></i>Only {esc(mentor_name)}</span></div>')
    html(f'<div class="tn-sched {"compact" if compact else ""}">{summary}'
         f'<table><tr><th></th>{head}</tr>{"".join(rows)}</table>{legend}</div>')


def progress_line(label, pct):
    pct = max(0, min(100, int(pct)))
    return (f'<div style="font-size:0.85rem;color:var(--muted);margin-top:0.55rem">{esc(label)}</div>'
            f'<div class="tn-bar"><i style="width:{pct}%"></i></div>')


def next_session(month, day, title, detail):
    html(f'<div class="tn-next"><div class="tn-date"><i>{esc(month)}</i><b>{esc(day)}</b></div>'
         f'<div><b style="font-weight:600">{esc(title)}</b>'
         f'<div style="color:var(--muted);font-size:0.88rem">{detail}</div></div></div>')


def attention(rows):
    """rows: list of (count, text)."""
    html("".join(f'<div class="tn-attn"><span class="tn-count {"" if n else "zero"}">{n}</span>'
                 f'<span>{esc(t)}</span></div>' for n, t in rows))


def updates(items):
    if not items:
        html('<div class="tn-empty">Nothing new yet. Reminders and match news will show up here.</div>')
        return
    html("".join(f'<div class="tn-upd"><b style="font-weight:500">{esc(s)}</b><small>{esc(a)}</small></div>'
                 for s, a in items))


def hero(title, subtitle, stats):
    page_header(title, subtitle)
    kpis(stats)


def profile(name, role, sub, tags, photo_uri=None):
    html(
        f'<div class="tn-profile">'
        f'{avatar(name, 84, photo_uri)}'
        f'<h3>{esc(name)}</h3>'
        f'<div class="sub">{esc(sub)}</div>'
        f'{chip(role, "gold")}'
        f'<div style="margin-top:0.7rem">{chips(tags)}</div>'
        f'</div>'
    )

