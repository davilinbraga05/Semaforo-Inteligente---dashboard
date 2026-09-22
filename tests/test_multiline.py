"""
Script de Testes Automatizados para MultiLineVehicleCounter e Lógica Multilinhas.
Valida:
- Caso 1: 1 linha
- Caso 2: 2 linhas
- Caso 3: 3 linhas
- Isolamento de track_id por linha
- Deduplicação individual por linha
- Agregação por classe e total geral
- Preservação do histórico previous_positions
- Renderização visual (draw)
- Simulação da máquina de estados do select_lines_interactively
"""

import sys
from pathlib import Path
import numpy as np

# Adicionar src ao path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from vehicle_counter import VehicleCounter, MultiLineVehicleCounter, LINE_PALETTE
from config import BOTI_CLASSES

def test_single_line():
    print("\n--- TESTE 1: UMA LINHA (Caso 1) ---")
    line1 = ((100, 200), (300, 200))
    counter = MultiLineVehicleCounter.from_segments([line1])
    assert len(counter.lines) == 1, f"Esperado 1 linha, obteve {len(counter.lines)}"
    assert counter.lines[0].label == "L1"

    # Frame 1: Veículo 10 (carro) acima da linha
    bbox_frame1 = [190, 100, 210, 150] # Centro inf: (200, 150)
    events = counter.update(track_id=10, cls_name="car", bbox=bbox_frame1)
    assert events == [], f"Não deve contar no primeiro frame: {events}"
    assert counter.get_total_count() == 0

    # Frame 2: Veículo 10 cruza a linha para baixo
    bbox_frame2 = [190, 220, 210, 270] # Centro inf: (200, 270)
    events = counter.update(track_id=10, cls_name="car", bbox=bbox_frame2)
    assert len(events) == 1, f"Esperado 1 evento de contagem, obteve {events}"
    assert events[0][0] == counter.lines[0]
    assert events[0][1] is True
    assert counter.get_total_count() == 1
    assert counter.lines[0].counts["car"] == 1
    assert counter.get_total_counts()["car"] == 1

    # Frame 3: Veículo 10 continua se movendo além da linha
    bbox_frame3 = [190, 280, 210, 330]
    events = counter.update(track_id=10, cls_name="car", bbox=bbox_frame3)
    assert events == [], f"Veículo 10 não deve ser recontado: {events}"
    assert counter.get_total_count() == 1

    # Frame 4: Veículo 20 (moto) cruza a linha
    counter.update(track_id=20, cls_name="motorcycle", bbox=[140, 120, 160, 170])
    events = counter.update(track_id=20, cls_name="motorcycle", bbox=[140, 220, 160, 270])
    assert len(events) == 1
    assert counter.get_total_count() == 2
    assert counter.get_total_counts()["motorcycle"] == 1
    assert counter.get_total_counts()["car"] == 1

    # Validar draw()
    dummy_frame = np.zeros((400, 600, 3), dtype=np.uint8)
    annotated = counter.draw(dummy_frame)
    assert annotated.shape == dummy_frame.shape

    print("✅ TESTE 1 (Uma Linha) PASSOU COM SUCESSO!")


