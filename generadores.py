# -*- coding: utf-8 -*-
"""
MÓDULO GENERADORES DE VARIABLES ALEATORIAS
UTN FRC - TP5 - Grupo 18
-----------------------------------------------------------------------------
Genera variables con distintas distribuciones de probabilidad a partir de RND.
Cada función retorna una tupla (valor, rnd1, [rnd2]) para poder auditorizar
los valores aleatorios generados en el vector de estado.
"""

import math
import random

def generar_exponencial(media):
    """
    Genera un valor con distribución exponencial negativa.
    Fórmula: -media * ln(rnd)
    Se redondea el RND a 2 dígitos y se evita RND = 0.00 para evitar log(0).
    """
    rnd = round(random.random(), 2)
    if rnd == 0.00:
        rnd = 0.01
    valor = -media * math.log(1 - rnd)
    return round(valor, 4), rnd


_cached_z2 = None
_cached_rnds = (None, None)

def inicializar_generadores():
    """
    Reinicia el caché de Box-Muller para que las corridas de simulación
    sean independientes.
    """
    global _cached_z2, _cached_rnds
    _cached_z2 = None
    _cached_rnds = (None, None)


def generar_normal(media, desvio, cache_owner=None, categoria=None):
    """
    Genera un valor con distribución normal usando el método de Box-Muller.
    Retorna: (tiempo_usar, rnd1, rnd2, t_at1, t_at2)
    
    Si se proporciona cache_owner (un objeto Juez) y categoria:
      - categoria 'Inicial'  -> usa/guarda en cache_owner.cached_t_ini
      - categoria 'Avanzado' -> usa/guarda en cache_owner.cached_t_avan
    Reutiliza la segunda variable normal (seno) en la siguiente llamada del
    mismo tipo, evitando generar nuevos RNDs.
    """
    global _cached_z2, _cached_rnds
    
    # Determinar el atributo de caché según la categoría del competidor
    cache_attr = None
    if cache_owner is not None and categoria is not None:
        cache_attr = 'cached_t_ini' if categoria == 'Inicial' else 'cached_t_avan'
    
    # Intentar consumir el caché del juez para esta categoría
    if cache_attr is not None:
        cached_val = getattr(cache_owner, cache_attr, None)
        if cached_val is not None:
            setattr(cache_owner, cache_attr, None)
            return cached_val, "-", "-", "-", cached_val
    
    # Intentar usar el caché global (sólo cuando no hay cache_owner)
    elif cache_owner is None and _cached_z2 is not None:
        z = _cached_z2
        _cached_z2 = None
        _cached_rnds = (None, None)
        valor = media + desvio * z
        valor = max(0.1, round(valor, 4))
        return valor, "-", "-", "-", valor
    
    # Generar nuevo par Box-Muller
    rnd1 = round(random.random(), 2)
    if rnd1 == 0.00:
        rnd1 = 0.01
    rnd2 = round(random.random(), 2)
    
    # Transformación de Box-Muller
    ln_part = math.sqrt(-2 * math.log(rnd1))
    angle_part = 2 * math.pi * rnd2
    
    z1 = ln_part * math.cos(angle_part)
    z2 = ln_part * math.sin(angle_part)
    
    t_at1 = media + desvio * z1
    t_at1 = max(0.1, round(t_at1, 4))
    
    t_at2 = media + desvio * z2
    t_at2 = max(0.1, round(t_at2, 4))
    
    # Guardar el segundo valor en el caché correspondiente
    if cache_attr is not None:
        setattr(cache_owner, cache_attr, t_at2)
    else:
        _cached_z2 = z2
        _cached_rnds = (rnd1, rnd2)
        
    return t_at1, rnd1, rnd2, t_at1, t_at2


def generar_uniforme(a, b):
    """
    Genera un valor con distribución uniforme entre a y b.
    Fórmula: a + (b-a) * rnd
    Se redondea el RND a 2 dígitos.
    """
    rnd = round(random.random(), 2)
    valor = a + (b - a) * rnd
    return round(valor, 4), rnd
