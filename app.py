import os
import sqlite3
import datetime as dt

import pandas as pd
import streamlit as st

import calculations as calc

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="HET Design Calculator", layout="wide")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "het_change_log.db")

DEFAULTS = {
    "power_W": dict(value=400.0, label="Power", unit="W", fmt="%.1f",
                     section="Thruster Performance", placeholder=False,
                     help="Anode power input"),
    "thrust_mN": dict(value=16.0, label="Thrust", unit="mN", fmt="%.2f",
                       section="Thruster Performance", placeholder=False,
                       help="Target thrust"),
    "voltage_V": dict(value=400.0, label="Discharge voltage", unit="V", fmt="%.1f",
                       section="Thruster Performance", placeholder=False,
                       help="Recorded for reference -- not used in the formulas below yet"),
    "efficiency": dict(value=0.25, label="Total efficiency", unit="", fmt="%.3f",
                        section="Thruster Performance", placeholder=False,
                        help="Overall thrust efficiency, 0-1"),
    "neutral_number_density": dict(value=1.2e19, label="Neutral number density", unit="m\u207b\u00b3", fmt="%.4e",
                                    section="Scaling Law Inputs", placeholder=False,
                                    help="n_n"),
    "neutral_mass_kr": dict(value=1.3915e-25, label="Neutral mass (krypton)", unit="kg", fmt="%.4e",
                             section="Scaling Law Inputs", placeholder=False,
                             help="m_n"),
    "anode_temperature_K": dict(value=550.0, label="Assumed anode temperature", unit="K", fmt="%.1f",
                                 section="Scaling Law Inputs", placeholder=False,
                                 help="T_anode"),
    "c_hd": dict(value=1.0, label="Channel aspect ratio C_hd", unit="", fmt="%.3f",
                 section="Placeholder values -- please verify", placeholder=True,
                 help="h = C_hd * d. No value was given -- verify against your scaling-law reference."),
    "electron_temperature_eV": dict(value=20.0, label="Electron temperature", unit="eV", fmt="%.2f",
                                     section="Placeholder values -- please verify", placeholder=True,
                                     help="T_e. No value was given."),
    "ionization_cross_section": dict(value=1e-19, label="Ionization cross-section", unit="m\u00b2", fmt="%.3e",
                                      section="Placeholder values -- please verify", placeholder=True,
                                      help="sigma_iz. No value was given."),
}

SECTION_ORDER = ["Thruster Performance", "Scaling Law Inputs", "Placeholder values -- please verify"]

# ---------------------------------------------------------------------------
# Change-log storage (SQLite file next to this script)
# ---------------------------------------------------------------------------


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user TEXT,
            parameter TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_change(user, parameter, old_value, new_value, reason=""):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "INSERT INTO change_log (timestamp, user, parameter, old_value, new_value, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (dt.datetime.now().isoformat(timespec="seconds"), user, parameter, str(old_value), str(new_value), reason),
    )
    conn.commit()
    conn.close()


def fetch_log():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    df = pd.read_sql_query(
        "SELECT timestamp, user, parameter, old_value, new_value, reason "
        "FROM change_log ORDER BY id DESC",
        conn,
    )
    conn.close()
    return df


init_db()

# ---------------------------------------------------------------------------
# Session state: "design" holds the committed values used for calculations
# ---------------------------------------------------------------------------
if "design" not in st.session_state:
    st.session_state.design = {k: v["value"] for k, v in DEFAULTS.items()}
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "csa_variant" not in st.session_state:
    st.session_state.csa_variant = "continuity"
if "ve_variant" not in st.session_state:
    st.session_state.ve_variant = "corrected"

design = st.session_state.design

# ---------------------------------------------------------------------------
# Sidebar: parameter form
# ---------------------------------------------------------------------------
st.sidebar.title("Design Parameters")
st.sidebar.caption("Edit values, then click Apply to update the outputs and record the change.")

