"""
Legal Agent FastAPI 서버

실행 방법:
    cd Kanana_Law
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

엔드포인트:
    GET  /              - API 정보
    GET  /health        - 헬스 체크
    POST /api/ask       - 질문 제출 (파일 업로드 포함 가능), job_id 반환
    GET  /api/jobs/{id} - 작업 상태 및 결과 조회
    GET  /api/jobs      - 전체 작업 목록 조회
"""

import os
import uuid
import shutil
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Literal
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import Config
PORT_NUM = Config.PORT_NUM
from src.Agent.schemas import UserInput, AnswerOutput
from src.Agent.kanana_pipeline import get_kanana_pipeline

# ============================================================================
# 업로드 파일 저장 경로 
# ============================================================================
UPLOAD_DIR = Path("./uploads") # 사용자가 올린 PDF 파일을 임시로 저장할 폴더 경로
UPLOAD_DIR.mkdir(parents = True, exist_ok = True) 

# ============================================================================
# 작업(Job) 저장소 (인메모리)
# ============================================================================
jobs: dict[str, dict] = {} # 현재 진행 중인 질문의 상태 (대기, 실행 중, 완료) + 결과값

# ============================================================================
# 스레드 풀 (에이전트는 동기 코드이므로 별도 스레드에서 실행)
# ============================================================================
executor = ThreadPoolExecutor(max_workers = 2) # 에이전트가 답변을 만드는 동안 서버가 멈추지 않도록 함 (별도 작업실 2개)

# ============================================================================
# FastAPI 앱 초기화
# ============================================================================
app = FastAPI(
    title = "Legal Agent API",
    description = "Kanana 기반 법률 AI 에이전트 API",
    version = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)


# ============================================================================
# 응답 스키마
# ============================================================================
class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class AskResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ============================================================================
# 에이전트 실행 함수 (동기, 스레드에서 실행)
# ============================================================================
def _run_agent(job_id: str, query: Optional[str], document_path: Optional[str]):
    """백그라운드 스레드에서 에이전트를 실행하고 jobs 딕셔너리를 업데이트합니다."""
    from main import legal_agent  # 순환 import 방지를 위해 지연 import

    jobs[job_id]["status"] = "running"

    try:
        agent = legal_agent()

        original_input = UserInput(
            query = query if query else None,
            document_path = document_path if document_path else None,
        )

        result = agent.invoke({
            "original_input": original_input,
            "input_query": query if query else "",
        })

        # 에러 처리
        if result.get("input_type") == "Error":
            error_msg = result.get("error_message", "알 수 없는 오류가 발생했습니다.")
            jobs[job_id].update({
                "status": "error",
                "error": error_msg,
                "completed_at": datetime.now().isoformat(),
            })
            return

        # 정상 응답 처리
        answer_obj: Optional[AnswerOutput] = result.get("answer")
        if answer_obj:
            jobs[job_id].update({
                "status": "done",
                "completed_at": datetime.now().isoformat(),
                "result": {
                    "answer": answer_obj.answer,
                    "sources": answer_obj.source,
                    "metadata":
                    {
                        "input_type": answer_obj.input_type,
                        "risk_summary": answer_obj.risk_summary,
                        "confidence_score": answer_obj.confidence_score,
                },
            }
            })
        else:
            jobs[job_id].update({
                "status": "error",
                "error": "에이전트가 응답을 생성하지 못했습니다.",
                "completed_at": datetime.now().isoformat(),
            })

    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error": str(e),
            "completed_at": datetime.now().isoformat(),
        })
    finally:
        # 업로드된 임시 파일 삭제
        if document_path and Path(document_path).exists():
            try:
                Path(document_path).unlink()
            except Exception:
                pass


# ============================================================================
# 라우터
# ============================================================================
@app.get("/", tags = ["일반"])
async def root():
    """API 정보를 반환합니다."""
    return {
        "name": "Legal Agent API",
        "version": "1.0.0",
        "description": "Kanana 기반 법률 AI 에이전트",
        "endpoints": {
            "POST /api/ask": "질문 제출 (파일 업로드 가능)",
            "GET /api/jobs/{job_id}": "작업 상태 및 결과 조회",
            "GET /api/jobs": "전체 작업 목록 조회",
            "GET /health": "헬스 체크",
        },
    }


@app.get("/health", tags = ["일반"])
async def health_check():
    """서버 상태를 확인합니다."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/ask", response_model = AskResponse, tags = ["에이전트"])
async def ask(
    background_tasks: BackgroundTasks,
    query: Optional[str] = Form(None, description = "법률 관련 질문"),
    document: Optional[UploadFile] = File(None, description = "분석할 PDF 문서 (선택)"),
):
    """
    법률 질문을 에이전트에 제출합니다.

    - **query**: 텍스트 질문 (문서만 첨부할 경우 생략 가능)
    - **document**: PDF 파일 (선택)

    응답으로 `job_id`를 반환하며, `GET /api/jobs/{job_id}`로 결과를 폴링하세요.
    """
    if not query and not document:
        raise HTTPException(
            status_code = 400,
            detail = "query 또는 document 중 하나 이상을 제공해야 합니다.",
        )

    job_id = str(uuid.uuid4()) # 각 질문에 대해 고유한 ID 생성
    document_path: Optional[str] = None

    # 파일 업로드 처리
    if document:
        suffix = Path(document.filename).suffix if document.filename else ".pdf"
        file_path = UPLOAD_DIR / f"{job_id}{suffix}"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(document.file, f)
        document_path = str(file_path)

    # 작업 등록
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }

    # 백그라운드 스레드에서 에이전트 실행
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        _run_agent,
        job_id,
        query,
        document_path,
    )

    return AskResponse(
        job_id = job_id,
        status = "pending",
        message = f"작업이 등록되었습니다. GET /api/jobs/{job_id} 로 결과를 확인하세요.",
    )


@app.get("/api/jobs/{job_id}", response_model = JobStatusResponse, tags = ["에이전트"])
async def get_job(job_id: str):
    """
    작업 상태와 결과를 조회합니다.

    - **status**: `pending` → `running` → `done` / `error`
    - **result**: 완료 시 답변 정보 포함
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"job_id '{job_id}'를 찾을 수 없습니다.")
    return jobs[job_id]


@app.get("/api/jobs", tags=["에이전트"])
async def list_jobs():
    """
    전체 작업 목록과 상태를 반환합니다.
    """
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j["job_id"],
                "status": j["status"],
                "created_at": j["created_at"],
                "completed_at": j["completed_at"],
            }
            for j in jobs.values()
        ],
    }


# ============================================================================
# 서버 시작 시 모델 사전 로드
# ============================================================================
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 Kanana 모델을 사전 로드합니다."""
    loop = asyncio.get_event_loop()
    print("🔄 Kanana 모델 사전 로드 중... (처음 실행 시 몇 분 소요될 수 있습니다)")
    await loop.run_in_executor(executor, get_kanana_pipeline)
    print("✅ Kanana 모델 로드 완료 — API 서버 준비!")


# ============================================================================
# 직접 실행 시
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host = "0.0.0.0", port = PORT_NUM, reload = False)
