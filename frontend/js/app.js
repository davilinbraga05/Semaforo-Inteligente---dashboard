/**
 * Sistema Inteligente de Controle Semafórico
 * Módulo Principal da Aplicação (app.js)
 *
 * Responsabilidades:
 * - Carregamento do arquivo data/intersections.json.
 * - Gerenciamento centralizado do estado de seleção (selectedIntersectionId).
 * - Renderização da lista lateral acessível de cruzamentos.
 * - Renderização do painel informativo do ponto ativo.
 * - Sincronização bidirecional entre a lista e o mapa (map.js).
 * - Tratamento gracioso de erros e fallbacks.
 */

document.addEventListener("DOMContentLoaded", () => {
  App.init();
});

const App = (() => {
  // Estado único da aplicação
  let intersections = [];
  let selectedId = null;
  let currentView = "map"; // "map" | "detail"

  // Elementos do DOM
  const elements = {};

  /**
   * Ponto de entrada da inicialização.
   */
  async function init() {
    cacheDomElements();
    setupWindowResize();
    setupNavigationEvents();
    setupVideoEvents();

    try {
      await loadIntersectionsData();
      initMapModule();
      renderIntersectionsList();
      renderActivePointDetails();
    } catch (err) {
      console.error("[App] Erro na inicialização da aplicação:", err);
      showGlobalError("Não foi possível carregar os pontos de monitoramento. Verifique se data/intersections.json está acessível.");
    }
  }

  /**
   * Cache de referências aos elementos da interface.
   */
  function cacheDomElements() {
    elements.listContainer = document.getElementById("intersections-list");
    elements.activePointPanel = document.getElementById("active-point-panel");
    elements.statTotal = document.getElementById("stat-total-count");
    elements.statVerified = document.getElementById("stat-verified-count");
    elements.mapFallback = document.getElementById("map-fallback-banner");
    elements.globalError = document.getElementById("global-error-banner");

    // Views e Navegação da Etapa 1C
    elements.mapView = document.getElementById("map-view");
    elements.detailView = document.getElementById("detail-view");
    elements.btnBackToMap = document.getElementById("btn-back-to-map");

    // Elementos da Detail View (Tela Individual)
    elements.detailCameraId = document.getElementById("detail-camera-id");
    elements.detailStatusBadge = document.getElementById("detail-status-badge");
    elements.detailIntersectionName = document.getElementById("detail-intersection-name");
    elements.detailLocationDetail = document.getElementById("detail-location-detail");
    elements.detailInfoCode = document.getElementById("detail-info-code");
    elements.detailInfoShortName = document.getElementById("detail-info-short-name");
    elements.detailInfoLocation = document.getElementById("detail-info-location");
    elements.detailInfoCoordsStatus = document.getElementById("detail-info-coords-status");
    elements.detailAnalysisStatus = document.getElementById("detail-analysis-status-text");

    // Elementos do Player de Vídeo (Etapa 2A)
    elements.videoPlayer = document.getElementById("intersection-video-player");
    elements.videoOverlay = document.getElementById("video-state-overlay");
    elements.videoPlaceholderTitle = document.getElementById("video-placeholder-title");
    elements.videoPlaceholderDesc = document.getElementById("video-placeholder-desc");
  }

  /**
   * Configura eventos de navegação global entre views.
   */
  function setupNavigationEvents() {
    if (elements.btnBackToMap) {
      elements.btnBackToMap.addEventListener("click", () => {
        showMapView();
      });
    }
  }

  /**
   * Configura eventos do elemento de vídeo HTML5.
   */
  function setupVideoEvents() {
    if (!elements.videoPlayer) return;

    elements.videoPlayer.addEventListener("canplay", () => {
      setVideoState("ready");
    });

    elements.videoPlayer.addEventListener("error", (e) => {
      console.warn("[App] Erro na reprodução do vídeo processado:", e);
      const errCode = elements.videoPlayer.error ? elements.videoPlayer.error.code : 0;
      if (errCode === 3 || errCode === 4) {
        setVideoState("error");
      } else {
        setVideoState("unavailable");
      }
    });
  }

  /**
   * Carrega e valida os dados de data/intersections.json via fetch.
   */
  async function loadIntersectionsData() {
    const response = await fetch("data/intersections.json");
    if (!response.ok) {
      throw new Error(`Erro HTTP ao buscar JSON: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    if (!Array.isArray(data)) {
      throw new Error("Formato inválido dos dados: esperado um array de cruzamentos.");
    }

    intersections = data;

    // Atualizar métricas no cabeçalho
    if (elements.statTotal) {
      elements.statTotal.textContent = intersections.length.toString();
    }

    const verifiedCount = intersections.filter(
      (item) => item.coordinate_status === "verified" && item.latitude !== null && item.longitude !== null
    ).length;

    if (elements.statVerified) {
      elements.statVerified.textContent = `${verifiedCount} / ${intersections.length}`;
    }
  }

  /**
   * Inicializa o módulo cartográfico (map.js).
   */
  function initMapModule() {
    if (typeof TrafficMap === "undefined") {
      console.warn("[App] TrafficMap não disponível.");
      showMapFallback();
      return;
    }

    const mapSuccess = TrafficMap.init(
      "traffic-map",
      (markerId) => {
        // Callback quando o usuário clica em um marcador no mapa
        selectIntersection(markerId, "map");
      },
      () => {
        // Callback se os tiles falharem
        showMapFallback();
      }
    );

    if (mapSuccess) {
      TrafficMap.renderMarkers(intersections, (markerId) => {
        selectIntersection(markerId, "map");
      });
    } else {
      showMapFallback();
    }
  }

  /**
   * Renderiza a lista vertical de cruzamentos no painel lateral.
   */
  function renderIntersectionsList() {
    if (!elements.listContainer) return;

    elements.listContainer.innerHTML = "";

    intersections.forEach((item) => {
      const isSelected = item.id === selectedId;
      const isVerified = item.coordinate_status === "verified";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `intersection-item-btn ${isSelected ? "selected" : ""}`;
      btn.id = `list-item-${item.id}`;
      btn.setAttribute("role", "listitem");
      btn.setAttribute("aria-label", `${item.camera_id} - ${item.short_name}`);

      btn.innerHTML = `
        <div class="item-header">
          <span class="item-camera-code">${escapeHtml(item.camera_id || "CET")}</span>
          <span class="item-status-pill ${isVerified ? "verified" : "pending"}">
            ${isVerified ? "Verificado" : "Pendente"}
          </span>
        </div>
        <div class="item-name">${escapeHtml(item.short_name || item.name)}</div>
        <div class="item-location">${escapeHtml(item.location_detail || "São Paulo, SP")}</div>
      `;

      // Evento de clique para seleção
      btn.addEventListener("click", () => {
        selectIntersection(item.id, "list");
      });

      // Suporte a teclado acessível (Enter / Space)
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectIntersection(item.id, "list");
        }
      });

      elements.listContainer.appendChild(btn);
    });
  }

  /**
   * Sincronização centralizada da seleção de cruzamento (Bidirecional: Mapa <-> Lista).
   * @param {string} id ID do cruzamento (e.g., "intersection_01")
   * @param {"map"|"list"|"init"} source Origem do evento de seleção
   */
  function selectIntersection(id, source = "list") {
    if (!id) return;

    selectedId = id;

    // 1. Atualizar classes ativas na lista lateral
    const allButtons = elements.listContainer.querySelectorAll(".intersection-item-btn");
    allButtons.forEach((btn) => btn.classList.remove("selected"));

    const activeBtn = document.getElementById(`list-item-${id}`);
    if (activeBtn) {
      activeBtn.classList.add("selected");
      // Se selecionado a partir do mapa, rolar suavemente a lista para visualizar o item
      if (source === "map") {
        activeBtn.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }

    // 2. Atualizar o marcador correspondente no mapa
    if (typeof TrafficMap !== "undefined" && TrafficMap.isAvailable()) {
      // Se veio da lista, move suavemente o mapa até o marcador (shouldPan = true)
      // Se veio do próprio mapa, apenas destaca o marcador sem salto redundante (shouldPan = false)
      const shouldPan = source === "list";
      TrafficMap.selectMarker(id, shouldPan);
    }

    // 3. Atualizar o painel informativo lateral com os dados do ponto ativo
    renderActivePointDetails();
  }

  /**
   * Renderiza o painel informativo do cruzamento ativo.
   */
  function renderActivePointDetails() {
    if (!elements.activePointPanel) return;

    if (!selectedId) {
      // Estado inicial sem seleção
      elements.activePointPanel.innerHTML = `
        <div class="active-point-empty">
          <div class="empty-icon-circle" aria-hidden="true"><span class="empty-icon-target"></span></div>
          <h4 class="empty-title">Ponto não selecionado</h4>
          <p class="empty-desc">Selecione um cruzamento no mapa ou na lista lateral para visualizar as informações operacionais.</p>
        </div>
      `;
      return;
    }

    const item = intersections.find((i) => i.id === selectedId);
    if (!item) return;

    const isVerified = item.coordinate_status === "verified";

    elements.activePointPanel.innerHTML = `
      <div class="active-point-card">
        <div class="active-card-top">
          <span class="active-camera-badge">${escapeHtml(item.camera_id || "CET")}</span>
          <span class="active-status-badge ${isVerified ? "verified" : "pending"}">
            ${isVerified ? "Coordenadas Verificadas" : "Coordenadas Pendentes"}
          </span>
        </div>

        <h3 class="active-point-title">${escapeHtml(item.name || "Cruzamento")}</h3>
        <p class="active-point-subtitle">${escapeHtml(item.location_detail || "São Paulo, SP")}</p>

        <div class="active-point-info-grid">
          <div class="info-row">
            <span class="info-label">Identificação Curta:</span>
            <span class="info-value">${escapeHtml(item.short_name || "-")}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Local:</span>
            <span class="info-value">${escapeHtml(item.location_detail || "São Paulo, SP")}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Status no Sistema:</span>
            <span class="info-value active-val-ready">Ponto disponível para análise</span>
          </div>
        </div>

        <!-- Ação para abrir Tela Individual (Etapa 1C) -->
        <div class="active-card-actions">
          <button type="button" id="btn-analyze-intersection" class="btn-analyze-action" aria-label="Analisar cruzamento ${escapeHtml(item.camera_id || '')}">
            Analisar cruzamento
          </button>
        </div>

        <div class="active-card-footnote">
          <span>Pronto para análise de fluxo e contagem veicular</span>
        </div>
      </div>
    `;

    // Conectar evento ao botão de análise
    const btnAnalyze = elements.activePointPanel.querySelector("#btn-analyze-intersection");
    if (btnAnalyze) {
      btnAnalyze.addEventListener("click", () => {
        showDetailView();
      });
    }
  }

  /**
   * Exibe a Tela Individual de Análise do Cruzamento (Detail View).
   */
  function showDetailView() {
    if (!selectedId) return;

    const item = intersections.find((i) => i.id === selectedId);
    if (!item) return;

    // 1. Preencher cabeçalho e dados da Detail View
    if (elements.detailCameraId) {
      elements.detailCameraId.textContent = item.camera_id || "CET";
    }
    if (elements.detailIntersectionName) {
      elements.detailIntersectionName.textContent = item.name || "Cruzamento";
    }
    if (elements.detailLocationDetail) {
      elements.detailLocationDetail.textContent = item.location_detail || "São Paulo, SP";
    }

    const isVerified = item.coordinate_status === "verified";
    if (elements.detailStatusBadge) {
      elements.detailStatusBadge.textContent = isVerified ? "Coordenadas verificadas" : "Coordenadas pendentes";
      elements.detailStatusBadge.className = `detail-status-badge ${isVerified ? "verified" : "pending"}`;
    }

    // 2. Preencher tabela de informações do ponto
    if (elements.detailInfoCode) {
      elements.detailInfoCode.textContent = item.camera_id || "CET";
    }
    if (elements.detailInfoShortName) {
      elements.detailInfoShortName.textContent = item.short_name || "-";
    }
    if (elements.detailInfoLocation) {
      elements.detailInfoLocation.textContent = item.location_detail || "São Paulo, SP";
    }
    if (elements.detailInfoCoordsStatus) {
      elements.detailInfoCoordsStatus.textContent = isVerified ? "Verificadas" : "Pendentes";
      elements.detailInfoCoordsStatus.className = `info-value ${isVerified ? "status-val-verified" : "status-val-pending"}`;
    }

    // 3. Carregar dinamicamente o vídeo processado do cruzamento selecionado (Etapa 2A)
    loadIntersectionVideo(item.output_video);

    // 4. Alternar exibição das views
    currentView = "detail";
    if (elements.mapView) {
      elements.mapView.hidden = true;
    }
    if (elements.detailView) {
      elements.detailView.hidden = false;
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /**
   * Retorna à visualização de mapa (Map View).
   */
  function showMapView() {
    // Pausar reprodução do vídeo ao sair da tela individual
    if (elements.videoPlayer) {
      elements.videoPlayer.pause();
    }

    currentView = "map";
    if (elements.detailView) {
      elements.detailView.hidden = true;
    }
    if (elements.mapView) {
      elements.mapView.hidden = false;
    }

    // Leaflet recalcula dimensões após exibição do container
    if (typeof TrafficMap !== "undefined" && TrafficMap.isAvailable()) {
      TrafficMap.invalidateSize();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /**
   * Define o estado visual do player e atualiza as mensagens informativas.
   * @param {"loading"|"ready"|"unavailable"|"error"} state
   */
  function setVideoState(state) {
    if (!elements.videoPlayer || !elements.videoOverlay) return;

    if (state === "ready") {
      elements.videoPlayer.hidden = false;
      elements.videoOverlay.hidden = true;
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Vídeo processado disponível.";
      }
    } else if (state === "loading") {
      elements.videoPlayer.hidden = true;
      elements.videoOverlay.hidden = false;
      if (elements.videoPlaceholderTitle) {
        elements.videoPlaceholderTitle.textContent = "CARREGANDO VÍDEO";
      }
      if (elements.videoPlaceholderDesc) {
        elements.videoPlaceholderDesc.textContent = "Carregando vídeo processado...";
      }
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Carregando vídeo processado...";
      }
    } else if (state === "error") {
      elements.videoPlayer.hidden = true;
      elements.videoOverlay.hidden = false;
      if (elements.videoPlaceholderTitle) {
        elements.videoPlaceholderTitle.textContent = "FALHA NA REPRODUÇÃO";
      }
      if (elements.videoPlaceholderDesc) {
        elements.videoPlaceholderDesc.textContent = "Não foi possível reproduzir o vídeo processado.";
      }
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Não foi possível reproduzir o vídeo processado.";
      }
    } else {
      // "unavailable"
      elements.videoPlayer.hidden = true;
      elements.videoOverlay.hidden = false;
      if (elements.videoPlaceholderTitle) {
        elements.videoPlaceholderTitle.textContent = "VÍDEO NÃO DISPONÍVEL";
      }
      if (elements.videoPlaceholderDesc) {
        elements.videoPlaceholderDesc.textContent = "Vídeo processado ainda não disponível para este ponto.";
      }
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Vídeo processado ainda não disponível.";
      }
    }
  }

  /**
   * Configura e carrega o vídeo processado do cruzamento ativo.
   * @param {string} videoPath Caminho do vídeo output
   */
  async function loadIntersectionVideo(videoPath) {
    if (!elements.videoPlayer) return;

    // 1. Interromper vídeo anterior, limpar source e zerar posição
    elements.videoPlayer.pause();
    elements.videoPlayer.removeAttribute("src");
    elements.videoPlayer.currentTime = 0;

    if (!videoPath) {
      setVideoState("unavailable");
      return;
    }

    // 2. Definir estado inicial de carregamento
    setVideoState("loading");

    // 3. Teste rápido de existência do recurso antes de atribuir ao player
    try {
      const response = await fetch(videoPath, { method: "HEAD" });
      if (!response.ok) {
        // Arquivo não existe no servidor (ex: 404)
        setVideoState("unavailable");
        return;
      }

      // 4. Arquivo existente no servidor: atribui ao player e aciona load()
      elements.videoPlayer.src = videoPath;
      elements.videoPlayer.load();
    } catch (e) {
      // Falha de rede ou indisponibilidade
      setVideoState("unavailable");
    }
  }

  /**
   * Exibe aviso discreto caso os tiles do mapa estejam indisponíveis.
   */
  function showMapFallback() {
    if (elements.mapFallback) {
      elements.mapFallback.style.display = "flex";
    }
  }

  /**
   * Exibe mensagem global caso o JSON não possa ser carregado.
   * @param {string} msg Mensagem de erro
   */
  function showGlobalError(msg) {
    if (elements.globalError) {
      elements.globalError.textContent = msg;
      elements.globalError.style.display = "block";
    }
  }

  /**
   * Ajusta o mapa quando a janela é redimensionada.
   */
  function setupWindowResize() {
    window.addEventListener("resize", () => {
      if (typeof TrafficMap !== "undefined" && TrafficMap.isAvailable()) {
        TrafficMap.invalidateSize();
      }
    });
  }

  /**
   * Sanitiza strings contra injeção de HTML.
   * @param {string} str Texto de entrada
   * @returns {string} Texto seguro
   */
  function escapeHtml(str) {
    if (typeof str !== "string") return String(str ?? "");
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  return {
    init,
    selectIntersection,
    showDetailView,
    showMapView,
    loadIntersectionVideo,
    setVideoState,
    getCurrentView: () => currentView,
    getSelectedId: () => selectedId,
    getVideoPlayer: () => elements.videoPlayer,
    getIntersections: () => intersections,
  };
})();