with st.sidebar.form("param_form"):
    name_input = st.text_input(
        "Your name", value=st.session_state.user_name,
        help="Attached to every change you make below",
    )

    new_values = {}
    for section in SECTION_ORDER:
        st.markdown(f"**{section}**")
        for key, meta in DEFAULTS.items():
            if meta["section"] != section:
                continue
            label = f"{meta['label']} ({meta['unit']})" if meta["unit"] else meta["label"]
            new_values[key] = st.number_input(
                label, value=float(design[key]), format=meta["fmt"], help=meta["help"], key=f"input_{key}",
            )

    st.markdown("**Equation variants**")
    csa_choice = st.radio(
        "Cross-sectional area formula",
        options=["continuity", "literal"],
        index=0 if st.session_state.csa_variant == "continuity" else 1,
        format_func=lambda x: "Mass-continuity form (recommended)" if x == "continuity" else "As originally written",
        help="See the Notes tab for the reasoning behind the recommended default.",
    )
    ve_choice = st.radio(
        "Electron velocity formula",
        options=["corrected", "literal"],
        index=0 if st.session_state.ve_variant == "corrected" else 1,
        format_func=lambda x: "Standard thermal velocity (recommended)" if x == "corrected" else "As originally written",
        help="See the Notes tab for the reasoning behind the recommended default.",
    )

    reason = st.text_area("Reason for this change (optional)", height=60)
    submitted = st.form_submit_button("Apply & Log Changes", width="stretch")

if submitted:
    user = name_input.strip() or "Unknown"
    st.session_state.user_name = user
    changed = False

    for key, new_val in new_values.items():
        old_val = design[key]
        if new_val != old_val:
            log_change(user, DEFAULTS[key]["label"], old_val, new_val, reason)
            design[key] = new_val
            changed = True

    if csa_choice != st.session_state.csa_variant:
        log_change(user, "Cross-sectional area formula", st.session_state.csa_variant, csa_choice, reason)
        st.session_state.csa_variant = csa_choice
        changed = True

    if ve_choice != st.session_state.ve_variant:
        log_change(user, "Electron velocity formula", st.session_state.ve_variant, ve_choice, reason)
        st.session_state.ve_variant = ve_choice
        changed = True

    if changed:
        st.sidebar.success("Changes applied and logged.")
    else:
        st.sidebar.info("No changes detected.")

if st.sidebar.button("Reset all to defaults", width="stretch"):
    user = st.session_state.user_name.strip() or "Unknown"
    for key, meta in DEFAULTS.items():
        if design[key] != meta["value"]:
            log_change(user, meta["label"], design[key], meta["value"], "Reset to default")
        design[key] = meta["value"]
    st.session_state.csa_variant = "continuity"
    st.session_state.ve_variant = "corrected"
    st.rerun()

# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
perf = calc.thruster_performance(design["power_W"], design["thrust_mN"], design["efficiency"])
sccm = calc.sccm_krypton(perf["mdot_mg_s"])
scaling = calc.scaling_laws(
    perf["mdot_kg_s"], design["neutral_number_density"], design["neutral_mass_kr"],
    design["anode_temperature_K"], design["c_hd"], csa_variant=st.session_state.csa_variant,
)
mfp = calc.ionization_mfp(
    scaling["velocity_neutral"], scaling["electron_number_density"], design["ionization_cross_section"],
    design["electron_temperature_eV"], ve_variant=st.session_state.ve_variant,
)

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("HET Design Parameter Calculator")
st.caption("Columbia Electric Propulsion -- shared design reference")

if any(DEFAULTS[k]["placeholder"] for k in DEFAULTS):
    st.warning(
        "Channel aspect ratio (C_hd), electron temperature, and ionization cross-section are placeholder "
        "values -- no numbers were given for these. Geometry and mean-free-path outputs below aren't "
        "trustworthy until you replace them.",
        icon="\u26a0\ufe0f",
    )

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Thruster Performance", "Scaling Laws & Geometry", "Ionization Mean Free Path", "Change Log", "Notes & Flagged Equations"]
)

with tab1:
    st.subheader("Thruster Performance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Specific impulse (Isp)", f"{perf['isp_s']:.1f} s")
    c2.metric("Mass flow rate", f"{perf['mdot_mg_s']:.4f} mg/s")
    c3.metric("Krypton flow", f"{sccm:.2f} SCCM")
    st.latex(r"I_{sp} = \frac{2 \cdot \eta \cdot P}{T \cdot g_0}")
    st.latex(r"\dot m = \frac{T}{I_{sp} \cdot g_0}")
    st.latex(r"\text{SCCM}_{Kr} = \frac{\dot m \, [\text{mg/s}]}{83.798} \times 1344.84")

