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


def generar_normal(media, desvio):
    """
    Genera un valor con distribución normal usando el método de Box-Muller.
    Retorna: (valor, rnd1, rnd2)
    Se redondean los RNDs a 2 dígitos y se evita rnd1 = 0.00.
    """
    rnd1 = round(random.random(), 2)
    if rnd1 == 0.00:
        rnd1 = 0.01
    rnd2 = round(random.random(), 2)
    
    z = math.sqrt(-2 * math.log(rnd1)) * math.cos(2 * math.pi * rnd2)
    valor = media + desvio * z
    # Truncamos en 0.1 para evitar tiempos negativos o nulos
    valor = max(0.1, round(valor, 4))
    return valor, rnd1, rnd2


def generar_uniforme(a, b):
    """
    Genera un valor con distribución uniforme entre a y b.
    Fórmula: a + (b-a) * rnd
    Se redondea el RND a 2 dígitos.
    """
    rnd = round(random.random(), 2)
    valor = a + (b - a) * rnd
    return round(valor, 4), rnd
