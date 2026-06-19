# -*- coding: utf-8 -*-
"""
MÓDULO RUNGE-KUTTA (RK4)
UTN FRC - TP5 - Grupo 18
-----------------------------------------------------------------------------
Contiene la lógica matemática para resolver la ecuación diferencial:
  dE/dt = (t^2 - E) * h^2
donde una unidad de t = 8 minutos.
"""

def f_diferencial(t, E, h):
    """
    Función de la ecuación diferencial: dE/dt = (t^2 - E) * h^2
    t: tiempo actual (en unidades de integración, 1 unidad = 8 min)
    E: valor actual de E
    h: paso de integración
    """
    return (t**2 - E) * (h**2)


def runge_kutta_4(E0, h, max_iter=10000, guardar_tabla=True):
    """
    Aplica Runge-Kutta de 4to orden para resolver dE/dt = (t^2 - E) * h^2.
    
    Parámetros:
      E0: valor inicial de E (E(0))
      h:  paso de integración
      guardar_tabla: si es False, no genera el detalle de las filas (optimización)
    
    Retorna:
      - tiempo_minutos: t_final * 8 (conversión a minutos reales)
      - tabla_rk: lista de filas para mostrar en frontend
    """
    t = 0.0
    E = E0
    tabla_rk = []
    
    if not guardar_tabla:
        # Camino rápido sin instanciar diccionarios ni redondear en cada paso
        for n in range(1, max_iter + 1):
            k1 = (t**2 - E) * (h**2)
            k2 = ((t + h/2)**2 - (E + h/2 * k1)) * (h**2)
            k3 = ((t + h/2)**2 - (E + h/2 * k2)) * (h**2)
            k4 = ((t + h)**2 - (E + h * k3)) * (h**2)
            
            E = E + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
            t = t + h
            
            if E > E0:
                return t * 8, []
        return t * 8, []

    for n in range(1, max_iter + 1):
        k1 = f_diferencial(t, E, h)
        k2 = f_diferencial(t + h/2, E + h/2 * k1, h)
        k3 = f_diferencial(t + h/2, E + h/2 * k2, h)
        k4 = f_diferencial(t + h, E + h * k3, h)
        
        E_nuevo = E + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
        t_nuevo = t + h
        
        tabla_rk.append({
            "n": n,
            "t": round(t, 6),
            "E": round(E, 6),
            "k1": round(k1, 6),
            "k2": round(k2, 6),
            "k3": round(k3, 6),
            "k4": round(k4, 6),
            "E_nuevo": round(E_nuevo, 6),
            "t_minutos": round(t * 8, 4)
        })
        
        t = t_nuevo
        E = E_nuevo
        
        # CONDICIÓN DE PARADA: E supera al valor inicial E0
        if E > E0:
            # Agregar la última fila donde E supera al inicial E0 (sin calcular k's)
            tabla_rk.append({
                "n": n + 1,
                "t": round(t, 6),
                "E": round(E, 6),
                "k1": "-",
                "k2": "-",
                "k3": "-",
                "k4": "-",
                "E_nuevo": "-",
                "t_minutos": round(t * 8, 4)
            })
            return t * 8, tabla_rk
    
    return t * 8, tabla_rk
