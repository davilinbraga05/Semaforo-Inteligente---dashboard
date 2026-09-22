"""
BOTI - Bot de Otimização de Tráfego Inteligente
Módulo de Contagem e Classificação de Veículos com Linha Virtual.

Este módulo implementa a contagem de veículos baseada na travessia de uma
linha virtual delimitada, utilizando os identificadores únicos (track_id)
gerados pelo ByteTrack para garantir contagem estritamente única por veículo.
"""

from typing import Dict, Tuple, Set, Optional, List
import cv2
import numpy as np

from config import (
    BOTI_CLASSES,
    BOTI_CLASS_NAMES_PT,
    BOTI_CLASS_COLORS,
    LINE_START,
    LINE_END,
    LINE_COLOR,
    LINE_THICKNESS
)


# Paleta de cores padrão para múltiplas linhas de contagem (BGR)
LINE_PALETTE: List[Tuple[int, int, int]] = [
    (0, 0, 255),      # L1: Vermelho
    (255, 180, 0),    # L2: Ciano / Azul Claro
    (0, 215, 255),    # L3: Amarelo
    (255, 0, 220),    # L4: Magenta
    (0, 255, 128),    # L5: Verde Claro
    (180, 105, 255),  # L6: Roxo
]


class VehicleCounter:
    """
    Controlador de contagem veicular baseado em uma linha virtual específica.
    
    Principais atribuições:
    - Rastreia o ponto de contato do veículo com a pista (centro inferior da bbox).
    - Detecta a transição efetiva de lado em relação à linha virtual (interseção geométrica).
    - Mantém registro imutável de IDs já contados nesta linha (garante zero contagem duplicada).
    - Mantém contadores separados para as 4 classes oficiais e contador total.
    - Renderiza a linha virtual e um painel de monitoramento no frame de saída.
    """

    def __init__(
        self,
        line_start: Tuple[int, int] = LINE_START,
        line_end: Tuple[int, int] = LINE_END,
        line_color: Optional[Tuple[int, int, int]] = None,
        line_thickness: int = LINE_THICKNESS,
        line_id: str = "line_1",
        label: str = "L1"
    ):
        self.line_id = line_id
        self.label = label
        self.line_start = tuple(map(int, line_start))
        self.line_end = tuple(map(int, line_end))
        self.line_color = line_color if line_color is not None else LINE_COLOR
        self.line_thickness = line_thickness

        # Posições no frame anterior para cada track_id ativo: {track_id: (x, y)}
        self.previous_positions: Dict[int, Tuple[float, float]] = {}

        # Conjunto de IDs que já cruzaram esta linha (nunca são contados novamente nesta linha)
        self.counted_ids: Set[int] = set()

        # Contadores individuais pelas classes oficiais para esta linha
        self.counts: Dict[str, int] = {cls_name: 0 for cls_name in BOTI_CLASSES.values()}

        # Histórico de veículos recém-contados para destaque visual temporário
        self.recent_crossings: Set[int] = set()

    def set_line(self, line_start: Tuple[int, int], line_end: Tuple[int, int]) -> None:
        """
        Atualiza dinamicamente as coordenadas da linha virtual de contagem.
        Mantém o histórico de veículos já contados para evitar recontagem.
        """
        self.line_start = tuple(map(int, line_start))
        self.line_end = tuple(map(int, line_end))


    @staticmethod
    def get_reference_point(bbox: List[float]) -> Tuple[float, float]:
        """
        Calcula o ponto de referência do veículo.
        Conforme especificação do projeto, utiliza o centro inferior da bounding box:
        x = (x1 + x2) / 2
        y = y2
        Representa o ponto mais próximo de contato do veículo com a pista.
        """
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, float(y2))

    def _has_crossed_line(self, pt1: Tuple[float, float], pt2: Tuple[float, float]) -> bool:
        """
        Determina com precisão geométrica se o deslocamento do veículo de pt1 (frame anterior)
        até pt2 (frame atual) cruzou a linha virtual delimitada (line_start -> line_end).
        
        Utiliza o produto vetorial 2D (teste de orientação):
        - Verifica se pt1 e pt2 estão em lados opostos da linha virtual.
        - Verifica se a linha virtual intercepta o segmento formado pela trajetória (pt1 -> pt2).
        """
        A = self.line_start
        B = self.line_end
        P = pt1
        Q = pt2

        # Se não houve movimento mensurável, não há cruzamento
        if P == Q:
            return False

        def cross_product(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        # Teste de lado dos pontos P e Q em relação à reta que contém o segmento AB
        cp1 = cross_product(A, B, P)
        cp2 = cross_product(A, B, Q)

        # Teste de lado dos pontos A e B em relação à reta que contém a trajetória PQ
        cq1 = cross_product(P, Q, A)
        cq2 = cross_product(P, Q, B)

        # Para haver cruzamento de segmentos:
        # P e Q devem estar em lados opostos de AB (cp1 e cp2 com sinais contrários)
        # E A e B devem estar em lados opostos de PQ (cq1 e cq2 com sinais contrários)
        if (cp1 * cp2 <= 0) and (cq1 * cq2 <= 0) and (cp1 != cp2):
            return True

        return False

    def update(self, track_id: int, cls_name: str, bbox: List[float]) -> bool:
        """
        Atualiza o estado do veículo e computa a contagem caso ocorra o cruzamento da linha.
        
        Retorna True se o veículo cruzou e foi contabilizado neste instante; False caso contrário.
        """
        # Garantir que a classe pertence às classes oficiais do BOTI
        if cls_name not in self.counts:
            return False

        current_pt = self.get_reference_point(bbox)
        just_counted = False

        if track_id in self.previous_positions:
            prev_pt = self.previous_positions[track_id]

            # Verificar se cruzou a linha
            if self._has_crossed_line(prev_pt, current_pt):
                # Regra estrita: contar APENAS se o track_id ainda não tiver sido contabilizado
                if track_id not in self.counted_ids:
                    self.counts[cls_name] += 1
                    self.counted_ids.add(track_id)
                    self.recent_crossings.add(track_id)
                    just_counted = True

        # Atualizar histórico de posição para o próximo frame
        self.previous_positions[track_id] = current_pt
        return just_counted

    def get_total_count(self) -> int:
        """Retorna o número total de veículos contabilizados (soma das 4 classes)."""
        return sum(self.counts.values())

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """
        Desenha a linha virtual e o painel de contagem no frame de vídeo.
        """
        annotated = frame.copy()

        # 1. Desenhar a Linha Virtual
        cv2.line(
            annotated,
            self.line_start,
            self.line_end,
            self.line_color,
            self.line_thickness,
            cv2.LINE_AA
        )

        # Marcadores nas extremidades da linha para maior clareza visual
        cv2.circle(annotated, self.line_start, 6, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.circle(annotated, self.line_end, 6, (0, 0, 255), -1, cv2.LINE_AA)

        # Rótulo sobre a linha
        label_pos = (self.line_start[0] + 10, max(20, self.line_start[1] - 8))
        cv2.putText(
            annotated,
            "LINHA DE CONTAGEM",
            label_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            2,
            cv2.LINE_AA
        )

        # 2. Painel Compacto de Estatísticas (HUD Minimalista no canto superior esquerdo)
        items = [
            ("Carro", self.counts.get("car", 0)),
            ("Moto", self.counts.get("motorcycle", 0)),
            ("Onibus", self.counts.get("bus", 0)),
            ("Caminhao", self.counts.get("truck", 0)),
            ("Total", self.get_total_count()),
        ]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.42
        font_thickness = 1
        line_height = 16
        pad_x, pad_y = 8, 6
        panel_x1, panel_y1 = 10, 10

        # Formatação das 5 linhas e ajuste dinâmico da largura necessária
        formatted_lines = [f"{label}: {count}" for label, count in items]
        max_text_w = max(
            cv2.getTextSize(line, font, font_scale, font_thickness)[0][0]
            for line in formatted_lines
        )
        panel_w = max_text_w + (pad_x * 2)
        panel_h = (len(formatted_lines) * line_height) + (pad_y * 2)
        panel_x2 = panel_x1 + panel_w
        panel_y2 = panel_y1 + panel_h

        # Fundo preto translúcido (alpha = 0.65)
        overlay = annotated.copy()
        cv2.rectangle(overlay, (panel_x1, panel_y1), (panel_x2, panel_y2), (0, 0, 0), -1)
        alpha = 0.65
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

        # Borda sutil
        cv2.rectangle(annotated, (panel_x1, panel_y1), (panel_x2, panel_y2), (70, 70, 70), 1)

        # Renderizar as linhas com espaçamento reduzido
        for idx, line_text in enumerate(formatted_lines):
            text_y = panel_y1 + pad_y + ((idx + 1) * line_height) - 4
            cv2.putText(
                annotated,
                line_text,
                (panel_x1 + pad_x, text_y),
                font,
                font_scale,
                (255, 255, 255),
                font_thickness,
                cv2.LINE_AA,
            )

        return annotated


class MultiLineVehicleCounter:
    """
    Gerenciador dinâmico de múltiplas linhas de contagem veicular (1 a N linhas).

    Principais atribuições:
    - Mantém uma coleção dinâmica de instâncias de VehicleCounter.
    - Gerencia de forma centralizada as posições anteriores de cada track_id para evitar redundâncias.
    - Avalia a travessia de cada veículo contra todas as linhas configuradas de forma independente.
    - Assegura memória de track_id isolada por linha (o mesmo veículo pode cruzar L1 e depois L2).
    - Agrega os totais gerais somando as contagens individuais de todas as linhas.
    - Renderiza visualmente todas as linhas com identificadores discretos e o HUD consolidado.
    """

    def __init__(self, lines: Optional[List[VehicleCounter]] = None):
        self.lines: List[VehicleCounter] = lines if lines is not None else []
        # Histórico centralizado de posições anteriores por track_id: {track_id: (x, y)}
        self.previous_positions: Dict[int, Tuple[float, float]] = {}

    @property
    def line_start(self) -> Optional[Tuple[int, int]]:
        return self.lines[0].line_start if self.lines else None

    @property
    def line_end(self) -> Optional[Tuple[int, int]]:
        return self.lines[0].line_end if self.lines else None

    @property
    def counts(self) -> Dict[str, int]:
        return self.get_total_counts()

    @classmethod
    def from_segments(
        cls,
        segments: List[Tuple[Tuple[int, int], Tuple[int, int]]],
        palette: List[Tuple[int, int, int]] = LINE_PALETTE
    ) -> "MultiLineVehicleCounter":
        """
        Cria o gerenciador a partir de uma lista dinâmica de pares de coordenadas:
        [((x1, y1), (x2, y2)), ((x3, y3), (x4, y4)), ...]
        """
        counters = []
        for idx, (start, end) in enumerate(segments, start=1):
            color = palette[(idx - 1) % len(palette)]
            vc = VehicleCounter(
                line_start=start,
                line_end=end,
                line_color=color,
                line_id=f"line_{idx}",
                label=f"L{idx}"
            )
            counters.append(vc)
        return cls(lines=counters)

    def add_line(self, line_start: Tuple[int, int], line_end: Tuple[int, int]) -> VehicleCounter:
        """Adiciona dinamicamente uma nova linha de contagem à coleção."""
        idx = len(self.lines) + 1
        color = LINE_PALETTE[(idx - 1) % len(LINE_PALETTE)]
        vc = VehicleCounter(
            line_start=line_start,
            line_end=line_end,
            line_color=color,
            line_id=f"line_{idx}",
            label=f"L{idx}"
        )
        self.lines.append(vc)
        return vc

    def update(self, track_id: int, cls_name: str, bbox: List[float]) -> List[Tuple[VehicleCounter, bool]]:
        """
        Atualiza o rastreamento do veículo e testa o cruzamento em relação a cada linha de contagem.
        Retorna lista de tuplas (linha, just_counted) para cada linha cruzada no instante atual.
        """
        if cls_name not in BOTI_CLASSES.values():
            return []

        current_pt = VehicleCounter.get_reference_point(bbox)
        prev_pt = self.previous_positions.get(track_id)
        events = []

        if prev_pt is not None:
            for line in self.lines:
                if line._has_crossed_line(prev_pt, current_pt):
                    # Proteção estrita por linha: conta apenas se ainda não cruzou esta linha
                    if track_id not in line.counted_ids:
                        line.counts[cls_name] += 1
                        line.counted_ids.add(track_id)
                        line.recent_crossings.add(track_id)
                        events.append((line, True))

        # Atualiza a posição histórica para a próxima iteração
        self.previous_positions[track_id] = current_pt
        return events

    def get_total_counts(self) -> Dict[str, int]:
        """Retorna as contagens consolidadas por classe (soma de todas as linhas)."""
        aggregated = {cls_name: 0 for cls_name in BOTI_CLASSES.values()}
        for line in self.lines:
            for cls_name, count in line.counts.items():
                aggregated[cls_name] += count
        return aggregated

    def get_total_count(self) -> int:
        """Retorna o total geral de veículos contabilizados em todas as linhas."""
        return sum(self.get_total_counts().values())

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """
        Renderiza todas as linhas de contagem com suas cores e identificadores,
        além do painel HUD consolidado no canto superior esquerdo.
        """
        annotated = frame.copy()

        # 1. Desenhar cada uma das linhas com sua respectiva cor e identificador
        for line in self.lines:
            cv2.line(
                annotated,
                line.line_start,
                line.line_end,
                line.line_color,
                line.line_thickness,
                cv2.LINE_AA
            )
            cv2.circle(annotated, line.line_start, 5, line.line_color, -1, cv2.LINE_AA)
            cv2.circle(annotated, line.line_end, 5, line.line_color, -1, cv2.LINE_AA)

            # Rótulo compacto da linha: "L1" (ou "L1: 5" quando mais de 1 linha)
            line_total = line.get_total_count()
            tag_text = f"{line.label}: {line_total}" if len(self.lines) > 1 else line.label
            tag_x = max(10, min(annotated.shape[1] - 80, line.line_start[0] + 8))
            tag_y = max(20, min(annotated.shape[0] - 10, line.line_start[1] - 6))

            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), (15, 15, 15), -1)
            cv2.rectangle(annotated, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), line.line_color, 1)
            cv2.putText(
                annotated,
                tag_text,
                (tag_x, tag_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

        # 2. Painel HUD Consolidado no canto superior esquerdo (Soma de Todas as Linhas)
        total_counts = self.get_total_counts()
        items = [
            ("Carro", total_counts.get("car", 0)),
            ("Moto", total_counts.get("motorcycle", 0)),
            ("Onibus", total_counts.get("bus", 0)),
            ("Caminhao", total_counts.get("truck", 0)),
            ("Total", self.get_total_count()),
        ]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.42
        font_thickness = 1
        line_height = 16
        pad_x, pad_y = 8, 6
        panel_x1, panel_y1 = 10, 10

        header_title = f"CONTAGEM TOTAL ({len(self.lines)}L)" if len(self.lines) > 1 else "CONTAGEM TOTAL"
        formatted_lines = [header_title] + [f"{label}: {count}" for label, count in items]

        max_text_w = max(
            cv2.getTextSize(line_str, font, font_scale, font_thickness)[0][0]
            for line_str in formatted_lines
        )
        panel_w = max_text_w + (pad_x * 2)
        panel_h = (len(formatted_lines) * line_height) + (pad_y * 2)
        panel_x2 = panel_x1 + panel_w
        panel_y2 = panel_y1 + panel_h

        # Fundo escuro translúcido (alpha = 0.68)
        overlay = annotated.copy()
        cv2.rectangle(overlay, (panel_x1, panel_y1), (panel_x2, panel_y2), (0, 0, 0), -1)
        alpha = 0.68
        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)
        cv2.rectangle(annotated, (panel_x1, panel_y1), (panel_x2, panel_y2), (70, 70, 70), 1)

        for idx, line_text in enumerate(formatted_lines):
            text_y = panel_y1 + pad_y + ((idx + 1) * line_height) - 4
            color = (0, 220, 255) if idx == 0 else ((0, 255, 180) if "Total" in line_text else (255, 255, 255))
            cv2.putText(
                annotated,
                line_text,
                (panel_x1 + pad_x, text_y),
                font,
                font_scale,
                color,
                font_thickness,
                cv2.LINE_AA,
            )

        return annotated