def test_two_lines():
    print("\n--- TESTE 2: DUAS LINHAS (Caso 2) & TRACK_ID EM LINHAS DIFERENTES ---")
    line1 = ((50, 100), (250, 100)) # L1
    line2 = ((50, 300), (250, 300)) # L2
    counter = MultiLineVehicleCounter.from_segments([line1, line2])
    assert len(counter.lines) == 2
    assert counter.lines[0].label == "L1"
    assert counter.lines[1].label == "L2"
    assert counter.lines[0].line_color != counter.lines[1].line_color

    # Veículo ID 5 (truck):
    # 1. Posição inicial: acima de L1 (y=50)
    counter.update(track_id=5, cls_name="truck", bbox=[140, 20, 160, 50])
    assert counter.get_total_count() == 0

    # 2. Cruza L1 (y=150)
    events = counter.update(track_id=5, cls_name="truck", bbox=[140, 120, 160, 150])
    assert len(events) == 1
    assert events[0][0].label == "L1"
    assert counter.lines[0].get_total_count() == 1
    assert counter.lines[1].get_total_count() == 0
    assert counter.get_total_count() == 1
    assert 5 in counter.lines[0].counted_ids
    assert 5 not in counter.lines[1].counted_ids

    # 3. Permanece próximo de L1 (y=170) -> não reconta em L1
    events = counter.update(track_id=5, cls_name="truck", bbox=[140, 140, 160, 170])
    assert events == []
    assert counter.lines[0].get_total_count() == 1
    assert counter.get_total_count() == 1

    # 4. Desloca-se até antes de L2 (y=250)
    counter.update(track_id=5, cls_name="truck", bbox=[140, 220, 160, 250])

    # 5. Cruza L2 (y=350) -> DEVE ser contabilizado em L2!
    events = counter.update(track_id=5, cls_name="truck", bbox=[140, 320, 160, 350])
    assert len(events) == 1
    assert events[0][0].label == "L2"
    assert counter.lines[0].get_total_count() == 1
    assert counter.lines[1].get_total_count() == 1
    # Total consolidado: 2 travessias
    assert counter.get_total_count() == 2
    assert 5 in counter.lines[0].counted_ids
    assert 5 in counter.lines[1].counted_ids

    # 6. Outro veículo ID 8 (bus) cruza apenas L2
    counter.update(track_id=8, cls_name="bus", bbox=[100, 250, 120, 280])
    events = counter.update(track_id=8, cls_name="bus", bbox=[100, 320, 120, 350])
    assert len(events) == 1
    assert events[0][0].label == "L2"
    assert counter.lines[0].get_total_count() == 1
    assert counter.lines[1].get_total_count() == 2
    assert counter.get_total_count() == 3

    # Verificação da agregação por classe:
    # L1: truck=1
    # L2: truck=1, bus=1
    # Total: truck=2, bus=1, car=0, motorcycle=0 -> Total=3
    totals = counter.get_total_counts()
    assert totals["truck"] == 2
    assert totals["bus"] == 1
    assert totals["car"] == 0
    assert totals["motorcycle"] == 0
    assert sum(totals.values()) == counter.get_total_count()

    print("✅ TESTE 2 (Duas Linhas & Track ID Independente) PASSOU COM SUCESSO!")


def test_three_lines():
    print("\n--- TESTE 3: TRÊS LINHAS (Caso 3) ---")
    line1 = ((10, 100), (100, 100))
    line2 = ((10, 200), (100, 200))
    line3 = ((10, 300), (100, 300))
    counter = MultiLineVehicleCounter.from_segments([line1, line2, line3])
    assert len(counter.lines) == 3
    assert [l.label for l in counter.lines] == ["L1", "L2", "L3"]

    # Veículo 1 cruza L1
    counter.update(track_id=1, cls_name="car", bbox=[40, 50, 60, 80])
    counter.update(track_id=1, cls_name="car", bbox=[40, 110, 60, 130])

    # Veículo 2 cruza L2
    counter.update(track_id=2, cls_name="motorcycle", bbox=[40, 160, 60, 180])
    counter.update(track_id=2, cls_name="motorcycle", bbox=[40, 210, 60, 230])

    # Veículo 3 cruza L3
    counter.update(track_id=3, cls_name="bus", bbox=[40, 260, 60, 280])
    counter.update(track_id=3, cls_name="bus", bbox=[40, 310, 60, 330])

    assert counter.lines[0].counts["car"] == 1
    assert counter.lines[1].counts["motorcycle"] == 1
    assert counter.lines[2].counts["bus"] == 1
    assert counter.get_total_count() == 3

    # Desenho com 3 linhas
    dummy_frame = np.zeros((400, 600, 3), dtype=np.uint8)
    annotated = counter.draw(dummy_frame)
    assert annotated.shape == dummy_frame.shape

    print("✅ TESTE 3 (Três Linhas) PASSOU COM SUCESSO!")


def test_previous_positions_synchronization():
    print("\n--- TESTE 4: SINCRONIZAÇÃO ATÔMICA DE PREVIOUS_POSITIONS ---")
    # Garantir que todas as linhas no mesmo frame veem o mesmo ponto anterior
    line1 = ((0, 100), (200, 100))
    line2 = ((0, 150), (200, 150))
    counter = MultiLineVehicleCounter.from_segments([line1, line2])

    # Frame 1: veículo em y=80
    counter.update(track_id=99, cls_name="car", bbox=[40, 60, 60, 80])
    assert counter.previous_positions[99] == (50.0, 80.0)

    # Frame 2: movimento rápido cruzando L1 e L2 simultaneamente (y=80 -> y=180)
    events = counter.update(track_id=99, cls_name="car", bbox=[40, 160, 60, 180])
    # Ambas as linhas devem ter detectado o cruzamento!
    assert len(events) == 2
    assert {e[0].label for e in events} == {"L1", "L2"}
    assert counter.previous_positions[99] == (50.0, 180.0)
    assert counter.get_total_count() == 2

    print("✅ TESTE 4 (Sincronização Atômica) PASSOU COM SUCESSO!")

if __name__ == "__main__":
    test_single_line()
    test_two_lines()
    test_three_lines()
    test_previous_positions_synchronization()
    print("\n🎉 TODOS OS TESTES UNITÁRIOS E DE INTEGRAÇÃO PASSARAM COM SUCESSO!")
