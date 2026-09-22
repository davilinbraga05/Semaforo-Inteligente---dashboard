"""
BOTI - Bot de Otimização de Tráfego Inteligente
Arquivo Central de Configurações Oficiais do Projeto.

===========================================================
CONGELAMENTO DA CAMADA DE PERCEPÇÃO
===========================================================
Este arquivo define as categorias oficiais de veículos e os parâmetros
de inferência do BOTI. 

Todas as futuras etapas do projeto (ROI, PCU, Densidade, Máquina de Estados,
Contagem e Semáforo) devem importar suas configurações exclusivamente deste arquivo.
"""

from typing import Dict, List

# COCO Dataset IDs das únicas classes oficiais de veículos para o trânsito urbano:
# 2 -> car (carro)
# 3 -> motorcycle (motocicleta)
# 5 -> bus (ônibus)
# 7 -> truck (caminhão)
BOTI_CLASS_IDS: List[int] = [2, 3, 5, 7]

# Mapeamento Oficial de Classes do BOTI (ID COCO -> Nome Oficial)
BOTI_CLASSES: Dict[int, str] = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Nomes amigáveis para exibição em relatórios e interface
BOTI_CLASS_NAMES_PT: Dict[str, str] = {
    "car": "Carro",
    "motorcycle": "Motocicleta",
    "bus": "Ônibus",
    "truck": "Caminhão"
}

# Fatores PCU (Passenger Car Unit) padronizados para etapas futuras
BOTI_PCU_FACTORS: Dict[str, float] = {
    "motorcycle": 0.5,
    "car": 1.0,
    "truck": 1.5,
    "bus": 2.0
}

# Paleta de Cores BGR para renderização gráfica das Bounding Boxes por classe
BOTI_CLASS_COLORS: Dict[str, tuple] = {
    "car": (0, 255, 0),          # Verde
    "bus": (0, 165, 255),        # Laranja
    "truck": (255, 191, 0),      # Azul Claro / Ciano
    "motorcycle": (255, 0, 255)  # Magenta
}

# Parâmetros padrão da camada de percepção (congelada)
PERCEPTION_CONFIG = {
    "model_path": "models/yolo26s.pt",
    "imgsz": 640,
    "conf": 0.25,
    "tracker": "bytetrack.yaml",
    "persist": True
}

# ===========================================================
# CONFIGURAÇÃO DA LINHA VIRTUAL DE CONTAGEM (MÓDULO DE CONTAGEM)
# ===========================================================
# Coordenadas (x, y) definindo o início e o fim da linha virtual
# Adaptável à resolução do fluxo de vídeo analisado
LINE_START: tuple = (50, 340)
LINE_END: tuple = (850, 340)

# Parâmetros visuais da linha virtual
LINE_COLOR: tuple = (0, 0, 255)       # Vermelho vibrante (BGR)
LINE_THICKNESS: int = 3

