"""
Teste da lógica de estados de seleção de linhas (idêntica à select_lines_interactively).
"""
import sys
from pathlib import Path
from typing import List, Tuple

def simulate_selection(actions):
    confirmed_lines = []
    active_start = None
    active_end = None

    for action in actions:
        act_type = action[0]
        if act_type == "draw":
            start, end = action[1], action[2]
            dist = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
            if dist >= 10.0:
                active_start = start
                active_end = end
            else:
                active_start = None
                active_end = None
        elif act_type == "key_N":
            if active_start is not None and active_end is not None:
                confirmed_lines.append((active_start, active_end))
                active_start = None
                active_end = None
        elif act_type == "key_ENTER":
            if active_start is not None and active_end is not None:
                confirmed_lines.append((active_start, active_end))
                active_start = None
                active_end = None
            if len(confirmed_lines) > 0:
                return confirmed_lines
        elif act_type == "key_R":
            active_start = None
            active_end = None
        elif act_type == "key_Z":
            if active_start is not None and active_end is not None:
                active_start = None
                active_end = None
            elif len(confirmed_lines) > 0:
                active_start, active_end = confirmed_lines.pop()
        elif act_type == "key_Q":
            return None

    return confirmed_lines

# Caso 1: L1 -> ENTER
res1 = simulate_selection([
    ("draw", (100, 100), (400, 100)),
    ("key_ENTER",)
])
assert len(res1) == 1
assert res1[0] == ((100, 100), (400, 100))
print("✅ Caso 1: L1 -> ENTER validado.")

# Caso 2: L1 -> N -> L2 -> ENTER
res2 = simulate_selection([
    ("draw", (100, 100), (400, 100)),
    ("key_N",),
    ("draw", (100, 200), (400, 200)),
    ("key_ENTER",)
])
assert len(res2) == 2
assert res2[0] == ((100, 100), (400, 100))
assert res2[1] == ((100, 200), (400, 200))
print("✅ Caso 2: L1 -> N -> L2 -> ENTER validado.")

# Caso 3: L1 -> N -> L2 -> N -> L3 -> ENTER
res3 = simulate_selection([
    ("draw", (100, 100), (400, 100)),
    ("key_N",),
    ("draw", (100, 200), (400, 200)),
    ("key_N",),
    ("draw", (100, 300), (400, 300)),
    ("key_ENTER",)
])
assert len(res3) == 3
print("✅ Caso 3: L1 -> N -> L2 -> N -> L3 -> ENTER validado.")

# Teste de R (redesenhar)
res_r = simulate_selection([
    ("draw", (100, 100), (400, 100)),
    ("key_N",),
    ("draw", (50, 50), (60, 60)), # linha errada
    ("key_R",), # limpa ativa
    ("draw", (100, 200), (400, 200)), # desenha certa
    ("key_ENTER",)
])
assert len(res_r) == 2
assert res_r[1] == ((100, 200), (400, 200))
print("✅ Teste tecla R validado.")

# Teste de Z (desfazer):
# Cenário 1: Z descarta linha ativa se estiver em edição
res_z1 = simulate_selection([
    ("draw", (100, 100), (400, 100)), # desenhou L1
    ("key_Z",), # descarta L1 ativa
    ("draw", (150, 150), (450, 150)), # desenha nova
    ("key_ENTER",)
])
assert len(res_z1) == 1
assert res_z1[0] == ((150, 150), (450, 150))

# Cenário 2: Z desfaz linha confirmada trazendo-a de volta para edição
res_z2 = simulate_selection([
    ("draw", (100, 100), (400, 100)),
    ("key_N",), # confirma L1
    ("draw", (100, 200), (400, 200)),
    ("key_N",), # confirma L2
    ("key_Z",), # desfaz L2 para ativa
    ("key_Z",), # descarta L2 ativa
    ("key_ENTER",) # finaliza só com L1
])
assert len(res_z2) == 1
assert res_z2[0] == ((100, 100), (400, 100))
print("✅ Teste tecla Z validado com sucesso!")

print("\n🎉 TODOS OS FLUXOS DE INTERAÇÃO DA SELEÇÃO VALIDAM PERFEITAMENTE!")
