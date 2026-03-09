import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://api.jobindsats.dk/v2"

# ── Tabelkonfiguration ────────────────────────────────────────────────────────
# Baseret på kortlægning af faktiske kolonnenavne fra API'et.
# Volumen: memba02_4b = fuldtidspersoner i pct. af arbejdsstyrken 16-66 år
# Afgang:  _amstatusb15 skal specificeres for at undgå 100%-summering

TABELLER = {
    "Volumen": {
        "beskrivelse": "Fuldtidspersoner i pct. af arbejdsstyrken (16–66 år). Direkte sammenlignelig på tværs af kommuner.",
        "tabeller": [
            {"id": "ptv_a02", "label": "Offentlig forsørgede (alle)", "maal": "memba02_4b"},
            {"id": "y01a02",  "label": "A-dagpenge",                   "maal": "memba02_4b"},
            {"id": "y60a02",  "label": "Kontanthjælp",                 "maal": "memba02_4b"},
            {"id": "y07a02",  "label": "Sygedagpenge",                 "maal": "memba02_4b"},
            {"id": "y08a02",  "label": "Fleksjob",                     "maal": "memba02_4b"},
            {"id": "y09a02",  "label": "Ledighedsydelse",              "maal": "memba02_4b"},
            {"id": "y11a02",  "label": "Ressourceforløb",              "maal": "memba02_4b"},
            {"id": "y12a02",  "label": "Jobafklaringsforløb",          "maal": "memba02_4b"},
            {"id": "y10a02",  "label": "Førtidspension",               "maal": "memba02_4b"},
        ]
    },
    "Økonomi": {
        "beskrivelse": "⚠️ Absolutte udgiftstal i løbende priser. Ikke normeret per indbygger — bør ikke bruges til direkte sammenligning af kommuner af forskellig størrelse.",
        "tabeller": [
            {"id": "ptvg01", "label": "Offentlig forsørgede (alle)", "maal": None},
            {"id": "y01g01", "label": "A-dagpenge",                   "maal": None},
            {"id": "y60g01", "label": "Kontanthjælp",                 "maal": None},
            {"id": "y07g01", "label": "Sygedagpenge",                 "maal": None},
            {"id": "y09g01", "label": "Ledighedsydelse",              "maal": None},
            {"id": "y12g01", "label": "Jobafklaringsforløb",          "maal": None},
            {"id": "y10g01", "label": "Førtidspension",               "maal": None},
        ]
    },
    "Varighed": {
        "beskrivelse": "Gennemsnitlig varighed af afsluttede forløb i uger. Sammenlignelig på tværs af kommuner.",
        "tabeller": [
            {"id": "y01a27", "label": "A-dagpenge",          "maal": None},
            {"id": "y60a27", "label": "Kontanthjælp",        "maal": None},
            {"id": "y07a07", "label": "Sygedagpenge",        "maal": None},
            {"id": "y09a27", "label": "Ledighedsydelse",     "maal": None},
            {"id": "y12a27", "label": "Jobafklaringsforløb", "maal": None},
        ]
    },
    "Afgang": {
        "beskrivelse": "Andel i lønmodtagerbeskæftigelse hhv. uddannelse 6 og 12 måneder efter afsluttet forløb (pct.). Kvartalsvise tal.",
        "tabeller": [
            {"id": "y01b15", "label": "A-dagpenge",          "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y60b15", "label": "Kontanthjælp",        "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y07b15", "label": "Sygedagpenge",        "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y09b15", "label": "Ledighedsydelse",     "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y12b15", "label": "Jobafklaringsforløb", "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y08b15", "label": "Fleksjob",            "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Lønmodtagerbeskæftigelse"},
            {"id": "y01b15", "label": "A-dagpenge (udd.)",   "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Uddannelse"},
            {"id": "y60b15", "label": "Kontanthjælp (udd.)", "maal": "membb15_3", "maal2": "membb15_4", "dim": "_amstatusb15=Uddannelse"},
        ]
    },
}

