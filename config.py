"""
Legal Agent 설정 파일

환경변수나 직접 설정으로 Agent의 동작을 제어합니다.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path = _DOTENV_PATH)

class Config:
    """Agent 전역 설정"""
    
    # ============================================================================
    # 로깅 설정 (기본값)
    # ============================================================================
    ENABLE_LOCAL_LOGGING = False

    # ============================================================================
    # 모델 설정
    # ============================================================================
    # Kanana 모델
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    KANANA_MODEL_NAME = "kakaocorp/kanana-1.5-2.1b-instruct-2505"
    KANANA_MAX_NEW_TOKENS = int(os.getenv("KANANA_MAX_NEW_TOKENS", "1024"))
    EMBEDDING_DEVICE = "cpu"

    # ============================================================================
    # 경로 설정
    # ============================================================================
    LOG_DIR = "./logs"
    KANANA_MODEL_PATH = "./Kanana_Model"
    EMBEDDING_MODEL_PATH = f"./Embedding_Model"
    
    # ============================================================================
    # FastAPI 경로 설정
    # ============================================================================
    PORT_NUM = 8000


    @classmethod
    def get_config_summary(cls):
        """현재 설정 요약"""
        return {
            "로컬 로깅": "활성화" if cls.ENABLE_LOCAL_LOGGING else "비활성화",
            "모델": cls.KANANA_MODEL_NAME,
        }
