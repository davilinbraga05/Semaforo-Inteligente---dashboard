# Modelo de Detecção

Este diretório armazena os pesos e instruções relacionados ao modelo de detecção de objetos utilizado pelo projeto.

---

## Modelo Atual

- **Arquivo:** `yolo26s.pt`
- **Origem:** Ultralytics oficial
- **Conjunto de Dados de Treinamento:** COCO (*Common Objects in Context*)
- **Arquitetura:** YOLO26s (Small)

O sistema utiliza o modelo oficial pré-treinado da Ultralytics. Modelos personalizados ou arquivos como `best.pt` foram investigados em etapas preliminares de experimentação, mas não são utilizados na versão funcional atual do pipeline.

---

## Classes de Detecção Utilizadas

O modelo COCO contém 80 classes gerais, das quais o sistema filtra exclusivamente as **quatro classes de interesse no trânsito urbano**:

| ID COCO | Classe Canônica | Nome em Português | Cor no HUD (BGR) |
| :---: | :--- | :--- | :--- |
| **2** | `car` | Carro | Verde `(0, 255, 0)` |
| **3** | `motorcycle` | Motocicleta | Magenta `(255, 0, 255)` |
| **5** | `bus` | Ônibus | Laranja `(0, 165, 255)` |
| **7** | `truck` | Caminhão | Ciano / Azul Claro `(255, 191, 0)` |

Todas as demais 76 classes do COCO são descartadas na camada de inferência e não geram contagem.

---

## Armazenamento e Download

Por padrão, arquivos binários com extensão `.pt` são ignorados pelo controle de versão (`.gitignore`) para preservar o tamanho do repositório.

O arquivo esperado é:
```text
models/yolo26s.pt
```

### Obtenção dos Pesos:

1. **Download Automático:**
   Ao executar o script principal ([`src/test_video.py`](file:///Users/davilinbraga/Semáforo%20Inteligente/detector-test-teste-1-contador-/src/test_video.py)), caso o arquivo `models/yolo26s.pt` não esteja presente, o sistema aciona o carregamento oficial da Ultralytics e move automaticamente o arquivo baixado para a pasta `models/`.

2. **Download Manual via Python:**
   ```bash
   python3 -c "from ultralytics import YOLO; YOLO('yolo26s.pt')"
   mv yolo26s.pt models/yolo26s.pt
   ```