FARVER = {"primær": "#2E86AB", "sammenlign": "#F4A261"}

# ── API-funktioner ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def hent_kommuner():
    r = requests.get(f"{BASE_URL}/tables/y01a02/json", headers={"Authorization": API_KEY})
    data = r.json()
    if isinstance(data, list):
        data = data[0]
    areas = data.get("Area", [])
    return sorted([a for a in areas if a != "Hele landet" and not a.startswith("RAR")])

@st.cache_data(ttl=1800, show_spinner=False)
def hent_data(tabel_id, area1, area2, perioder, maal_id=None, dim_filter=None):
    areas = f"{area1},{area2}" if area2 and area2 != area1 else area1
    url = f"{BASE_URL}/data/{tabel_id}/json?area={areas}&period={perioder}"
    if maal_id:
        url += f"&measurement={maal_id}"
    if dim_filter:
        url += f"&{dim_filter}"
    try:
        r = requests.get(url, headers={"Authorization": API_KEY}, timeout=20)
        data = r.json()
        if isinstance(data, list):
            data = data[0]
        variables = data.get("Variables", [])
        rows = data.get("Data", [])
        if not rows or not variables:
            return pd.DataFrame(), [], {}
        col_names = [v["Name"] for v in variables]
        col_labels = {v["Name"]: v["Label"] for v in variables}
        df = pd.DataFrame(rows, columns=col_names)
        # Kun numeriske målekolonner (ikke dimensionskolonner som _amstatusb15)
        maal_cols = []
        for c in col_names:
            if c in ["area", "period"]:
                continue
            converted = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
            if converted.notna().any():
                df[c] = converted
                maal_cols.append(c)
        # Aggreger til ét tal per area+period (håndterer duplikater fra dimensionskolonner)
        if maal_cols:
            df = df.groupby(["area", "period"], as_index=False)[maal_cols].mean(numeric_only=True)
        return df, maal_cols, col_labels
    except Exception:
        return pd.DataFrame(), [], {}

# ── Hjælpefunktioner ───────────────────────────────────────────────────────────

def formater_tal(v, label):
    if pd.isna(v):
        return "–"
    l = label.lower()
    if any(x in l for x in ["pct", "andel", "grad", "%", "procent"]):
        return f"{v:.1f}%"
    if any(x in l for x in ["udgifter", "priser", "kr"]):
        return f"{v/1_000_000:.1f} mio. kr." if v >= 1_000_000 else f"{int(v):,} kr.".replace(",", ".")
    if "uger" in l or "varighed" in l:
        return f"{v:.1f} uger"
    return f"{int(v):,}".replace(",", ".")

def seneste_vaerdi(df, area, maal_col):
    sub = (df[df["area"] == area]
               .groupby("period", as_index=False)[maal_col].mean()
               .dropna(subset=[maal_col])
               .sort_values("period"))
    return sub.iloc[-1][maal_col] if not sub.empty else float("nan")

