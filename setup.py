import subprocess
import sys
from pathlib import Path

from config import Config

########################################################
### Kanana 모델 설정
########################################################

def download_kanana(model_name: str, save_dir: Path) -> None:
    """
    Hugging Face에서 Kanana 모델을 다운로드하는 함수 (최초 1회 실행).
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    save_dir.mkdir(parents = True, exist_ok = True)

    tokenizer = AutoTokenizer.from_pretrained(model_name, fix_mistral_regex = True)
    model = AutoModelForCausalLM.from_pretrained(model_name)

    tokenizer.save_pretrained(str(save_dir))
    model.save_pretrained(str(save_dir))

    print(f"✅ 모델과 토크나이저가 `{save_dir}`에 저장되었습니다.")


def has_local_kanana(save_dir: Path) -> bool:
    """
    로컬 모델 폴더에 필수 파일이 있는지 확인합니다.
    """
    required_files = [
        save_dir / "config.json",
        save_dir / "tokenizer_config.json",
    ]
    return all(path.exists() for path in required_files)

def ensure_kanana_model() -> None:
    """
    Config에서 model_name, save_dir를 가져와 로컬 모델 존재 여부를 확인하고 필요 시 다운로드합니다.
    """
    model_name = Config.KANANA_MODEL_NAME
    save_dir = Path(Config.KANANA_MODEL_PATH)

    print("Kanana 모델 확인 중..")
    if has_local_kanana(save_dir):
        print("✅ 모델 확인 완료")
        return

    print("로컬 모델이 없어 다운로드를 시작합니다..")
    download_kanana(model_name, save_dir)
    print("✅ Kanana 모델 준비 완료")

########################################################
### RAG용 Embedding 모델 설정 (BGE-M3)
########################################################

def download_embedding_model(model_name: str, save_dir: Path) -> None:
    """
    Hugging Face에서 Embedding 모델을 다운로드하는 함수 (최초 1회 실행).
    """
    from transformers import AutoModel, AutoTokenizer

    save_dir.mkdir(parents = True, exist_ok = True)

    tokenizer = AutoTokenizer.from_pretrained(model_name, fix_mistral_regex = True)
    model = AutoModel.from_pretrained(model_name)

    tokenizer.save_pretrained(str(save_dir))
    model.save_pretrained(str(save_dir))

    print(f"✅ 모델과 토크나이저가 `{save_dir}`에 저장되었습니다.")

def has_local_embedding_model(save_dir: Path) -> bool:
    """
    로컬 모델 폴더에 필수 파일이 있는지 확인합니다.
    """
    required_files = [
        save_dir / "config.json",
        save_dir / "tokenizer_config.json",
    ]
    return all(path.exists() for path in required_files)

def ensure_embedding_model() -> None:
    """
    Config에서 model_name, save_dir를 가져와 로컬 모델 존재 여부를 확인하고 필요 시 다운로드합니다.
    """
    model_name = Config.EMBEDDING_MODEL_NAME
    save_dir = Path(Config.EMBEDDING_MODEL_PATH)

    print("Embedding 모델 확인 중..")
    if has_local_embedding_model(save_dir):
        print("✅ 모델 확인 완료")
        return

    print("로컬 모델이 없어 다운로드를 시작합니다..")
    download_embedding_model(model_name, save_dir)
    print("✅ Embedding 모델 준비 완료")

########################################################
### RAG용 DB 설정
########################################################

def ensure_law_db() -> None:
    """
    LawDB 폴더 내 .sqlite3 파일 존재 여부를 확인하고
    없으면 src.RAG.db_main을 실행해 생성합니다.
    """
    db_path = Path("./database/LawDB")
    sqlite_files = list(db_path.glob("*.sqlite3")) if db_path.exists() else []

    print("RAG를 위한 DB 확인 중..")
    if sqlite_files:
        print("✅ DB 확인 완료")
        return

    print("LawDB가 없어 DB 생성을 시작합니다..")
    result = subprocess.run(
        [sys.executable, "-m", "src.RAG.db_main"],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("DB 생성에 실패했습니다. `src.RAG.db_main` 실행 로그를 확인해주세요.")

    print("✅ DB 확인 완료")

def ensure_env_file() -> None:
    """
    .env 파일에 Tavily API 접근을 위한 API_KEY 설정이 있는지 확인합니다.
    """
    if not Path(".env").exists():
        raise FileNotFoundError(".env 파일이 없습니다. 환경 변수를 설정해주세요.")
    
    with open(".env", "r") as f:
        for line in f:
            if "TAVILY_API_KEY" in line:
                return
    
    raise ValueError("TAVILY_API_KEY이 설정되어 있지 않습니다. .env 파일에 TAVILY_API_KEY을 설정해주세요.")



def main() -> None:
    print("초기 환경 점검을 시작합니다.")
    ensure_kanana_model()
    ensure_embedding_model()
    ensure_law_db()
    print("모든 초기 설정이 완료되었습니다.")


if __name__ == "__main__":
    main()

