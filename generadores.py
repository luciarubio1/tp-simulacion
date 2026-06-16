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
    Fórmula: -media * ln(1 - rnd)  (o -media * ln(rnd))
    """
    rnd = random.random()
    # Evitar log(0)
    rnd = max(0.000001, rnd)
    valor = -media * math.log(rnd)
    return round(valor, 4), round(rnd, 6)


def generar_normal(media, desvio):
    """
    Genera un valor con distribución normal usando el método de Box-Muller.
    Retorna: (valor, rnd1, rnd2)
    """
    rnd1 = random.random()
    rnd2 = random.random()
    # Evitar log(0)
    rnd1 = max(0.000001, rnd1)
    z = math.sqrt(-2 * math.log(rnd1)) * math.cos(2 * math.pi * rnd2)
    valor = media + desvio * z
    # Truncamos en 0.1 para evitar tiempos negativos o nulos
    valor = max(0.1, round(valor, 4))
    return valor, round(rnd1, 6), round(rnd2, 6)


def generar_uniforme(a, b):
    """
    Genera un valor con distribución uniforme entre a y b.
    Fórmula: a + (b-a) * rnd
    """
    rnd = random.random()
    valor = a + (b - a) * rnd
    return round(valor, 4), round(rnd, 6)