def lav_tidsserie(df, maal_col, label, area1, area2):
    import re
    def sort_periode(p):
        m = re.match(r"(\d{4})(M|Q|Y)(\d+)", str(p))
        return (int(m.group(1)), int(m.group(3))) if m else (0, 0)

    fig = go.Figure()
    alle_vaerdier = []
    for area, farve in [(area1, FARVER["primær"]), (area2, FARVER["sammenlign"])]:
        if not area:
            continue
        subset = (df[df["area"] == area]
                    .groupby("period", as_index=False)[maal_col].mean()
                    .dropna(subset=[maal_col]))
        if subset.empty:
            continue
        subset = subset.iloc[sorted(range(len(subset)), key=lambda i: sort_periode(subset.iloc[i]["period"]))]
        alle_vaerdier.extend(subset[maal_col].tolist())
        fig.add_trace(go.Scatter(
            x=subset["period"], y=subset[maal_col], name=area,
            line=dict(color=farve, width=2.5), mode="lines+markers",
            marker=dict(size=4, color=farve),
            hovertemplate=f"<b>{area}</b><br>%{{x}}<br>{label}: %{{y:,.2f}}<extra></extra>"
        ))
    if alle_vaerdier:
        y_min = max(0, min(alle_vaerdier) * 0.85)
        y_max = max(alle_vaerdier) * 1.08
    else:
        y_min, y_max = None, None
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="#F8F9FA",
        font=dict(family="Inter, sans-serif", color="#1A1A2E"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11, color="#1A1A2E"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E9ECEF", borderwidth=1
        ),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=10, color="#444")),
        yaxis=dict(
            gridcolor="#E9ECEF", tickfont=dict(size=10, color="#444"),
            range=[y_min, y_max] if y_min is not None else None
        ),
        height=240,
    )
    return fig

