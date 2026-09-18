# Detector Test - Treinamento e Inferência YOLOv8 🚀

Repositório leve, seguro e completo para **treinamento**, **carregamento de pesos** (`best.pt`) e **inferência** do modelo **YOLOv8** em imagens estáticas e vídeos. Permite a integração segura de chaves de API via `.env` e suporte ao Roboflow.

---

## 🎯 Classes de Detecção do Projeto (7 Classes)

O modelo foi capacitado para reconhecer as seguintes classes de veículos:
1. `ambulance` (Ambulância)
2. `bus` (Ônibus)
3. `car` (Carro)
4. `fire truck` (Caminhão de Bombeiros)
5. `motorcycle` (Motocicleta)
6. `police car` (Viatura Policial)
7. `truck` (Caminhão)

---

## 📂 Arquitetura do Repositório

```text
detector-test/
├── models/
│   ├── README.md              # Instruções e armazenamento de pesos (best.pt / yolov8n.pt)
│   └── best.pt                # Pesos treinados do modelo (salvo após o treino ou inserido manualmente)
├── media/
│   ├── inputs/                # Insira suas imagens e vídeos de teste aqui
│   └── outputs/               # Resultados anotados salvos automaticamente aqui
├── src/
│   ├── __init__.py
│   ├── train.py               # Script de treinamento do YOLOv8 (Local e Roboflow)
│   ├── test_image.py          # Script de teste e inferência em imagens estáticas
│   └── test_video.py          # Script de teste e inferência em vídeos em tempo real
├── datasets/                  # Pasta criada automaticamente ao baixar datasets do Roboflow
├── .env.example               # Modelo para variáveis de ambiente (Roboflow API, Workspace, etc.)
├── .gitignore                 # Proteção contra commit de pesos, datasets, mídias e chaves sensíveis
├── requirements.txt           # Dependências do projeto Python (ultralytics, opencv, roboflow, etc.)
└── README.md                  # Guia completo de treinamento, instalação e execução
```

---

## ⚙️ Guia Passo a Passo de Instalação e Configuração

### 1. Clonar ou Acessar a Pasta do Repositório
Abra o terminal e navegue até a pasta do projeto:
```bash
cd detector-test
```

### 2. Criar e Ativar o Ambiente Virtual Python (`venv`)

- **no macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **no Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

### 3. Instalar as Dependências
Com o ambiente virtual ativo, instale os pacotes requeridos:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente (`.env`)
Copie o arquivo `.env.example` para criar o seu arquivo `.env`:
```bash
cp .env.example .env
```
Abra o arquivo `.env` e preencha suas credenciais do Roboflow (se for utilizar a integração automática para download do dataset):
```env
ROBOFLOW_API_KEY=sua_chave_privada_aqui
ROBOFLOW_WORKSPACE=seu_workspace_aqui
ROBOFLOW_PROJECT=seu_projeto_aqui
ROBOFLOW_VERSION=1
```

---

## 🏋️‍♂️ Treinamento do Modelo (YOLOv8 Training)

Você pode treinar o modelo de três formas principais: usando o script **Python do repositório**, via **linha de comando (CLI)** ou na **nuvem (Google Colab)**.

---

### Estrutura do Dataset (`data.yaml`)

Para que o treinamento funcione com o dataset local, a pasta do dataset deve conter a seguinte estrutura:

```text
meu_dataset/
├── train/
│   ├── images/
│   └── labels/
├── val/
│   ├── images/
│   └── labels/
└── data.yaml
```

Exemplo do arquivo `data.yaml`:
```yaml
path: ../meu_dataset  # caminho relativo ou absoluto para a raiz do dataset
train: train/images
val: val/images

names:
  0: ambulance
  1: bus
  2: car
  3: fire truck
  4: motorcycle
  5: police car
  6: truck
```

---

### Forma 1: Treinamento via Script Python (`src/train.py`)