with tab2:
    st.subheader("Scaling Laws & Channel Geometry")
    c1, c2 = st.columns(2)
    c1.metric("Electron number density", f"{scaling['electron_number_density']:.3e} m\u207b\u00b3")
    c1.metric("Neutral velocity", f"{scaling['velocity_neutral']:.1f} m/s")
    c1.metric("Cross-sectional area", f"{scaling['csa_m2']*1e4:.4f} cm\u00b2")
    c2.metric("Mean channel diameter (d)", f"{scaling['d_m']*1000:.2f} mm")
    c2.metric("Channel height (h)", f"{scaling['h_m']*1000:.2f} mm")
    c2.metric("Outer / inner diameter", f"{scaling['d_outer_m']*1000:.2f} / {scaling['d_inner_m']*1000:.2f} mm")
    st.latex(r"n_e = 0.1 \cdot n_n")
    st.latex(r"v_n = \sqrt{\frac{8 k_B T_{anode}}{\pi m_n}}")
    st.latex(r"A = \frac{\dot m}{n_n \cdot m_n \cdot v_n} \quad \text{(mass-continuity form)}")
    st.latex(r"d = \sqrt{\frac{A}{\pi \cdot C_{hd}}}, \quad h = C_{hd} \cdot d, \quad d_{outer}=d+h,\ d_{inner}=d-h")

with tab3:
    st.subheader("Ionization Mean Free Path")
    c1, c2 = st.columns(2)
    c1.metric("Electron velocity", f"{mfp['velocity_electrons']:.3e} m/s")
    c2.metric("Mean free path (\u03bb)", f"{mfp['lambda_m']*1000:.3f} mm")
    st.metric("99% ionization length (L99%)", f"{mfp['l99_m']*1000:.3f} mm")
    st.latex(r"v_e = \sqrt{\frac{2 e T_e[\text{eV}]}{m_e}}")
    st.latex(r"\lambda = \frac{v_n}{n_e \cdot \sigma_{iz} \cdot v_e}")
    st.latex(r"L_{99\%} = -\lambda \ln(0.01)")

with tab4:
    st.subheader("Change Log")
    log_df = fetch_log()
    if log_df.empty:
        st.info("No changes logged yet. Adjust a value in the sidebar and click Apply & Log Changes.")
    else:
        st.dataframe(log_df, width="stretch", hide_index=True)
        csv = log_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download full log as CSV", csv, file_name="het_change_log.csv", mime="text/csv")

with tab5:
    st.subheader("Notes & Flagged Equations")
    st.markdown(
        """
Two of the formulas you provided had an ambiguity or a dimensional inconsistency. Rather than silently
"fixing" your physics, both interpretations are implemented and selectable in the sidebar under
**Equation variants** -- here's the reasoning behind the recommended default in each case.

**Cross-sectional area**

As written, `A = mdot / (n_n * n_e * v_n)` doesn't reduce to units of m\u00b2 (there's a leftover
m\u207b\u00b3\u00b7s). With your example numbers (400 W, 16 mN, 0.25 eff, n_n = 1.2e19 m\u207b\u00b3, 550 K anode),
that formula gives A \u2248 2.4e-46 m\u00b2 -- not physically meaningful.

The mass-continuity relation `mdot = \u03c1 v A = n_n m_n v A` rearranges to
`A = mdot / (n_n * m_n * v_n)`, which is dimensionally consistent and gives A \u2248 2.1e-3 m\u00b2
(\u2248 20.5 cm\u00b2) with the same numbers -- a plausible channel cross-section. **This is the default.**

**Electron velocity**

As written, `v_e = sqrt(2*Te) / m_e` isn't dimensionally consistent regardless of whether Te is in K or eV --
with Te = 20 eV it comes out to roughly 7e30 m/s, far past the speed of light. The standard electron
thermal velocity, treating Te as being in eV, is `v_e = sqrt(2 e Te / m_e)` (e = elementary charge,
converting eV to joules) -- this gives \u2248 2.65e6 m/s, a physically reasonable number, and is the default.

**Geometry note:** with `C_hd`, `T_e`, and the ionization cross-section still at placeholder values,
`d_inner` and the mean-free-path outputs may look degenerate or unrealistic (e.g. C_hd = 1 forces
d_inner = 0). Update those three inputs first before trusting the geometry or L99% numbers.

**Voltage (400 V)** is recorded as an input for reference but isn't used in any formula above -- none of
the equations given use it yet. Let me know if you want a current or channel-field calculation added.
        """
    )

st.divider()
st.caption(f"Change log stored at: {DB_PATH}")
