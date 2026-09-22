import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import cv2
from ultralytics import YOLO

# Garantir que a pasta src esteja no caminho de busca do Python
src_dir = Path(__file__).resolve().parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from config import BOTI_CLASS_IDS, BOTI_CLASSES, PERCEPTION_CONFIG

# Carregar variáveis de ambiente a partir do arquivo .env
load_dotenv()

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")

def main():
    parser = argparse.ArgumentParser(description="Teste de inferência YOLO26s em imagens estáticas (BOTI).")
    parser.add_argument(
        "-i", "--input", 
        type=str, 
        default=None, 
        help="Caminho para a imagem de entrada. Se omitido, busca automaticamente na pasta media/inputs/"
    )
    parser.add_argument(
        "-c", "--conf", 
        type=float, 
        default=PERCEPTION_CONFIG["conf"], 
        help=f"Limiar de confiança para detecção (padrão: {PERCEPTION_CONFIG['conf']})"
    )
    args = parser.parse_args()

    # Definir diretórios base do projeto
    base_dir = Path(__file__).resolve().parent.parent
    model_path = base_dir / PERCEPTION_CONFIG["model_path"]

    inputs_dir = base_dir / "media" / "inputs"
    outputs_dir = base_dir / "media" / "outputs"

    outputs_dir.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Verificar existência do modelo oficial; efetuar download se ausente
    if not model_path.exists():
        print(f"🔄 Modelo '{model_path.name}' não encontrado localmente em {model_path.parent}. Efetuando download oficial...")
        try:
            downloaded = YOLO("yolo26s.pt")
            root_dl = base_dir / "yolo26s.pt"
            if root_dl.exists() and root_dl != model_path:
                root_dl.rename(model_path)
        except Exception as e:
            print(f"❌ Erro ao obter o modelo '{model_path}': {e}")
            sys.exit(1)

    # Selecionar imagem de entrada
    if args.input:
        image_path = Path(args.input)
    else:
        valid_extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
        found_images = []
        for ext in valid_extensions:
            found_images.extend(inputs_dir.glob(ext))
            found_images.extend(inputs_dir.glob(ext.upper()))

        if not found_images:
            print(f"❌ Erro: Nenhuma imagem encontrada na pasta: {inputs_dir}")
            print("💡 Adicione uma imagem (.jpg, .jpeg, .png, etc.) em 'media/inputs/' ou especifique via '--input caminho/imagem.jpg'.")
            sys.exit(1)

        image_path = found_images[0]
        print(f"🔍 Imagem selecionada automaticamente: {image_path.name}")

    if not image_path.exists():
        print(f"❌ Erro: O arquivo de imagem especificado não existe: {image_path}")
        sys.exit(1)

    print(f"🚀 Carregando modelo oficial YOLO26s: {model_path}")
    model = YOLO(str(model_path))

    print(f"📸 Processando imagem com filtro de classes BOTI {BOTI_CLASS_IDS}: {image_path.name}...")
    results = model.predict(
        source=str(image_path),
        conf=args.conf,
        imgsz=PERCEPTION_CONFIG["imgsz"],
        classes=BOTI_CLASS_IDS
    )

    # Obter imagem anotada com bounding boxes e rótulos
    annotated_image = results[0].plot()

    # Definir caminho de saída e salvar imagem
    output_filename = f"output_{image_path.name}"
    output_path = outputs_dir / output_filename
    cv2.imwrite(str(output_path), annotated_image)
    print(f"✅ Resultado salvo com sucesso em: {output_path}")

    # Exibir resumo das detecções no terminal
    boxes = results[0].boxes
    print(f"📊 Detecções de veículos encontradas: {len(boxes)}")
    for box in boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names.get(cls_id, BOTI_CLASSES.get(cls_id, str(cls_id)))
        confidence = float(box.conf[0])
        print(f"  • Classe: {cls_name:<12} | Confiança: {confidence:.2%}")

    # Exibir imagem na janela OpenCV
    print("📺 Exibindo imagem... Pressione qualquer tecla na janela para fechar.")
    cv2.imshow("BOTI - YOLO26s Detecção em Imagem", annotated_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
