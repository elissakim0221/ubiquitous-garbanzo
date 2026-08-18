"""
Pure calculation functions for the Columbia HET design parameter tool.

Deliberately has no Streamlit dependency so the physics can be tested and
reused independently of the UI.
"""
import math

# ---- Physical constants (fixed, not user-adjustable) ----
G0 = 9.80665                 # standard gravity, m/s^2
K_B = 1.380649e-23           # Boltzmann constant, J/K
M_E = 9.10938356e-31         # electron mass, kg
E_CHARGE = 1.602176634e-19   # elementary charge, C
M_KR = 83.798                # molar mass of krypton, g/mol


def thruster_performance(power_W, thrust_mN, efficiency):
    """Isp and mass flow rate from power, thrust, and total efficiency.

    Derived from eta = T^2 / (2 * mdot * P) and Isp = T / (mdot * g0):
        Isp  = 2 * eta * P / (T * g0)
        mdot = T / (Isp * g0)
    """
    thrust_N = thrust_mN * 1e-3
    isp_s = (2 * efficiency * power_W) / (thrust_N * G0)
    mdot_kg_s = thrust_N / (isp_s * G0)
    mdot_mg_s = mdot_kg_s * 1e6
    return {
        "thrust_N": thrust_N,
        "isp_s": isp_s,
        "mdot_kg_s": mdot_kg_s,
        "mdot_mg_s": mdot_mg_s,
    }


def sccm_krypton(mdot_mg_s):
    """Convert mg/s mass flow to SCCM for krypton (Vm = 22,414 mL/mol @ STP)."""
    return (mdot_mg_s / M_KR) * 1344.84


def scaling_laws(mdot_kg_s, neutral_number_density, neutral_mass_kr,
                  anode_temperature_K, c_hd, csa_variant="continuity"):
    """Channel geometry from the scaling-law chain.

    csa_variant:
        "continuity" (default): A = mdot / (n_n * m_n * v_n)   [mass continuity, mdot = rho*v*A]
        "literal":               A = mdot / (n_n * n_e * v_n)  [as originally written]
    """
    electron_number_density = 0.1 * neutral_number_density
    velocity_neutral = math.sqrt((8 * K_B * anode_temperature_K) / (math.pi * neutral_mass_kr))

    if csa_variant == "literal":
        csa = mdot_kg_s / (neutral_number_density * electron_number_density * velocity_neutral)
    else:
        csa = mdot_kg_s / (neutral_number_density * neutral_mass_kr * velocity_neutral)

    # From A = pi*h*d and h = C_hd*d  =>  A = pi*C_hd*d^2  =>  d = sqrt(A / (pi*C_hd))
    d = math.sqrt(csa / (math.pi * c_hd))
    h = c_hd * d
    d_outer = d + h
    d_inner = d - h

    return {
        "electron_number_density": electron_number_density,
        "velocity_neutral": velocity_neutral,
        "csa_m2": csa,
        "d_m": d,
        "h_m": h,
        "d_outer_m": d_outer,
        "d_inner_m": d_inner,
    }


def ionization_mfp(velocity_neutral, electron_number_density, ionization_cross_section,
                    electron_temperature_eV, ve_variant="corrected"):
    """Electron-impact ionization mean free path and 99%-ionization length.

    ve_variant:
        "corrected" (default): v_e = sqrt(2*e*Te[eV] / m_e)   [standard electron thermal speed]
        "literal":              v_e = sqrt(2*Te) / m_e         [as originally written]
    """
    if ve_variant == "literal":
        velocity_electrons = math.sqrt(2 * electron_temperature_eV) / M_E
    else:
        velocity_electrons = math.sqrt(2 * E_CHARGE * electron_temperature_eV / M_E)

    lam = velocity_neutral / (electron_number_density * ionization_cross_section * velocity_electrons)
    l99 = -lam * math.log(0.01)

    return {
        "velocity_electrons": velocity_electrons,
        "lambda_m": lam,
        "l99_m": l99,
    }
