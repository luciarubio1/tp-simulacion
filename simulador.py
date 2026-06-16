# -*- coding: utf-8 -*-
"""
MÓDULO SIMULADOR PRINCIPAL (MOTOR DE EVENTOS)
UTN FRC - TP5 - Grupo 18
-----------------------------------------------------------------------------
Contiene las clases del dominio y el motor principal de simulación por eventos.
"""

import random
from runge_kutta import runge_kutta_4
from generadores import generar_exponencial, generar_normal, generar_uniforme

# ─────────────────────────────────────────────────────────────────────────────
#  CLASES DEL SISTEMA
# ─────────────────────────────────────────────────────────────────────────────

class Competidor:
    _contador = 0

    def __init__(self, tiempo_llegada, rnd_categoria, rnd_llegada):
        Competidor._contador += 1
        self.id = Competidor._contador
        self.tiempo_llegada = tiempo_llegada
        self.rnd_llegada = rnd_llegada
        self.rnd_categoria = rnd_categoria
        
        # 60% Inicial, 40% Avanzado
        self.categoria = 'Inicial' if rnd_categoria < 0.60 else 'Avanzado'
        
        self.tiempo_inicio_atencion = None
        self.tiempo_fin_atencion = None
        self.juez_asignado = None
        self.tiempo_en_cola = 0
        
        # RNDs de atención
        self.rnd_atencion_1 = None
        self.rnd_atencion_2 = None
        self.tiempo_atencion = None


class Juez:
    def __init__(self, nombre):
        self.nombre = nombre
        self.estado = 'Libre' if nombre != 'Refuerzo' else 'Inactivo'
        self.competidor_actual = None
        self.tiempo_fin_atencion = None
        self.tiempo_ocupado_total = 0.0
        self.competidores_atendidos = 0
        
        # Para el juez de refuerzo
        self.tiempo_llegada_refuerzo = None
        self.tiempo_fin_turno = None
        self.activo = False
        self.convocado = False
        self.rnd_duracion_turno = None
        self.duracion_turno = None
        self.debe_retirarse = False
        
        # Inicio de periodo de ocupación (para cálculo de % ocupación)
        self._inicio_periodo_ocupado = None


