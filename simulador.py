# -*- coding: utf-8 -*-
"""
MÓDULO SIMULADOR PRINCIPAL (MOTOR DE EVENTOS)
UTN FRC - TP5 - Grupo 18
-----------------------------------------------------------------------------
Contiene las clases del dominio y el motor principal de simulación por eventos.
"""

import random
from runge_kutta import runge_kutta_4
from generadores import generar_exponencial, generar_normal, generar_uniforme, inicializar_generadores

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
        
        # Slot estático para el vector de estado
        self.slot_idx = -1


class Juez:
    def __init__(self, nombre):
        self.nombre = nombre
        self.estado = 'Libre' if nombre != 'Refuerzo' else 'Inactivo'
        self.competidor_actual = None
        self.tiempo_fin_atencion = None
        self.tiempo_ocupado_total = 0.0
        self.competidores_atendidos = 0
        self.cached_t_ini = None   # Caché Box-Muller para competidores Iniciales
        self.cached_t_avan = None  # Caché Box-Muller para competidores Avanzados (solo Julián)
        
        # Para el juez de refuerzo
        self.tiempo_llegada_refuerzo = None
        self.tiempo_fin_turno = None
        self.activo = False
        self.convocado = False
        self.rnd_duracion_turno = None
        self.duracion_turno = None
        self.debe_retirarse = False


