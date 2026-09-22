import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import cv2
from ultralytics import YOLO

# Garantir que a pasta src esteja no caminho de busca do Python
src_dir = Path(__file__).resolve().parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

# Importar configurações oficiais do BOTI (Classes de Veículos e Cores)
# ATENÇÃO: As definições em config.py são oficiais e definitivas para todo o BOTI.
# Futuras etapas (ROI, PCU, Densidade e Controle Semafórico) devem importar tais configurações.
from config import (
    BOTI_CLASS_IDS,
    BOTI_CLASSES,
    BOTI_CLASS_NAMES_PT,
    BOTI_CLASS_COLORS,
    PERCEPTION_CONFIG,
    LINE_START,
    LINE_END
)
from vehicle_counter import VehicleCounter, MultiLineVehicleCounter, LINE_PALETTE
from auto_line import AutoLineDetector

def get_model_class_mapping(model_names: Dict[int, str]) -> Dict[int, str]:
    """
    Mapeia dinamicamente os IDs de classe do modelo (COCO oficial ou modelo customizado)
    para as 4 classes canônicas do BOTI: 'car', 'motorcycle', 'bus', 'truck'.

    Suporta variações de nomes em inglês e português:
    - car / carro / automovel / auto / veiculo -> 'car'
    - motorcycle / moto / motocicleta / motorbike -> 'motorcycle'
    - bus / onibus / ônibus / autobus -> 'bus'
    - truck / caminhao / caminhão -> 'truck'
    """
    CLASS_ALIASES = {
        "car": {"car", "carro", "cars", "automobile", "auto", "veiculo", "veiculo_leve"},
        "motorcycle": {"motorcycle", "moto", "motocicleta", "motorbike", "motos", "motorcycles"},
        "bus": {"bus", "onibus", "ônibus", "buses", "autobus"},
        "truck": {"truck", "caminhao", "caminhão", "trucks", "caminhoes", "caminhões"}
    }

    mapping: Dict[int, str] = {}
    for cid, raw_name in model_names.items():
        clean_name = str(raw_name).strip().lower()
        for canonical, aliases in CLASS_ALIASES.items():
            if clean_name in aliases:
                mapping[int(cid)] = canonical
                break

    # Fallback seguro: se o modelo utilizar IDs COCO numéricos sem nomes compatíveis
    if not mapping:
        mapping = {cid: name for cid, name in BOTI_CLASSES.items() if cid in model_names}

    return mapping

# Garantir suporte a UTF-8 no stdout (evita falhas de encoding no terminal Windows)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")

WINDOW_NAME = "Percepção e Contagem de Veículos"