def render_metric_card(tbl, df, maal_col, col_labels, primaer, sammenlign, maal2_col=None, col_labels2=None):
    label = col_labels.get(maal_col, maal_col)
    v_p = seneste_vaerdi(df, primaer, maal_col)
    v_s = seneste_vaerdi(df, sammenlign, maal_col)

    # Ekstra linje hvis to målinger (6 mdr + 12 mdr)
    extra = ""
    if maal2_col and maal2_col in df.columns:
        label2 = (col_labels2 or col_labels).get(maal2_col, maal2_col)
        v_p2 = seneste_vaerdi(df, primaer, maal2_col)
        v_s2 = seneste_vaerdi(df, sammenlign, maal2_col)
        extra = (
            '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #F0F0F0;">'
            '<span style="font-size:0.75rem;color:#6C757D;">12 mdr.: </span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:#1B3A5C;">{formater_tal(v_p2, label2)}</span>'
            f'<span style="font-size:0.78rem;color:#E76F51;"> / {sammenlign}: {formater_tal(v_s2, label2)}</span>'
            '</div>'
        )

    html = (
        '<div class="metric-card">'
        f'<div class="metric-ydelse">{tbl["label"]}</div>'
        f'<div class="metric-val-primary">{formater_tal(v_p, label)}</div>'
        f'<div class="metric-val-compare">&#8596; {sammenlign}: {formater_tal(v_s, label)}</div>'
        f'<div class="metric-label-small">{label}</div>'
        f'{extra}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    fig = lav_tidsserie(df, maal_col, label, primaer, sammenlign)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Streamlit setup ────────────────────────────────────────────────────────────

st.set_page_config(page_title="Jobindsats Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main-title { font-family: 'DM Serif Display', serif; font-size: 2rem; color: #1B3A5C; margin-bottom: 2px; }
.sub-title { font-size: 0.88rem; color: #6C757D; margin-bottom: 1rem; }
.pill-blue { display:inline-block; background:#E8F4FD; color:#2E86AB; border-radius:20px; padding:2px 10px; font-size:0.78rem; font-weight:600; }
.pill-orange { display:inline-block; background:#FFF3E8; color:#E76F51; border-radius:20px; padding:2px 10px; font-size:0.78rem; font-weight:600; }
.metric-card { background:white; border:1px solid #E9ECEF; border-radius:10px; padding:14px 18px; margin-bottom:8px; border-left:4px solid #2E86AB; }
.metric-ydelse { font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#6C757D; margin-bottom:3px; }
.metric-val-primary { font-size:1.55rem; font-weight:700; color:#1B3A5C; line-height:1.1; }
.metric-val-compare { font-size:0.95rem; font-weight:500; color:#E76F51; margin-top:1px; }
.metric-label-small { font-size:0.72rem; color:#6C757D; margin-top:2px; }
.metric-sublabel { font-size:0.75rem; color:#6C757D; }
.metric-subval-p { font-size:0.85rem; font-weight:600; color:#1B3A5C; }
.metric-subval-s { font-size:0.78rem; color:#E76F51; }
.section-note { font-size:0.78rem; color:#6C757D; background:#F8F9FA; border-radius:6px; padding:8px 12px; margin-bottom:14px; border-left:3px solid #dee2e6; }
.warning-note { font-size:0.78rem; color:#856404; background:#fff3cd; border-radius:6px; padding:8px 12px; margin-bottom:14px; border-left:3px solid #ffc107; }
.section-header { font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:#6C757D; border-bottom:1px solid #E9ECEF; padding-bottom:6px; margin:16px 0 10px 0; }
[data-testid="stSidebar"] { background: #1B3A5C !important; }
[data-testid="stSidebar"] label { color: #A8C4DC !important; font-size:0.72rem !important; font-weight:600 !important; text-transform:uppercase; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div { color: white !important; }
[data-testid="stSidebar"] small { color: #A8C4DC !important; }
</style>
""", unsafe_allow_html=True)

# ── Adgangskode ───────────────────────────────────────────────────────────────
adgangskode = st.sidebar.text_input("Adgangskode", type="password")
if adgangskode != st.secrets["PASSWORD"]:
    st.sidebar.warning("Indtast adgangskode for at fortsætte")
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Jobindsats")
    st.markdown("---")
    with st.spinner("Henter kommuner..."):
        kommuner = hent_kommuner()
    st.markdown("**Primær kommune**")
    default_idx = kommuner.index("Aarhus") if "Aarhus" in kommuner else 0
    primaer = st.selectbox("Primær", kommuner, index=default_idx, label_visibility="collapsed")
    st.markdown("**Sammenlign med**")
    sammenlign_opts = ["Hele landet"] + [k for k in kommuner if k != primaer]
    sammenlign = st.selectbox("Sammenlign", sammenlign_opts, label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**Periodefrekvens**")
    freq_map = {"Månedlig": "M", "Kvartal": "Q", "År": "Y"}
    freq_label = st.selectbox("Frekvens", list(freq_map.keys()), label_visibility="collapsed")
    freq = freq_map[freq_label]
    st.markdown("**Antal perioder**")
    antal = st.slider("Perioder", 6, 36, 24, label_visibility="collapsed")
    periode_str = f"l({freq}:{antal})"
    # Afgang er kun kvartal
    afgang_periode = f"l(Q:{min(antal, 16)})"
    st.markdown("---")
    st.caption("Kilde: api.jobindsats.dk")

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">Beskæftigelsesdashboard</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">Sammenligner <span class="pill-blue">{primaer}</span> '
    f'med <span class="pill-orange">{sammenlign}</span> — '
    f'seneste {antal} perioder ({freq_label.lower()})</div>',
    unsafe_allow_html=True
)

# ── Faner ──────────────────────────────────────────────────────────────────────

tabs = st.tabs(["📈 Volumen", "💰 Økonomi", "⏱ Varighed", "🎯 Afgang"])

# ── Volumen ────────────────────────────────────────────────────────────────────
with tabs[0]:
    kat = TABELLER["Volumen"]
    st.markdown(f'<div class="section-note">{kat["beskrivelse"]}</div>', unsafe_allow_html=True)
    tabeller = kat["tabeller"]
    for i in range(0, len(tabeller), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(tabeller):
                break
            tbl = tabeller[i + j]
            with col:
                with st.spinner(f"{tbl['label']}..."):
                    df, maal_cols, col_labels = hent_data(tbl["id"], primaer, sammenlign, periode_str)
                if df.empty or not maal_cols:
                    st.warning(f"Ingen data: {tbl['label']}")
                    continue
                # Brug pct. af arbejdsstyrken hvis tilgængelig, ellers første kolonne
                foretrukken = tbl.get("maal", "memba02_4b")
                valgt = foretrukken if foretrukken in df.columns else maal_cols[0]
                render_metric_card(tbl, df, valgt, col_labels, primaer, sammenlign)

# ── Økonomi ────────────────────────────────────────────────────────────────────
with tabs[1]:
    kat = TABELLER["Økonomi"]
    st.markdown(f'<div class="warning-note">{kat["beskrivelse"]}</div>', unsafe_allow_html=True)
    tabeller = kat["tabeller"]
    for i in range(0, len(tabeller), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(tabeller):
                break
            tbl = tabeller[i + j]
            with col:
                with st.spinner(f"{tbl['label']}..."):
                    df, maal_cols, col_labels = hent_data(tbl["id"], primaer, sammenlign, periode_str)
                if df.empty or not maal_cols:
                    st.warning(f"Ingen data: {tbl['label']}")
                    continue
                render_metric_card(tbl, df, maal_cols[0], col_labels, primaer, sammenlign)

# ── Varighed ───────────────────────────────────────────────────────────────────
with tabs[2]:
    kat = TABELLER["Varighed"]
    st.markdown(f'<div class="section-note">{kat["beskrivelse"]}</div>', unsafe_allow_html=True)
    tabeller = kat["tabeller"]
    for i in range(0, len(tabeller), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(tabeller):
                break
            tbl = tabeller[i + j]
            with col:
                with st.spinner(f"{tbl['label']}..."):
                    df, maal_cols, col_labels = hent_data(tbl["id"], primaer, sammenlign, periode_str)
                if df.empty or not maal_cols:
                    st.warning(f"Ingen data: {tbl['label']}")
                    continue
                # Find gnsn. varighed kolonne (ikke fordelingskolonne)
                varighed_col = next((c for c in maal_cols if "gnsn" in col_labels.get(c,"").lower()), maal_cols[-1])
                render_metric_card(tbl, df, varighed_col, col_labels, primaer, sammenlign)

# ── Afgang ─────────────────────────────────────────────────────────────────────
with tabs[3]:
    kat = TABELLER["Afgang"]
    st.markdown(f'<div class="section-note">{kat["beskrivelse"]}</div>', unsafe_allow_html=True)
    tabeller = kat["tabeller"]
    for i in range(0, len(tabeller), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(tabeller):
                break
            tbl = tabeller[i + j]
            with col:
                with st.spinner(f"{tbl['label']}..."):
                    df, maal_cols, col_labels = hent_data(
                        tbl["id"], primaer, sammenlign, afgang_periode,
                        dim_filter=tbl.get("dim")
                    )
                if df.empty or not maal_cols:
                    st.markdown(f'''<div class="metric-card"><div class="metric-ydelse">{tbl["label"]}</div>
                    <div style="color:#6C757D;font-size:0.85rem;padding:8px 0;">Ikke tilgængeligt på kommuneniveau</div></div>''', unsafe_allow_html=True)
                    continue
                # Tjek om der faktisk er data for primær kommune
                maal_6 = next((c for c in maal_cols if c == "membb15_3"), maal_cols[0])
                maal_12 = next((c for c in maal_cols if c == "membb15_4"), None)
                # Kræv mindst 4 datapunkter for begge områder
                n_primaer = len(df[df["area"] == primaer].dropna(subset=[maal_6]))
                n_sammenlign = len(df[df["area"] == sammenlign].dropna(subset=[maal_6]))
                if n_primaer < 4 or n_sammenlign < 4:
                    mangler = primaer if n_primaer < 4 else sammenlign
                    st.markdown(f'''<div class="metric-card"><div class="metric-ydelse">{tbl["label"]}</div>
                    <div style="color:#6C757D;font-size:0.85rem;padding:8px 0;">Ikke tilgængeligt for {mangler} (for få forløb)</div></div>''', unsafe_allow_html=True)
                    continue
                render_metric_card(tbl, df, maal_6, col_labels, primaer, sammenlign,
                                   maal2_col=maal_12, col_labels2=col_labels)
