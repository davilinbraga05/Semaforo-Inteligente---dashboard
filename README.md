# Sistema Inteligente de Controle Semafórico

## Contagem e Classificação de Veículos com Visão Computacional

---

## 1. Visão Geral

Este projeto consiste em um protótipo acadêmico voltado à aplicação de técnicas de **visão computacional** e **aprendizado profundo** (*deep learning*) para a extração automática de dados de tráfego veicular a partir de fluxos de vídeo.

O sistema integra:
- Detecção de veículos em tempo real com **YOLO26s**;
- Filtragem de classes canônicas de trânsito urbano;
- Rastreamento multi-objeto persistente com **ByteTrack**;
- Interface interativa para definição dinâmica de **múltiplas linhas virtuais de contagem**;
- Contabilização estrita de travessias com prevenção contra recontagem;
- Agregação de contagens por classe veicular e por linha virtual;
- Geração de vídeo processado com visualização consolidada e métricas em tempo real.

O desenvolvimento foi concebido com fins de pesquisa e experimentação acadêmica, visando investigar como dados de percepção visual podem subsidiar futuramente estratégias de gestão inteligente e controle semafórico adaptativo.

---

## 2. Contexto e Problema

Sistemas semafóricos convencionais operam predominantemente com planos de temporização fixa ou acionamentos manuais pré-programados. Esses métodos apresentam limitações estruturais diante da dinâmica variável das cidades:

- **Alocação ineficiente de tempos de verde:** aproximações vazias recebem tempo desnecessário enquanto ramos concorrentes acumulam filas de espera.
- **Falta de diferenciação de modais:** planos tradicionais têm dificuldade para mensurar a composição da frota (e.g., proporção de veículos pesados, transporte coletivo e motocicletas).
- **Ausência de dados dinâmicos em tempo real:** controladores locais frequentemente operam isolados, sem sensores capazes de quantificar o volume efetivo de travessias por faixa.

> **Nota de Escopo:** O presente módulo do repositório fornece a **camada de percepção visual e contagem veicular**. O sistema **não atua nem controla fisicamente atuadores de campo ou semáforos**. A proposta atual limita-se a extrair e consolidar os dados de tráfego que servirão de insumo para futuras etapas de decisão.

---

## 3. Objetivos do Projeto

### Objetivo Geral
Desenvolver um módulo de visão computacional capaz de identificar, classificar e contabilizar o fluxo de veículos em vias públicas a partir de gravações em vídeo, permitindo a configuração dinâmica de linhas virtuais para apoiar o planejamento e a modelagem semafórica.

### Objetivos Específicos Implementados
1. **Detecção:** Identificar veículos com localização precisa de bounding boxes.
2. **Classificação:** Categorizar os objetos detectados nas quatro classes canônicas do projeto.
3. **Rastreamento:** Associar identificadores numéricos persistentes (*track IDs*) ao longo dos quadros.
4. **Linhas Virtuais Flexíveis:** Permitir ao operador traçar interativamente de 1 a $N$ linhas de corte diretamente sobre o vídeo.
5. **Contabilização de Travessias:** Registrar cruzamentos por vetor de deslocamento com memória de estados independente por linha.
6. **Agregação e Saída:** Exibir painel com métricas consolidadas e salvar o vídeo resultante anotado.

---

## 4. Evolução Técnica do Projeto

No início do desenvolvimento, utilizou-se o modelo **YOLOv8n** (*nano*) da Ultralytics. Embora apresentasse baixo custo computacional, o modelo demonstrou limitações em vídeos com veículos compactados ou posicionamento elevado de câmeras.

Buscando maior sensibilidade de detecção sem introduzir atrasos impeditivos de inferência, o pipeline migrou para a arquitetura **YOLO26s** oficial pré-treinada no conjunto de dados COCO. 

