"""
Pure calculation functions for the Columbia HET design parameter tool.

Deliberately has no Streamlit dependency so the physics can be tested and
reused independently of the UI.
"""
import math

# ---- Physical constants (fixed, not user-adjustable) ----
G0 = 9.80665                 # standard gravity, m/s^2
K_B = 1.380649e-23           # Boltzmann constant, J/K
M_E = 9.1093837139e-31       # electron mass, kg
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
                  anode_temperature_K, c_hd):
    """Channel geometry from the confirmed scaling-law chain.

    Cross-sectional area follows mass continuity:
        mdot = n_n * m_n * v_n * A
        A = mdot / (n_n * m_n * v_n)
    """
    electron_number_density = 0.1 * neutral_number_density
    velocity_neutral = math.sqrt((8 * K_B * anode_temperature_K) / (math.pi * neutral_mass_kr))
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
                    electron_energy_eV):
    """Electron-impact ionization mean free path and 99%-ionization length.

    The user supplies electron energy in eV. Convert it to joules first, then
    use the kinetic-energy relation

        E_e = (1/2) * m_e * v_e^2

    so that

        v_e = sqrt(2 * E_e[J] / m_e).
    """
    electron_energy_J = electron_energy_eV * E_CHARGE
    velocity_electrons = math.sqrt(2 * electron_energy_J / M_E)

    lam = velocity_neutral / (electron_number_density * ionization_cross_section * velocity_electrons)
    l99 = -lam * math.log(0.01)

    return {
        "electron_energy_J": electron_energy_J,
        "velocity_electrons": velocity_electrons,
        "lambda_m": lam,
        "l99_m": l99,
    }