def simular(params):
    """
    Simula el comportamiento del centro de evaluación por eventos discretos.
    """
    inicializar_generadores()
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
    reloj_anterior = 0.0
    
    # Slots de competidores activos (15 posiciones fijas)
    competidores_slots = [None] * 15

    def ocupar_slot(comp):
        for idx in range(15):
            if competidores_slots[idx] is None:
                competidores_slots[idx] = comp
                comp.slot_idx = idx
                return idx
        return -1

    def liberar_slot(comp):
        if comp and comp.slot_idx != -1:
            competidores_slots[comp.slot_idx] = None
            comp.slot_idx = -1
    
    # Calcular primer corte con RK4
    E0_inicial = 20.0
    tiempo_primer_corte, tabla_rk_inicial = runge_kutta_4(E0_inicial, H_RK)
    t_final_rk_inicial = tabla_rk_inicial[-1]['t'] if tabla_rk_inicial else 0.0
    
    # Eventos iniciales
    t_llegada, rnd_llegada = generar_exponencial(MEDIA_LLEGADAS)
    t_prox_llegada = t_llegada
    t_prox_corte = tiempo_primer_corte
    
    en_corte = False
    t_fin_corte = None
    
    # Acumuladores y contadores
    lista_tiempos_cola_ini  = []
    lista_tiempos_cola_avan = []
    
    acum_espera_ini = 0.0
    cont_espera_ini = 0
    acum_espera_avan = 0.0
    cont_espera_avan = 0
    max_espera = 0.0
    
    acum_ocupacion_julian = 0.0
    acum_ocupacion_enzo = 0.0
    acum_ocupacion_refuerzo = 0.0
    
    vector_estado = []
    fila_final = None
    
    todas_las_tablas_rk = [
        {"titulo": f"RK4 - Primer corte (E0={E0_inicial}, h={H_RK})", "filas": tabla_rk_inicial}
    ]
    
    iteracion = 0

    # ─────────────────────────────────────────────────────────────────────────
    #  ASIGNACIÓN DESDE COLA (CORREGIDA CON CAPTURA DE DETALLES)
    # ─────────────────────────────────────────────────────────────────────────
    def asignar_desde_cola(detalles_dict=None):
        if en_corte or not cola:
            return
        
        while cola:
            comp = cola[0]
            if comp.categoria == 'Avanzado':
                if julian.estado == 'Libre':
                    _iniciar_atencion(comp, julian, detalles_dict)
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
                    _iniciar_atencion(comp, juez_libre, detalles_dict)
                    cola.pop(0)
                else:
                    # No hay jueces libres
                    break

    def _iniciar_atencion(comp, juez, detalles_dict=None):
        comp.tiempo_inicio_atencion = reloj
        comp.tiempo_en_cola = reloj - comp.tiempo_llegada
        comp.juez_asignado = juez.nombre
        
        espera = comp.tiempo_en_cola
        nonlocal acum_espera_ini, cont_espera_ini, acum_espera_avan, cont_espera_avan, max_espera
        if comp.categoria == 'Inicial':
            acum_espera_ini += espera
            cont_espera_ini += 1
            lista_tiempos_cola_ini.append(espera)
        else:
            acum_espera_avan += espera
            cont_espera_avan += 1
            lista_tiempos_cola_avan.append(espera)
            
        max_espera = max(max_espera, espera)
        
        if comp.categoria == 'Inicial':
            t_aten, r1, r2, t_at1, t_at2 = generar_normal(MEDIA_INI, DESVIO_INI, cache_owner=juez, categoria='Inicial')
        else:
            t_aten, r1, r2, t_at1, t_at2 = generar_normal(MEDIA_AVAN, DESVIO_AVAN, cache_owner=juez, categoria='Avanzado')
        
        comp.tiempo_atencion  = t_aten
        comp.rnd_atencion_1   = r1
        comp.rnd_atencion_2   = r2
        comp.tiempo_fin_atencion = reloj + t_aten
        
        juez.estado = 'Ocupado'
        juez.competidor_actual = comp
        juez.tiempo_fin_atencion = comp.tiempo_fin_atencion
        
        if detalles_dict is not None:
            # Separar variables según el juez asignado y la categoría del competidor
            if juez.nombre == 'Julian':
                if comp.categoria == 'Inicial':
                    detalles_dict['var_rnd_at1_julian'] = r1
                    detalles_dict['var_rnd_at2_julian'] = r2
                    detalles_dict['var_t_at1_julian'] = t_at1
                    detalles_dict['var_t_at2_julian'] = t_at2
                else:  # Avanzado
                    detalles_dict['var_rnd_at1_julian_avan'] = r1
                    detalles_dict['var_rnd_at2_julian_avan'] = r2
                    detalles_dict['var_t_at1_julian_avan'] = t_at1
                    detalles_dict['var_t_at2_julian_avan'] = t_at2
            elif juez.nombre == 'Enzo':
                detalles_dict['var_rnd_at1_enzo'] = r1
                detalles_dict['var_rnd_at2_enzo'] = r2
                detalles_dict['var_t_at1_enzo'] = t_at1
                detalles_dict['var_t_at2_enzo'] = t_at2
            elif juez.nombre == 'Refuerzo':
                detalles_dict['var_rnd_at1_refuerzo'] = r1
                detalles_dict['var_rnd_at2_refuerzo'] = r2
                detalles_dict['var_t_at1_refuerzo'] = t_at1
                detalles_dict['var_t_at2_refuerzo'] = t_at2

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
        
        # Serializar competidores activos para el panel inferior
        competidores_activos = []
        for c in cola:
            competidores_activos.append({
                "id": c.id,
                "categoria": c.categoria,
                "tiempo_llegada": round(c.tiempo_llegada, 4),
                "estado": f"EA({c.categoria[0]})",
                "tiempo_inicio_atencion": "-",
                "tiempo_fin_atencion": "-",
                "juez_asignado": "-",
                "tiempo_en_cola": round(reloj - c.tiempo_llegada, 4),
                "rnd_categoria": round(c.rnd_categoria, 2),
                "rnd_atencion_1": "-",
                "rnd_atencion_2": "-",
                "tiempo_atencion": "-",
                "rnd_llegada": round(c.rnd_llegada, 2)
            })
        for juez_obj in [julian, enzo, refuerzo]:
            if juez_obj.competidor_actual:
                c = juez_obj.competidor_actual
                est_juez_str = "SUSP" if juez_obj.estado == 'Interrumpido' else "SA"
                competidores_activos.append({
                    "id": c.id,
                    "categoria": c.categoria,
                    "tiempo_llegada": round(c.tiempo_llegada, 4),
                    "estado": f"{est_juez_str}({juez_obj.nombre[:3]})",
                    "tiempo_inicio_atencion": round(c.tiempo_inicio_atencion, 4),
                    "tiempo_fin_atencion": round(c.tiempo_fin_atencion, 4),
                    "juez_asignado": juez_obj.nombre,
                    "tiempo_en_cola": round(c.tiempo_en_cola, 4),
                    "rnd_categoria": round(c.rnd_categoria, 2),
                    "rnd_atencion_1": round(c.rnd_atencion_1, 2) if isinstance(c.rnd_atencion_1, (int, float)) else "-",
                    "rnd_atencion_2": round(c.rnd_atencion_2, 2) if isinstance(c.rnd_atencion_2, (int, float)) else "-",
                    "tiempo_atencion": round(c.tiempo_atencion, 4) if isinstance(c.tiempo_atencion, (int, float)) else "-",
                    "rnd_llegada": round(c.rnd_llegada, 2)
                })

        # Inicializar variables aleatorias del evento actual
        rnd_llegada_val = '-'
        t_llegada_val = '-'
        rnd_cat_val = '-'
        cat_val = '-'
        
        # Jueces por separado
        rnd_at1_julian = '-'
        rnd_at2_julian = '-'
        t_at1_julian = '-'
        t_at2_julian = '-'
        rnd_at1_enzo = '-'
        rnd_at2_enzo = '-'
        t_at1_enzo = '-'
        t_at2_enzo = '-'
        rnd_at1_refuerzo = '-'
        rnd_at2_refuerzo = '-'
        t_at1_refuerzo = '-'
        t_at2_refuerzo = '-'
        
        # Julián - columnas extra para competidores Avanzados
        rnd_at1_julian_avan = '-'
        rnd_at2_julian_avan = '-'
        t_at1_julian_avan = '-'
        t_at2_julian_avan = '-'
        
        rnd_corte_val = '-'
        t_corte_val = '-'
        rnd_turno_val = '-'
        t_turno_val = '-'
        rk_e0_val = '-'
        rk_t_final_val = '-'

        if detalles_evento:
            rnd_llegada_val = detalles_evento.get('var_rnd_llegada', '-')
            t_llegada_val = detalles_evento.get('var_t_llegada', '-')
            rnd_cat_val = detalles_evento.get('var_rnd_cat', '-')
            cat_val = detalles_evento.get('var_cat', '-')
            
            # Julián
            rnd_at1_julian = detalles_evento.get('var_rnd_at1_julian', '-')
            rnd_at2_julian = detalles_evento.get('var_rnd_at2_julian', '-')
            t_at1_julian = detalles_evento.get('var_t_at1_julian', '-')
            t_at2_julian = detalles_evento.get('var_t_at2_julian', '-')
            
            # Enzo
            rnd_at1_enzo = detalles_evento.get('var_rnd_at1_enzo', '-')
            rnd_at2_enzo = detalles_evento.get('var_rnd_at2_enzo', '-')
            t_at1_enzo = detalles_evento.get('var_t_at1_enzo', '-')
            t_at2_enzo = detalles_evento.get('var_t_at2_enzo', '-')
            
            # Refuerzo
            rnd_at1_refuerzo = detalles_evento.get('var_rnd_at1_refuerzo', '-')
            rnd_at2_refuerzo = detalles_evento.get('var_rnd_at2_refuerzo', '-')
            t_at1_refuerzo = detalles_evento.get('var_t_at1_refuerzo', '-')
            t_at2_refuerzo = detalles_evento.get('var_t_at2_refuerzo', '-')
            
            # Julián - Avanzados
            rnd_at1_julian_avan = detalles_evento.get('var_rnd_at1_julian_avan', '-')
            rnd_at2_julian_avan = detalles_evento.get('var_rnd_at2_julian_avan', '-')
            t_at1_julian_avan = detalles_evento.get('var_t_at1_julian_avan', '-')
            t_at2_julian_avan = detalles_evento.get('var_t_at2_julian_avan', '-')
            
            rnd_corte_val = detalles_evento.get('var_rnd_corte', '-')
            t_corte_val = detalles_evento.get('var_t_corte', '-')
            rnd_turno_val = detalles_evento.get('var_rnd_turno', '-')
            t_turno_val = detalles_evento.get('var_t_turno', '-')
            rk_e0_val = detalles_evento.get('rk_e0', '-')
            rk_t_final_val = detalles_evento.get('rk_t_final', '-')

        def format_float(val, dec=4):
            if isinstance(val, (int, float)):
                return round(val, dec)
            return val

        # Formatear la información de los 15 slots fijos de competidores
        slots_info = []
        for idx in range(15):
            comp = competidores_slots[idx]
            if comp is None:
                slots_info.append({"estado": "-", "hora_llegada": "-"})
            else:
                if comp in cola:
                    est_str = f"EA({comp.categoria[0]})"
                elif julian.competidor_actual == comp:
                    est_str = "SUSP(Jul)" if julian.estado == 'Interrumpido' else "SA(Jul)"
                elif enzo.competidor_actual == comp:
                    est_str = "SUSP(Enz)" if enzo.estado == 'Interrumpido' else "SA(Enz)"
                elif refuerzo.competidor_actual == comp:
                    est_str = "SUSP(Ref)" if refuerzo.estado == 'Interrumpido' else "SA(Ref)"
                else:
                    est_str = "-"
                slots_info.append({
                    "estado": est_str,
                    "hora_llegada": round(comp.tiempo_llegada, 4)
                })

        fila = {
            "iteracion":          iteracion,
            "evento":             evento,
            "reloj":              round(reloj, 4),
            
            # Variables Aleatorias Generadas (Llegada)
            "var_rnd_llegada":    rnd_llegada_val,
            "var_t_llegada":      format_float(t_llegada_val, 4),
            "var_rnd_cat":        rnd_cat_val,
            "var_cat":            cat_val,
            
            # Variables de Atención Julián
            "var_rnd_at1_julian": rnd_at1_julian,
            "var_rnd_at2_julian": rnd_at2_julian,
            "var_t_at1_julian":   format_float(t_at1_julian, 4),
            "var_t_at2_julian":   format_float(t_at2_julian, 4),
            
            # Variables de Atención Julián - Avanzados (columnas extra)
            "var_rnd_at1_julian_avan": rnd_at1_julian_avan,
            "var_rnd_at2_julian_avan": rnd_at2_julian_avan,
            "var_t_at1_julian_avan":   format_float(t_at1_julian_avan, 4),
            "var_t_at2_julian_avan":   format_float(t_at2_julian_avan, 4),
            
            # Variables de Atención Enzo
            "var_rnd_at1_enzo":   rnd_at1_enzo,
            "var_rnd_at2_enzo":   rnd_at2_enzo,
            "var_t_at1_enzo":     format_float(t_at1_enzo, 4),
            "var_t_at2_enzo":     format_float(t_at2_enzo, 4),
            
            # Variables de Atención Refuerzo
            "var_rnd_at1_refuerzo": rnd_at1_refuerzo,
            "var_rnd_at2_refuerzo": rnd_at2_refuerzo,
            "var_t_at1_refuerzo":  format_float(t_at1_refuerzo, 4),
            "var_t_at2_refuerzo":  format_float(t_at2_refuerzo, 4),
            
            # Variables de Corte e Integración RK4
            "var_rnd_corte":      rnd_corte_val,
            "var_t_corte":        format_float(t_corte_val, 4),
            "var_rnd_turno":      rnd_turno_val,
            "var_t_turno":        format_float(t_turno_val, 4),
            "rk_e0":              rk_e0_val,
            "rk_t_final":         rk_t_final_val,

            # Próximos eventos Clocks
            "prox_llegada":       prox_llegada_str,
            "prox_corte":         prox_corte_str,
            "fin_corte":          fin_corte_str,
            "fin_aten_julian":    julian_fin,
            "fin_aten_enzo":      enzo_fin,
            "fin_aten_refuerzo":  ref_fin,
            "llegada_refuerzo":   round(refuerzo.tiempo_llegada_refuerzo, 4) if refuerzo.convocado else '-',
            "fin_turno_refuerzo": ref_fin_turno,
            
            # Servidores
            "julian_estado":   julian_estado,
            "julian_comp_id":  julian_comp,
            "julian_comp_cat": julian_cat,
            
            "enzo_estado":     enzo_estado,
            "enzo_comp_id":    enzo_comp,
            "enzo_comp_cat":   enzo_cat,
            
            "ref_estado":      ref_estado,
            "ref_comp_id":     ref_comp,
            "ref_comp_cat":    '-',
            
            # Cola
            "cola_tamanio":  len(cola),
            "cola_detalle":  cola_str,
            "en_corte":   'Sí' if en_corte else 'No',
            
            # Acumuladores y Contadores
            "acum_espera_ini":    round(acum_espera_ini, 4),
            "cont_espera_ini":    cont_espera_ini,
            "acum_espera_avan":   round(acum_espera_avan, 4),
            "cont_espera_avan":   cont_espera_avan,
            "acum_ocupacion_julian": round(acum_ocupacion_julian, 4),
            "acum_ocupacion_enzo":   round(acum_ocupacion_enzo, 4),
            "acum_ocupacion_refuerzo": round(acum_ocupacion_refuerzo, 4),
            "cont_atendidos_julian": julian.competidores_atendidos,
            "cont_atendidos_enzo":   enzo.competidores_atendidos,
            "cont_atendidos_refuerzo": refuerzo.competidores_atendidos,
            "max_espera":         round(max_espera, 4),
            
            # Slots estáticos de competidores
            "slots":              slots_info,
            
            "competidores_activos": competidores_activos
        }
        
        if refuerzo.competidor_actual:
            fila["ref_comp_cat"] = refuerzo.competidor_actual.categoria
            
        return fila

    # ── AGREGAR FILA INICIAL (Inicio) ────────────────────────────────────────
    detalles_inicio = {
        'var_rnd_llegada': rnd_llegada,
        'var_t_llegada': t_llegada,
        'rk_e0': E0_inicial,
        'rk_t_final': round(t_final_rk_inicial, 4)
    }
    fila_inicio = construir_fila('Inicio', detalles_inicio)
    if ITER_DESDE <= 0 or ITER_DESDE == 1:
        vector_estado.append(fila_inicio)

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
        
        # Calcular delta_t para acumular ocupación del paso que está terminando
        t_limitado = min(t_evento, T_MAX)
        delta_t = t_limitado - reloj
        if delta_t > 0:
            if julian.estado in ('Ocupado', 'Interrumpido'):
                acum_ocupacion_julian += delta_t
            if enzo.estado in ('Ocupado', 'Interrumpido'):
                acum_ocupacion_enzo += delta_t
            if refuerzo.estado in ('Ocupado', 'Interrumpido'):
                acum_ocupacion_refuerzo += delta_t
        
        if t_evento > T_MAX:
            reloj = T_MAX
            fila_final = construir_fila('Fin simulación (tiempo X)', es_ultima=True)
            break
        
        reloj = t_evento
        iteracion += 1
        detalles = {}
        
        # ── EVENTO: LLEGADA ──────────────────────────────────────────────────
        if evento_tipo == 'llegada_competidor':
            rnd_cat = round(random.random(), 2)
            comp = Competidor(reloj, rnd_cat, rnd_llegada)
            
            # Asignar slot fijo para esta fila
            ocupar_slot(comp)
            
            detalles['var_rnd_cat']  = rnd_cat
            detalles['var_cat'] = comp.categoria
            
            cola.append(comp)
            
            if len(cola) >= UMBRAL_REFUERZO and not refuerzo.activo and not refuerzo.convocado:
                refuerzo.convocado = True
                refuerzo.tiempo_llegada_refuerzo = reloj + 10
            
            if not en_corte:
                asignar_desde_cola(detalles)
            
            t_inter, rnd_llegada_sig = generar_exponencial(MEDIA_LLEGADAS)
            t_prox_llegada = reloj + t_inter
            
            detalles['var_rnd_llegada'] = rnd_llegada_sig
            detalles['var_t_llegada']   = t_inter
            rnd_llegada = rnd_llegada_sig
            
        # ── EVENTO: FIN ATENCIÓN JULIÁN ──────────────────────────────────────
        elif evento_tipo == 'fin_atencion_julian':
            comp = julian.competidor_actual
            julian.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            # Liberar slot fijo del competidor que abandona el sistema
            liberar_slot(comp)
            
            julian.estado = 'Libre'
            julian.competidor_actual = None
            julian.tiempo_fin_atencion = None
            
            if not en_corte:
                asignar_desde_cola(detalles)
                
        # ── EVENTO: FIN ATENCIÓN ENZO ────────────────────────────────────────
        elif evento_tipo == 'fin_atencion_enzo':
            comp = enzo.competidor_actual
            enzo.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            # Liberar slot fijo
            liberar_slot(comp)
            
            enzo.estado = 'Libre'
            enzo.competidor_actual = None
            enzo.tiempo_fin_atencion = None
            
            if not en_corte:
                asignar_desde_cola(detalles)
                
        # ── EVENTO: FIN ATENCIÓN REFUERZO ────────────────────────────────────
        elif evento_tipo == 'fin_atencion_refuerzo':
            comp = refuerzo.competidor_actual
            refuerzo.competidores_atendidos += 1
            
            detalles['comp_id_fin']  = comp.id
            detalles['comp_cat_fin'] = comp.categoria
            detalles['tiempo_cola_comp'] = round(comp.tiempo_en_cola, 4)
            
            # Liberar slot fijo
            liberar_slot(comp)
            
            refuerzo.competidor_actual = None
            refuerzo.tiempo_fin_atencion = None
            
            if refuerzo.debe_retirarse:
                refuerzo.activo = False
                refuerzo.estado = 'Inactivo'
                refuerzo.debe_retirarse = False
                detalles['ref_decision'] = 'Se retiró del sistema tras terminar atención'
            else:
                refuerzo.estado = 'Libre'
                if not en_corte:
                    asignar_desde_cola(detalles)
                    
        # ── EVENTO: LLEGADA DEL REFUERZO ─────────────────────────────────────
        elif evento_tipo == 'llegada_refuerzo':
            refuerzo.activo = True
            refuerzo.convocado = False
            refuerzo.estado = 'Libre'
            
            dur_turno, rnd_dur = generar_uniforme(30, 50)
            refuerzo.duracion_turno = dur_turno
            refuerzo.rnd_duracion_turno = rnd_dur
            refuerzo.tiempo_fin_turno = reloj + dur_turno
            
            detalles['var_rnd_turno'] = rnd_dur
            detalles['var_t_turno']   = dur_turno
            
            if not en_corte:
                asignar_desde_cola(detalles)
                
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
                
                detalles['var_rnd_turno'] = rnd_ren
                detalles['var_t_turno']   = renovacion
                detalles['ref_decision'] = f'Renovó turno {round(renovacion,2)} min'
                
        # ── EVENTO: CORTE ELÉCTRICO ──────────────────────────────────────────
        elif evento_tipo == 'corte_electrico':
            en_corte = True
            dur_corte, rnd_corte = generar_exponencial(MEDIA_CORTE)
            t_fin_corte = reloj + dur_corte
            
            detalles['var_rnd_corte'] = rnd_corte
            detalles['var_t_corte']   = dur_corte
            
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
            
            t_final_rk_nueva = tabla_rk_nueva[-1]['t'] if tabla_rk_nueva else 0.0
            
            todas_las_tablas_rk.append({
                "titulo": f"RK4 - Corte desde reloj={round(reloj,2)} (E0={E0_nuevo}, h={H_RK})",
                "filas": tabla_rk_nueva
            })
            
            detalles['rk_e0']      = round(E0_nuevo, 4)
            detalles['rk_t_final'] = round(t_final_rk_nueva, 4)
            detalles['prox_corte_calc']  = round(t_prox_corte, 4)
            
            asignar_desde_cola(detalles)
            
        fila = construir_fila(evento_tipo, detalles)
        if ITER_DESDE <= iteracion < ITER_DESDE + ITER_CANT:
            vector_estado.append(fila)

    if fila_final is None:
        fila_final = construir_fila('Fin simulación (límite iteraciones)', es_ultima=True)

    vector_estado.append({**fila_final, "es_ultima_fila": True})
    
    # Métricas finales
    tiempo_total_sim = reloj
    
    prom_cola_ini  = (acum_espera_ini / cont_espera_ini
                      if cont_espera_ini > 0 else 0)
    prom_cola_avan = (acum_espera_avan / cont_espera_avan
                      if cont_espera_avan > 0 else 0)
    prom_cola_total = (
        (acum_espera_ini + acum_espera_avan)
        / (cont_espera_ini + cont_espera_avan)
        if (cont_espera_ini + cont_espera_avan) > 0 else 0
    )

    pct_ocupacion_enzo = (acum_ocupacion_enzo / tiempo_total_sim * 100
                          if tiempo_total_sim > 0 else 0)
    pct_ocupacion_julian = (acum_ocupacion_julian / tiempo_total_sim * 100
                            if tiempo_total_sim > 0 else 0)
    pct_ocupacion_refuerzo = (acum_ocupacion_refuerzo / tiempo_total_sim * 100
                              if tiempo_total_sim > 0 else 0)

    atendidos_julian   = julian.competidores_atendidos
    atendidos_enzo     = enzo.competidores_atendidos
    atendidos_refuerzo = refuerzo.competidores_atendidos
    total_atendidos    = atendidos_julian + atendidos_enzo + atendidos_refuerzo

    total_ini  = cont_espera_ini
    total_avan = cont_espera_avan
    
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
