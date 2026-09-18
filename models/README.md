# Modelos de Detecção YOLOv8

Este diretório armazena os modelos e arquivos de pesos treinados do YOLOv8.

## Como obter ou gerar o arquivo `best.pt`:

### Opção 1: Geração Automática via Treinamento Local (`src/train.py`)
Ao rodar o script de treinamento do projeto:
```bash
python src/train.py --data caminho/para/data.yaml
```
O arquivo `best.pt` gerado será copiado e salvo **automaticamente** nesta pasta (`models/best.pt`).

### Opção 2: Adição Manual
1. Baixe o arquivo de pesos `best.pt` do seu repositório no Roboflow, Google Drive ou Google Colab.
2. Mova ou cole o arquivo `best.pt` dentro desta pasta (`models/`).
3. O caminho final esperado é: `detector-test/models/best.pt`.

---

### Classes de Detecção do Projeto (7 classes):
- `ambulance` (Ambulância)
- `bus` (Ônibus)
- `car` (Carro)
- `fire truck` (Caminhão de Bombeiros)
- `motorcycle` (Motocicleta)
- `police car` (Viatura Policial)
- `truck` (Caminhão)
