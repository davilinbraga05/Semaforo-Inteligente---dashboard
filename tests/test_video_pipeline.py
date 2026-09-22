"""
Teste de Pipeline Completo de Vídeo com YOLO26s + ByteTrack + MultiLineVehicleCounter.
Executa sobre media/inputs/video_teste5.mp4:
- Caso 1: 1 Linha
- Caso 2: 2 Linhas
- Caso 3: 3 Linhas
"""

import sys
from pathlib import Path
import cv2
from ultralytics import YOLO

# Adicionar src ao path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from vehicle_counter import VehicleCounter, MultiLineVehicleCounter, LINE_PALETTE
from test_video import draw_tracking_annotations
from config import PERCEPTION_CONFIG, BOTI_CLASSES, BOTI_CLASS_NAMES_PT

def run_pipeline_test(num_lines: int, max_frames: int = 90):
    print(f"\n========================================================")
    print(f"🎬 TESTANDO PIPELINE COM {num_lines} LINHA(S) ({max_frames} FRAMES)")
    print(f"========================================================")

    base_dir = Path(__file__).resolve().parent.parent
    video_path = base_dir / "media" / "inputs" / "video_teste5.mp4"
    model_path = base_dir / "models" / "yolo26s.pt"

    assert video_path.exists(), f"Vídeo não encontrado: {video_path}"
    assert model_path.exists(), f"Modelo não encontrado: {model_path}"

    cap = cv2.VideoCapture(str(video_path))
    assert cap.isOpened(), "Falha ao abrir vídeo"

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Gerar segmentos de linha dependendo de num_lines
    segments = []
    y_step = height // (num_lines + 2)
    for i in range(1, num_lines + 1):
        y_pos = y_step * (i + 1)
        segments.append(((int(width * 0.1), y_pos), (int(width * 0.9), y_pos)))

    counter = MultiLineVehicleCounter.from_segments(segments)
    assert len(counter.lines) == num_lines

    model = YOLO(str(model_path))
    active_class_ids = [2, 3, 5, 7]
    class_mapping = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    output_test_path = base_dir / "media" / "outputs" / f"test_{num_lines}lines_output.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_test_path), fourcc, fps, (width, height))

    frame_count = 0
    total_events_detected = 0

    while cap.isOpened() and frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        results = model.track(
            frame,
            tracker=PERCEPTION_CONFIG["tracker"],
            persist=PERCEPTION_CONFIG["persist"],
            conf=PERCEPTION_CONFIG["conf"],
            imgsz=PERCEPTION_CONFIG["imgsz"],
            classes=active_class_ids,
            verbose=False
        )

        boxes = results[0].boxes
        if boxes is not None and boxes.id is not None:
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
                            total_events_detected += 1
                            pt_name = BOTI_CLASS_NAMES_PT.get(canonical_cls, canonical_cls)
                            print(f"  🚦 [Frame {frame_count}] [{line.label}] {pt_name} (ID: {track_id}) cruzou a linha! Total Linha: {line.get_total_count()} | Total Geral: {counter.get_total_count()}")

        # Desenhar anotações
        annotated_frame = draw_tracking_annotations(frame, results, model.names, class_mapping)
        annotated_frame = counter.draw(annotated_frame)
        out.write(annotated_frame)

    cap.release()
    out.release()

    # Validações matemáticas estritas
    sum_lines_total = sum(l.get_total_count() for l in counter.lines)
    assert counter.get_total_count() == sum_lines_total, (
        f"Inconsistência: get_total_count()={counter.get_total_count()} vs soma das linhas={sum_lines_total}"
    )

    total_counts_by_class = counter.get_total_counts()
    sum_classes_total = sum(total_counts_by_class.values())
    assert counter.get_total_count() == sum_classes_total, (
        f"Inconsistência: get_total_count()={counter.get_total_count()} vs soma das classes={sum_classes_total}"
    )

    for cls_name in ["car", "motorcycle", "bus", "truck"]:
        sum_line_cls = sum(l.counts[cls_name] for l in counter.lines)
        assert total_counts_by_class[cls_name] == sum_line_cls, (
            f"Inconsistência na classe {cls_name}: total={total_counts_by_class[cls_name]} vs soma={sum_line_cls}"
        )

    # Verificar existência e tamanho do vídeo de saída
    assert output_test_path.exists(), "Vídeo de saída não foi gerado!"
    assert output_test_path.stat().st_size > 1000, "Vídeo de saída está corrompido ou vazio!"

    print(f"✅ Sucesso com {num_lines} linha(s) em {frame_count} frames!")
    print(f"   • Total de Linhas: {len(counter.lines)}")
    for l in counter.lines:
        print(f"   • {l.label}: {l.get_total_count()} veículos contados ({l.counts})")
    print(f"   • Total Agregado: {counter.get_total_count()}")
    print(f"   • Total por Classe: {total_counts_by_class}")
    print(f"   • Vídeo de saída gerado: {output_test_path} ({output_test_path.stat().st_size} bytes)")

if __name__ == "__main__":
    # Teste A: 1 Linha
    run_pipeline_test(num_lines=1, max_frames=75)
    # Teste B: 2 Linhas
    run_pipeline_test(num_lines=2, max_frames=75)
    # Teste C: 3 Linhas
    run_pipeline_test(num_lines=3, max_frames=75)
    print("\n🎉 TODOS OS TESTES DE PIPELINE COM VÍDEO REAL FORAM CONCLUÍDOS COM SUCESSO!")
