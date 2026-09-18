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
from vehicle_counter import VehicleCounter
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

WINDOW_NAME = "BOTI - Percepção e Contagem de Veículos"

def select_line_interactively(initial_frame, window_name=WINDOW_NAME, initial_line=None):
    """
    Permite ao usuário desenhar manualmente a linha virtual de contagem com o mouse
    diretamente sobre o primeiro quadro do vídeo antes do início do processamento.

    Controles:
    - Botão esquerdo pressionado + arrastar: define o segmento da linha virtual.
    - [ENTER] ou [ESPAÇO]: confirma a linha e inicia a contagem.
    - [R]: limpa a linha e permite redesenhar.
    - [Q] ou [ESC]: cancela e encerra a execução.
    """
    h, w = initial_frame.shape[:2]
    drawing = False
    pt_start = None
    pt_current = None
    line_start = tuple(map(int, initial_line[0])) if initial_line else None
    line_end = tuple(map(int, initial_line[1])) if initial_line else None
    warning_message = ""
    warning_frames = 0

    def mouse_callback(event, x, y, flags, param):
        nonlocal drawing, pt_start, pt_current, line_start, line_end, warning_message, warning_frames
        clamped_x = max(0, min(w - 1, int(x)))
        clamped_y = max(0, min(h - 1, int(y)))

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            pt_start = (clamped_x, clamped_y)
            pt_current = (clamped_x, clamped_y)
            line_start = None
            line_end = None
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
                    line_start = pt_start
                    line_end = pt_end
                else:
                    line_start = None
                    line_end = None
                    warning_message = "Distância muito curta! Arraste o mouse para traçar a linha."
                    warning_frames = 45

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, mouse_callback)

    while True:
        display_frame = initial_frame.copy()

        # 1. Desenhar a linha enquanto o usuário está arrastando o mouse
        if drawing and pt_start and pt_current:
            cv2.line(display_frame, pt_start, pt_current, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(display_frame, pt_start, 5, (0, 255, 0), -1, cv2.LINE_AA)
            cv2.circle(display_frame, pt_current, 5, (0, 255, 255), -1, cv2.LINE_AA)
            tooltip = f"({pt_current[0]}, {pt_current[1]})"
            tt_x = min(w - 90, pt_current[0] + 12)
            tt_y = max(20, pt_current[1] - 8)
            cv2.putText(display_frame, tooltip, (tt_x, tt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        # 2. Desenhar a linha confirmada pelo término do arrasto
        elif line_start and line_end:
            cv2.line(display_frame, line_start, line_end, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.circle(display_frame, line_start, 6, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(display_frame, line_end, 6, (0, 0, 255), -1, cv2.LINE_AA)

            cv2.putText(display_frame, f"A: {line_start}", (line_start[0] + 8, max(20, line_start[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)
            cv2.putText(display_frame, f"B: {line_end}", (line_end[0] + 8, max(20, line_end[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)

            mid_x = (line_start[0] + line_end[0]) // 2
            mid_y = (line_start[1] + line_end[1]) // 2
            cv2.putText(display_frame, "LINHA DE CONTAGEM", (mid_x + 10, max(20, mid_y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)

        # 3. Desenhar banner HUD com instruções no topo
        banner_w = min(w - 40, 680)
        banner_h = 74
        banner_x1 = max(10, (w - banner_w) // 2)
        banner_y1 = 15
        banner_x2 = banner_x1 + banner_w
        banner_y2 = banner_y1 + banner_h

        overlay = display_frame.copy()
        cv2.rectangle(overlay, (banner_x1, banner_y1), (banner_x2, banner_y2), (20, 20, 20), -1)
        cv2.rectangle(overlay, (banner_x1, banner_y1), (banner_x2, banner_y2), (0, 190, 255), 1)
        cv2.addWeighted(overlay, 0.82, display_frame, 0.18, 0, display_frame)

        cv2.putText(display_frame, "BOTI - DEFINICAO MANUAL DA LINHA DE CONTAGEM",
                    (banner_x1 + 18, banner_y1 + 24),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        if warning_frames > 0 and warning_message:
            warning_frames -= 1
            cv2.putText(display_frame, f"Aviso: {warning_message}",
                        (banner_x1 + 18, banner_y1 + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 140, 255), 1, cv2.LINE_AA)
        elif line_start and line_end:
            cv2.putText(display_frame, f"Linha: {line_start} -> {line_end}  |  [ENTER/ESPACO] Iniciar  |  [R] Redesenhar  |  [Q/ESC] Sair",
                        (banner_x1 + 18, banner_y1 + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.43, (0, 255, 180), 1, cv2.LINE_AA)
        elif drawing:
            cv2.putText(display_frame, "Solte o botao esquerdo para fixar os pontos da linha virtual.",
                        (banner_x1 + 18, banner_y1 + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1, cv2.LINE_AA)
        else:
            cv2.putText(display_frame, "Clique com botao esquerdo e arraste para desenhar  |  [Q/ESC] Sair",
                        (banner_x1 + 18, banner_y1 + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)

        cv2.imshow(window_name, display_frame)
        key = cv2.waitKey(20) & 0xFF

        # Sair: Q ou ESC
        if key in (ord('q'), ord('Q'), 27):
            return None, None

        # Redesenhar / Limpar: R
        elif key in (ord('r'), ord('R')):
            line_start = None
            line_end = None
            pt_start = None
            pt_current = None
            drawing = False
            warning_message = "Linha limpa. Clique e arraste para desenhar novamente."
            warning_frames = 35

        # Confirmar: ENTER (13 ou 10) ou ESPAÇO (32)
        elif key in (13, 10, 32):
            if line_start is not None and line_end is not None:
                return line_start, line_end
            else:
                warning_message = "Desenhe a linha com o mouse antes de confirmar!"
                warning_frames = 50

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
    parser = argparse.ArgumentParser(description="Rastreamento de veículos com YOLOv8 e ByteTrack (BOTI).")
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
    
    # Modelo oficial do projeto: YOLOv8n
    model_path = base_dir / "models" / "yolov8n.pt"
            
    inputs_dir = base_dir / "media" / "inputs"
    outputs_dir = base_dir / "media" / "outputs"

    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Verificar se o arquivo do modelo existe
    if not model_path.exists():
        print(f"❌ Erro: O modelo '{model_path}' não foi encontrado.")
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

    # Carregar o modelo oficial YOLOv8n do projeto
    model_path = Path("models/yolov8n.pt")

    print(f"Carregando modelo YOLOv8n: {model_path}")
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
        counter = VehicleCounter(line_start=line_start, line_end=line_end)
        print(f"📏 Linha Virtual de Contagem (Manual CLI): {counter.line_start} -> {counter.line_end}")

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
        # 3. Modo Manual Interativo com o MOUSE diretamente no vídeo
        line_mode_label = "Manual (Desenhada com Mouse)"
        print("🖱️ Modo de DEFINIÇÃO MANUAL DA LINHA com o MOUSE ativado.")
        print("💡 Janela de vídeo aberta: clique com o botão esquerdo e arraste para desenhar a linha.")
        print("💡 Controles: [ENTER / ESPAÇO] Confirmar  |  [R] Redesenhar  |  [Q / ESC] Sair\n")

        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            print("❌ Erro ao carregar o primeiro quadro do vídeo.")
            sys.exit(1)

        drawn_start, drawn_end = select_line_interactively(first_frame, WINDOW_NAME)
        if drawn_start is None or drawn_end is None:
            print("🛑 Processamento cancelado pelo usuário durante a definição da linha.")
            cap.release()
            out.release()
            cv2.destroyAllWindows()
            sys.exit(0)

        # Instanciação direta do VehicleCounter com as coordenadas reais do mouse
        counter = VehicleCounter(line_start=drawn_start, line_end=drawn_end)
        print(f"📏 Linha Virtual de Contagem (Mouse): {counter.line_start} -> {counter.line_end}")

        # Reiniciar o vídeo para o frame 0 garantindo contagem e gravação desde o início
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != 0:
            cap.release()
            cap = cv2.VideoCapture(str(video_path))

    print(f"🎬 Iniciando rastreamento ByteTrack e contagem no vídeo: {video_path.name}")
    print(f"🎯 Classes Filtradas na Inferência: {active_class_ids}")
    print(f"📐 Resolução: {width}x{height} | FPS: {fps:.1f} | Total de Frames: {total_frames}")
    if show_gui:
        print("💡 Pressione 'q' ou 'ESC' para sair | Pressione 'r' para redefinir a linha.\n")

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
                    counter = VehicleCounter(line_start=calib_start, line_end=calib_end)
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
                    counter = VehicleCounter(line_start=calib_start, line_end=calib_end)
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
                            just_counted = counter.update(track_id, canonical_cls, bbox)
                            if just_counted:
                                pt_name = BOTI_CLASS_NAMES_PT.get(canonical_cls, canonical_cls)
                                print(f"🚦 [CONTAGEM] {pt_name} (ID: {track_id}) cruzou a linha virtual! Total: {counter.get_total_count()}")

                # Desenhar bounding boxes com o rótulo formatado (ID: <track_id> | <classe> | <conf>%)
                annotated_frame = draw_tracking_annotations(frame, results, model.names, class_mapping)

                # Desenhar a linha virtual e o painel de contagem sobreposto
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

                    # Tecla R para redefinir/redesenhar a linha interativamente em tempo de execução
                    elif key in (ord('r'), ord('R')) and counter is not None:
                        print("\n⏸️ Vídeo pausado para redefinição da linha de contagem com o mouse.")
                        new_start, new_end = select_line_interactively(
                            frame,
                            WINDOW_NAME,
                            initial_line=(counter.line_start, counter.line_end)
                        )
                        if new_start is not None and new_end is not None:
                            counter.set_line(new_start, new_end)
                            line_mode_label = "Manual (Redefinida com Mouse)"
                            print(f"🔄 Linha Virtual Redefinida: {counter.line_start} -> {counter.line_end}")
                        else:
                            print("ℹ️ Redefinição cancelada. Mantendo linha anterior.")
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
            counter = VehicleCounter(line_start=calib_start, line_end=calib_end)
        else:
            counter = VehicleCounter(line_start=LINE_START, line_end=LINE_END)

    print(f"\n✅ Processamento e Contagem Concluídos!")
    print(f"📹 Vídeo anotado salvo com sucesso em: {output_path}")
    print("\n" + "="*45)
    print("📊 RELATÓRIO OFICIAL DE CONTAGEM (BOTI)")
    print("="*45)
    print(f"  • Modo da Linha: {line_mode_label}")
    print(f"  • Linha Utilizada: {counter.line_start} -> {counter.line_end}")
    if auto_detector is not None and auto_detector.flow_direction is not None:
        print(f"  • Fluxo Predominante: {auto_detector.flow_direction.upper()}")
    print("-" * 45)
    for cls_key in ["car", "motorcycle", "bus", "truck"]:
        pt_name = BOTI_CLASS_NAMES_PT.get(cls_key, cls_key)
        print(f"  • {pt_name}: {counter.counts[cls_key]}")
    print("-" * 45)
    print(f"  🏆 TOTAL DE VEÍCULOS: {counter.get_total_count()}")
    print("="*45 + "\n")


if __name__ == "__main__":
    main()