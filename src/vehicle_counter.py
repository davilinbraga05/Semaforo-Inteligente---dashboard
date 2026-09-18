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


class VehicleCounter:
    """
    Controlador de contagem veicular baseado em linha virtual.
    
    Principais atribuições:
    - Rastreia o ponto de contato do veículo com a pista (centro inferior da bbox).
    - Detecta a transição efetiva de lado em relação à linha virtual (interseção geométrica).
    - Mantém registro imutável de IDs já contados (garante zero contagem duplicada).
    - Mantém contadores separados para as 4 classes oficiais do BOTI e contador total.
    - Renderiza a linha virtual e um painel de monitoramento no frame de saída.
    """

    def __init__(
        self,
        line_start: Tuple[int, int] = LINE_START,
        line_end: Tuple[int, int] = LINE_END,
        line_color: Tuple[int, int, int] = LINE_COLOR,
        line_thickness: int = LINE_THICKNESS
    ):
        self.line_start = tuple(map(int, line_start))
        self.line_end = tuple(map(int, line_end))
        self.line_color = line_color
        self.line_thickness = line_thickness

        # Posições no frame anterior para cada track_id ativo: {track_id: (x, y)}
        self.previous_positions: Dict[int, Tuple[float, float]] = {}

        # Conjunto de IDs que já cruzaram a linha (nunca são contados novamente)
        self.counted_ids: Set[int] = set()

        # Contadores individuais pelas classes oficiais do BOTI
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
