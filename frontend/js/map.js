/**
 * Sistema Inteligente de Controle Semafórico
 * Módulo Cartográfico (map.js) — Leaflet e OpenStreetMap
 *
 * Responsabilidades:
 * - Inicialização do mapa Leaflet sobre o elemento DOM #traffic-map.
 * - Adição de camada de tiles OpenStreetMap com atribuição oficial.
 * - Criação de marcadores personalizados via L.divIcon.
 * - Gerenciamento de foco, zoom (fitBounds e flyTo).
 * - Sincronização visual de seleção de marcadores.
 * - Detecção de indisponibilidade de tiles para acionamento do fallback.
 */

const TrafficMap = (() => {
  let map = null;
  const markers = {}; // { [intersectionId]: L.Marker }
  let activeMarkerId = null;
  let tileLayer = null;
  let tileErrorTriggered = false;
  let tileErrorCount = 0;
  const TILE_ERROR_THRESHOLD = 3;

  // Centro padrão de São Paulo
  const SAO_PAULO_CENTER = [-23.5505, -46.6333];
  const DEFAULT_ZOOM = 12;

  /**
   * Inicializa a instância do mapa no container especificado.
   * @param {string} containerId ID do elemento DOM do mapa
   * @param {Function} onSelectCallback Callback disparado ao clicar em um marcador: (id) => void
   * @param {Function} onTileErrorCallback Callback disparado se os tiles falharem: () => void
   * @returns {boolean} True se o mapa foi inicializado com sucesso
   */
  function init(containerId, onSelectCallback, onTileErrorCallback) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`[TrafficMap] Container #${containerId} não encontrado.`);
      return false;
    }

    if (typeof L === "undefined") {
      console.error("[TrafficMap] Biblioteca Leaflet não carregada.");
      if (typeof onTileErrorCallback === "function") onTileErrorCallback();
      return false;
    }

    try {
      map = L.map(containerId, {
        center: SAO_PAULO_CENTER,
        zoom: DEFAULT_ZOOM,
        zoomControl: true,
        attributionControl: true,
        scrollWheelZoom: true,
      });

      // Camada padrão do OpenStreetMap com atribuição legal
      tileLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      });

      // Tratamento de falha nos tiles (offline ou timeout repetido)
      tileLayer.on("tileerror", () => {
        tileErrorCount++;
        if (!tileErrorTriggered && tileErrorCount >= TILE_ERROR_THRESHOLD) {
          tileErrorTriggered = true;
          console.warn("[TrafficMap] Falha persistente no carregamento dos tiles cartográficos do OpenStreetMap.");
          if (typeof onTileErrorCallback === "function") {
            onTileErrorCallback();
          }
        }
      });

      tileLayer.addTo(map);

      // Reposicionar controle de zoom para canto inferior direito para não sobrepor elementos
      map.zoomControl.setPosition("bottomright");

      return true;
    } catch (err) {
      console.error("[TrafficMap] Erro ao inicializar Leaflet:", err);
      if (typeof onTileErrorCallback === "function") onTileErrorCallback();
      return false;
    }
  }

  /**
   * Renderiza os 8 cruzamentos no mapa utilizando L.divIcon customizado.
   * @param {Array<Object>} intersections Lista de cruzamentos do JSON
   * @param {Function} onSelectCallback Callback disparado ao clicar no marcador
   */
  function renderMarkers(intersections, onSelectCallback) {
    if (!map) return;

    // Limpar marcadores anteriores se houver
    Object.values(markers).forEach((m) => map.removeLayer(m));
    for (const key in markers) delete markers[key];

    const validLatLngs = [];

    intersections.forEach((item) => {
      // Validar coordenadas e status
      if (
        item.coordinate_status !== "verified" ||
        item.latitude === null ||
        item.longitude === null ||
        isNaN(item.latitude) ||
        isNaN(item.longitude)
      ) {
        return; // Não cria marcador para cruzamentos pending ou sem coordenadas
      }

      const latLng = [Number(item.latitude), Number(item.longitude)];
      validLatLngs.push(latLng);

      // Criação de divIcon operacional personalizado
      const iconHtml = `
        <div class="custom-marker" id="marker-icon-${item.id}">
          <span class="marker-dot"></span>
          <span class="marker-code">${item.camera_id || "CET"}</span>
        </div>
      `;

      const customIcon = L.divIcon({
        className: "custom-div-icon-wrapper",
        html: iconHtml,
        iconSize: [60, 24],
        iconAnchor: [30, 12],
      });

      const marker = L.marker(latLng, {
        icon: customIcon,
        title: `${item.camera_id} — ${item.short_name}`,
        riseOnHover: true,
      });

      // Tooltip informativo compacto ao passar o mouse
      const tooltipContent = `
        <div class="marker-tooltip-content">
          <div class="tooltip-camera">${item.camera_id || "CET"}</div>
          <div class="tooltip-title">${item.short_name || item.name}</div>
        </div>
      `;

      marker.bindTooltip(tooltipContent, {
        direction: "top",
        offset: [0, -14],
        className: "custom-map-tooltip",
        opacity: 0.95,
      });

      // Evento de clique no marcador
      marker.on("click", () => {
        if (typeof onSelectCallback === "function") {
          onSelectCallback(item.id);
        }
      });

      marker.addTo(map);
      markers[item.id] = marker;
    });

    // Enquadrar automaticamente todos os marcadores válidos com margem de segurança
    if (validLatLngs.length > 0) {
      fitAllMarkers(validLatLngs);
    }
  }

  /**
   * Enquadra o mapa para exibir todos os marcadores cadastrados.
   * @param {Array<Array<number>>} latLngs Lista de pares [lat, lon]
   */
  function fitAllMarkers(latLngs) {
    if (!map || !latLngs || latLngs.length === 0) return;
    try {
      const bounds = L.latLngBounds(latLngs);
      map.fitBounds(bounds, {
        padding: [50, 50],
        maxZoom: 15,
        animate: false,
      });
    } catch (e) {
      console.warn("[TrafficMap] Erro ao aplicar fitBounds:", e);
    }
  }

  /**
   * Destaca visualmente o marcador da interseção selecionada e move o mapa.
   * @param {string} id ID do cruzamento (e.g., "intersection_01")
   * @param {boolean} shouldPan Se o mapa deve se deslocar suavemente até o marcador
   */
  function selectMarker(id, shouldPan = true) {
    // Remover classe ativa do marcador anterior
    if (activeMarkerId && markers[activeMarkerId]) {
      const prevEl = document.getElementById(`marker-icon-${activeMarkerId}`);
      if (prevEl) {
        prevEl.classList.remove("active-marker");
      }
      markers[activeMarkerId].setZIndexOffset(0);
    }

    activeMarkerId = id;

    // Ativar novo marcador
    if (id && markers[id]) {
      const currEl = document.getElementById(`marker-icon-${id}`);
      if (currEl) {
        currEl.classList.add("active-marker");
      }
      markers[id].setZIndexOffset(1000); // Traz para a frente de outros marcadores

      if (shouldPan && map) {
        const markerLatLng = markers[id].getLatLng();
        map.flyTo(markerLatLng, Math.max(map.getZoom(), 14), {
          duration: 0.6,
          easeLinearity: 0.25,
        });
      }
    }
  }

  /**
   * Atualiza as dimensões do mapa após mudanças de layout na janela.
   */
  function invalidateSize() {
    if (map) {
      map.invalidateSize();
    }
  }

  return {
    init,
    renderMarkers,
    selectMarker,
    fitAllMarkers,
    invalidateSize,
    isAvailable: () => map !== null,
  };
})();
