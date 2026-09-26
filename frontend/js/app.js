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

  // Estado da Execução Demonstrativa de Análise (Etapa 2A.1)
  let prepTimeout = null;
  let isAnalysisActive = false;
  let isSeeking = false;
  let videoLoadToken = 0;
  let activeIntersectionId = null;
  let currentPlaybackRate = 1;
  let isRecalculating = false;

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
    setupCustomControlsEvents();

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

    // Elementos do Player de Vídeo e Execução Demonstrativa (Etapas 2A e 2A.1)
    elements.videoPlayer = document.getElementById("intersection-video-player");
    elements.videoOverlay = document.getElementById("video-state-overlay");
    elements.videoPlaceholderTitle = document.getElementById("video-placeholder-title");
    elements.videoPlaceholderDesc = document.getElementById("video-placeholder-desc");
    elements.videoContainer = document.getElementById("video-display-area");

    // Componentes da Interface Técnica de Análise (Etapa 2A.1)
    elements.analysisExecHeader = document.getElementById("analysis-execution-header");
    elements.analysisStatusBadge = document.getElementById("analysis-status-badge");
    elements.analysisStatusText = document.getElementById("analysis-status-text");
    elements.analysisReadyOverlay = document.getElementById("analysis-ready-overlay");
    elements.btnStartAnalysis = document.getElementById("btn-start-analysis");
    elements.analysisPrepOverlay = document.getElementById("analysis-prep-overlay");
    elements.prepOverlayTitle = document.getElementById("prep-overlay-title");
    elements.prepOverlayDesc = document.getElementById("prep-overlay-desc");
    elements.analysisEndedOverlay = document.getElementById("analysis-ended-overlay");
    elements.btnRestartAnalysisOverlay = document.getElementById("btn-restart-analysis-overlay");
    elements.videoControls = document.getElementById("video-custom-controls");
    elements.btnPlayPause = document.getElementById("btn-control-playpause");
    elements.playPauseText = document.getElementById("control-playpause-text");
    elements.btnRestart = document.getElementById("btn-control-restart");
    elements.seekSlider = document.getElementById("video-seek-slider");
    elements.timerDisplay = document.getElementById("video-timer-display");
    elements.btnFullscreen = document.getElementById("btn-control-fullscreen");
    elements.controlsLeftGroup = document.getElementById("controls-left-group");
    elements.btnSpeed1x = document.getElementById("btn-speed-1x");
    elements.btnSpeed2x = document.getElementById("btn-speed-2x");
    elements.btnSpeed3x = document.getElementById("btn-speed-3x");
    elements.detailResultsContent = document.getElementById("detail-results-content");
    elements.detailResultsStatus = document.getElementById("detail-results-status");
    elements.simulationSection = document.getElementById("detail-simulation-section");
    elements.simulationContent = document.getElementById("detail-simulation-content");
    elements.simulationStatusBadge = document.getElementById("simulation-status-badge");
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
   * Executa o reset forte e imediato do elemento de vídeo HTML5.
   * Descarta buffer, frame anterior, metadados e current source do navegador.
   */
  function resetVideoElement() {
    if (!elements.videoPlayer) return;

    // 1. Pausa imediatamente a reprodução
    elements.videoPlayer.pause();

    // 2. Oculta o elemento para que nenhum frame residual seja visível
    elements.videoPlayer.hidden = true;
    elements.videoPlayer.style.display = "none";

    // 3. Remove source e força descarga completa da mídia decodificada anterior
    elements.videoPlayer.removeAttribute("src");
    try {
      elements.videoPlayer.load();
    } catch (e) {
      // Ignora erro de load vazio
    }

    // 4. Reseta tempo com segurança
    try {
      elements.videoPlayer.currentTime = 0;
    } catch (e) {}
  }

  /**
   * Configura eventos do elemento de vídeo HTML5.
   */
  function setupVideoEvents() {
    if (!elements.videoPlayer) return;

    elements.videoPlayer.addEventListener("canplay", () => {
      // Proteção: apenas o cruzamento ativo no token atual pode atualizar o estado
      if (selectedId !== activeIntersectionId) return;

      // Se a análise ainda não foi iniciada pelo usuário, entra no estado READY (pré-execução)
      if (!isAnalysisActive) {
        setVideoState("ready", videoLoadToken);
      }
    });

    elements.videoPlayer.addEventListener("loadedmetadata", () => {
      if (selectedId !== activeIntersectionId) return;

      if (elements.videoPlayer) {
        elements.videoPlayer.playbackRate = currentPlaybackRate;
      }

      if (elements.timerDisplay && elements.videoPlayer) {
        const dur = elements.videoPlayer.duration;
        const formattedDur = (!isNaN(dur) && isFinite(dur)) ? formatTime(dur) : "00:00";
        elements.timerDisplay.textContent = `00:00 / ${formattedDur}`;
      }

      // Se ainda não iniciou, loadedmetadata também assegura READY
      if (!isAnalysisActive) {
        setVideoState("ready", videoLoadToken);
      }
    });

    elements.videoPlayer.addEventListener("timeupdate", () => {
      if (!elements.videoPlayer || !isAnalysisActive) return;
      const current = elements.videoPlayer.currentTime || 0;
      const duration = elements.videoPlayer.duration || 0;

      // Não sobrescrever a posição do slider durante interação ou busca ativa do decoder
      if (!isSeeking && !elements.videoPlayer.seeking && duration > 0 && elements.seekSlider) {
        elements.seekSlider.value = ((current / duration) * 100).toFixed(1);
      }

      if (!isSeeking && elements.timerDisplay) {
        elements.timerDisplay.textContent = `${formatTime(current)} / ${formatTime(duration)}`;
      }
    });

    elements.videoPlayer.addEventListener("play", () => {
      if (isAnalysisActive) {
        if (elements.btnPlayPause) elements.btnPlayPause.hidden = false;
        if (elements.btnRestart) elements.btnRestart.hidden = false;
        if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "";
        if (elements.playPauseText) elements.playPauseText.textContent = "Pausar";
        updateExecutionBadge("playing");
        if (elements.analysisEndedOverlay) elements.analysisEndedOverlay.hidden = true;
      }
    });

    elements.videoPlayer.addEventListener("pause", () => {
      if (isAnalysisActive && !elements.videoPlayer.ended) {
        if (elements.btnPlayPause) elements.btnPlayPause.hidden = false;
        if (elements.btnRestart) elements.btnRestart.hidden = false;
        if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "";
        if (elements.playPauseText) elements.playPauseText.textContent = "Continuar";
        updateExecutionBadge("paused");
      }
    });

    elements.videoPlayer.addEventListener("ended", () => {
      if (isAnalysisActive) {
        // Oculta botões de ação na barra inferior para evitar duplicidade de Reiniciar
        if (elements.btnPlayPause) elements.btnPlayPause.hidden = true;
        if (elements.btnRestart) elements.btnRestart.hidden = true;
        if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "none";

        updateExecutionBadge("ended");
        if (elements.analysisEndedOverlay) elements.analysisEndedOverlay.hidden = false;
        if (elements.detailAnalysisStatus) {
          elements.detailAnalysisStatus.textContent = "Execução demonstrativa concluída.";
        }

        // Revela os resultados reais consolidados ou aviso institucional
        renderResultsSection("completed");

        // Habilita a simulação de controle semafórico adaptativo (Etapa Final)
        renderSimulationSection("ready");
      }
    });

    elements.videoPlayer.addEventListener("error", (e) => {
      // Ignora erro se o elemento está sem src devido a reset intencional
      if (!elements.videoPlayer.hasAttribute("src") && !elements.videoPlayer.currentSrc) {
        return;
      }

      if (selectedId !== activeIntersectionId) return;

      console.warn("[App] Erro na reprodução do vídeo processado:", e);
      const errCode = elements.videoPlayer.error ? elements.videoPlayer.error.code : 0;
      if (errCode === 3 || errCode === 4) {
        setVideoState("error", videoLoadToken);
      } else {
        setVideoState("unavailable", videoLoadToken);
      }
    });
  }

  /**
   * Configura eventos dos controles customizados e transições da análise (Etapa 2A.1).
   */
  function setupCustomControlsEvents() {
    // Botão Principal: INICIAR ANÁLISE
    if (elements.btnStartAnalysis) {
      elements.btnStartAnalysis.addEventListener("click", () => {
        startAnalysisExecution();
      });
    }

    // Botão Pausar / Continuar
    if (elements.btnPlayPause) {
      elements.btnPlayPause.addEventListener("click", () => {
        if (!elements.videoPlayer) return;
        if (elements.videoPlayer.ended) {
          elements.videoPlayer.currentTime = 0;
          if (elements.analysisEndedOverlay) elements.analysisEndedOverlay.hidden = true;
          elements.videoPlayer.play().catch(() => {});
        } else if (elements.videoPlayer.paused) {
          elements.videoPlayer.play().catch(() => {});
        } else {
          elements.videoPlayer.pause();
        }
      });
    }

    // Botão Reiniciar (Barra de Controles)
    if (elements.btnRestart) {
      elements.btnRestart.addEventListener("click", () => {
        restartAnalysisExecution();
      });
    }

    // Botão Reiniciar (Overlay de Conclusão)
    if (elements.btnRestartAnalysisOverlay) {
      elements.btnRestartAnalysisOverlay.addEventListener("click", () => {
        restartAnalysisExecution();
      });
    }

    // Slider de Seek (Progresso da Análise com Navegação Livre e Robusta)
    if (elements.seekSlider) {
      const applySeekFromSlider = () => {
        if (!elements.videoPlayer) return;
        const duration = elements.videoPlayer.duration;
        if (!duration || isNaN(duration) || !isFinite(duration) || duration <= 0) return;

        const percent = Number(elements.seekSlider.value) / 100;
        const targetTime = percent * duration;

        elements.videoPlayer.currentTime = targetTime;

        if (elements.timerDisplay) {
          elements.timerDisplay.textContent = `${formatTime(targetTime)} / ${formatTime(duration)}`;
        }
      };

      // Disparado imediatamente ao clicar ou arrastar
      elements.seekSlider.addEventListener("input", () => {
        isSeeking = true;
        applySeekFromSlider();
      });

      // Disparado ao soltar o clique/arraste (confirmação final)
      elements.seekSlider.addEventListener("change", () => {
        applySeekFromSlider();
        isSeeking = false;
      });

      // Garantia de liberação do estado isSeeking caso o mouse seja solto fora do slider
      window.addEventListener("mouseup", () => {
        if (isSeeking) {
          isSeeking = false;
        }
      });
      window.addEventListener("pointerup", () => {
        if (isSeeking) {
          isSeeking = false;
        }
      });
      window.addEventListener("touchend", () => {
        if (isSeeking) {
          isSeeking = false;
        }
      });
    }

    // Controle de Velocidade 1x / 2x / 3x
    if (elements.btnSpeed1x) {
      elements.btnSpeed1x.addEventListener("click", () => {
        setPlaybackRate(1);
      });
    }

    if (elements.btnSpeed2x) {
      elements.btnSpeed2x.addEventListener("click", () => {
        setPlaybackRate(2);
      });
    }

    if (elements.btnSpeed3x) {
      elements.btnSpeed3x.addEventListener("click", () => {
        setPlaybackRate(3);
      });
    }

    // Botão Tela Cheia
    if (elements.btnFullscreen) {
      elements.btnFullscreen.addEventListener("click", () => {
        toggleFullscreen();
      });
    }

    // Eventos da Simulação de Controle Semafórico Adaptativo (Etapa Final)
    if (elements.simulationContent) {
      elements.simulationContent.addEventListener("click", (e) => {
        const btnRun = e.target.closest("#btn-run-simulation");
        const btnRecalc = e.target.closest("#btn-recalculate-simulation");
        if (btnRun && !btnRun.disabled && !btnRun.classList.contains("disabled")) {
          runAdaptiveSimulation(false);
        } else if (btnRecalc && !isRecalculating && !btnRecalc.disabled) {
          triggerRecalculateSimulation(btnRecalc);
        }
      });
    }
  }

  /**
   * Inicia o fluxo de execução demonstrativa com transição honesta de preparação.
   */
  function startAnalysisExecution() {
    if (prepTimeout) {
      clearTimeout(prepTimeout);
      prepTimeout = null;
    }

    // 1. Ocultar estado "Análise pronta"
    if (elements.analysisReadyOverlay) {
      elements.analysisReadyOverlay.hidden = true;
    }

    // 2. Entrar em estado de preparação curto (~1000ms)
    if (elements.analysisPrepOverlay) {
      elements.analysisPrepOverlay.hidden = false;
    }
    if (elements.prepOverlayTitle) {
      elements.prepOverlayTitle.textContent = "Preparando visualização...";
    }
    if (elements.prepOverlayDesc) {
      elements.prepOverlayDesc.textContent = "Carregando análise processada do cruzamento";
    }
    if (elements.detailAnalysisStatus) {
      elements.detailAnalysisStatus.textContent = "Preparando visualização da análise...";
    }

    // Informa que a análise está em execução
    renderResultsSection("running");
    renderSimulationSection("waiting");

    // Capturar o token e cruzamento atuais para proteger contra trocas durante a preparação
    const prepToken = videoLoadToken;
    const prepExpectedId = selectedId;

    prepTimeout = setTimeout(() => {
      prepTimeout = null;

      // Se o usuário trocou de tela ou de ponto durante a preparação, cancela!
      if (prepToken !== videoLoadToken || selectedId !== prepExpectedId || currentView !== "detail") {
        return;
      }

      isAnalysisActive = true;

      // 3. Ocultar preparação e exibir interface técnica de execução
      if (elements.analysisPrepOverlay) {
        elements.analysisPrepOverlay.hidden = true;
      }

      // 4. SOMENTE AQUI o vídeo é revelado!
      if (elements.videoPlayer) {
        elements.videoPlayer.hidden = false;
        elements.videoPlayer.style.display = "block";
        elements.videoPlayer.currentTime = 0;
        elements.videoPlayer.playbackRate = currentPlaybackRate;
      }

      if (elements.analysisExecHeader) {
        elements.analysisExecHeader.hidden = false;
      }
      if (elements.videoControls) {
        elements.videoControls.hidden = false;
      }

      // Assegurar botões visíveis no início
      if (elements.btnPlayPause) elements.btnPlayPause.hidden = false;
      if (elements.btnRestart) elements.btnRestart.hidden = false;
      if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "";
      if (elements.playPauseText) elements.playPauseText.textContent = "Pausar";

      updateExecutionBadge("playing");

      // 5. Iniciar reprodução do vídeo processado
      if (elements.videoPlayer) {
        elements.videoPlayer.play().catch((err) => {
          console.warn("[App] Reprodução automática bloqueada pelo navegador:", err);
          updateExecutionBadge("paused");
        });
      }

      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Execução demonstrativa em andamento.";
      }
    }, 1000);
  }

  /**
   * Reinicia a execução demonstrativa a partir do início.
   */
  function restartAnalysisExecution() {
    if (!elements.videoPlayer) return;
    elements.videoPlayer.currentTime = 0;
    elements.videoPlayer.playbackRate = currentPlaybackRate;
    if (elements.analysisEndedOverlay) {
      elements.analysisEndedOverlay.hidden = true;
    }

    // Restaura visibilidade dos botões da barra de controles
    if (elements.btnPlayPause) elements.btnPlayPause.hidden = false;
    if (elements.btnRestart) elements.btnRestart.hidden = false;
    if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "";
    if (elements.playPauseText) elements.playPauseText.textContent = "Pausar";

    updateExecutionBadge("playing");

    // Remove temporariamente os cards de resultados e volta ao estado de execução
    renderResultsSection("running");
    renderSimulationSection("waiting");

    elements.videoPlayer.play().catch(() => {});
  }

  /**
   * Alterna modo tela cheia de forma segura e com suporte a diferentes navegadores.
   */
  function toggleFullscreen() {
    const targetElement = elements.videoContainer || elements.videoPlayer;
    if (!targetElement) return;

    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      if (targetElement.requestFullscreen) {
        targetElement.requestFullscreen().catch(() => {});
      } else if (targetElement.webkitRequestFullscreen) {
        targetElement.webkitRequestFullscreen();
      } else if (elements.videoPlayer && elements.videoPlayer.webkitEnterFullscreen) {
        elements.videoPlayer.webkitEnterFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
    }
  }

  /**
   * Atualiza o selo técnico e status da execução demonstrativa.
   * @param {"playing"|"paused"|"ended"} state
   */
  function updateExecutionBadge(state) {
    if (!elements.analysisStatusBadge || !elements.analysisStatusText) return;

    if (state === "playing") {
      elements.analysisStatusBadge.className = "exec-status-badge";
      elements.analysisStatusText.textContent = "EXECUÇÃO DEMONSTRATIVA";
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Execução demonstrativa em andamento.";
      }
    } else if (state === "paused") {
      elements.analysisStatusBadge.className = "exec-status-badge paused";
      elements.analysisStatusText.textContent = "ANÁLISE PAUSADA";
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Análise pausada.";
      }
    } else if (state === "ended") {
      elements.analysisStatusBadge.className = "exec-status-badge ended";
      elements.analysisStatusText.textContent = "ANÁLISE CONCLUÍDA";
      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Execução demonstrativa concluída.";
      }
    }
  }

  /**
   * Reseta completamente os estados e elementos visuais da interface de execução.
   */
  function resetAnalysisExecutionState() {
    if (prepTimeout) {
      clearTimeout(prepTimeout);
      prepTimeout = null;
    }
    isAnalysisActive = false;
    isSeeking = false;
    isRecalculating = false;

    if (elements.analysisExecHeader) elements.analysisExecHeader.hidden = true;
    if (elements.analysisReadyOverlay) elements.analysisReadyOverlay.hidden = true;
    if (elements.analysisPrepOverlay) elements.analysisPrepOverlay.hidden = true;
    if (elements.analysisEndedOverlay) elements.analysisEndedOverlay.hidden = true;
    if (elements.videoControls) elements.videoControls.hidden = true;

    if (elements.btnPlayPause) elements.btnPlayPause.hidden = false;
    if (elements.btnRestart) elements.btnRestart.hidden = false;
    if (elements.controlsLeftGroup) elements.controlsLeftGroup.style.display = "";
    if (elements.playPauseText) elements.playPauseText.textContent = "Pausar";

    if (elements.seekSlider) elements.seekSlider.value = "0";
    if (elements.timerDisplay) elements.timerDisplay.textContent = "00:00 / 00:00";
    if (elements.analysisStatusBadge && elements.analysisStatusText) {
      elements.analysisStatusBadge.className = "exec-status-badge";
      elements.analysisStatusText.textContent = "EXECUÇÃO DEMONSTRATIVA";
    }

    renderResultsSection("waiting");
    renderSimulationSection("waiting");
  }

  /**
   * Define e aplica a taxa de velocidade de reprodução (1x, 2x ou 3x).
   * @param {1|2|3} rate
   */
  function setPlaybackRate(rate) {
    if (rate === 3) {
      currentPlaybackRate = 3;
    } else if (rate === 2) {
      currentPlaybackRate = 2;
    } else {
      currentPlaybackRate = 1;
    }

    if (elements.videoPlayer) {
      elements.videoPlayer.playbackRate = currentPlaybackRate;
    }
    if (elements.btnSpeed1x) {
      elements.btnSpeed1x.classList.toggle("active", currentPlaybackRate === 1);
    }
    if (elements.btnSpeed2x) {
      elements.btnSpeed2x.classList.toggle("active", currentPlaybackRate === 2);
    }
    if (elements.btnSpeed3x) {
      elements.btnSpeed3x.classList.toggle("active", currentPlaybackRate === 3);
    }
  }

  /**
   * Renderiza o conteúdo da seção de Resultados do Processamento.
   * @param {"waiting"|"running"|"completed"} state
   */
  function renderResultsSection(state) {
    if (!elements.detailResultsContent) return;

    if (state === "waiting") {
      elements.detailResultsContent.innerHTML = `
        <p id="detail-results-status" class="results-neutral-text">Aguardando conclusão da análise.</p>
      `;
      return;
    }

    if (state === "running") {
      elements.detailResultsContent.innerHTML = `
        <p id="detail-results-status" class="results-neutral-text">Análise em execução. Os resultados serão exibidos ao final.</p>
      `;
      return;
    }

    if (state === "completed") {
      const item = intersections.find((i) => i.id === selectedId);
      if (!item) return;

      const processing = item.processing;
      const isComplete = processing && processing.scope === "complete" && processing.counts;

      if (isComplete) {
        const counts = processing.counts;
        const lines = processing.lines || [];
        const linesText = lines.length > 0
          ? lines.map((l) => `${escapeHtml(l.id)} ${l.total}`).join(" &middot; ")
          : "";

        elements.detailResultsContent.innerHTML = `
          <div class="results-metrics-grid">
            <div class="metric-card">
              <span class="metric-card-label">Carros</span>
              <span class="metric-card-value">${counts.car ?? 0}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card-label">Motocicletas</span>
              <span class="metric-card-value">${counts.motorcycle ?? 0}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card-label">Ônibus</span>
              <span class="metric-card-value">${counts.bus ?? 0}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card-label">Caminhões</span>
              <span class="metric-card-value">${counts.truck ?? 0}</span>
            </div>
            <div class="metric-card metric-card-total">
              <span class="metric-card-label">Travessias</span>
              <span class="metric-card-value">${counts.total_traversals ?? 0}</span>
            </div>
          </div>
          ${linesText ? `<div class="results-lines-info">Linhas de contagem: ${linesText}</div>` : ""}
        `;
      } else {
        // Trecho processado / parcial (CET-01 a CET-04)
        elements.detailResultsContent.innerHTML = `
          <div class="results-partial-message">
            Métricas consolidadas não disponíveis para este trecho processado.
          </div>
        `;
      }
    }
  }

  /**
   * Renderiza a seção de Simulação do Controle Semafórico Adaptativo.
   * @param {"waiting"|"ready"|"simulated"} state
   * @param {Object} [data] Dados calculados da simulação
   */
  function renderSimulationSection(state, data) {
    if (!elements.simulationContent) return;

    if (state === "waiting") {
      if (elements.simulationStatusBadge) {
        elements.simulationStatusBadge.textContent = "Aguardando simulação";
      }
      elements.simulationContent.innerHTML = `
        <div class="simulation-waiting-state">
          <p id="detail-simulation-status" class="simulation-neutral-text">
            Aguardando conclusão da análise veicular para habilitar a simulação adaptativa.
          </p>
          <button type="button" id="btn-run-simulation" class="btn-simulate-action disabled" disabled aria-disabled="true">
            SIMULAR CONTROLE ADAPTATIVO
          </button>
        </div>
      `;
      return;
    }

    if (state === "ready") {
      if (elements.simulationStatusBadge) {
        elements.simulationStatusBadge.textContent = "Disponível";
      }
      elements.simulationContent.innerHTML = `
        <div class="simulation-ready-state">
          <p class="simulation-desc-text">
            Utilize os dados processados para gerar uma recomendação demonstrativa de temporização.
          </p>
          <button type="button" id="btn-run-simulation" class="btn-simulate-action" aria-label="Simular controle adaptativo">
            SIMULAR CONTROLE ADAPTATIVO
          </button>
        </div>
      `;
      return;
    }

    if (state === "simulated" && data) {
      if (elements.simulationStatusBadge) {
        elements.simulationStatusBadge.textContent = data.badgeText || "Simulação calculada";
      }

      const formattedDemand = data.weightedPerMinute.toFixed(1).replace(".", ",");
      const formattedRed = data.redEstimated.toFixed(1).replace(".", ",");

      elements.simulationContent.innerHTML = `
        <div class="simulation-results-wrapper">
          <!-- Grupo 1: Diagnóstico de Tráfego -->
          <div class="simulation-group-header">
            <span class="simulation-group-title">Diagnóstico do Fluxo Observado</span>
          </div>
          <div class="simulation-metrics-grid">
            <div class="metric-card simulation-card-level">
              <span class="metric-card-label">Nível de Fluxo</span>
              <span class="metric-card-value simulation-level-badge level-${data.level.toLowerCase()}">
                ${data.level}
              </span>
            </div>
            <div class="metric-card">
              <span class="metric-card-label">Demanda Ponderada</span>
              <span class="metric-card-value">
                ${formattedDemand} <small class="metric-unit">unidades equivalentes/min</small>
              </span>
            </div>
            <div class="metric-card simulation-card-line">
              <span class="metric-card-label">Maior Fluxo Observado</span>
              <span class="metric-card-value simulation-line-value">
                ${data.lineText}
              </span>
            </div>
          </div>

          <!-- Grupo 2: Fases Semafóricas Didáticas (Ciclo de 60s) -->
          <div class="simulation-group-header">
            <span class="simulation-group-title">Temporização Semafórica Sugerida (Ciclo de 60 s)</span>
          </div>
          <div class="simulation-metrics-grid simulation-phases-main">
            <div class="metric-card simulation-phase-card simulation-phase-green">
              <div class="phase-header">
                <span class="phase-indicator" aria-hidden="true"></span>
                <span class="phase-label">Tempo de Verde</span>
              </div>
              <div class="phase-value-row">
                <span class="phase-number">${data.green}</span>
                <span class="phase-unit">s</span>
              </div>
            </div>
            <div class="metric-card simulation-phase-card simulation-phase-yellow">
              <div class="phase-header">
                <span class="phase-indicator" aria-hidden="true"></span>
                <span class="phase-label">Tempo de Amarelo</span>
              </div>
              <div class="phase-value-row">
                <span class="phase-number">3</span>
                <span class="phase-unit">s</span>
              </div>
            </div>
            <div class="metric-card simulation-phase-card simulation-phase-red">
              <div class="phase-header">
                <span class="phase-indicator" aria-hidden="true"></span>
                <span class="phase-label">Vermelho Estimado</span>
              </div>
              <div class="phase-value-row">
                <span class="phase-number">${formattedRed}</span>
                <span class="phase-unit">s</span>
              </div>
            </div>
          </div>

          <!-- Parâmetro Técnico de Segurança: Entreverdes -->
          <div class="simulation-intergreen-card">
            <div class="intergreen-header">
              <div class="intergreen-title-group">
                <span class="intergreen-badge">SEGURANÇA</span>
                <span class="intergreen-label">Entreverdes</span>
              </div>
              <div class="intergreen-value-row">
                <span class="intergreen-number">1,5</span>
                <span class="intergreen-unit">s</span>
              </div>
            </div>
            <p class="intergreen-desc">
              Vermelho geral de segurança entre fases. Intervalo em que todas as aproximações permanecem temporariamente no vermelho antes da liberação da próxima fase.
            </p>
          </div>

          <!-- Linha-resumo textual do ciclo sugerido -->
          <div class="simulation-cycle-summary">
            <span class="summary-bullet" aria-hidden="true">&#9679;</span>
            <span class="summary-text">
              Ciclo demonstrativo: <strong>${data.green} s de verde</strong>, <strong>3 s de amarelo</strong>, <strong>${formattedRed} s de vermelho estimado</strong> e <strong>1,5 s de entreverdes</strong>.
            </span>
          </div>

          <!-- Bloco de Notas Didáticas e Institucionais -->
          <div class="simulation-notes-block">
            <p class="simulation-note-item">
              &bull; O vermelho apresentado é uma estimativa dentro de um ciclo demonstrativo de 60 segundos.
            </p>
            <p class="simulation-note-item">
              &bull; Entreverdes: intervalo de segurança em que todas as aproximações permanecem temporariamente no vermelho antes da liberação da próxima fase.
            </p>
            <p class="simulation-note-item">
              &bull; Simulação demonstrativa baseada nos dados do trecho analisado. Não representa controle semafórico em operação real.
            </p>
          </div>

          <div class="simulation-footer-row">
            <button type="button" id="btn-recalculate-simulation" class="btn-recalculate-action" aria-label="Recalcular simulação">
              RECALCULAR SIMULAÇÃO
            </button>
          </div>
        </div>
      `;
    }
  }

  /**
   * Aciona o recálculo da simulação semafórica com transição de loading de 500ms.
   * @param {HTMLButtonElement} btn Elemento do botão clicado
   */
  function triggerRecalculateSimulation(btn) {
    if (isRecalculating) return;
    isRecalculating = true;

    // 1. Feedback visual imediato: altera texto e desabilita o botão
    if (btn) {
      btn.disabled = true;
      btn.classList.add("disabled", "recalculating");
      btn.textContent = "RECALCULANDO...";
    }

    // 2. Atualiza temporariamente o status superior
    if (elements.simulationStatusBadge) {
      elements.simulationStatusBadge.textContent = "Recalculando...";
    }

    // 3. Efeito sutil de atualização no container da simulação
    const resultsWrapper = elements.simulationContent
      ? elements.simulationContent.querySelector(".simulation-results-wrapper")
      : null;
    if (resultsWrapper) {
      resultsWrapper.classList.add("recalculating-pulse");
    }

    // 4. Execução determinística após 500ms (janela de 400-700ms)
    setTimeout(() => {
      isRecalculating = false;
      runAdaptiveSimulation(true);
    }, 500);
  }

  /**
   * Executa os cálculos da Simulação do Controle Semafórico Adaptativo.
   * @param {boolean} [isRecalculation=false] Indica se é fruto do botão Recalcular
   */
  function runAdaptiveSimulation(isRecalculation = false) {
    const item = intersections.find((i) => i.id === selectedId);
    if (!item || !item.processing || !item.processing.counts) {
      console.warn("[App] Dados de processamento indisponíveis para simulação.");
      return;
    }

    const counts = item.processing.counts;
    const car = Number(counts.car) || 0;
    const motorcycle = Number(counts.motorcycle) || 0;
    const bus = Number(counts.bus) || 0;
    const truck = Number(counts.truck) || 0;

    // Fórmula oficial:
    // weightedTotal = (car * 1.0) + (motorcycle * 0.5) + (bus * 2.0) + (truck * 1.5)
    const weightedTotal = (car * 1.0) + (motorcycle * 0.5) + (bus * 2.0) + (truck * 1.5);

    // Duração obtida diretamente do elemento HTML5 de vídeo (segundos convertidos para minutos)
    let durationSec = elements.videoPlayer ? elements.videoPlayer.duration : 0;
    if (isNaN(durationSec) || !isFinite(durationSec) || durationSec <= 0) {
      durationSec = 60; // Fallback de proteção
    }
    const durationMin = durationSec / 60;
    const weightedPerMinute = durationMin > 0 ? (weightedTotal / durationMin) : 0;

    // Heurística demonstrativa de classificação:
    // < 30 => BAIXO (Verde: 20s)
    // >= 30 e <= 60 => MODERADO (Verde: 30s)
    // > 60 => ALTO (Verde: 40s)
    let level = "MODERADO";
    let green = 30;
    if (weightedPerMinute < 30) {
      level = "BAIXO";
      green = 20;
    } else if (weightedPerMinute <= 60) {
      level = "MODERADO";
      green = 30;
    } else {
      level = "ALTO";
      green = 40;
    }

    // Ciclo demonstrativo de 60 segundos
    const cycleTotal = 60;
    const yellow = 3;
    const intergreen = 1.5;
    const redEstimated = cycleTotal - green - yellow - intergreen;

    // Identificação da linha de maior fluxo observado
    const lines = item.processing.lines || [];
    let lineText = "-";
    if (lines.length === 1) {
      lineText = `Única linha monitorada: ${escapeHtml(lines[0].id)}`;
    } else if (lines.length > 1) {
      const maxLine = lines.reduce((prev, curr) => (Number(curr.total) > Number(prev.total) ? curr : prev), lines[0]);
      lineText = `${escapeHtml(maxLine.id)} — ${maxLine.total} travessias`;
    }

    const badgeText = isRecalculation ? "Simulação recalculada" : "Simulação calculada";

    renderSimulationSection("simulated", {
      weightedTotal,
      weightedPerMinute,
      level,
      green,
      yellow,
      intergreen,
      redEstimated,
      lineText,
      badgeText
    });
  }

  /**
   * Converte segundos em formato mm:ss legível.
   * @param {number} seconds
   * @returns {string}
   */
  function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds) || seconds < 0) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
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

    // 3. Alternar exibição das views
    currentView = "detail";
    if (elements.mapView) {
      elements.mapView.hidden = true;
    }
    if (elements.detailView) {
      elements.detailView.hidden = false;
    }

    // Reset de velocidade e resultados ao trocar de cruzamento
    setPlaybackRate(1);
    isRecalculating = false;
    renderResultsSection("waiting");
    renderSimulationSection("waiting");

    // 4. Carregar dinamicamente o vídeo processado do cruzamento selecionado com isolamento estrito
    loadIntersectionVideo(item.output_video, item.id);

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /**
   * Retorna à visualização de mapa (Map View).
   */
  function showMapView() {
    // 1. Invalidar qualquer carregamento em andamento
    videoLoadToken++;
    activeIntersectionId = null;

    // 2. Cancelar qualquer timer de preparação ativo
    if (prepTimeout) {
      clearTimeout(prepTimeout);
      prepTimeout = null;
    }

    // 3. Reset forte do player de vídeo (descarta buffer, frames e metadados)
    resetVideoElement();

    // 4. Reset completo dos controles e overlays da análise
    resetAnalysisExecutionState();

    // 5. Reset seguro de velocidade e resultados
    setPlaybackRate(1);
    isRecalculating = false;
    renderResultsSection("waiting");
    renderSimulationSection("waiting");

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
   * @param {number} [token] Token de carregamento para validação de concorrência
   */
  function setVideoState(state, token) {
    if (!elements.videoPlayer || !elements.videoOverlay) return;

    // Se um token for fornecido e for diferente do ativo, ignora o evento atrasado
    if (token !== undefined && token !== videoLoadToken) {
      return;
    }

    if (state === "ready") {
      // Estado READY: PRÉ-EXECUÇÃO.
      // O vídeo NÃO deve ser exibido, NÃO deve iniciar e os controles NÃO devem aparecer.
      if (prepTimeout) {
        clearTimeout(prepTimeout);
        prepTimeout = null;
      }
      isAnalysisActive = false;

      // O elemento <video> permanece pausado e estritamente oculto
      elements.videoPlayer.pause();
      elements.videoPlayer.hidden = true;
      elements.videoPlayer.style.display = "none";

      // Oculta placeholder neutro
      elements.videoOverlay.hidden = true;

      // Mostra a tela de ANÁLISE PRONTA com especificações e botão INICIAR ANÁLISE
      if (elements.analysisReadyOverlay) elements.analysisReadyOverlay.hidden = false;

      // Controles, cabeçalho e demais overlays permanecem ocultos
      if (elements.analysisExecHeader) elements.analysisExecHeader.hidden = true;
      if (elements.analysisPrepOverlay) elements.analysisPrepOverlay.hidden = true;
      if (elements.analysisEndedOverlay) elements.analysisEndedOverlay.hidden = true;
      if (elements.videoControls) elements.videoControls.hidden = true;

      if (elements.detailAnalysisStatus) {
        elements.detailAnalysisStatus.textContent = "Análise veicular pronta para execução demonstrativa.";
      }
    } else if (state === "loading") {
      resetAnalysisExecutionState();

      elements.videoPlayer.hidden = true;
      elements.videoPlayer.style.display = "none";
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
      resetAnalysisExecutionState();

      elements.videoPlayer.hidden = true;
      elements.videoPlayer.style.display = "none";
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
      resetAnalysisExecutionState();

      elements.videoPlayer.hidden = true;
      elements.videoPlayer.style.display = "none";
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
   * Configura e carrega o vídeo processado com isolamento absoluto por cruzamento.
   * @param {string|null} videoPath Caminho do vídeo output
   * @param {string} [intersectionId] ID do cruzamento ativo
   */
  async function loadIntersectionVideo(videoPath, intersectionId) {
    if (!elements.videoPlayer) return;

    // 1. Gera um novo token para invalidar qualquer evento ou fetch anterior
    const myToken = ++videoLoadToken;
    activeIntersectionId = intersectionId || selectedId;

    // 2. Cancela qualquer timer de preparação ativo
    if (prepTimeout) {
      clearTimeout(prepTimeout);
      prepTimeout = null;
    }

    // 3. Reset forte do elemento <video> (descarta buffer, frame residual, metadados)
    resetVideoElement();

    // 4. Reset completo da UI para estado neutro LOADING
    resetAnalysisExecutionState();

    // 5. Se o cruzamento não possui arquivo configurado no JSON
    if (!videoPath) {
      setVideoState("unavailable", myToken);
      return;
    }

    // 6. Entra imediatamente em LOADING neutro antes de qualquer verificação
    setVideoState("loading", myToken);

    // 7. Teste de existência física do recurso via fetch HEAD
    try {
      const response = await fetch(videoPath, { method: "HEAD" });

      // Se o usuário trocou de ponto durante o fetch, aborta!
      if (myToken !== videoLoadToken || selectedId !== activeIntersectionId) {
        return;
      }

      if (!response.ok) {
        // Arquivo não existe no servidor (ex: 404) -> UNAVAILABLE
        setVideoState("unavailable", myToken);
        return;
      }

      // 8. Arquivo existe no servidor: atribui ao player e aciona load()
      elements.videoPlayer.src = videoPath;
      elements.videoPlayer.load();
    } catch (e) {
      if (myToken !== videoLoadToken || selectedId !== activeIntersectionId) {
        return;
      }
      setVideoState("unavailable", myToken);
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
    setPlaybackRate,
    renderResultsSection,
    renderSimulationSection,
    runAdaptiveSimulation,
    triggerRecalculateSimulation,
    getCurrentView: () => currentView,
    getSelectedId: () => selectedId,
    getVideoPlayer: () => elements.videoPlayer,
    getIntersections: () => intersections,
  };
})();

window.App = App;