def select_lines_interactively(initial_frame, window_name=WINDOW_NAME, initial_lines=None):
    """
    Permite ao usuário definir interativamente de 1 a N linhas virtuais de contagem com o mouse
    sobre o primeiro quadro do vídeo antes do início do processamento.

    Controles:
    - Botão esquerdo pressionado + arrastar: define o segmento da linha ativa.
    - [N]: confirma a linha ativa e inicia uma NOVA linha (L2, L3, ...).
    - [ENTER] ou [ESPAÇO]: confirma todas as linhas válidas e inicia o processamento.
    - [R]: redefine/limpa somente a linha ativa.
    - [Z] ou [BACKSPACE]: desfaz a última linha confirmada e restaura para edição.
    - [Q] ou [ESC]: cancela e encerra a execução.
    """
    h, w = initial_frame.shape[:2]
    confirmed_lines: List[Tuple[Tuple[int, int], Tuple[int, int]]] = list(initial_lines) if initial_lines else []
    
    drawing = False
    pt_start = None
    pt_current = None
    active_start = None
    active_end = None
    warning_message = ""
    warning_frames = 0

    def mouse_callback(event, x, y, flags, param):
        nonlocal drawing, pt_start, pt_current, active_start, active_end, warning_message, warning_frames
        clamped_x = max(0, min(w - 1, int(x)))
        clamped_y = max(0, min(h - 1, int(y)))

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            pt_start = (clamped_x, clamped_y)
            pt_current = (clamped_x, clamped_y)
            active_start = None
            active_end = None
            warning_message = ""
            warning_frames = 0

        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing:
                pt_current = (clamped_x, clamped_y)

        elif event == cv2.EVENT_LBUTTONUP:
            if drawing:
                drawing = False
                pt_end = (clamped_x, clamped_y)
                dist = ((pt_end[0] - pt_start[0]) ** 2 + (pt_end[1] - pt_start[1]) ** 2) ** 0.5
                if dist >= 10.0:
                    active_start = pt_start
                    active_end = pt_end
                else:
                    active_start = None
                    active_end = None
                    warning_message = "Distancia muito curta! Arraste o mouse para tracar a linha."
                    warning_frames = 45

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, mouse_callback)

    while True:
        display_frame = initial_frame.copy()
        active_idx = len(confirmed_lines) + 1
        active_color = LINE_PALETTE[(active_idx - 1) % len(LINE_PALETTE)]

        # 1. Desenhar todas as linhas já confirmadas
        for idx, (c_start, c_end) in enumerate(confirmed_lines, start=1):
            c_color = LINE_PALETTE[(idx - 1) % len(LINE_PALETTE)]
            cv2.line(display_frame, c_start, c_end, c_color, 3, cv2.LINE_AA)
            cv2.circle(display_frame, c_start, 5, c_color, -1, cv2.LINE_AA)
            cv2.circle(display_frame, c_end, 5, c_color, -1, cv2.LINE_AA)

            tag_text = f"L{idx}"
            tag_x = max(10, min(w - 50, c_start[0] + 8))
            tag_y = max(20, min(h - 10, c_start[1] - 6))
            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(display_frame, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), (15, 15, 15), -1)
            cv2.rectangle(display_frame, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), c_color, 1)
            cv2.putText(display_frame, tag_text, (tag_x, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 2. Desenhar a linha ativa (em arrasto ou recém-posicionada)
        if drawing and pt_start and pt_current:
            cv2.line(display_frame, pt_start, pt_current, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(display_frame, pt_start, 5, (0, 255, 0), -1, cv2.LINE_AA)
            cv2.circle(display_frame, pt_current, 5, (0, 255, 255), -1, cv2.LINE_AA)
            tooltip = f"L{active_idx}: ({pt_current[0]}, {pt_current[1]})"
            tt_x = min(w - 110, pt_current[0] + 12)
            tt_y = max(20, pt_current[1] - 8)
            cv2.putText(display_frame, tooltip, (tt_x, tt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        elif active_start and active_end:
            cv2.line(display_frame, active_start, active_end, active_color, 3, cv2.LINE_AA)
            cv2.circle(display_frame, active_start, 6, active_color, -1, cv2.LINE_AA)
            cv2.circle(display_frame, active_end, 6, active_color, -1, cv2.LINE_AA)

            tag_text = f"L{active_idx} (ativa)"
            tag_x = max(10, min(w - 90, active_start[0] + 8))
            tag_y = max(20, min(h - 10, active_start[1] - 6))
            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(display_frame, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), (15, 15, 15), -1)
            cv2.rectangle(display_frame, (tag_x - 3, tag_y - th - 3), (tag_x + tw + 3, tag_y + 3), (0, 255, 255), 1)
            cv2.putText(display_frame, tag_text, (tag_x, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Painel HUD discreto e responsivo no canto superior esquerdo
        margin_x = max(10, int(w * 0.02))
        margin_y = max(10, int(h * 0.02))

        if warning_frames > 0 and warning_message:
            warning_frames -= 1
            title_text = "Aviso"
            sub_text = warning_message
            title_color = (0, 160, 255)
            sub_color = (240, 240, 240)
        elif active_start and active_end:
            title_text = f"Linha L{active_idx} definida | Criadas: {len(confirmed_lines)}"
            sub_text = "[N] Nova linha  |  [ENTER] Iniciar  |  [R] Redesenhar"
            title_color = (0, 255, 180)
            sub_color = (220, 220, 220)
        elif drawing:
            title_text = f"Desenhando linha L{active_idx}"
            sub_text = "Solte o botao para fixar a linha"
            title_color = (255, 255, 255)
            sub_color = (200, 200, 200)
        else:
            if len(confirmed_lines) == 0:
                title_text = "Defina a linha de contagem (L1)"
                sub_text = "Clique e arraste para posicionar  |  [ENTER] Iniciar"
            else:
                title_text = f"Linha ativa: L{active_idx}  |  Criadas: {len(confirmed_lines)}"
                sub_text = "Arraste para desenhar  |  [ENTER] Iniciar  |  [Z] Desfazer"
            title_color = (255, 255, 255)
            sub_color = (200, 200, 200)

        # Escalas de fonte responsivas calculadas de acordo com a resolução
        base_scale = max(0.38, min(0.58, w / 1600.0))
        title_scale = base_scale * 1.05
        sub_scale = base_scale * 0.88

        # Garantir que o texto nunca ultrapasse os limites da tela
        max_allowed_w = w - (margin_x * 2) - 24
        while max_allowed_w > 80:
            (t_w, t_h), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, title_scale, 1)
            (s_w, s_h), _ = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, sub_scale, 1)
            if max(t_w, s_w) <= max_allowed_w or title_scale <= 0.28:
                break
            title_scale *= 0.92
            sub_scale *= 0.92

        (t_w, t_h), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, title_scale, 1)
        (s_w, s_h), _ = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, sub_scale, 1)

        pad_x = max(10, int(w * 0.015))
        pad_y = max(7, int(h * 0.015))
        spacing = max(5, int(h * 0.01))

        panel_w = max(t_w, s_w) + (2 * pad_x)
        panel_h = t_h + s_h + (2 * pad_y) + spacing

        p_x1 = margin_x
        p_y1 = margin_y
        p_x2 = min(w - margin_x, p_x1 + panel_w)
        p_y2 = min(h - margin_y, p_y1 + panel_h)

        overlay = display_frame.copy()
        cv2.rectangle(overlay, (p_x1, p_y1), (p_x2, p_y2), (18, 20, 24), -1)
        cv2.rectangle(overlay, (p_x1, p_y1), (p_x2, p_y2), (70, 75, 85), 1)
        cv2.addWeighted(overlay, 0.80, display_frame, 0.20, 0, display_frame)

        title_baseline = p_y1 + pad_y + t_h
        sub_baseline = title_baseline + spacing + s_h
        cv2.putText(display_frame, title_text, (p_x1 + pad_x, title_baseline),
                    cv2.FONT_HERSHEY_SIMPLEX, title_scale, title_color, 1, cv2.LINE_AA)
        cv2.putText(display_frame, sub_text, (p_x1 + pad_x, sub_baseline),
                    cv2.FONT_HERSHEY_SIMPLEX, sub_scale, sub_color, 1, cv2.LINE_AA)

        cv2.imshow(window_name, display_frame)
        key = cv2.waitKey(20) & 0xFF

        # Sair: Q ou ESC
        if key in (ord('q'), ord('Q'), 27):
            return None

        # Nova linha: N
        elif key in (ord('n'), ord('N')):
            if active_start is not None and active_end is not None:
                confirmed_lines.append((active_start, active_end))
                active_start = None
                active_end = None
                pt_start = None
                pt_current = None
                drawing = False
                warning_message = f"L{len(confirmed_lines)} criada com sucesso! Desenhe L{len(confirmed_lines)+1}."
                warning_frames = 35
            else:
                warning_message = "Defina a linha atual antes de criar outra."
                warning_frames = 45

        # Confirmar e iniciar: ENTER ou ESPACO
        elif key in (13, 10, 32):
            if active_start is not None and active_end is not None:
                confirmed_lines.append((active_start, active_end))
                active_start = None
                active_end = None

            if len(confirmed_lines) > 0:
                return confirmed_lines
            else:
                warning_message = "Defina ao menos uma linha antes de iniciar!"
                warning_frames = 45

        # Redefinir somente a linha ativa: R
        elif key in (ord('r'), ord('R')):
            active_start = None
            active_end = None
            pt_start = None
            pt_current = None
            drawing = False
            warning_message = f"Linha L{active_idx} limpa. Arraste novamente."
            warning_frames = 35

        # Desfazer última linha: Z ou BACKSPACE
        elif key in (ord('z'), ord('Z'), 8):
            if active_start is not None and active_end is not None:
                active_start = None
                active_end = None
                warning_message = f"Linha ativa L{active_idx} descartada."
                warning_frames = 35
            elif len(confirmed_lines) > 0:
                active_start, active_end = confirmed_lines.pop()
                warning_message = f"L{len(confirmed_lines)+1} restaurada para edicao."
                warning_frames = 35
            else:
                warning_message = "Nenhuma linha para desfazer."
                warning_frames = 35


def select_line_interactively(initial_frame, window_name=WINDOW_NAME, initial_line=None):
    """
    Função legada para seleção de uma única linha.
    Mantida para compatibilidade direta.
    """
    initial_lines = [initial_line] if initial_line else None
    lines = select_lines_interactively(initial_frame, window_name, initial_lines)
    if lines and len(lines) > 0:
        return lines[0]
    return None, None

def draw_tracking_annotations(frame, results, model_names, class_mapping):
    """
    Desenha as caixas delimitadoras e os rótulos de rastreamento EXCLUSIVAMENTE para as
    classes oficiais de veículos do BOTI no formato:
    ID: <track_id> | <classe> | <confiança>%
    """
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return frame

    annotated_frame = frame.copy()

    for i, box in enumerate(boxes):
        cls_id = int(box.cls[0])
        
        # Filtro estrito: apenas classes mapeadas para o BOTI
        if cls_id not in class_mapping:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

        # Obter ID de tracking persistente fornecido pelo ByteTrack
        if boxes.id is not None and len(boxes.id) > i:
            track_id = int(boxes.id[i])
            id_str = f"ID: {track_id}"
        else:
            id_str = "ID: N/A"

        canonical_cls = class_mapping[cls_id]
        raw_name = model_names.get(cls_id, canonical_cls)
        conf = float(box.conf[0])

        # Formato visual: ID: 15 | car | 87% (exibe o nome retornado pelo modelo)
        label = f"{id_str} | {raw_name} | {int(conf * 100)}%"

        # Obter cor configurada oficialmente para a classe canônica
        color = BOTI_CLASS_COLORS.get(canonical_cls, (0, 255, 0))

        # Desenhar retângulo da bounding box
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

        # Configurar retângulo de fundo para o texto (garante legibilidade)
        font_scale = 0.55
        thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

        bg_y1 = max(0, y1 - text_h - 8)
        bg_y2 = y1

        cv2.rectangle(
            annotated_frame,
            (x1, bg_y1),
            (x1 + text_w + 8, bg_y2),
            color,
            -1
        )

        # Desenhar texto legível em branco sobre o fundo colorido
        cv2.putText(
            annotated_frame,
            label,
            (x1 + 4, max(text_h + 2, bg_y2 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )

    return annotated_frame

def main():
    parser = argparse.ArgumentParser(description="Rastreamento de veículos com YOLO26s e ByteTrack (BOTI).")
    parser.add_argument(
        "-i", "--input", 
        type=str, 
        default=None, 
        help="Caminho para o vídeo de entrada. Se omitido, busca automaticamente na pasta media/inputs/"
    )
    parser.add_argument(
        "-c", "--conf", 
        type=float, 
        default=PERCEPTION_CONFIG["conf"], 
        help=f"Limiar de confiança para detecção (padrão: {PERCEPTION_CONFIG['conf']})"
    )
    parser.add_argument(
        "--imgsz", "--img-size",
        type=int,
        default=PERCEPTION_CONFIG["imgsz"],
        help=f"Tamanho da imagem para inferência (padrão: {PERCEPTION_CONFIG['imgsz']})"
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Não exibir a janela do vídeo em tempo real (útil para execuções sem GUI/segundo plano)."
    )
    parser.add_argument(
        "--line-start",
        type=int,
        nargs=2,
        default=None,
        help="Coordenadas X Y de início da linha virtual. Se omitido, permite desenhar interativamente com o mouse."
    )
    parser.add_argument(
        "--line-end",
        type=int,
        nargs=2,
        default=None,
        help="Coordenadas X Y de fim da linha virtual. Se omitido, permite desenhar interativamente com o mouse."
    )
    parser.add_argument(
        "--auto-line",
        action="store_true",
        help="Utilizar calibração automática da linha (AutoLineDetector) em vez do desenho manual com o mouse."
    )
    parser.add_argument(
        "--calib-frames",
        type=int,
        default=75,
        help="Quantidade de quadros iniciais para calibração automática da linha (padrão: 75)."
    )
    
    args = parser.parse_args()

    # Definir diretórios base do projeto
    base_dir = Path(__file__).resolve().parent.parent
    
    # Modelo oficial do projeto: YOLO26s (configuração centralizada)
    model_path = base_dir / PERCEPTION_CONFIG["model_path"]
            
    inputs_dir = base_dir / "media" / "inputs"
    outputs_dir = base_dir / "media" / "outputs"

    outputs_dir.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Verificar se o arquivo do modelo existe; se não, obter via Ultralytics
    if not model_path.exists():
        print(f"🔄 Modelo '{model_path.name}' não foi encontrado em {model_path.parent}. Efetuando download oficial...")
        try:
            downloaded = YOLO("yolo26s.pt")
            root_dl = base_dir / "yolo26s.pt"
            if root_dl.exists() and root_dl != model_path:
                root_dl.rename(model_path)
        except Exception as e:
            print(f"❌ Erro ao obter o modelo '{model_path}': {e}")
            sys.exit(1)

    # Selecionar vídeo de entrada
    if args.input:
        video_path = Path(args.input)
    else:
        valid_extensions = ("*.mp4", "*.avi", "*.mov", "*.mkv")
        found_videos = []
        for ext in valid_extensions:
            found_videos.extend(inputs_dir.glob(ext))
            found_videos.extend(inputs_dir.glob(ext.upper()))

        if not found_videos:
            print(f"❌ Erro: Nenhum vídeo encontrado na pasta: {inputs_dir}")
            print("💡 Adicione um vídeo (.mp4, .avi, etc.) em 'media/inputs/' ou especifique via '--input caminho/video.mp4'.")
            sys.exit(1)

        video_path = found_videos[0]
        print(f"🔍 Vídeo selecionado automaticamente: {video_path.name}")

    if not video_path.exists():
        print(f"❌ Erro: O arquivo de vídeo especificado não existe: {video_path}")
        sys.exit(1)

    # Inicializar a captura de vídeo com OpenCV
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ Erro: Não foi possível abrir o vídeo: {video_path}")
        sys.exit(1)

    # Obter propriedades do vídeo de entrada
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps != fps: # tratar NaN ou FPS zero
        fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Configurar salvamento do vídeo de saída
    output_filename = f"output_{video_path.name}"
    output_path = outputs_dir / output_filename

    # Utilizar codec mp4v para saída em MP4
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    # Carregar o modelo oficial YOLO26s do projeto
    print(f"Carregando modelo YOLO26s: {model_path}")
    model = YOLO(str(model_path))

    # Classes de veículos utilizadas pelo projeto (COCO)
    # 2 = car | 3 = motorcycle | 5 = bus | 7 = truck
    active_class_ids = [2, 3, 5, 7]

    class_mapping = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    print("Classes utilizadas: car, motorcycle, bus, truck")

    # Determinar modo de definição da linha
    auto_detector = None
    counter = None
    line_mode_label = ""
    show_gui = not args.no_show

    if args.line_start is not None and args.line_end is not None:
        # 1. Modo Manual via argumentos CLI
        line_mode_label = "Manual (CLI)"
        line_start = tuple(args.line_start)
        line_end = tuple(args.line_end)
        counter = MultiLineVehicleCounter.from_segments([(line_start, line_end)])
        print(f"📏 Linha Virtual de Contagem (Manual CLI): {line_start} -> {line_end}")

    elif args.auto_line or (not show_gui and (args.line_start is None or args.line_end is None)):
        # 2. Modo de Auto-Calibração com AutoLineDetector
        line_mode_label = "Automática (AutoLineDetector)"
        print("⚙️ Modo de AUTO-CALIBRAÇÃO ativado.")
        print(f"🔬 Amostrando trajetórias nos primeiros {args.calib_frames} frames do vídeo...")
        auto_detector = AutoLineDetector(
            calibration_frames=args.calib_frames,
            frame_width=width,
            frame_height=height
        )

    else:
        # 3. Modo Manual Interativo com o MOUSE diretamente no vídeo (1 a N linhas)
        line_mode_label = "Manual (Desenhada com Mouse)"
        print("🖱️ Modo de DEFINIÇÃO MANUAL DE LINHAS com o MOUSE ativado.")
        print("💡 Janela de vídeo aberta: clique e arraste para desenhar cada linha.")
        print("💡 Controles: [N] Nova linha  |  [ENTER / ESPAÇO] Iniciar  |  [R] Redesenhar ativa  |  [Z] Desfazer  |  [Q / ESC] Sair\n")

        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            print("❌ Erro ao carregar o primeiro quadro do vídeo.")
            sys.exit(1)

        drawn_lines = select_lines_interactively(first_frame, WINDOW_NAME)
        if not drawn_lines:
            print("🛑 Processamento cancelado pelo usuário durante a definição das linhas.")
            cap.release()
            out.release()
            cv2.destroyAllWindows()
            sys.exit(0)

        # Instanciação direta do MultiLineVehicleCounter com as coordenadas reais do mouse
        counter = MultiLineVehicleCounter.from_segments(drawn_lines)
        line_info = ", ".join([f"{l.label}: {l.line_start}->{l.line_end}" for l in counter.lines])
        print(f"📏 Linhas Virtuais de Contagem ({len(counter.lines)}): {line_info}")

        # Reiniciar o vídeo para o frame 0 garantindo contagem e gravação desde o início
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != 0:
            cap.release()
            cap = cv2.VideoCapture(str(video_path))

    print(f"🎬 Iniciando rastreamento ByteTrack e contagem no vídeo: {video_path.name}")
    print(f"🎯 Classes Filtradas na Inferência: {active_class_ids}")
    print(f"📐 Resolução: {width}x{height} | FPS: {fps:.1f} | Total de Frames: {total_frames}")
    if show_gui:
        print("💡 Pressione 'q' ou 'ESC' para sair | Pressione 'r' para redefinir as linhas.\n")

    frame_count = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # Executar rastreamento com ByteTrack filtrado pelas classes mapeadas
            results = model.track(
                frame,
                tracker=PERCEPTION_CONFIG["tracker"],
                persist=PERCEPTION_CONFIG["persist"],
                conf=args.conf,
                imgsz=args.imgsz,
                classes=active_class_ids,
                verbose=False
            )

            boxes = results[0].boxes

            # Verificar se estamos na fase de calibração automática
            if auto_detector is not None and auto_detector.is_calibrating():
                # 1. Coleta de trajetórias durante a calibração
                if boxes is not None and boxes.id is not None:
                    for i, box in enumerate(boxes):
                        cls_id = int(box.cls[0])
                        if cls_id not in class_mapping:
                            continue
                        if len(boxes.id) > i:
                            track_id = int(boxes.id[i])
                            bbox = list(map(float, box.xyxy[0].tolist()))
                            auto_detector.update_track(track_id, bbox)

                # Avançar o relógio de calibração
                calibrated_now = auto_detector.step()
                if calibrated_now:
                    calib_start, calib_end = auto_detector.calibrate()
                    counter = MultiLineVehicleCounter.from_segments([(calib_start, calib_end)])
                    # Semear últimas posições conhecidas para transição contínua
                    counter.previous_positions = auto_detector.get_last_positions()
                    print(f"🚦 [AUTO-CALIBRAÇÃO] Linha calibrada com sucesso: {calib_start} -> {calib_end}")
                    print(f"🏁 Iniciando contagem veicular a partir do frame {frame_count}!\n")

                # Desenhar anotações das caixas delimitadoras e o aviso visual de calibração
                annotated_frame = draw_tracking_annotations(frame, results, model.names, class_mapping)
                annotated_frame = auto_detector.draw_calibration_notice(annotated_frame)

            else:
                # 2. Fase de contagem ativa de veículos
                if counter is None and auto_detector is not None:
                    # Garantir que counter exista se a calibração foi concluída
                    calib_start, calib_end = auto_detector.calibrate()
                    counter = MultiLineVehicleCounter.from_segments([(calib_start, calib_end)])
                    counter.previous_positions = auto_detector.get_last_positions()

                if boxes is not None and boxes.id is not None and counter is not None:
                    for i, box in enumerate(boxes):
                        cls_id = int(box.cls[0])
                        if cls_id not in class_mapping:
                            continue
                        if len(boxes.id) > i:
                            track_id = int(boxes.id[i])
                            canonical_cls = class_mapping[cls_id]
                            bbox = list(map(float, box.xyxy[0].tolist()))
                            events = counter.update(track_id, canonical_cls, bbox)
                            for line, just_counted in events:
                                if just_counted:
                                    pt_name = BOTI_CLASS_NAMES_PT.get(canonical_cls, canonical_cls)
                                    print(f"🚦 [CONTAGEM - {line.label}] {pt_name} (ID: {track_id}) cruzou a linha! Total Linha: {line.get_total_count()} | Total Geral: {counter.get_total_count()}")

                # Desenhar bounding boxes com o rótulo formatado (ID: <track_id> | <classe> | <conf>%)
                annotated_frame = draw_tracking_annotations(frame, results, model.names, class_mapping)

                # Desenhar as linhas virtuais e o painel de contagem sobreposto
                if counter is not None:
                    annotated_frame = counter.draw(annotated_frame)

            # Gravar o frame anotado no vídeo de saída
            out.write(annotated_frame)

            # Exibir o frame na tela (se habilitado)
            if show_gui:
                try:
                    cv2.imshow(WINDOW_NAME, annotated_frame)
                    key = cv2.waitKey(1) & 0xFF

                    # Tecla Q ou ESC para interromper
                    if key in (ord('q'), ord('Q'), 27):
                        print("\n⏹️ Processamento interrompido pelo usuário ('q' / ESC).")
                        break

                    # Tecla R para redefinir/redesenhar as linhas interativamente em tempo de execução
                    elif key in (ord('r'), ord('R')) and counter is not None:
                        print("\n⏸️ Vídeo pausado para redefinição das linhas de contagem com o mouse.")
                        current_segments = [(l.line_start, l.line_end) for l in counter.lines]
                        new_lines = select_lines_interactively(
                            frame,
                            WINDOW_NAME,
                            initial_lines=current_segments
                        )
                        if new_lines and len(new_lines) > 0:
                            new_counter = MultiLineVehicleCounter.from_segments(new_lines)
                            new_counter.previous_positions = counter.previous_positions
                            counter = new_counter
                            line_mode_label = "Manual (Redefinida com Mouse)"
                            line_info = ", ".join([f"{l.label}: {l.line_start}->{l.line_end}" for l in counter.lines])
                            print(f"🔄 Linhas Virtuais Redefinidas ({len(counter.lines)}): {line_info}")
                        else:
                            print("ℹ️ Redefinição cancelada. Mantendo linhas anteriores.")
                except cv2.error:
                    show_gui = False
                    print("⚠️ Interface gráfica indisponível. Continuando processamento em segundo plano...")

            # Atualizar progresso no terminal
            if total_frames > 0 and frame_count % 30 == 0:
                progress = (frame_count / total_frames) * 100
                current_total = counter.get_total_count() if counter is not None else 0
                phase_label = "Calibrando" if (auto_detector and auto_detector.is_calibrating()) else "Contando"
                print(f"⏳ Processando: Frame {frame_count}/{total_frames} ({progress:.1f}%) | Fase: {phase_label} | Total Contado: {current_total}")
    finally:
        # Liberação dos recursos de vídeo e janelas
        cap.release()
        out.release()
        if show_gui:
            cv2.destroyAllWindows()

    # Garantir que counter esteja instanciado para o relatório final
    if counter is None:
        if auto_detector is not None:
            calib_start, calib_end = auto_detector.calibrate()
            counter = MultiLineVehicleCounter.from_segments([(calib_start, calib_end)])
        else:
            counter = MultiLineVehicleCounter.from_segments([(LINE_START, LINE_END)])

    print(f"\n✅ Processamento e Contagem Concluídos!")
    print(f"📹 Vídeo anotado salvo com sucesso em: {output_path}")
    print("\n" + "="*45)
    print("📊 RELATÓRIO OFICIAL DE CONTAGEM (BOTI)")
    print("="*45)
    print(f"  • Modo da Linha: {line_mode_label}")
    print(f"  • Total de Linhas: {len(counter.lines)}")
    for line in counter.lines:
        print(f"  • {line.label} ({line.line_id}): {line.line_start} -> {line.line_end} | Total: {line.get_total_count()}")
    if auto_detector is not None and auto_detector.flow_direction is not None:
        print(f"  • Fluxo Predominante: {auto_detector.flow_direction.upper()}")
    print("-" * 45)
    print("  • CONTAGEM TOTAL POR CLASSE (CONSOLIDADA):")
    total_by_class = counter.get_total_counts()
    for cls_key in ["car", "motorcycle", "bus", "truck"]:
        pt_name = BOTI_CLASS_NAMES_PT.get(cls_key, cls_key)
        print(f"    - {pt_name}: {total_by_class.get(cls_key, 0)}")
    print("-" * 45)
    print(f"  🏆 TOTAL DE VEÍCULOS (TRAVESSIAS): {counter.get_total_count()}")
    print("="*45 + "\n")


if __name__ == "__main__":
    main()