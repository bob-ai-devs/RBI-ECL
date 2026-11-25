"""Bank of Baroda palette (vermilion, red, golden yellow, orange, blue) and Streamlit CSS."""
NAVY, ORANGE, VERMILION, RED, GOLD, CREAM, INK = "#0A2A66", "#F26B21", "#E4402A", "#C8102E", "#FDB515", "#FFF8F0", "#1F2937"

CSS = f"""
<style>
.block-container{{padding-top:1.2rem;max-width:1500px}}
[data-testid="stSidebar"]{{background:linear-gradient(180deg,{NAVY} 0%,#0c3277 100%)}}
[data-testid="stSidebar"] *{{color:#888}}
[data-testid="stSidebar"] .stButton>button,[data-testid="stSidebar"] .stDownloadButton>button{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.35);color:#fff}}
[data-testid="stSidebar"] .stButton>button:hover{{background:{GOLD};color:{NAVY};border-color:{GOLD}}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{{background:rgba(255,255,255,.08);border:1px dashed {GOLD}}}
[data-testid="stSidebar"] textarea,[data-testid="stSidebar"] input{{color:{INK}!important}}
.hero{{background:linear-gradient(115deg,{VERMILION} 0%,{ORANGE} 58%,{GOLD} 100%);border-bottom:6px solid {NAVY};border-radius:14px;padding:22px 30px;color:#fff;margin-bottom:14px;position:relative;overflow:hidden}}
.hero:after{{content:"";position:absolute;right:-40px;top:-60px;width:260px;height:260px;border-radius:50%;background:rgba(255,255,255,.12)}}
.hero small{{letter-spacing:.16em;font-weight:700;font-size:11px;opacity:.95}}
.hero h1{{margin:4px 0 4px;font-size:30px;color:#fff;padding:0}}
.hero p{{margin:0;max-width:880px;opacity:.97;font-size:14px}}
.tile{{border:1px solid #E5D9CC;border-top:5px solid {ORANGE};border-radius:12px;padding:10px 14px;background:#fff;height:100%}}
.tile.on{{border-top-color:{NAVY};background:{CREAM}}}
.tile b{{color:{NAVY};font-size:13.5px}}
.tile .st{{font-size:12px;color:#6B7280}}
.tile .pc{{font-size:24px;font-weight:800;color:{VERMILION}}}
.tile .bar{{height:6px;background:#eee;border-radius:5px;overflow:hidden;margin-top:4px}}
.tile .bar i{{display:block;height:100%;background:linear-gradient(90deg,{VERMILION},{ORANGE},{GOLD})}}
.panel{{border:1px solid #E5D9CC;border-left:6px solid {ORANGE};border-radius:12px;padding:6px 16px 2px;background:#fff;margin-bottom:10px}}
h3.sub{{color:{NAVY};border-bottom:3px solid {GOLD};display:inline-block;padding-bottom:2px;margin:6px 0 10px;font-size:18px}}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{{background:linear-gradient(100deg,{VERMILION},{ORANGE});border:0;color:#fff;font-weight:700}}
.stButton>button[kind="primary"]:hover{{filter:brightness(1.07)}}
.stButton>button,.stDownloadButton>button{{border-radius:10px}}
</style>
"""


def hero(title: str, subtitle: str) -> str:
    return f'<div class="hero"><small>BANK OF BARODA · MODEL RISK MANAGEMENT · CREDIT RISK ANALYTICS</small><h1>{title}</h1><p>{subtitle}</p></div>'
