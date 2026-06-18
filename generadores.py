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
    valor = -media * math.log(rnd)
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


def generar_normal(media, desvio, cache_owner=None):
    """
    Genera un valor con distribución normal usando el método de Box-Muller.
    Retorna: (tiempo_usar, rnd1, rnd2, t_at1, t_at2)
    Reutiliza la segunda variable normal (seno) en la siguiente llamada,
    evitando generar nuevos RNDs.
    """
    global _cached_z2, _cached_rnds
    
    # Si tenemos un dueño de caché (Juez) y ya tiene un tiempo guardado, lo consumimos directamente
    if cache_owner is not None and getattr(cache_owner, 'cached_t_at2', None) is not None:
        valor = cache_owner.cached_t_at2
        cache_owner.cached_t_at2 = None
        return valor, "-", "-", "-", valor
        
    # Si no hay cache_owner pero hay un valor en el caché global (estándar), usamos el global
    elif cache_owner is None and _cached_z2 is not None:
        z = _cached_z2
        _cached_z2 = None
        _cached_rnds = (None, None)
        valor = media + desvio * z
        valor = max(0.1, round(valor, 4))
        return valor, "-", "-", "-", valor
        
    else:
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
        
        # Guardamos en el dueño del caché si se proporcionó, si no en el global
        if cache_owner is not None:
            cache_owner.cached_t_at2 = t_at2
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
