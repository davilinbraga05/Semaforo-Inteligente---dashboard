/**
 * Sistema Inteligente de Controle Semafórico
 * Módulo Base do Dashboard — Carregamento e Validação dos Pontos de Monitoramento
 */

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  const container = document.getElementById("intersections-grid");
  const loadingIndicator = document.getElementById("state-loading");
  const errorContainer = document.getElementById("state-error");
  const countDisplay = document.getElementById("stat-total-count");
  const verifiedDisplay = document.getElementById("stat-verified-count");

  try {
    const response = await fetch("data/intersections.json");
    if (!response.ok) {
      throw new Error(`Falha na requisição HTTP: status ${response.status} (${response.statusText})`);
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error("O arquivo de dados não contém uma lista válida de cruzamentos (esperado array).");
    }

    // Ocultar estado de carregamento
    if (loadingIndicator) {
      loadingIndicator.style.display = "none";
    }

    // Métricas do carregamento
    let verifiedCount = 0;

    // Renderizar registros
    container.innerHTML = "";
    data.forEach((item) => {
      const isVerified = item.coordinate_status === "verified" &&
                         item.latitude !== null &&
                         item.longitude !== null &&
                         !isNaN(item.latitude) &&
                         !isNaN(item.longitude);

      if (isVerified) {
        verifiedCount++;
      }

      const card = createIntersectionCard(item, isVerified);
      container.appendChild(card);
    });

    // Atualizar estatísticas na barra
    if (countDisplay) {
      countDisplay.textContent = data.length.toString();
    }
    if (verifiedDisplay) {
      verifiedDisplay.textContent = `${verifiedCount} / ${data.length}`;
    }

  } catch (error) {
    console.error("[Dashboard] Erro ao carregar os pontos de monitoramento:", error);

    if (loadingIndicator) {
      loadingIndicator.style.display = "none";
    }

    if (errorContainer) {
      errorContainer.textContent = "Não foi possível carregar os pontos de monitoramento. Verifique se o arquivo data/intersections.json está acessível.";
      errorContainer.style.display = "block";
    }
  }
}

/**
 * Cria o card DOM de um ponto de monitoramento.
 * @param {Object} item Dados do cruzamento
 * @param {boolean} isVerified Se as coordenadas estão validadas
 * @returns {HTMLElement} Elemento card construído
 */
function createIntersectionCard(item, isVerified) {
  const card = document.createElement("article");
  card.className = "intersection-card";
  card.id = `card-${item.id || "unknown"}`;

  const coordsText = isVerified
    ? `${Number(item.latitude).toFixed(6)}, ${Number(item.longitude).toFixed(6)}`
    : "Coordenadas pendentes";

  const statusClass = isVerified ? "verified" : "pending";
  const statusLabel = isVerified ? "Verificada" : "Pendente";

  // Extrair nome simples do arquivo de vídeo para exibição limpa
  const videoInputName = item.input_video ? item.input_video.split("/").pop() : "Não vinculado";

  card.innerHTML = `
    <div class="card-top">
      <span class="camera-tag">${escapeHtml(item.camera_id || "CET-XX")}</span>
      <span class="badge-status ${statusClass}">${statusLabel}</span>
    </div>

    <div class="card-title-area">
      <h3 class="intersection-name">${escapeHtml(item.name || "Cruzamento não identificado")}</h3>
      <span class="intersection-location">${escapeHtml(item.location_detail || "São Paulo, SP")}</span>
    </div>

    <div class="card-details-table">
      <div class="detail-row">
        <span class="detail-label">Nome Curto:</span>
        <span class="detail-value">${escapeHtml(item.short_name || "-")}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Coordenadas:</span>
        <span class="detail-value">${coordsText}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Vídeo de Entrada:</span>
        <span class="detail-value">${escapeHtml(videoInputName)}</span>
      </div>
    </div>

    <div class="card-footer">
      <div class="card-footer-item">
        ID: <span>${escapeHtml(item.id || "-")}</span>
      </div>
      <div class="card-footer-item">
        Status: <span>${escapeHtml(item.status || "available")}</span>
      </div>
    </div>
  `;

  return card;
}

/**
 * Sanitiza strings para exibição segura no DOM.
 * @param {string} str Texto original
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