A adoção do YOLO26s trouxe melhoria na delimitação de contornos e no reconhecimento de classes como caminhões e ônibus. Contudo, cabe ressaltar que a qualidade intrínseca das gravações (resoluções variadas, taxa de quadros reduzida e ângulos da CET) permanece como fator determinante para o desempenho do sistema.

---

## 5. Arquitetura do Sistema

O fluxo de processamento de dados opera de forma sequencial e desacoplada em cada quadro de vídeo:

```text
               Fluxo de Vídeo (Câmera / Arquivo MP4)
                                 │
                                 ▼
                     Detecção Visual (YOLO26s)
                                 │
                                 ▼
             Filtro de Classes COCO (2, 3, 5 e 7)
                                 │
                                 ▼
               Rastreamento de Objetos (ByteTrack)
                                 │
                                 ▼
              Atribuição de Identificadores (Track IDs)
                                 │
                                 ▼
             Cálculo de Vetores de Movimento (Ponto de Contato)
                                 │
                                 ▼
             Avaliação Geométrica com Linhas Virtuais
             ├── Linha 1 (L1)  ──>  Registro em L1.counted_ids
             ├── Linha 2 (L2)  ──>  Registro em L2.counted_ids
             └── Linha N (LN)  ──>  Registro em LN.counted_ids
                                 │
                                 ▼
        Agregação de Travessias por Classe e por Linha
                                 │
                                 ▼
         Renderização Visual de HUD e Vídeo de Saída
```

---

## 6. Modelo de Detecção e Classes Oficiais

O detector em operação é o **YOLO26s oficial pré-treinado no dataset COCO** (*Common Objects in Context*).

- **Arquivo local esperado:** `models/yolo26s.pt`
- **Treinamento ativo:** Não há treinamento personalizado ativo nesta versão funcional; o sistema utiliza a generalização oficial do COCO.

### Classes Utilizadas pelo Projeto

Dentre as 80 categorias do dataset COCO, o sistema filtra exclusivamente as 4 classes relevantes para a dinâmica de vias urbanas:

| ID COCO | Classe Canônica | Nome em Português | Cor no HUD (BGR) |
| :---: | :--- | :--- | :--- |
| **2** | `car` | Carro | Verde `(0, 255, 0)` |
| **3** | `motorcycle` | Motocicleta | Magenta `(255, 0, 255)` |
| **5** | `bus` | Ônibus | Laranja `(0, 165, 255)` |
| **7** | `truck` | Caminhão | Ciano / Azul Claro `(255, 191, 0)` |

Qualquer outra classe presente no COCO (como pedestres, bicicletas ou objetos estáticos) é ignorada pela camada de contagem.

---

## 7. Rastreamento com ByteTrack

Para monitorar veículos ao longo do tempo, o projeto utiliza o algoritmo **ByteTrack** integrado via Ultralytics:

- **Parâmetros:** `tracker="bytetrack.yaml"`, `persist=True`
- **Funcionamento:** O algoritmo analisa as correspondências geométricas e de aparência das caixas delimitadoras entre quadros sucessivos, atribuindo e mantendo um `track_id` único para cada veículo.
- **Ponto de Referência:** A posição espacial de cada veículo é calculada pelo ponto central inferior da bounding box:
  $$x_{\text{ref}} = \frac{x_1 + x_2}{2}, \quad y_{\text{ref}} = y_2$$
  Esse ponto aproxima o contato das rodas do veículo com a pista, mitigando oscilações causadas pela altura do veículo.

---

## 8. Definição Dinâmica de Múltiplas Linhas de Contagem

O sistema permite ao usuário traçar interativamente **de 1 a $N$ linhas virtuais de contagem** diretamente sobre o primeiro quadro do vídeo.

### Fluxo Operacional
1. Ao iniciar o script com interface gráfica, o vídeo é pausado no quadro inicial.
2. O usuário clica com o botão esquerdo e arrasta para posicionar a linha **L1**.
3. **Opção 1 Linha:** Pressionar `ENTER` confirma L1 e inicia a execução imediatamente com uma única linha.
4. **Opção Múltiplas Linhas:**
   - Pressionar `N` confirma L1 e abre a edição da linha **L2**.
   - Desenhar L2 e pressionar `N` para criar **L3**, repetindo para quantas linhas forem necessárias.
   - Pressionar `ENTER` confirma todas as linhas desenhadas e dá início ao processamento.