# ─────────────────────────────────────────────────────────────────────────────
#  MOTOR DE SIMULACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def simular(params):
    """
    Simula el comportamiento del centro de evaluación por eventos discretos.
    Recibe parámetros configurados desde el frontend y retorna las filas del
    vector de estado, métricas y las tablas Runge-Kutta generadas.
    """
    T_MAX       = float(params.get('tiempo_maximo', 480))
    MAX_ITER    = int(params.get('max_iteraciones', 100000))
    ITER_DESDE  = int(params.get('iter_desde', 1))
    ITER_CANT   = int(params.get('iter_cantidad', 50))
    
    MEDIA_LLEGADAS  = float(params.get('media_llegadas', 5))
    MEDIA_INI       = float(params.get('media_ini', 8))
    DESVIO_INI      = float(params.get('desvio_ini', 2))
    MEDIA_AVAN      = float(params.get('media_avan', 12))
    DESVIO_AVAN     = float(params.get('desvio_avan', 3))
    MEDIA_CORTE     = float(params.get('media_corte', 2))
    H_RK            = float(params.get('h_rk', 0.1))
    UMBRAL_REFUERZO = int(params.get('umbral_refuerzo', 5))

    # Inicializar jueces
    Competidor._contador = 0
    julian  = Juez('Julian')
    enzo    = Juez('Enzo')
    refuerzo = Juez('Refuerzo')

    cola = []
    reloj = 0.0
    
    # Calcular primer corte con RK4
    E0_inicial = 20.0
    tiempo_primer_corte, tabla_rk_inicial = runge_kutta_4(E0_inicial, H_RK)
    
    # Eventos iniciales
    t_llegada, rnd_llegada = generar_exponencial(MEDIA_LLEGADAS)
    t_prox_llegada = t_llegada
    t_prox_corte = tiempo_primer_corte
    
    en_corte = False
    t_fin_corte = None
    
    # Acumuladores
    lista_tiempos_cola_ini  = []
    lista_tiempos_cola_avan = []
    
    vector_estado = []
    fila_final = None
    
    todas_las_tablas_rk = [
        {"titulo": f"RK4 - Primer corte (E0={E0_inicial}, h={H_RK})", "filas": tabla_rk_inicial}
    ]
    
    iteracion = 0

    # ─────────────────────────────────────────────────────────────────────────
    #  ASIGNACIÓN DESDE COLA (CORREGIDA)
    # ─────────────────────────────────────────────────────────────────────────
    def asignar_desde_cola():
        if en_corte or not cola:
            return
        
        while cola:
            comp = cola[0]
            if comp.categoria == 'Avanzado':
                if julian.estado == 'Libre':
                    _iniciar_atencion(comp, julian)
                    cola.pop(0)
                else:
                    # Avanzado al frente y Julián ocupado -> Cola bloqueada
                    break
            else:  # Inicial
                juez_libre = None
                if julian.estado == 'Libre':
                    juez_libre = julian
                elif enzo.estado == 'Libre':
                    juez_libre = enzo
                elif refuerzo.activo and refuerzo.estado == 'Libre':
                    juez_libre = refuerzo
                
                if juez_libre:
                    _iniciar_atencion(comp, juez_libre)
                    cola.pop(0)
                else:
                    # No hay jueces libres
                    break

    def _iniciar_atencion(comp, juez):
        comp.tiempo_inicio_atencion = reloj
        comp.tiempo_en_cola = reloj - comp.tiempo_llegada
        comp.juez_asignado = juez.nombre
        
        if comp.categoria == 'Inicial':
            t_aten, r1, r2 = generar_normal(MEDIA_INI, DESVIO_INI)
        else:
            t_aten, r1, r2 = generar_normal(MEDIA_AVAN, DESVIO_AVAN)
        
        comp.tiempo_atencion  = t_aten
        comp.rnd_atencion_1   = r1
        comp.rnd_atencion_2   = r2
        comp.tiempo_fin_atencion = reloj + t_aten
        
        juez.estado = 'Ocupado'
        juez.competidor_actual = comp
        juez.tiempo_fin_atencion = comp.tiempo_fin_atencion
        juez._inicio_periodo_ocupado = reloj

    # ─────────────────────────────────────────────────────────────────────────
    #  CONSTRUIR FILA DEL VECTOR DE ESTADO
    # ─────────────────────────────────────────────────────────────────────────
    def construir_fila(evento, detalles_evento=None, es_ultima=False):
        julian_estado = julian.estado
        julian_comp = julian.competidor_actual.id if julian.competidor_actual else '-'
        julian_fin  = round(julian.tiempo_fin_atencion, 4) if julian.tiempo_fin_atencion else '-'
        julian_cat  = julian.competidor_actual.categoria if julian.competidor_actual else '-'
        
        enzo_estado = enzo.estado
        enzo_comp   = enzo.competidor_actual.id if enzo.competidor_actual else '-'
        enzo_fin    = round(enzo.tiempo_fin_atencion, 4) if enzo.tiempo_fin_atencion else '-'
        enzo_cat    = enzo.competidor_actual.categoria if enzo.competidor_actual else '-'
        
        if not refuerzo.activo and not refuerzo.convocado:
            ref_estado = 'Inactivo'
        elif refuerzo.convocado and not refuerzo.activo:
            ref_estado = f'En camino (llega: {round(refuerzo.tiempo_llegada_refuerzo,2)})'
        else:
            ref_estado = refuerzo.estado
            
        ref_comp   = refuerzo.competidor_actual.id if refuerzo.competidor_actual else '-'
        ref_fin    = round(refuerzo.tiempo_fin_atencion, 4) if refuerzo.tiempo_fin_atencion else '-'
        ref_fin_turno = round(refuerzo.tiempo_fin_turno, 4) if refuerzo.tiempo_fin_turno else '-'
        
        cola_str = ', '.join([f"C{c.id}({c.categoria[0]})" for c in cola]) if cola else '[]'
        
        prox_llegada_str = round(t_prox_llegada, 4) if t_prox_llegada < float('inf') else 'inf'
        prox_corte_str   = round(t_prox_corte, 4)   if not en_corte else '-'
        fin_corte_str    = round(t_fin_corte, 4)     if en_corte else '-'
        
        # Serializar competidores activos
        competidores_activos = []
        for c in cola:
            competidores_activos.append({
                "id": c.id,
                "categoria": c.categoria,
                "tiempo_llegada": round(c.tiempo_llegada, 4),
                "estado": "En Cola",
                "tiempo_inicio_atencion": "-",
                "tiempo_fin_atencion": "-",
                "juez_asignado": "-",
                "tiempo_en_cola": round(reloj - c.tiempo_llegada, 4),
                "rnd_categoria": round(c.rnd_categoria, 6),
                "rnd_atencion_1": "-",
                "rnd_atencion_2": "-",
                "tiempo_atencion": "-",
                "rnd_llegada": round(c.rnd_llegada, 6)
            })
        if julian.competidor_actual:
            c = julian.competidor_actual
            competidores_activos.append({
                "id": c.id,
                "categoria": c.categoria,
                "tiempo_llegada": round(c.tiempo_llegada, 4),
                "estado": f"Evaluación ({julian_estado})",
                "tiempo_inicio_atencion": round(c.tiempo_inicio_atencion, 4),
                "tiempo_fin_atencion": round(c.tiempo_fin_atencion, 4),
                "juez_asignado": "Julian",
                "tiempo_en_cola": round(c.tiempo_en_cola, 4),
                "rnd_categoria": round(c.rnd_categoria, 6),
                "rnd_atencion_1": round(c.rnd_atencion_1, 6) if c.rnd_atencion_1 else "-",
                "rnd_atencion_2": round(c.rnd_atencion_2, 6) if c.rnd_atencion_2 else "-",
                "tiempo_atencion": round(c.tiempo_atencion, 4) if c.tiempo_atencion else "-",
                "rnd_llegada": round(c.rnd_llegada, 6)
            })
        if enzo.competidor_actual:
            c = enzo.competidor_actual
            competidores_activos.append({
                "id": c.id,
                "categoria": c.categoria,
                "tiempo_llegada": round(c.tiempo_llegada, 4),
                "estado": f"Evaluación ({enzo_estado})",
                "tiempo_inicio_atencion": round(c.tiempo_inicio_atencion, 4),
                "tiempo_fin_atencion": round(c.tiempo_fin_atencion, 4),
                "juez_asignado": "Enzo",
                "tiempo_en_cola": round(c.tiempo_en_cola, 4),
                "rnd_categoria": round(c.rnd_categoria, 6),
                "rnd_atencion_1": round(c.rnd_atencion_1, 6) if c.rnd_atencion_1 else "-",
                "rnd_atencion_2": round(c.rnd_atencion_2, 6) if c.rnd_atencion_2 else "-",
                "tiempo_atencion": round(c.tiempo_atencion, 4) if c.tiempo_atencion else "-",
                "rnd_llegada": round(c.rnd_llegada, 6)
            })
        if refuerzo.competidor_actual:
            c = refuerzo.competidor_actual
            competidores_activos.append({
                "id": c.id,
                "categoria": c.categoria,
                "tiempo_llegada": round(c.tiempo_llegada, 4),
                "estado": f"Evaluación ({ref_estado})",
                "tiempo_inicio_atencion": round(c.tiempo_inicio_atencion, 4),
                "tiempo_fin_atencion": round(c.tiempo_fin_atencion, 4),
                "juez_asignado": "Refuerzo",
                "tiempo_en_cola": round(c.tiempo_en_cola, 4),
                "rnd_categoria": round(c.rnd_categoria, 6),
                "rnd_atencion_1": round(c.rnd_atencion_1, 6) if c.rnd_atencion_1 else "-",
                "rnd_atencion_2": round(c.rnd_atencion_2, 6) if c.rnd_atencion_2 else "-",
                "tiempo_atencion": round(c.tiempo_atencion, 4) if c.tiempo_atencion else "-",
                "rnd_llegada": round(c.rnd_llegada, 6)
            })

        fila = {
            "iteracion":          iteracion,
            "evento":             evento,
            "reloj":              round(reloj, 4),
            
            "prox_llegada":       prox_llegada_str,
            "prox_corte":         prox_corte_str,
            "fin_corte":          fin_corte_str,
            "fin_aten_julian":    julian_fin,
            "fin_aten_enzo":      enzo_fin,
            "fin_aten_refuerzo":  ref_fin,
            "llegada_refuerzo":   round(refuerzo.tiempo_llegada_refuerzo, 4) if refuerzo.convocado else '-',
            "fin_turno_refuerzo": ref_fin_turno,
            
            "julian_estado":   julian_estado,
            "julian_comp_id":  julian_comp,
            "julian_comp_cat": julian_cat,
            
            "enzo_estado":     enzo_estado,
            "enzo_comp_id":    enzo_comp,
            "enzo_comp_cat":   enzo_cat,
            
            "ref_estado":      ref_estado,
            "ref_comp_id":     ref_comp,
            "ref_comp_cat":    '-',
            
            "cola_tamanio":  len(cola),
            "cola_detalle":  cola_str,
            "en_corte":   'Sí' if en_corte else 'No',
            
            "atendidos_julian":   julian.competidores_atendidos,
            "atendidos_enzo":     enzo.competidores_atendidos,
            "atendidos_refuerzo": refuerzo.competidores_atendidos,
            "competidores_activos": competidores_activos
        }
        
        if refuerzo.competidor_actual:
            fila["ref_comp_cat"] = refuerzo.competidor_actual.categoria
            
        if detalles_evento:
            fila.update(detalles_evento)
        
        return fila

    # ─────────────────────────────────────────────────────────────────────────
    #  LOOP DE EVENTOS
    # ─────────────────────────────────────────────────────────────────────────
    while iteracion < MAX_ITER:
        eventos_posibles = []
        
        if t_prox_llegada < float('inf'):
            eventos_posibles.append(('llegada_competidor', t_prox_llegada))
        
        if julian.estado == 'Ocupado' and julian.tiempo_fin_atencion:
            eventos_posibles.append(('fin_atencion_julian', julian.tiempo_fin_atencion))
            
        if enzo.estado == 'Ocupado' and enzo.tiempo_fin_atencion:
            eventos_posibles.append(('fin_atencion_enzo', enzo.tiempo_fin_atencion))
            
        if refuerzo.activo and refuerzo.estado == 'Ocupado' and refuerzo.tiempo_fin_atencion:
            eventos_posibles.append(('fin_atencion_refuerzo', refuerzo.tiempo_fin_atencion))
            
        if refuerzo.convocado and not refuerzo.activo:
            eventos_posibles.append(('llegada_refuerzo', refuerzo.tiempo_llegada_refuerzo))
            
        if refuerzo.activo and refuerzo.tiempo_fin_turno:
            eventos_posibles.append(('fin_turno_refuerzo', refuerzo.tiempo_fin_turno))
            
        if not en_corte:
            eventos_posibles.append(('corte_electrico', t_prox_corte))
            
        if en_corte and t_fin_corte:
            eventos_posibles.append(('fin_corte_electrico', t_fin_corte))
            
        if not eventos_posibles:
            break
        
        evento_tipo, t_evento = min(eventos_posibles, key=lambda x: x[1])
        
        if t_evento > T_MAX:
            reloj = T_MAX
            for juez in [julian, enzo, refuerzo]:
                if juez._inicio_periodo_ocupado is not None:
                    juez.tiempo_ocupado_total += reloj - juez._inicio_periodo_ocupado
                    juez._inicio_periodo_ocupado = None
            fila_final = construir_fila('Fin simulación (tiempo X)', es_ultima=True)
            break
        
        reloj = t_evento
        iteracion += 1
        detalles = {}
        
        # ── EVENTO: LLEGADA ──────────────────────────────────────────────────
        if evento_tipo == 'llegada_competidor':
            rnd_cat = random.random()
            comp = Competidor(reloj, rnd_cat, round(rnd_llegada, 6))
            
            detalles['rnd_categoria']  = round(rnd_cat, 6)
            detalles['comp_id_nuevo']  = comp.id
            detalles['comp_cat_nuevo'] = comp.categoria
            
            cola.append(comp)
            
            if len(cola) >= UMBRAL_REFUERZO and not refuerzo.activo and not refuerzo.convocado:
                refuerzo.convocado = True
                refuerzo.tiempo_llegada_refuerzo = reloj + 10
                detalles['evento_refuerzo'] = f'Convocado! Llega t={round(reloj+10,2)}'
            
            if not en_corte:
                asignar_desde_cola()
            
            t_inter, rnd_llegada = generar_exponencial(MEDIA_LLEGADAS)
            t_prox_llegada = reloj + t_inter
            detalles['rnd_llegada']   = round(rnd_llegada, 6)
            detalles['prox_llegada_calc'] = round(t_prox_llegada, 4)
            
        # ── EVENTO: FIN ATENCIÓN JULIÁN ──────────────────────────────────────
        elif evento_tipo == 'fin_atencion_julian':
            comp = julian.competidor_actual
            
            if comp.categoria == 'Inicial':
                lista_tiempos_cola_ini.append(comp.tiempo_en_cola)
            else:
                lista_tiempos_cola_avan.append(comp.tiempo_en_cola)
            
            julian.tiempo_ocupado_total += reloj - julian._inicio_periodo_ocupado
            julian.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            julian.estado = 'Libre'
            julian.competidor_actual = None
            julian.tiempo_fin_atencion = None
            julian._inicio_periodo_ocupado = None
            
            if not en_corte:
                asignar_desde_cola()
                
        # ── EVENTO: FIN ATENCIÓN ENZO ────────────────────────────────────────
        elif evento_tipo == 'fin_atencion_enzo':
            comp = enzo.competidor_actual
            
            if comp.categoria == 'Inicial':
                lista_tiempos_cola_ini.append(comp.tiempo_en_cola)
            else:
                lista_tiempos_cola_avan.append(comp.tiempo_en_cola)
            
            enzo.tiempo_ocupado_total += reloj - enzo._inicio_periodo_ocupado
            enzo.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            enzo.estado = 'Libre'
            enzo.competidor_actual = None
            enzo.tiempo_fin_atencion = None
            enzo._inicio_periodo_ocupado = None
            
            if not en_corte:
                asignar_desde_cola()
                
        # ── EVENTO: FIN ATENCIÓN REFUERZO ────────────────────────────────────
        elif evento_tipo == 'fin_atencion_refuerzo':
            comp = refuerzo.competidor_actual
            
            if comp.categoria == 'Inicial':
                lista_tiempos_cola_ini.append(comp.tiempo_en_cola)
            else:
                lista_tiempos_cola_avan.append(comp.tiempo_en_cola)
            
            refuerzo.tiempo_ocupado_total += reloj - refuerzo._inicio_periodo_ocupado
            refuerzo.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            refuerzo.competidor_actual = None
            refuerzo.tiempo_fin_atencion = None
            refuerzo._inicio_periodo_ocupado = None
            
            if refuerzo.debe_retirarse:
                refuerzo.activo = False
                refuerzo.estado = 'Inactivo'
                refuerzo.debe_retirarse = False
                detalles['ref_decision'] = 'Se retiró del sistema tras terminar atención'
            else:
                refuerzo.estado = 'Libre'
                if not en_corte:
                    asignar_desde_cola()
                    
        # ── EVENTO: LLEGADA DEL REFUERZO ─────────────────────────────────────
        elif evento_tipo == 'llegada_refuerzo':
            refuerzo.activo = True
            refuerzo.convocado = False
            refuerzo.estado = 'Libre'
            
            dur_turno, rnd_dur = generar_uniforme(30, 50)
            refuerzo.duracion_turno = dur_turno
            refuerzo.rnd_duracion_turno = rnd_dur
            refuerzo.tiempo_fin_turno = reloj + dur_turno
            
            detalles['rnd_dur_refuerzo'] = round(rnd_dur, 6)
            detalles['dur_turno_ref']    = round(dur_turno, 4)
            detalles['fin_turno_ref']    = round(refuerzo.tiempo_fin_turno, 4)
            
            if not en_corte:
                asignar_desde_cola()
                
        # ── EVENTO: FIN TURNO REFUERZO ───────────────────────────────────────
        elif evento_tipo == 'fin_turno_refuerzo':
            if len(cola) <= 1:
                if refuerzo.competidor_actual is not None:
                    refuerzo.debe_retirarse = True
                    refuerzo.tiempo_fin_turno = None
                    detalles['ref_decision'] = 'Programó retiro tras finalizar atención (cola <= 1)'
                else:
                    refuerzo.activo = False
                    refuerzo.estado = 'Inactivo'
                    refuerzo.tiempo_fin_turno = None
                    detalles['ref_decision'] = 'Se retira inmediatamente (cola <= 1)'
            else:
                renovacion, rnd_ren = generar_uniforme(10, 18)
                refuerzo.tiempo_fin_turno = reloj + renovacion
                refuerzo.rnd_duracion_turno = rnd_ren
                detalles['ref_decision'] = f'Renovó turno {round(renovacion,2)} min'
                detalles['rnd_renovacion'] = round(rnd_ren, 6)
                
        # ── EVENTO: CORTE ELÉCTRICO ──────────────────────────────────────────
        elif evento_tipo == 'corte_electrico':
            en_corte = True
            dur_corte, rnd_corte = generar_exponencial(MEDIA_CORTE)
            t_fin_corte = reloj + dur_corte
            
            detalles['rnd_corte']   = round(rnd_corte, 6)
            detalles['dur_corte']   = round(dur_corte, 4)
            detalles['fin_corte_calc'] = round(t_fin_corte, 4)
            
            for juez in [julian, enzo, refuerzo]:
                if juez.estado == 'Ocupado':
                    juez.estado = 'Interrumpido'
                    juez.tiempo_fin_atencion += dur_corte
                    if juez.competidor_actual:
                        juez.competidor_actual.tiempo_fin_atencion += dur_corte
                        
        # ── EVENTO: FIN CORTE ELÉCTRICO ──────────────────────────────────────
        elif evento_tipo == 'fin_corte_electrico':
            en_corte = False
            t_fin_corte = None
            
            for juez in [julian, enzo, refuerzo]:
                if juez.estado == 'Interrumpido':
                    juez.estado = 'Ocupado'
            
            E0_nuevo = reloj
            tiempo_siguiente_corte, tabla_rk_nueva = runge_kutta_4(E0_nuevo, H_RK)
            t_prox_corte = reloj + tiempo_siguiente_corte
            
            todas_las_tablas_rk.append({
                "titulo": f"RK4 - Corte desde reloj={round(reloj,2)} (E0={E0_nuevo}, h={H_RK})",
                "filas": tabla_rk_nueva
            })
            
            detalles['nuevo_e0']         = round(E0_nuevo, 4)
            detalles['prox_corte_calc']  = round(t_prox_corte, 4)
            
            asignar_desde_cola()
            
        fila = construir_fila(evento_tipo, detalles)
        if ITER_DESDE <= iteracion < ITER_DESDE + ITER_CANT:
            vector_estado.append(fila)

    if fila_final is None:
        for juez in [julian, enzo, refuerzo]:
            if juez._inicio_periodo_ocupado is not None:
                juez.tiempo_ocupado_total += reloj - juez._inicio_periodo_ocupado
                juez._inicio_periodo_ocupado = None
        fila_final = construir_fila('Fin simulación (límite iteraciones)', es_ultima=True)

    vector_estado.append({**fila_final, "es_ultima_fila": True})
    
    # Métricas
    tiempo_total_sim = reloj
    
    prom_cola_ini  = (sum(lista_tiempos_cola_ini) / len(lista_tiempos_cola_ini)
                      if lista_tiempos_cola_ini else 0)
    prom_cola_avan = (sum(lista_tiempos_cola_avan) / len(lista_tiempos_cola_avan)
                      if lista_tiempos_cola_avan else 0)
    prom_cola_total = (
        (sum(lista_tiempos_cola_ini) + sum(lista_tiempos_cola_avan))
        / (len(lista_tiempos_cola_ini) + len(lista_tiempos_cola_avan))
        if (lista_tiempos_cola_ini or lista_tiempos_cola_avan) else 0
    )

    pct_ocupacion_enzo = (enzo.tiempo_ocupado_total / tiempo_total_sim * 100
                          if tiempo_total_sim > 0 else 0)
    pct_ocupacion_julian = (julian.tiempo_ocupado_total / tiempo_total_sim * 100
                            if tiempo_total_sim > 0 else 0)
    pct_ocupacion_refuerzo = (refuerzo.tiempo_ocupado_total / tiempo_total_sim * 100
                              if tiempo_total_sim > 0 else 0)

    atendidos_julian   = julian.competidores_atendidos
    atendidos_enzo     = enzo.competidores_atendidos
    atendidos_refuerzo = refuerzo.competidores_atendidos
    total_atendidos    = atendidos_julian + atendidos_enzo + atendidos_refuerzo

    total_ini  = len(lista_tiempos_cola_ini)
    total_avan = len(lista_tiempos_cola_avan)
    
    max_espera = max(
        (max(lista_tiempos_cola_ini)  if lista_tiempos_cola_ini  else 0),
        (max(lista_tiempos_cola_avan) if lista_tiempos_cola_avan else 0)
    )

    metricas = {
        "prom_cola_inicial":       round(prom_cola_ini, 4),
        "prom_cola_avanzado":      round(prom_cola_avan, 4),
        "prom_cola_total":         round(prom_cola_total, 4),
        "pct_ocupacion_enzo":      round(pct_ocupacion_enzo, 2),
        "pct_ocupacion_julian":    round(pct_ocupacion_julian, 2),
        "pct_ocupacion_refuerzo":  round(pct_ocupacion_refuerzo, 2),
        "atendidos_julian":        atendidos_julian,
        "atendidos_enzo":          atendidos_enzo,
        "atendidos_refuerzo":      atendidos_refuerzo,
        "total_atendidos":         total_atendidos,
        "total_ini_atendidos":     total_ini,
        "total_avan_atendidos":    total_avan,
        "max_tiempo_espera":       round(max_espera, 4),
        "tiempo_simulado":         round(tiempo_total_sim, 4),
        "iteraciones_totales":     iteracion,
    }

    return {
        "vector_estado":   vector_estado,
        "tablas_rk":       todas_las_tablas_rk,
        "metricas":        metricas,
    }