O repositório inclui o script [`src/train.py`](file:///Users/davilinbraga/detector-test/src/train.py) totalmente pré-configurado para treinar o YOLOv8 e atualizar **automatically** o arquivo de pesos `models/best.pt`.

#### Opção A: Treinar com Dataset Local (`data.yaml`)
```bash
python src/train.py --data caminho/para/meu_dataset/data.yaml --epochs 50 --batch 16 --imgsz 640
```

#### Opção B: Baixar Dataset do Roboflow Automaticamente e Treinar
Certifique-se de que configurou `ROBOFLOW_API_KEY`, `ROBOFLOW_WORKSPACE` e `ROBOFLOW_PROJECT` no seu `.env`, e execute:
```bash
python src/train.py --download-rf --epochs 50 --batch 16
```

#### Principais Argumentos do `src/train.py`:
- `-d`, `--data`: Caminho para o `data.yaml` local.
- `-e`, `--epochs`: Número de épocas de treinamento (padrão: `50`).
- `-b`, `--batch`: Tamanho do batch (padrão: `16`).
- `--imgsz`: Tamanho da imagem (padrão: `640`).
- `-m`, `--model`: Modelo base pré-treinado (padrão: `yolov8n.pt`). Opções: `yolov8s.pt`, `yolov8m.pt`, `yolov8l.pt`, `yolov8x.pt`.
- `--device`: Dispositivo de execução. Ex: `0` (GPU), `cpu`, ou `mps` (Apple Silicon GPU).
- `--download-rf`: Força o download do dataset configurado no Roboflow antes de treinar.

---

### Forma 2: Treinamento via Linha de Comando (CLI Ultralytics)

Caso prefira rodar diretamente via terminal CLI da Ultralytics:

```bash
yolo detect train data=caminho/para/data.yaml model=yolov8n.pt epochs=50 imgsz=640 batch=16
```

Após a conclusão do treino via CLI, copie os melhores pesos gerados em `runs/detect/train/weights/best.pt` para a pasta `models/`:
```bash
cp runs/detect/train/weights/best.pt models/best.pt
```

---

### Forma 3: Treinamento na Nuvem (Google Colab / GPU Acelerada)

Se a sua máquina não tiver GPU dedicada (NVIDIA/Apple Silicon), recomendamos treinar no **Google Colab** gratuitamente:

1. Abra um novo notebook no [Google Colab](https://colab.research.google.com/) e altere o ambiente de execução para **GPU T4** (`Editar > Configurações do ambiente de execução > GPU T4`).
2. Execute a instalação do Ultralytics e Roboflow:
   ```python
   !pip install ultralytics roboflow
   ```
3. Baixe seu dataset do Roboflow no Colab:
   ```python
   from roboflow import Roboflow
   rf = Roboflow(api_key="SUA_ROBOFLOW_API_KEY")
   project = rf.workspace("SEU_WORKSPACE").project("SEU_PROJETO")
   dataset = project.version(1).download("yolov8")
   ```
4. Inicie o treinamento:
   ```python
   from ultralytics import YOLO
   model = YOLO("yolov8n.pt")
   model.train(data=f"{dataset.location}/data.yaml", epochs=50, imgsz=640, batch=16)
   ```
5. Baixe o arquivo `best.pt` gerado em `runs/detect/train/weights/best.pt` e salve-o na pasta `models/best.pt` do seu repositório local.

---

## 📸 Execução dos Testes e Inferência

Com o modelo treinado (`models/best.pt`), você pode realizar os testes em imagens ou vídeos.

### 🟢 Teste em Imagem Estática (`src/test_image.py`)
1. Coloque uma imagem (ex: `exemplo.jpg`) na pasta `media/inputs/`.
2. Execute o script:
   ```bash
   python src/test_image.py
   ```
   *Nota: O script selecionará automaticamente a primeira imagem encontrada em `media/inputs/`.*

3. Ou especifique uma imagem específica via argumento:
   ```bash
   python src/test_image.py -i media/inputs/minha_imagem.jpg --conf 0.30
   ```
4. O resultado anotado será exibido na tela via OpenCV e salvo em `media/outputs/output_exemplo.jpg`.

---

### 🎥 Rastreamento e Contagem em Vídeo com ByteTrack (`src/test_video.py`)
1. Coloque um vídeo (ex: `video_teste.mp4`) na pasta `media/inputs/`.
2. Execute o script de rastreamento e contagem:
   ```bash
   python src/test_video.py -i media/inputs/video_teste.mp4
   ```
   *Nota: O script selecionará automaticamente o primeiro vídeo em `media/inputs/` se o argumento `-i` não for informado.*

3. **🖱️ Definição Manual da Linha de Contagem com o Mouse:**
   - Ao iniciar, a janela do vídeo abrirá pausada no primeiro quadro.
   - **Desenhar Linha:** Pressione o **botão esquerdo do mouse**, arraste até o outro ponto desejado e solte o botão.
   - **Confirmar:** Pressione **`[ENTER]`** ou **`[ESPAÇO]`** para confirmar a linha e iniciar a contagem do vídeo.
   - **Redesenhar:** Pressione **`[R]`** para limpar a linha e desenhar novamente.
   - **Sair:** Pressione **`[Q]`** ou **`[ESC]`** para encerrar o programa.

4. **⌨️ Controles Durante a Execução:**
   - **`[Q]` ou `[ESC]`:** Interrompe a execução a qualquer momento e exibe o relatório final.
   - **`[R]`:** Pausa o vídeo a qualquer momento e permite redefinir/redesenhar a linha de contagem com o mouse.

5. **Opções Adicionais de Linha de Comando:**
   - Calibração automática em vez de manual:
     ```bash
     python src/test_video.py --auto-line
     ```
   - Especificar coordenadas exatas via CLI (sem usar o mouse):
     ```bash
     python src/test_video.py --line-start 100 300 --line-end 800 300
     ```
   - Especificar confiança personalizada:
     ```bash
     python src/test_video.py --conf 0.30
     ```
   - Execução em segundo plano (sem janela gráfica):
     ```bash
     python src/test_video.py --no-show
     ```

6. **Durante o Rastreamento:**
   - O algoritmo **ByteTrack** associa e mantém o mesmo `track_id` para cada veículo ao longo dos frames.
   - Cada veículo recebe uma anotação visual: `ID: <track_id> | <classe> | <confiança>%`.
   - A travessia da linha é calculada utilizando o centro inferior da bounding box do veículo e produto vetorial 2D. Cada `track_id` é contado estritamente uma única vez.
   - O painel HUD translúcido exibe as contagens em tempo real por classe (`Carro`, `Motocicleta`, `Ônibus`, `Caminhão`) e o `TOTAL`.
7. O vídeo final com todas as anotações e contagens será salvo em `media/outputs/output_<nome_do_video>.mp4`.
8. Ao término, um relatório consolidado é exibido no terminal com a linha utilizada e totais por classe.


---

## 🔐 Segurança do Repositório

Este repositório possui regras no `.gitignore` configuradas para garantir que:
- Chaves de API no arquivo `.env` nunca sejam expostas no Git.
- O arquivo de pesos `best.pt` e dados brutos de datasets não sejam commitados.
- Suas imagens e vídeos de teste em `media/inputs/` e `media/outputs/` fiquem isolados no seu ambiente local.
