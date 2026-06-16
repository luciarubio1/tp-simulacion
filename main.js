// main.js - Manejo del Frontend interactivo de la Simulación

let rkTablesData = []; // Guardará todas las tablas RK recibidas en la última ejecución
let stateVectorData = []; // Guardará las filas del vector de estado recibidas

// Cambiar de Pestaña (Tabs)
function switchTab(tabId, btn) {
  // Desactivar todos los paneles y botones de pestañas
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(button => button.classList.remove('active'));
  
  // Activar el panel seleccionado y su botón
  document.getElementById(tabId).classList.add('active');
  btn.classList.add('active');
}

// Ejecutar la simulación llamando al backend
async function ejecutarSimulacion() {
  const btn = document.getElementById('btn-run');
  const originalBtnHTML = btn.innerHTML;
  
  // Mostrar estado de carga
  btn.disabled = true;
  btn.innerHTML = `
    <svg style="width: 1.2rem; height: 1.2rem; fill: currentColor; animation: spin 1s linear infinite;" viewBox="0 0 24 24">
      <path d="M12,4V2A10,10 0 0,0 2,12H4A8,8 0 0,1 12,4Z"/>
    </svg>
    Simulando...
  `;
  
  // Agregar estilo para la animación del spinner
  if (!document.getElementById('spin-style')) {
    const style = document.createElement('style');
    style.id = 'spin-style';
    style.innerHTML = `@keyframes spin { 100% { transform: rotate(360deg); } }`;
    document.head.appendChild(style);
  }

  // Recolectar parámetros del formulario
  const params = {
    iter_desde: parseInt(document.getElementById('iter_desde').value),
    iter_cantidad: parseInt(document.getElementById('iter_cantidad').value),
    tiempo_maximo: parseFloat(document.getElementById('tiempo_maximo').value),
    max_iteraciones: parseInt(document.getElementById('max_iteraciones').value),
    media_llegadas: parseFloat(document.getElementById('media_llegadas').value),
    media_ini: parseFloat(document.getElementById('media_ini').value),
    desvio_ini: parseFloat(document.getElementById('desvio_ini').value),
    media_avan: parseFloat(document.getElementById('media_avan').value),
    desvio_avan: parseFloat(document.getElementById('desvio_avan').value),
    media_corte: parseFloat(document.getElementById('media_corte').value),
    h_rk: parseFloat(document.getElementById('h_rk').value),
    umbral_refuerzo: parseInt(document.getElementById('umbral_refuerzo').value)
  };

  try {
    const response = await fetch('/simular', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(params)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    // Guardar datos globales
    stateVectorData = data.vector_estado || [];
    rkTablesData = data.tablas_rk || [];
    const metricas = data.metricas || {};

    // 1. Actualizar Dashboard de Métricas
    actualizarMetricas(metricas);

    // 2. Renderizar Vector de Estado
    renderizarVectorEstado();

    // 3. Configurar Selector y Renderizar primera tabla RK4
    configurarSelectorRK();

    // Mostrar un toast informativo de éxito
    mostrarToast("Simulación completada con éxito!");

  } catch (error) {
    console.error("Error ejecutando simulación:", error);
    mostrarToast("Ocurrió un error al ejecutar la simulación. Asegúrate de que el backend esté corriendo.", true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalBtnHTML;
  }
}

// Actualizar las métricas en pantalla
function actualizarMetricas(m) {
  // Tarjetas principales
  document.getElementById('val-prom-ini').innerText = m.prom_cola_inicial !== undefined ? `${m.prom_cola_inicial} min` : '-';
  document.getElementById('val-prom-avan').innerText = m.prom_cola_avanzado !== undefined ? `${m.prom_cola_avanzado} min` : '-';
  document.getElementById('val-oc-enzo').innerText = m.pct_ocupacion_enzo !== undefined ? `${m.pct_ocupacion_enzo}%` : '-';
  document.getElementById('val-total-atendidos').innerText = m.total_atendidos !== undefined ? m.total_atendidos : '-';

  // Detalles e Informativas (Tab 3)
  document.getElementById('val-media-ini-det').innerText = m.prom_cola_inicial !== undefined ? `${m.prom_cola_inicial} min` : '-';
  document.getElementById('val-media-avan-det').innerText = m.prom_cola_avanzado !== undefined ? `${m.prom_cola_avanzado} min` : '-';
  document.getElementById('val-media-global-det').innerText = m.prom_cola_total !== undefined ? `${m.prom_cola_total} min` : '-';
  
  document.getElementById('val-atendidos-julian').innerText = m.atendidos_julian !== undefined ? m.atendidos_julian : '-';
  document.getElementById('val-atendidos-enzo').innerText = m.atendidos_enzo !== undefined ? m.atendidos_enzo : '-';
  document.getElementById('val-atendidos-refuerzo').innerText = m.atendidos_refuerzo !== undefined ? m.atendidos_refuerzo : '-';
  
  document.getElementById('val-res-tiempo').innerText = m.tiempo_simulado !== undefined ? `${m.tiempo_simulado} min` : '-';
  document.getElementById('val-res-iteraciones').innerText = m.iteraciones_totales !== undefined ? m.iteraciones_totales : '-';

  // 4 Estadísticas Adicionales
  document.getElementById('stat-oc-julian').innerText = m.pct_ocupacion_julian !== undefined ? `${m.pct_ocupacion_julian}%` : '-';
  document.getElementById('stat-oc-refuerzo').innerText = m.pct_ocupacion_refuerzo !== undefined ? `${m.pct_ocupacion_refuerzo}%` : '-';
  document.getElementById('stat-max-espera').innerText = m.max_tiempo_espera !== undefined ? `${m.max_tiempo_espera} min` : '-';
  
  if (m.total_ini_atendidos !== undefined && m.total_avan_atendidos !== undefined) {
    const total = m.total_ini_atendidos + m.total_avan_atendidos;
    if (total > 0) {
      const pctIni = ((m.total_ini_atendidos / total) * 100).toFixed(1);
      const pctAvan = ((m.total_avan_atendidos / total) * 100).toFixed(1);
      document.getElementById('stat-proporcion-categorias').innerHTML = `
        ${m.total_ini_atendidos} Iniciales (${pctIni}%)<br>
        ${m.total_avan_atendidos} Avanzados (${pctAvan}%)
      `;
    } else {
      document.getElementById('stat-proporcion-categorias').innerText = '0 Inicial / 0 Avanzado';
    }
  } else {
    document.getElementById('stat-proporcion-categorias').innerText = '-';
  }
}

// Renderizar el Vector de Estado en la Tabla
function renderizarVectorEstado() {
  const tbody = document.getElementById('body-vector-estado');
  tbody.innerHTML = '';

  if (stateVectorData.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="19" class="empty-state">
          <i>📊</i>
          <p>No se encontraron resultados en el rango de iteraciones seleccionado.</p>
        </td>
      </tr>
    `;
    return;
  }

  // Ocultar el panel de detalles de competidores hasta que el usuario elija una fila
  document.getElementById('competitors-detail-panel').style.display = 'none';

  stateVectorData.forEach((fila) => {
    const tr = document.createElement('tr');
    tr.id = `row-iter-${fila.iteracion}`;
    
    // Si es la fila final (instante X), darle un estilo diferenciador sutil
    if (fila.es_ultima_fila) {
      tr.style.borderTop = '2px solid var(--accent-amber)';
      tr.style.backgroundColor = 'rgba(245, 158, 11, 0.03)';
    }

    // Formateador de badges de Juez
    const badgeJuez = (estado) => {
      const estLower = estado.toLowerCase();
      let clase = 'badge-inactivo';
      if (estLower.includes('libre')) clase = 'badge-libre';
      else if (estLower.includes('ocupado')) clase = 'badge-ocupado';
      else if (estLower.includes('interrumpido')) clase = 'badge-interrumpido';
      
      return `<span class="badge ${clase}">${estado}</span>`;
    };

    // Formateador de categorías
    const badgeCat = (cat) => {
      if (cat === 'Inicial') return `<span class="badge badge-inicial">${cat}</span>`;
      if (cat === 'Avanzado') return `<span class="badge badge-avanzado">${cat}</span>`;
      return '-';
    };

    tr.innerHTML = `
      <td class="code-val" style="font-weight: 600;">${fila.iteracion}</td>
      <td style="font-weight: 500; font-size: 0.83rem;">${fila.evento}</td>
      <td class="code-val">${fila.reloj}</td>
      <td class="code-val">${fila.prox_llegada}</td>
      <td class="code-val">${fila.prox_corte}</td>
      <td class="code-val">${fila.fin_corte}</td>
      
      <!-- Julián -->
      <td>${badgeJuez(fila.julian_estado)}</td>
      <td class="code-val">${fila.julian_comp_id}</td>
      <td class="code-val">${fila.fin_aten_julian}</td>
      
      <!-- Enzo -->
      <td>${badgeJuez(fila.enzo_estado)}</td>
      <td class="code-val">${fila.enzo_comp_id}</td>
      <td class="code-val">${fila.fin_aten_enzo}</td>
      
      <!-- Refuerzo -->
      <td>${badgeJuez(fila.ref_estado)}</td>
      <td class="code-val">${fila.ref_comp_id}</td>
      <td class="code-val">${fila.fin_aten_refuerzo}</td>
      <td class="code-val">${fila.fin_turno_refuerzo}</td>
      
      <!-- Cola -->
      <td style="font-weight: 700; color: ${fila.cola_tamanio >= 5 ? 'var(--accent-rose)' : 'var(--text-primary)'};">${fila.cola_tamanio}</td>
      <td style="font-size: 0.75rem; font-family: var(--font-family-mono); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${fila.cola_detalle}">${fila.cola_detalle}</td>
      
      <td style="font-weight: 600; color: ${fila.en_corte === 'Sí' ? 'var(--accent-amber)' : 'var(--text-muted)'};">${fila.en_corte}</td>
    `;

    // Interactividad: Clic en la fila
    tr.addEventListener('click', () => {
      // Remover selección previa
      document.querySelectorAll('#body-vector-estado tr').forEach(r => r.classList.remove('selected-row'));
      tr.classList.add('selected-row');
      
      // Mostrar panel de competidores
      mostrarCompetidoresActivos(fila.iteracion, fila.competidores_activos);
    });

    tbody.appendChild(tr);
  });
}

// Mostrar los competidores activos para la fila seleccionada
function mostrarCompetidoresActivos(iteracion, competidores) {
  document.getElementById('selected-iter-label').innerText = iteracion;
  const tbody = document.getElementById('body-competidores-detalles');
  tbody.innerHTML = '';

  if (!competidores || competidores.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="12" class="empty-state">
          <p>No hay competidores en el sistema en este instante.</p>
        </td>
      </tr>
    `;
  } else {
    competidores.forEach(c => {
      const tr = document.createElement('tr');
      
      const badgeCat = (cat) => {
        if (cat === 'Inicial') return `<span class="badge badge-inicial">${cat}</span>`;
        if (cat === 'Avanzado') return `<span class="badge badge-avanzado">${cat}</span>`;
        return '-';
      };

      const styleEstado = (est) => {
        if (est === 'En Cola') return `<span style="color: var(--text-secondary); font-weight:600;">${est}</span>`;
        return `<span style="color: var(--accent-emerald); font-weight:600;">${est}</span>`;
      };

      tr.innerHTML = `
        <td class="code-val" style="font-weight:600;">C${c.id}</td>
        <td>${badgeCat(c.categoria)}</td>
        <td class="code-val">${c.tiempo_llegada}</td>
        <td class="code-val">${c.rnd_llegada}</td>
        <td class="code-val">${c.rnd_categoria}</td>
        <td>${styleEstado(c.estado)}</td>
        <td style="font-weight: 500;">${c.juez_asignado}</td>
        <td class="code-val">${c.tiempo_en_cola}</td>
        <td class="code-val">${c.rnd_atencion_1}</td>
        <td class="code-val">${c.rnd_atencion_2}</td>
        <td class="code-val">${c.tiempo_atencion}</td>
        <td class="code-val">${c.tiempo_fin_atencion}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Desplegar panel
  document.getElementById('competitors-detail-panel').style.display = 'block';
  // Hacer scroll suave al panel de detalles
  document.getElementById('competitors-detail-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Configurar el dropdown de selección de tablas RK4
function configurarSelectorRK() {
  const selector = document.getElementById('rk-table-selector');
  selector.innerHTML = '';

  if (rkTablesData.length === 0) {
    selector.innerHTML = '<option value="">-- No hay tablas Runge-Kutta calculadas --</option>';
    mostrarTablaRKVacía();
    return;
  }

  rkTablesData.forEach((tabla, index) => {
    const option = document.createElement('option');
    option.value = index;
    option.innerText = tabla.titulo;
    selector.appendChild(option);
  });

  // Mostrar la primera por defecto
  mostrarTablaRKSeleccionada(0);
}

// Mostrar la tabla RK4 seleccionada por index
function mostrarTablaRKSeleccionada(index) {
  const tbody = document.getElementById('body-runge-kutta');
  tbody.innerHTML = '';

  const indexInt = parseInt(index);
  if (isNaN(indexInt) || !rkTablesData[indexInt]) {
    mostrarTablaRKVacía();
    return;
  }

  const filas = rkTablesData[indexInt].filas;

  filas.forEach(f => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="code-val" style="font-weight:600;">${f.n}</td>
      <td class="code-val">${f.t}</td>
      <td class="code-val">${f.E}</td>
      <td class="code-val">${f.k1}</td>
      <td class="code-val">${f.k2}</td>
      <td class="code-val">${f.k3}</td>
      <td class="code-val">${f.k4}</td>
      <td class="code-val" style="color: var(--accent-cyan); font-weight:600;">${f.E_nuevo}</td>
      <td class="code-val">${f.t_minutos}</td>
    `;
    tbody.appendChild(tr);
  });
}

function mostrarTablaRKVacía() {
  const tbody = document.getElementById('body-runge-kutta');
  tbody.innerHTML = `
    <tr>
      <td colspan="9" class="empty-state">
        <i>📈</i>
        <p>No hay datos RK4 disponibles para mostrar.</p>
      </td>
    </tr>
  `;
}

// Toast de notificación en pantalla
function mostrarToast(mensaje, esError = false) {
  // Eliminar toast previo si existe
  const toastPrevio = document.getElementById('toast-banner');
  if (toastPrevio) toastPrevio.remove();

  const toast = document.createElement('div');
  toast.id = 'toast-banner';
  toast.className = 'toast';
  if (esError) {
    toast.style.borderColor = 'var(--accent-rose)';
    toast.style.boxShadow = '0 0 20px rgba(244, 63, 148, 0.15)';
    toast.innerHTML = `
      <svg style="width: 1.2rem; height: 1.2rem; fill: var(--accent-rose);" viewBox="0 0 24 24"><path d="M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z"/></svg>
      <span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">${mensaje}</span>
    `;
  } else {
    toast.innerHTML = `
      <svg style="width: 1.2rem; height: 1.2rem; fill: var(--accent-cyan);" viewBox="0 0 24 24"><path d="M12,2C6.5,2 2,6.5 2,12S6.5,22 12,22 22,17.5 22,12 17.5,2 12,2M10,17L5,12L6.41,10.59L10,14.17L17.59,6.58L19,8L10,17Z"/></svg>
      <span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">${mensaje}</span>
    `;
  }

  document.body.appendChild(toast);

  // Ocultar automáticamente en 4 segundos
  setTimeout(() => {
    if (toast) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.5s ease';
      setTimeout(() => toast.remove(), 500);
    }
  }, 4000);
}