### Atalhos de Teclado na Interface de Configuração

| Comando / Tecla | Ação |
| :--- | :--- |
| **Clique esquerdo + Arrastar** | Desenha o segmento de reta da linha ativa |
| **`N`** | Confirma a linha ativa atual e habilita o traçado da próxima linha |
| **`ENTER` ou `ESPAÇO`** | Confirma as linhas e inicia o processamento do vídeo |
| **`R`** | Redefine/limpa apenas a linha ativa em edição |
| **`Z` ou `Backspace`** | Descarta a linha ativa ou traz a última confirmada de volta para edição |
| **`Q` ou `ESC`** | Cancela e encerra a aplicação |

Durante o processamento do vídeo, pressionar a tecla **`R`** pausa a reprodução e reabre a interface interativa caso o operador precise redefinir o traçado das linhas.

---

## 9. Lógica de Contagem e Total Agregado

### Detecção Geométrica de Cruzamento
A travessia de cada linha virtual é avaliada através do produto vetorial bidimensional entre o vetor de deslocamento do veículo $(\vec{P}_{\text{ant}} \to \vec{P}_{\text{atual}})$ e o segmento que define a linha virtual $(\vec{A} \to \vec{B})$. O cruzamento só é confirmado quando os segmentos se interceptam no plano da imagem.

### Memória Independente por Linha
Cada linha configurada mantém sua própria estrutura de dados:
- `line.counted_ids`: Conjunto de identificadores de veículos já contabilizados naquela linha específica.
- `line.counts`: Dicionário com contadores individuais por classe veicular.

### Significado de "Total Agregado" (Travessias)
O sistema quantifica **TRAVESSIAS DE LINHA** e não necessariamente veículos únicos globais. 

- Se o veículo com `track_id = 14` cruzar a linha `L1`, ele será contabilizado uma única vez em `L1`.
- Caso ele permaneça parado ou oscile sobre `L1`, a presença em `L1.counted_ids` impede qualquer recontagem.
- Se esse mesmo veículo continuar seu percurso e posteriormente cruzar a linha `L2`, ele será contabilizado em `L2`.

Dessa forma, o total consolidado exibido no painel superior esquerdo representa a **soma de todas as travessias registradas**:
$$\text{Total por Classe} = \sum_{k=1}^N \text{Linha}_k[\text{classe}], \quad \text{Total Geral} = \sum \text{Total por Classe}$$

---

## 10. Estrutura do Repositório

```text
.
├── media/
│   ├── inputs/                       # Arquivos de vídeo e imagem para teste
│   └── outputs/                      # Vídeos anotados gerados pelo sistema
├── models/
│   ├── README.md                     # Documentação dos pesos e classes COCO
│   └── yolo26s.pt                    # Pesos oficiais do YOLO26s (ignorado no Git)
├── src/
│   ├── __init__.py
│   ├── auto_line.py                  # Calibrador automático opcional de linhas
│   ├── config.py                     # Configurações canônicas de classes e cores
│   ├── test_image.py                 # Script de inferência em imagens estáticas
│   ├── test_video.py                 # Pipeline principal de vídeo e contagem
│   ├── train.py                      # Script de treinamento auxiliar (Roboflow/Local)
│   └── vehicle_counter.py            # Classes VehicleCounter e MultiLineVehicleCounter
├── tests/
│   ├── test_interactive_logic.py     # Testes da máquina de estados do desenho interativo
│   ├── test_multiline.py             # Testes unitários e de integração de multilinhas
│   └── test_video_pipeline.py        # Testes de ponta a ponta com vídeo real
├── .env.example                      # Modelo para configuração de chaves de API
├── .gitignore                        # Proteção de binários .pt, mídias e caches
├── README.md                         # Documentação principal do projeto
└── requirements.txt                  # Dependências Python oficiais
```

