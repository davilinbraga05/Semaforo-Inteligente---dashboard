"""
BOTI - Bot de Otimização de Tráfego Inteligente
Módulo de Detecção e Calibração Automática da Linha Virtual de Contagem.

Este módulo implementa a classe AutoLineDetector, responsável por amostrar as
trajetórias dos veículos nos primeiros segundos de vídeo, identificar a direção
predominante do fluxo (horizontal vs vertical), calcular a posição média do tráfego
e gerar as coordenadas perpendiculares ideais para a linha virtual de contagem.
"""

from typing import Dict, List, Tuple, Optional
import sys
import numpy as np
import cv2

from config import LINE_START, LINE_END

# Garantir suporte a UTF-8 no stdout (evita falhas de encoding com emojis no Windows)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class AutoLineDetector:
    """
    Detector e calibrador automático da linha de contagem veicular.

    Principais atribuições:
    - Acumula trajetórias (track_id e posições) durante a janela de calibração inicial.
    - Determina se o fluxo predominante é horizontal ou vertical com base nas variações médias em X e Y.
    - Calcula a posição média do fluxo de tráfego.
    - Gera as coordenadas de corte perpendicular (line_start e line_end).
    - Aplica fallback seguro caso nenhum veículo se mova durante a calibração.
    - Renderiza visualmente o status da calibração na tela.
    """

    def __init__(
        self,
        calibration_frames: int = 75,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        margin_ratio: float = 0.05,
        min_displacement: float = 10.0,
        fallback_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    ):
        """
        Inicializa o detector de auto-calibração.

        :param calibration_frames: Quantidade de quadros iniciais para amostragem (padrão: 75).
        :param frame_width: Largura da imagem/vídeo.
        :param frame_height: Altura da imagem/vídeo.
        :param margin_ratio: Margem proporcional às bordas do frame (padrão: 0.05 = 5%).
        :param min_displacement: Deslocamento mínimo em pixels para considerar veículo em movimento.
        :param fallback_line: Tupla ((x1, y1), (x2, y2)) de fallback caso não haja fluxo detectável.
        """
        self.calibration_frames = max(1, int(calibration_frames))
        self.frame_width = int(frame_width) if frame_width is not None else None
        self.frame_height = int(frame_height) if frame_height is not None else None
        self.margin_ratio = float(margin_ratio)
        self.min_displacement = float(min_displacement)
        self.fallback_line = fallback_line or (LINE_START, LINE_END)

        # Histórico de trajetórias: {track_id: [(x, y), ...]}
        self.trajectories: Dict[int, List[Tuple[float, float]]] = {}

        # Última posição registrada por veículo ativo: {track_id: (x, y)}
        self.last_positions: Dict[int, Tuple[float, float]] = {}

        # Estado da calibração
        self.current_frame: int = 0
        self.is_calibrated: bool = False
        self.flow_direction: Optional[str] = None  # 'horizontal' ou 'vertical'
        self.line_start: Optional[Tuple[int, int]] = None
        self.line_end: Optional[Tuple[int, int]] = None
        self.used_fallback: bool = False

        # Métricas calculadas para relatório e depuração
        self.avg_dx: float = 0.0
        self.avg_dy: float = 0.0
        self.sampled_tracks_count: int = 0
        self.moving_tracks_count: int = 0

    @staticmethod
    def get_reference_point(bbox: List[float]) -> Tuple[float, float]:
        """
        Calcula o ponto de referência do veículo (centro inferior da bounding box),
        alinhado à convenção do VehicleCounter.
        """
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, float(y2))

    def update_track(self, track_id: int, bbox: List[float]) -> None:
        """
        Registra a posição de um veículo ativo durante a fase de calibração.
        """
        if self.is_calibrated:
            return

        ref_pt = self.get_reference_point(bbox)
        if track_id not in self.trajectories:
            self.trajectories[track_id] = []

        self.trajectories[track_id].append(ref_pt)
        self.last_positions[track_id] = ref_pt

    def step(self) -> bool:
        """
        Avança o contador de quadros da calibração.
        Retorna True caso a calibração tenha sido concluída exatamente neste passo.
        """
        if self.is_calibrated:
            return False

        self.current_frame += 1
        if self.current_frame >= self.calibration_frames:
            self.calibrate()
            return True
        return False

    def is_calibrating(self) -> bool:
        """
        Informa se o sistema ainda se encontra na janela ativa de calibração.
        """
        return (not self.is_calibrated) and (self.current_frame < self.calibration_frames)

    def calibrate(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Processa as trajetórias acumuladas, identifica o fluxo predominante
        e calcula os pontos de início e fim da linha de contagem perpendicular.
        """
        if self.is_calibrated and self.line_start is not None and self.line_end is not None:
            return self.line_start, self.line_end

        self.is_calibrated = True
        self.sampled_tracks_count = len(self.trajectories)

        # 1. Filtrar trajetórias com amostragem suficiente e calcular deslocamentos
        valid_tracks = []
        moving_tracks = []

        for tid, pts in self.trajectories.items():
            if len(pts) >= 2:
                valid_tracks.append(pts)
                p_first = pts[0]
                p_last = pts[-1]
                dx = abs(p_last[0] - p_first[0])
                dy = abs(p_last[1] - p_first[1])
                displacement = np.hypot(dx, dy)
                if displacement >= self.min_displacement:
                    moving_tracks.append((dx, dy, pts))

        self.moving_tracks_count = len(moving_tracks)

        # 2. Verificar necessidade de fallback seguro caso não haja veículos em movimento
        if not moving_tracks:
            # Tentar relaxar critério usando qualquer track com >= 2 pontos
            if valid_tracks:
                for pts in valid_tracks:
                    dx = abs(pts[-1][0] - pts[0][0])
                    dy = abs(pts[-1][1] - pts[0][1])
                    moving_tracks.append((dx, dy, pts))

        if not moving_tracks:
            # Fallback seguro absoluto
            self.used_fallback = True
            self.flow_direction = "vertical"  # Orientação padrão habitual
            self.line_start = tuple(map(int, self.fallback_line[0]))
            self.line_end = tuple(map(int, self.fallback_line[1]))
            print("⚠️ [AutoLineDetector] Nenhum fluxo veicular significativo detectado na calibração.")
            print(f"🔄 Aplicando fallback seguro da linha: {self.line_start} -> {self.line_end}")
            return self.line_start, self.line_end

        # 3. Analisar variações médias em X e Y
        dx_list = [item[0] for item in moving_tracks]
        dy_list = [item[1] for item in moving_tracks]
        self.avg_dx = float(np.mean(dx_list))
        self.avg_dy = float(np.mean(dy_list))

        # Posição média do fluxo veicular
        all_x = [pt[0] for item in moving_tracks for pt in item[2]]
        all_y = [pt[1] for item in moving_tracks for pt in item[2]]
        mean_x = int(round(float(np.mean(all_x))))
        mean_y = int(round(float(np.mean(all_y))))

        width = self.frame_width if self.frame_width is not None else int(max(all_x) * 1.1)
        height = self.frame_height if self.frame_height is not None else int(max(all_y) * 1.1)

        # 4. Determinar corte perpendicular ao fluxo
        if self.avg_dx >= self.avg_dy:
            # Fluxo predominante HORIZONTAL -> linha perpendicular é VERTICAL
            self.flow_direction = "horizontal"
            # Garante que mean_x fique contido nos limites do frame
            clamped_x = max(int(width * 0.1), min(int(width * 0.9), mean_x))
            y_start = int(self.margin_ratio * height)
            y_end = int((1.0 - self.margin_ratio) * height)
            self.line_start = (clamped_x, y_start)
            self.line_end = (clamped_x, y_end)
        else:
            # Fluxo predominante VERTICAL -> linha perpendicular é HORIZONTAL
            self.flow_direction = "vertical"
            # Garante que mean_y fique contido nos limites do frame
            clamped_y = max(int(height * 0.1), min(int(height * 0.9), mean_y))
            x_start = int(self.margin_ratio * width)
            x_end = int((1.0 - self.margin_ratio) * width)
            self.line_start = (x_start, clamped_y)
            self.line_end = (x_end, clamped_y)

        print(f"🎯 [AutoLineDetector] Calibração concluída com sucesso!")
        print(f"   • Fluxo detectado: {self.flow_direction.upper()} (DeltaX médio: {self.avg_dx:.1f}px | DeltaY médio: {self.avg_dy:.1f}px)")
        print(f"   • Veículos rastreados na amostragem: {self.sampled_tracks_count} ({self.moving_tracks_count} em movimento)")
        print(f"   • Linha calculada perpendicular: {self.line_start} -> {self.line_end}")

        return self.line_start, self.line_end

    def get_last_positions(self) -> Dict[int, Tuple[float, float]]:
        """
        Retorna o dicionário com as últimas posições conhecidas dos veículos amostrados.
        Útil para semear o VehicleCounter evitando perda na transição do frame.
        """
        return dict(self.last_positions)

    def draw_calibration_notice(self, frame: np.ndarray) -> np.ndarray:
        """
        Desenha o aviso visual de calibração automática em andamento sobre o frame.
        Mantém o padrão estético moderno com painel translúcido e barra de progresso.
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        # Dimensões do banner HUD superior centralizado
        banner_w = 460
        banner_h = 60
        banner_x1 = max(10, (w - banner_w) // 2)
        banner_y1 = 18
        banner_x2 = banner_x1 + banner_w
        banner_y2 = banner_y1 + banner_h

        # Overlay semi-transparente escuro
        overlay = annotated.copy()
        cv2.rectangle(overlay, (banner_x1, banner_y1), (banner_x2, banner_y2), (20, 20, 20), -1)
        # Borda com tom âmbar/amarelo de calibração
        cv2.rectangle(overlay, (banner_x1, banner_y1), (banner_x2, banner_y2), (0, 190, 255), 2)

        alpha = 0.82
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

        # Ícone visual indicador (círculo pulsante / de status)
        indicator_center = (banner_x1 + 25, banner_y1 + 25)
        cv2.circle(annotated, indicator_center, 7, (0, 190, 255), -1, cv2.LINE_AA)
        cv2.circle(annotated, indicator_center, 11, (0, 220, 255), 1, cv2.LINE_AA)

        # Título principal do aviso
        title_text = "Calibrando linha automatica..."
        cv2.putText(
            annotated,
            title_text,
            (banner_x1 + 44, banner_y1 + 28),
            cv2.FONT_HERSHEY_DUPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

        # Barra de progresso da amostragem
        progress = min(1.0, self.current_frame / float(self.calibration_frames))
        bar_x1 = banner_x1 + 44
        bar_y1 = banner_y1 + 38
        bar_w = banner_w - 60
        bar_h = 8
        bar_x2 = bar_x1 + bar_w
        bar_y2 = bar_y1 + bar_h

        # Fundo da barra
        cv2.rectangle(annotated, (bar_x1, bar_y1), (bar_x2, bar_y2), (50, 50, 50), -1)

        # Preenchimento da barra de progresso
        filled_w = int(bar_w * progress)
        if filled_w > 0:
            cv2.rectangle(annotated, (bar_x1, bar_y1), (bar_x1 + filled_w, bar_y2), (0, 200, 255), -1)

        # Contador numérico discreto
        prog_text = f"{self.current_frame}/{self.calibration_frames}"
        cv2.putText(
            annotated,
            prog_text,
            (banner_x2 - 45, banner_y1 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (200, 200, 200),
            1,
            cv2.LINE_AA
        )

        return annotated
