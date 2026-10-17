"""Global look & feel: deep-navy glass UI with violet/blue accents. Injected once per run."""
from __future__ import annotations

import streamlit as st

FONTS = (
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@500;600;700;800"
    "&family=JetBrains+Mono:wght@400;500&display=swap');"
    "@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&display=swap');"
)

CSS = FONTS + """
:root{
  --bg0:#060A19; --bg1:#0A1030; --bg2:#0F1840;
  --card:rgba(20,28,66,.58); --card2:rgba(28,38,86,.55); --solid:#10183c;
  --line:rgba(140,150,255,.14); --line2:rgba(140,150,255,.30);
  --txt:#E9ECFF; --txt2:#A9B2DE; --txt3:#7580B5;
  --v1:#8B5CF6; --v2:#6366F1; --b1:#3B82F6; --c1:#22D3EE;
  --ok:#34D399; --warn:#FBBF24; --bad:#F87171;
  --grad:linear-gradient(135deg,#8B5CF6 0%,#6366F1 48%,#3B82F6 100%);
  --radius:18px;
}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {font-family:'Inter',system-ui,sans-serif !important;}
.stApp{
  color:var(--txt);
  background:
    radial-gradient(1100px 560px at 6% -8%, rgba(139,92,246,.24), transparent 60%),
    radial-gradient(900px 520px at 104% 2%, rgba(59,130,246,.20), transparent 56%),
    radial-gradient(900px 600px at 50% 125%, rgba(34,211,238,.09), transparent 60%),
    var(--bg0);
  background-attachment:fixed;
}
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stToolbar"] {visibility:hidden; height:0;}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.6rem !important; padding-bottom:4rem; max-width:1280px;}
h1,h2,h3,h4{font-family:'Sora','Inter',sans-serif !important; letter-spacing:-.01em; color:var(--txt);}
h1{font-weight:800} h2,h3{font-weight:700}
p, li, label, span{color:inherit}
a{color:#9db4ff !important; text-decoration:none}
a:hover{color:#c4d0ff !important}
hr{border-color:var(--line) !important}
::-webkit-scrollbar{width:9px;height:9px} ::-webkit-scrollbar-thumb{background:rgba(139,92,246,.35);border-radius:9px} ::-webkit-scrollbar-track{background:transparent}

/* ---------------- sidebar ---------------- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0C1340 0%,#080D28 55%,#060A1D 100%);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] > div:first-child{padding-top:.6rem}
[data-testid="stSidebar"] .block-container{padding-top:1rem}
.mx-brand{display:flex;align-items:center;gap:12px;padding:6px 6px 16px 6px}
.mx-logo{width:42px;height:42px;border-radius:13px;background:var(--grad);display:grid;place-items:center;
  box-shadow:0 8px 24px rgba(99,102,241,.45), inset 0 1px 0 rgba(255,255,255,.35)}
.mx-logo svg{width:24px;height:24px}
.mx-brand-name{font-family:'Sora',sans-serif;font-weight:800;font-size:1.28rem;letter-spacing:-.02em;
  background:linear-gradient(90deg,#fff,#c7bbff);-webkit-background-clip:text;background-clip:text;color:transparent}
.mx-brand-sub{font-size:.72rem;color:var(--txt3);margin-top:-2px;letter-spacing:.04em}
.mx-nav-label{font-size:.68rem;letter-spacing:.14em;color:var(--txt3);text-transform:uppercase;margin:14px 6px 6px}
[data-testid="stSidebar"] .stButton{margin-bottom:-8px}
[data-testid="stSidebar"] .stButton>button{
  width:100%;justify-content:flex-start;text-align:left;gap:10px;border:1px solid transparent;
  background:transparent;color:var(--txt2);padding:.55rem .8rem;border-radius:12px;font-weight:500;font-size:.93rem;
  transition:all .18s ease;box-shadow:none;
}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(139,92,246,.12);color:#fff;border-color:var(--line);transform:translateX(2px)}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:linear-gradient(135deg,rgba(139,92,246,.30),rgba(59,130,246,.22));color:#fff;border:1px solid var(--line2);
  box-shadow:inset 3px 0 0 var(--v1), 0 6px 20px rgba(99,102,241,.18);
}
[data-testid="stSidebar"] .stButton>button p{font-size:.93rem}
.mx-side-card{margin:14px 4px 4px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.03);font-size:.8rem;color:var(--txt2)}
.mx-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:middle}
.mx-dot.on{background:var(--ok);box-shadow:0 0 10px var(--ok)} .mx-dot.off{background:#56608f}

/* ---------------- buttons & inputs ---------------- */
.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button, .stLinkButton>a{
  border-radius:12px;border:1px solid var(--line2);background:rgba(255,255,255,.04);color:var(--txt);font-weight:600;
  transition:all .18s ease;padding:.5rem 1rem;
}
.stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover, .stLinkButton>a:hover{
  border-color:#8f7bff;background:rgba(139,92,246,.16);color:#fff;transform:translateY(-1px);box-shadow:0 8px 22px rgba(99,102,241,.25)}
.stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"], .stDownloadButton>button[kind="primary"]{
  background:var(--grad);border:none;color:#fff;box-shadow:0 8px 26px rgba(99,102,241,.38);
}
.stButton>button[kind="primary"]:hover{filter:brightness(1.1);box-shadow:0 12px 32px rgba(99,102,241,.5)}
.stButton>button:disabled{opacity:.45;transform:none;box-shadow:none}
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input, .stTimeInput input,
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div, div[data-baseweb="textarea"]>div{
  background:rgba(10,16,48,.75) !important;border:1px solid var(--line) !important;border-radius:12px !important;color:var(--txt) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus{border-color:#8f7bff !important;box-shadow:0 0 0 3px rgba(139,92,246,.22) !important}
div[data-baseweb="popover"] ul{background:#0e1640 !important}
label[data-testid="stWidgetLabel"] p{color:var(--txt2);font-size:.82rem;font-weight:500}
[data-testid="stFileUploader"] section{background:rgba(139,92,246,.06);border:1.5px dashed rgba(139,92,246,.55);border-radius:18px;padding:1.4rem}
[data-testid="stFileUploader"] section:hover{background:rgba(139,92,246,.12);border-color:#a78bfa}
[data-testid="stFileUploader"] button{border-radius:10px}

/* ---------------- tabs / expander / containers ---------------- */
.stTabs [data-baseweb="tab-list"]{gap:6px;background:rgba(255,255,255,.035);padding:5px;border-radius:14px;border:1px solid var(--line);width:fit-content;max-width:100%;overflow-x:auto}
.stTabs [data-baseweb="tab"]{height:38px;border-radius:10px;padding:0 16px;color:var(--txt2);font-weight:600;background:transparent}
.stTabs [aria-selected="true"]{background:var(--grad) !important;color:#fff !important;box-shadow:0 6px 18px rgba(99,102,241,.35)}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none}
[data-testid="stExpander"]{border:1px solid var(--line) !important;border-radius:14px !important;background:var(--card);overflow:hidden}
[data-testid="stExpander"] summary:hover{color:#fff}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {border-radius:var(--radius)}
div[data-testid="stVerticalBlockBorderWrapper"][class*="st-emotion"]{border-color:var(--line) !important}
[data-testid="stForm"]{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:1.2rem}
[data-testid="stAlert"]{border-radius:14px;border:1px solid var(--line)}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px}
[data-testid="stDataFrame"], [data-testid="stDataEditor"]{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.stProgress > div > div > div{background:var(--grad)}
.stSlider [role="slider"]{background:var(--v1)}
[data-testid="stToast"]{border-radius:14px;border:1px solid var(--line2);background:#121a45}

/* ---------------- custom components ---------------- */
.mx-hero{position:relative;overflow:hidden;border-radius:26px;padding:34px 36px;margin-bottom:22px;border:1px solid var(--line2);
  background:linear-gradient(120deg,rgba(139,92,246,.30),rgba(59,130,246,.18) 55%,rgba(34,211,238,.10)), rgba(12,18,52,.8);
  box-shadow:0 24px 60px rgba(40,30,120,.35)}
.mx-hero:before,.mx-hero:after{content:"";position:absolute;border-radius:50%;filter:blur(40px);opacity:.55;animation:float 9s ease-in-out infinite}
.mx-hero:before{width:260px;height:260px;right:-60px;top:-90px;background:#7c5cff}
.mx-hero:after{width:200px;height:200px;right:180px;bottom:-110px;background:#2dd4ff;animation-delay:-4s}
.mx-hero h1{position:relative;margin:0 0 6px;font-size:2.15rem;line-height:1.15}
.mx-hero p{position:relative;margin:0;color:var(--txt2);max-width:640px;font-size:1.02rem}
.mx-hero .mx-grad{background:linear-gradient(90deg,#fff,#c4b5fd 55%,#7dd3fc);-webkit-background-clip:text;background-clip:text;color:transparent}
@keyframes float{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(18px) scale(1.07)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.block-container > div > div > div{animation:fadeUp .45s ease both}
.mx-pagehead{display:flex;align-items:center;gap:14px;margin:0 0 18px}
.mx-pagehead .ic{width:48px;height:48px;border-radius:15px;background:var(--grad);display:grid;place-items:center;box-shadow:0 10px 28px rgba(99,102,241,.4);flex:none}
.mx-pagehead .ic .material-symbols-rounded{font-size:26px;color:#fff}
.mx-pagehead h1{margin:0;font-size:1.65rem;line-height:1.15}
.mx-pagehead p{margin:2px 0 0;color:var(--txt2);font-size:.95rem}
.material-symbols-rounded{font-family:'Material Symbols Rounded' !important;font-weight:400;font-style:normal;line-height:1;display:inline-block;vertical-align:middle;
  font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24; letter-spacing:normal;text-transform:none;white-space:nowrap;direction:ltr}
.mx-grid{display:grid;gap:14px}
.mx-metric{position:relative;overflow:hidden;border-radius:var(--radius);padding:18px 18px 16px;border:1px solid var(--line);background:var(--card);
  backdrop-filter:blur(10px);transition:all .22s ease}
.mx-metric:hover{transform:translateY(-3px);border-color:var(--line2);box-shadow:0 16px 40px rgba(40,30,140,.3)}
.mx-metric .ic{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;margin-bottom:12px;
  background:linear-gradient(135deg,rgba(139,92,246,.35),rgba(59,130,246,.25));border:1px solid var(--line2)}
.mx-metric .ic .material-symbols-rounded{font-size:21px;color:#d9d1ff}
.mx-metric .v{font-family:'Sora',sans-serif;font-size:1.95rem;font-weight:800;line-height:1;color:#fff}
.mx-metric .l{font-size:.78rem;color:var(--txt2);margin-top:6px;font-weight:500;letter-spacing:.02em}
.mx-metric .s{font-size:.74rem;color:var(--txt3);margin-top:4px}
.mx-metric.good .ic{background:rgba(52,211,153,.16);border-color:rgba(52,211,153,.4)} .mx-metric.good .ic span{color:#6ee7b7}
.mx-metric.warn .ic{background:rgba(251,191,36,.14);border-color:rgba(251,191,36,.4)} .mx-metric.warn .ic span{color:#fcd34d}
.mx-metric.bad .ic{background:rgba(248,113,113,.14);border-color:rgba(248,113,113,.4)} .mx-metric.bad .ic span{color:#fca5a5}
.mx-card{border-radius:var(--radius);padding:18px 20px;border:1px solid var(--line);background:var(--card);backdrop-filter:blur(10px);margin-bottom:12px;transition:all .2s ease}
.mx-card.hover:hover{border-color:var(--line2);transform:translateY(-2px);box-shadow:0 14px 36px rgba(40,30,140,.28)}
.mx-card h4{margin:0 0 6px;font-size:1.02rem}
.mx-sub{color:var(--txt2);font-size:.86rem}
.mx-muted{color:var(--txt3);font-size:.8rem}
.mx-section{display:flex;align-items:center;gap:10px;margin:26px 0 12px}
.mx-section h3{margin:0;font-size:1.12rem}
.mx-section .material-symbols-rounded{color:#a78bfa;font-size:22px}
.mx-section .line{flex:1;height:1px;background:linear-gradient(90deg,var(--line2),transparent)}
.mx-chip{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:600;border:1px solid var(--line2);
  background:rgba(139,92,246,.14);color:#cfc4ff;white-space:nowrap}
.mx-chip .material-symbols-rounded{font-size:14px}
.mx-chip.ok{background:rgba(52,211,153,.13);border-color:rgba(52,211,153,.4);color:#7ee7bd}
.mx-chip.warn{background:rgba(251,191,36,.12);border-color:rgba(251,191,36,.4);color:#fcd34d}
.mx-chip.bad{background:rgba(248,113,113,.13);border-color:rgba(248,113,113,.4);color:#fca5a5}
.mx-chip.info{background:rgba(59,130,246,.15);border-color:rgba(59,130,246,.45);color:#93c5fd}
.mx-chip.mute{background:rgba(255,255,255,.05);border-color:var(--line);color:var(--txt2)}
.mx-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.mx-mcard{display:flex;gap:14px;align-items:flex-start}
.mx-mcard .date{flex:none;width:54px;text-align:center;border-radius:14px;padding:8px 0;border:1px solid var(--line2);background:rgba(139,92,246,.12)}
.mx-mcard .date b{display:block;font-family:'Sora';font-size:1.3rem;line-height:1;color:#fff}
.mx-mcard .date span{font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:#b8a9ff}
.mx-mcard .t{font-weight:700;color:#fff;font-size:1.02rem;margin-bottom:2px}
.mx-empty{text-align:center;padding:46px 20px;border:1.5px dashed var(--line2);border-radius:22px;background:rgba(139,92,246,.045)}
.mx-empty .ic{width:64px;height:64px;border-radius:20px;background:var(--grad);display:grid;place-items:center;margin:0 auto 14px;box-shadow:0 12px 32px rgba(99,102,241,.4)}
.mx-empty .ic .material-symbols-rounded{font-size:32px;color:#fff}
.mx-empty h3{margin:0 0 4px} .mx-empty p{margin:0 auto;color:var(--txt2);max-width:440px}
/* transcript */
.mx-tr{max-height:620px;overflow-y:auto;padding:6px 10px 6px 2px}
.mx-seg{display:flex;gap:12px;padding:11px 12px;border-radius:14px;margin-bottom:6px;border:1px solid transparent;transition:all .15s}
.mx-seg:hover{background:rgba(139,92,246,.07);border-color:var(--line)}
.mx-seg.hl{background:rgba(251,191,36,.08);border-color:rgba(251,191,36,.35)}
.mx-av{flex:none;width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-weight:700;font-size:.82rem;color:#fff}
.mx-seg .who{font-weight:700;font-size:.9rem;color:#fff}
.mx-seg .ts{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#a99cff;background:rgba(139,92,246,.14);padding:1px 8px;border-radius:7px;margin-left:8px}
.mx-seg .tx{color:#d6dbf7;font-size:.94rem;line-height:1.6;margin-top:3px}
.mx-seg mark{background:rgba(251,191,36,.35);color:#fff;padding:0 3px;border-radius:4px}
.mx-seg .tag{margin-left:8px}
/* evidence quote */
.mx-quote{border-left:3px solid var(--v1);padding:8px 12px;margin:8px 0;background:rgba(139,92,246,.07);border-radius:0 12px 12px 0;color:#cfd5f5;font-size:.88rem}
.mx-quote small{color:var(--txt3)}
/* chat */
[data-testid="stChatMessage"]{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin-bottom:10px}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){background:linear-gradient(135deg,rgba(139,92,246,.22),rgba(59,130,246,.14));border-color:var(--line2)}
[data-testid="stChatInput"]{border-radius:16px;border:1px solid var(--line2);background:rgba(10,16,48,.85)}
[data-testid="stChatInput"] textarea{background:transparent !important;border:none !important}
.mx-src{border:1px solid var(--line);border-radius:14px;padding:10px 12px;margin:6px 0;background:rgba(255,255,255,.025);font-size:.85rem}
.mx-src b{color:#fff}
.mx-grounded{display:inline-flex;gap:6px;align-items:center;font-size:.74rem;color:#7ee7bd}
/* stepper */
.mx-steps{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 12px}
.mx-step{display:flex;align-items:center;gap:7px;padding:6px 12px;border-radius:999px;font-size:.78rem;border:1px solid var(--line);color:var(--txt3);background:rgba(255,255,255,.03)}
.mx-step.done{color:#7ee7bd;border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.08)}
.mx-step.cur{color:#fff;border-color:#8f7bff;background:rgba(139,92,246,.2);animation:pulse 1.4s ease-in-out infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(139,92,246,.5)}50%{box-shadow:0 0 0 7px rgba(139,92,246,0)}}
/* calendar */
.mx-cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}
.mx-cal .dow{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--txt3);padding:4px 6px;text-align:left}
.mx-day{min-height:104px;border:1px solid var(--line);border-radius:14px;padding:7px 7px 5px;background:var(--card);overflow:hidden}
.mx-day.out{opacity:.35}
.mx-day.today{border-color:#8f7bff;box-shadow:0 0 0 1px #8f7bff inset, 0 8px 24px rgba(99,102,241,.25)}
.mx-day .n{font-size:.78rem;font-weight:700;color:var(--txt2);margin-bottom:4px}
.mx-day.today .n{color:#fff}
.mx-ev{font-size:.68rem;line-height:1.25;border-radius:7px;padding:2px 6px;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:3px solid}
.mx-ev.event{background:rgba(139,92,246,.2);border-color:#8b5cf6;color:#e0d9ff}
.mx-ev.task{background:rgba(59,130,246,.18);border-color:#3b82f6;color:#cfe1ff}
.mx-ev.done{background:rgba(52,211,153,.14);border-color:#34d399;color:#bff3dd;text-decoration:line-through}
.mx-ev.over{background:rgba(248,113,113,.17);border-color:#f87171;color:#ffd0d0}
.mx-more{font-size:.66rem;color:var(--txt3)}
/* misc */
.mx-bar{height:8px;border-radius:99px;background:rgba(255,255,255,.07);overflow:hidden}
.mx-bar>i{display:block;height:100%;border-radius:99px;background:var(--grad)}
.mx-kv{display:grid;grid-template-columns:150px 1fr;gap:6px 12px;font-size:.9rem}
.mx-kv b{color:var(--txt2);font-weight:500}
.mx-login{max-width:440px;margin:9vh auto 0;text-align:center}
.mx-why{font-size:.8rem;color:var(--txt2)}
.mx-metric{min-height:150px}
@media (max-width:1100px){
  [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:.7rem !important}
  [data-testid="stColumn"], [data-testid="column"]{min-width:min(100%, 210px) !important;flex:1 1 210px !important}
}
@media (max-width:900px){
  .block-container{padding:2.6rem .9rem 4rem !important}
  .mx-metric{min-height:0}
  .mx-hero{padding:24px 20px} .mx-hero h1{font-size:1.6rem}
  .mx-day{min-height:70px;padding:4px} .mx-ev{font-size:.6rem;padding:1px 4px}
  .mx-kv{grid-template-columns:1fr}
  .mx-pagehead h1{font-size:1.35rem}
}
"""


def apply() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