---

## 11. Instalação e Configuração

### Pré-requisitos
- Python 3.9 ou superior
- Sistema Operacional: macOS, Linux ou Windows

### 1. Criar e Ativar o Ambiente Virtual
- **No macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **No Windows:**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

### 2. Instalar Dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Obtenção do Modelo YOLO26s
O arquivo `models/yolo26s.pt` é ignorado pelo controle de versão. Ao executar [`src/test_video.py`](file:///Users/davilinbraga/Semáforo%20Inteligente/detector-test-teste-1-contador-/src/test_video.py), caso o arquivo não seja localizado, o script efetua o download oficial automático via Ultralytics. Alternativamente, pode ser baixado manualmente:
```bash
python3 -c "from ultralytics import YOLO; YOLO('yolo26s.pt')"
mv yolo26s.pt models/yolo26s.pt
```

---

## 12. Execução

### Modo Padrão (Definição Manual com o Mouse)
Para processar um vídeo selecionando interativamente uma ou mais linhas:
```bash
python3 src/test_video.py --input media/inputs/video_teste5.mp4
```
*Se o argumento `--input` for omitido, o sistema seleciona automaticamente o primeiro vídeo válido encontrado em `media/inputs/`.*

### Argumentos de Linha de Comando Disponíveis

| Argumento | Tipo | Descrição |
| :--- | :--- | :--- |
| `-i`, `--input` | `str` | Caminho para o vídeo de entrada |
| `-c`, `--conf` | `float` | Limiar de confiança de detecção (padrão: `0.25`) |
| `--imgsz` | `int` | Resolução de entrada da imagem na inferência (padrão: `640`) |
| `--no-show` | `flag` | Executa sem abrir janela gráfica (modo silencioso / background) |
| `--line-start X Y` | `int int` | Coordenadas $(x_1, y_1)$ para fixar uma linha manual via CLI |
| `--line-end X Y` | `int int` | Coordenadas $(x_2, y_2)$ para fixar uma linha manual via CLI |
| `--auto-line` | `flag` | Ativa a auto-calibração da linha via `AutoLineDetector` |
| `--calib-frames` | `int` | Quantidade de quadros para calibração automática (padrão: `75`) |

---

## 13. Arquivos de Saída

Os vídeos processados são salvos automaticamente no diretório `media/outputs/` com o prefixo `output_`:
```text
media/outputs/output_<nome_do_arquivo>.mp4
```

O vídeo gravado contém:
- Caixas delimitadoras coloridas por classe;
- Rótulos formatados: `ID: <track_id> | <classe> | <confiança>%`;
- Linhas virtuais ativas com suas cores e identificadores (`L1`, `L2`, ...);
- Painel HUD semitransparente com a contagem agregada em tempo real;
- Relatório final impresso no terminal após a conclusão.

---

## 14. Suíte de Testes Automatizados

O projeto possui suíte de testes em `tests/` desenvolvida para validar a integridade da lógica multilinhas e do pipeline:

1. **`tests/test_multiline.py`:**
   - Validação com 1 linha virtual (Caso 1);
   - Validação com 2 linhas e independência de IDs (Caso 2);
   - Validação com 3 linhas dinâmicas (Caso 3);
   - Sincronização atômica de `previous_positions`.
2. **`tests/test_interactive_logic.py`:**
   - Teste da máquina de estados dos atalhos de teclado (`N`, `ENTER`, `R`, `Z`).
3. **`tests/test_video_pipeline.py`:**
   - Execução ponta a ponta com vídeo real, inferência YOLO26s, ByteTrack e gravação de saída para 1, 2 e 3 linhas.

### Execução dos Testes
```bash
python3 tests/test_multiline.py
python3 tests/test_interactive_logic.py
python3 tests/test_video_pipeline.py
```

---

## 15. Limitações Técnicas Conhecidas

Em conformidade com o rigor científico do projeto, destacam-se as seguintes limitações do sistema atual:

1. **Dependência da Qualidade da Mídia:** Em gravações com baixa resolução, compressão acentuada ou ângulos oblíquos severos, a precisão das detecções diminui.
2. **Falsos Negativos em Veículos Distantes:** Veículos situados no fundo da cena com reduzida contagem de pixels podem não atingir o limiar de confiança.
3. **Descontinuidades no Rastreamento:** Em situações de oclusão mútua prolongada (ex.: ônibus encobrindo motocicleta), o ByteTrack pode eventualmente perder ou alternar identificadores (*ID switch*).
4. **Métrica Baseada em Travessias:** O sistema computa o volume de cortes transversais; veículos que manobram ou cruzam múltiplas linhas são contabilizados em cada seção correspondente.
5. **Calibração Sensível ao Operador:** A acurácia da contagem requer que as linhas virtuais sejam traçadas em posições perpendiculares ao fluxo de tráfego.
6. **Escopo Acadêmico:** O sistema consiste em uma prova de conceito para validação em bancada, não constituindo produto homologado para operações viárias de missão crítica.

---

## 16. Módulos Investigados Preliminarmente

Durante as fases iniciais do estudo, foram elaboradas formulações teóricas e experimentais envolvendo:
- Definição estática de Regiões de Interesse (**ROI**);
- Métricas de densidade espacial por ocupação percentual de área;
- Conversão para Unidades de Carro de Passageiro (**PCU**);
- Algoritmos clássicos de temporização adaptativa (modelo SCATS/Webster).

Devido às variações de qualidade dos vídeos reais de tráfego urbano disponíveis, optou-se por focar o pipeline atual estritamente na **alta confiabilidade de detecção, rastreamento e contagem por linhas virtuais**. Os módulos conceituais de ROI e PCU não integram o pipeline funcional deste repositório.

---

## 17. Próximas Etapas e Trabalhos Futuros

Como continuidade do plano de pesquisa, as seguintes etapas estão **planejadas**:

- **Interface Web / Dashboard Interativo:** Construção de painel web para visualização gráfica das métricas e das curvas de fluxo ao longo do tempo.
- **Georreferenciamento de Cruzamentos:** Mapa interativo da cidade de São Paulo indicando os pontos de coleta e o nível de serviço de cada aproximação.
- **Simulador de Decisão Semafórica:** Implementação de algoritmo em ambiente simulado para sugerir ajustes na duração das fases verde/vermelho com base no volume medido pelas linhas virtuais.

---

## 18. Status Atual do Repositório

| Funcionalidade | Situação | Observações |
| :--- | :---: | :--- |
| Detecção com YOLO26s (Ultralytics) | Concluído | Modelo oficial COCO pré-treinado |
| Filtro das 4 Classes Oficiais | Concluído | Carro, Motocicleta, Ônibus e Caminhão |
| Rastreamento Multi-Objeto (ByteTrack) | Concluído | IDs contínuos ao longo dos quadros |
| Linha Única de Contagem | Concluído | Operação com mouse ou argumentos CLI |
| Múltiplas Linhas Dinâmicas ($1$ a $N$) | Concluído | Teclas `N`, `ENTER`, `R` e `Z` integradas |
| Deduplicação Estrita por Linha | Concluído | `counted_ids` independente por linha |
| Agregação de Totais por Modal | Concluído | Painel HUD consolidado no vídeo |
| Vídeo Anotado de Saída | Concluído | Gravado em `media/outputs/` |
| Suíte de Testes Automatizados | Concluído | Testes unitários, de interface e de vídeo |
| Dashboard Web / Mapa | Planejado | Próxima fase do projeto de pesquisa |
| Controle Semafórico Adaptativo | Planejado | Próxima fase do projeto de pesquisa |
