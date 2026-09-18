import os
import sys
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv
from ultralytics import YOLO

# Carregar variáveis de ambiente a partir do arquivo .env
load_dotenv()

def download_roboflow_dataset(workspace: str, project: str, version: int, api_key: str, download_dir: Path) -> Path:
    """
    Baixa um dataset do Roboflow utilizando a API Key e salva na pasta especificada.
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        print("❌ Erro: O pacote 'roboflow' não está instalado.")
        print("💡 Execute: pip install roboflow")
        sys.exit(1)

    print(f"🔄 Conectando ao Roboflow (Workspace: '{workspace}', Projeto: '{project}', Versão: {version})...")
    rf = Roboflow(api_key=api_key)
    proj = rf.workspace(workspace).project(project)
    dataset_info = proj.version(version).download("yolov8", location=str(download_dir / f"{project}-{version}"))
    
    yaml_path = Path(dataset_info.location) / "data.yaml"
    if not yaml_path.exists():
        print(f"❌ Erro: O arquivo 'data.yaml' não foi encontrado em {yaml_path}")
        sys.exit(1)
        
    print(f"✅ Dataset do Roboflow baixado com sucesso em: {dataset_info.location}")
    return yaml_path

def main():
    parser = argparse.ArgumentParser(description="Treinamento do modelo YOLOv8 para detecção de veículos.")
    
    parser.add_argument(
        "-d", "--data",
        type=str,
        default=None,
        help="Caminho para o arquivo 'data.yaml' local do dataset."
    )
    parser.add_argument(
        "-e", "--epochs",
        type=int,
        default=50,
        help="Número de épocas de treinamento (padrão: 50)"
    )
    parser.add_argument(
        "--imgsz", "--img",
        type=int,
        default=640,
        help="Tamanho das imagens para o treinamento (padrão: 640)"
    )
    parser.add_argument(
        "-b", "--batch",
        type=int,
        default=16,
        help="Tamanho do batch (padrão: 16)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="yolov8n.pt",
        help="Modelo base pré-treinado do YOLOv8 (padrão: 'yolov8n.pt')"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Dispositivo de execução: '0' para GPU GPU0, 'cpu', ou 'mps' para Apple Silicon (padrão: seleção automática)"
    )
    parser.add_argument(
        "--rf-workspace",
        type=str,
        default=os.getenv("ROBOFLOW_WORKSPACE"),
        help="Nome do workspace no Roboflow (ou definir no .env como ROBOFLOW_WORKSPACE)"
    )
    parser.add_argument(
        "--rf-project",
        type=str,
        default=os.getenv("ROBOFLOW_PROJECT"),
        help="Nome do projeto no Roboflow (ou definir no .env como ROBOFLOW_PROJECT)"
    )
    parser.add_argument(
        "--rf-version",
        type=int,
        default=int(os.getenv("ROBOFLOW_VERSION", "1")),
        help="Versão do dataset no Roboflow (padrão: 1)"
    )
    parser.add_argument(
        "--download-rf",
        action="store_true",
        help="Forçar o download do dataset do Roboflow antes do treinamento."
    )

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    datasets_dir = base_dir / "datasets"

    api_key = os.getenv("ROBOFLOW_API_KEY")

    yaml_path = None

    # 1. Tentar usar dataset do Roboflow se configurado ou solicitado
    if args.download_rf or (args.rf_workspace and args.rf_project and not args.data):
        if not api_key or api_key == "sua_chave_privada_aqui":
            print("❌ Erro: ROBOFLOW_API_KEY não configurada no arquivo .env!")
            print("💡 Configure a variável ROBOFLOW_API_KEY no seu arquivo .env para baixar automaticamente do Roboflow.")
            sys.exit(1)
        
        yaml_path = download_roboflow_dataset(
            workspace=args.rf_workspace,
            project=args.rf_project,
            version=args.rf_version,
            api_key=api_key,
            download_dir=datasets_dir
        )
    
    # 2. Caso contrário, verificar se foi passado um arquivo data.yaml local
    elif args.data:
        yaml_path = Path(args.data).resolve()
        if not yaml_path.exists():
            print(f"❌ Erro: O arquivo de dataset informado não existe: {yaml_path}")
            sys.exit(1)
            
    # 3. Procurar por data.yaml existente na pasta datasets/
    else:
        existing_yamls = list(datasets_dir.glob("**/data.yaml")) if datasets_dir.exists() else []
        if existing_yamls:
            yaml_path = existing_yamls[0]
            print(f"🔍 Dataset 'data.yaml' encontrado automaticamente em: {yaml_path}")
        else:
            print("❌ Erro: Nenhum dataset foi especificado e nenhum 'data.yaml' local foi encontrado!")
            print("\n💡 Como resolver:")
            print("  1. Para rodar com dataset local:")
            print("     python src/train.py --data caminho/para/data.yaml")
            print("  2. Para baixar automaticamente do Roboflow:")
            print("     Configure ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE e ROBOFLOW_PROJECT no seu .env e execute:")
            print("     python src/train.py --download-rf")
            sys.exit(1)

    print("\n" + "="*60)
    print("🚀 INICIANDO TREINAMENTO YOLOV8")
    print("="*60)
    print(f"📋 Modelo Base:      {args.model}")
    print(f"📄 Arquivo Data:      {yaml_path}")
    print(f"⏱️ Épocas:           {args.epochs}")
    print(f"📐 Resolução (imgsz): {args.imgsz}")
    print(f"📦 Batch size:       {args.batch}")
    print(f"💻 Dispositivo:       {args.device if args.device else 'Automático'}")
    print("="*60 + "\n")

    # Carregar modelo pré-treinado
    model = YOLO(args.model)

    # Configurar argumentos de treino
    train_args = {
        "data": str(yaml_path),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "project": str(base_dir / "runs"),
        "name": "train",
        "exist_ok": True,
    }

    if args.device:
        train_args["device"] = args.device

    # Executar o treinamento
    results = model.train(**train_args)

    # Identificar onde os pesos treinados foram salvos
    weights_path = Path(results.save_dir) / "weights" / "best.pt"
    target_best_path = models_dir / "best.pt"

    if weights_path.exists():
        shutil.copy(weights_path, target_best_path)
        print("\n" + "="*60)
        print("🎉 TREINAMENTO CONCLUÍDO COM SUCESSO!")
        print("="*60)
        print(f"🏆 Pesos salvos em:                {weights_path}")
        print(f"📌 Atualizado em modelos do projeto: {target_best_path}")
        print("="*60)
        print("💡 Agora você pode rodar a inferência com:")
        print("   python src/test_image.py")
        print("   python src/test_video.py")
    else:
        print(f"⚠️ Treinamento finalizado, mas o arquivo {weights_path} não foi localizado automaticamente.")

if __name__ == "__main__":
    main()
