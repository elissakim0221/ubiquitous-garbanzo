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
    "c_hd": dict(value=0.242, label="Channel aspect ratio C_hd", unit="", fmt="%.3f",
                 section="Scaling Law Inputs", placeholder=False,
                 help="Confirmed value: C_hd = 0.242, with h = C_hd * d."),
    "electron_energy_eV": dict(value=30.0, label="Electron energy", unit="eV", fmt="%.2f",
                               section="Ionization Inputs", placeholder=False,
                               help="Changeable electron energy. Converted from eV to joules before calculating v_e."),
    "ionization_cross_section": dict(value=2.516e-20, label="Ionization cross-section", unit="m\u00b2", fmt="%.3e",
                                      section="Ionization Inputs", placeholder=False,
                                      help="Ionization cross-section, sigma_iz. Default = 2.516e-20 m^2."),
}

SECTION_ORDER = ["Thruster Performance", "Scaling Law Inputs", "Ionization Inputs"]

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
else:
    # Keep existing browser sessions compatible when parameters are added/renamed.
    for key, meta in DEFAULTS.items():
        st.session_state.design.setdefault(key, meta["value"])
    st.session_state.design.pop("electron_temperature_eV", None)
    # Migrate the old placeholder cross-section to the confirmed value.
    if st.session_state.design.get("ionization_cross_section") == 1e-19:
        st.session_state.design["ionization_cross_section"] = 2.516e-20

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

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
    st.rerun()

# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
perf = calc.thruster_performance(design["power_W"], design["thrust_mN"], design["efficiency"])
sccm = calc.sccm_krypton(perf["mdot_mg_s"])
scaling = calc.scaling_laws(
    perf["mdot_kg_s"], design["neutral_number_density"], design["neutral_mass_kr"],
    design["anode_temperature_K"], design["c_hd"],
)

mfp = calc.ionization_mfp(
    scaling["velocity_neutral"],
    scaling["electron_number_density"],
    design["ionization_cross_section"],
    design["electron_energy_eV"],
)

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("HET Design Parameter Calculator")
st.caption("Columbia Electric Propulsion -- shared design reference")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Thruster Performance", "Scaling Laws & Geometry", "Ionization Mean Free Path", "Change Log", "Notes & Equations"]
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
    c1.metric("Electron energy", f"{design['electron_energy_eV']:.2f} eV = {mfp['electron_energy_J']:.3e} J")
    c2.metric("Electron velocity", f"{mfp['velocity_electrons']:.3e} m/s")
    c3, c4 = st.columns(2)
    c3.metric("Mean free path (\u03bb)", f"{mfp['lambda_m']*1000:.3f} mm")
    c4.metric("99% ionization length (L99%)", f"{mfp['l99_m']*1000:.3f} mm")
    st.latex(r"E_e[\mathrm{J}] = E_e[\mathrm{eV}] \times e")
    st.latex(r"E_e = \frac{1}{2}m_e v_e^2 \quad \Longrightarrow \quad v_e = \sqrt{\frac{2E_e[\mathrm{J}]}{m_e}}")
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
    st.subheader("Notes & Equations")
    st.markdown(
        """
**Confirmed cross-sectional area interpretation**

The model uses the mass-continuity relation
`mdot = rho * v * A = n_n * m_n * v_n * A`, so
`A = mdot / (n_n * m_n * v_n)`. This is now the only implemented area equation.

**Confirmed channel aspect ratio**

`C_hd = 0.242`, with `h = C_hd * d`. The value remains editable in the sidebar and all geometry
outputs update when it changes.

**Confirmed electron-energy / velocity relation**

Electron energy defaults to `30 eV` but is editable. Before calculating velocity, the input is converted
from electron-volts to joules using `E_e[J] = E_e[eV] * e`, where
`e = 1.602176634e-19 J/eV`. The model then uses the kinetic-energy relation
`E_e = (1/2) * m_e * v_e^2`, giving `v_e = sqrt(2 * E_e[J] / m_e)`.

**Ionization cross-section**

The default ionization cross-section is `2.516e-20 m^2`. It remains editable in the sidebar, and the
mean-free-path and 99% ionization-length outputs update automatically when it changes.

**Voltage (400 V)** is recorded as an input for reference but isn't used in the current formulas.
        """
    )

st.divider()
st.caption(f"Change log stored at: {DB_PATH}")
