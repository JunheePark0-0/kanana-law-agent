# Legal Agent: RAG 기반 법률 질의응답 에이전트

법률 질문(및 첨부 문서)을 받아 내부 법령 DB(RAG)와 웹 검색을 결합해 근거 있는 답변을 생성하는 LangGraph 기반 에이전트입니다. Kanana(kakaocorp/kanana-1.5-2.1b-instruct-2505) 모델로 추론하고, BGE-M3 임베딩과 Chroma 벡터 DB로 법령을 검색합니다.

## 주요 기능

- `src/Agent`: LangGraph 기반 멀티 스텝 워크플로우 (질의 확장 → 문서 파싱/쟁점 추출 → RAG 검색 → 컨텍스트 평가/웹 보강 → 리랭킹 → 답변 생성/검증/재생성)
- `src/RAG`: 법령 데이터 임베딩 및 Chroma 벡터 DB 구축/검색
- `main.py`: 대화형 CLI로 에이전트를 직접 실행하는 통합 진입점
- `api.py`: FastAPI 백엔드 (질문 제출 후 job_id로 비동기 상태를 폴링하는 구조)
- `orchestrator.py`: `api.py` 서버에 요청을 보내는 커맨드라인 클라이언트 예시
- `setup.py`: Kanana 모델, 임베딩 모델, 법령 벡터 DB를 최초 1회 준비하는 초기화 스크립트

## 프로젝트 구조

```text
Kanana_Law/
├── main.py              # CLI 진입점 (대화형 모드)
├── api.py                # FastAPI 서버
├── orchestrator.py       # API 서버 호출 클라이언트
├── setup.py               # 모델/DB 초기 설정 스크립트
├── config.py
├── requirements.txt
└── src/
    ├── Agent/
    │   ├── graph.py           # LangGraph 워크플로우 정의
    │   ├── nodes.py           # 각 노드 로직
    │   ├── tools.py           # RAG/웹검색/답변생성 등 실제 툴 구현
    │   ├── functions.py       # 라우팅 조건, 프롬프트 로딩 등 보조 함수
    │   ├── kanana_pipeline.py # Kanana 모델 로드 및 호출
    │   ├── schemas.py         # Pydantic 입출력 스키마
    │   ├── states.py          # LangGraph 상태 정의
    │   └── prompts.yaml       # 프롬프트 템플릿
    └── RAG/
        ├── db_main.py             # 법령 벡터 DB 생성
        ├── embedding.py           # BGE-M3 임베딩
        ├── vector_db.py           # Chroma DB 유틸
        └── search_kanana_main.py  # RAG 검색 + 재정렬
```

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

`.env` 파일에 웹 검색용 API 키를 설정합니다.

```
TAVILY_API_KEY=your_api_key
```

## 초기 설정 (최초 1회)

Kanana 모델, 임베딩 모델 다운로드와 법령 벡터 DB 생성을 자동으로 확인/수행합니다.

```bash
python setup.py
```

## CLI 실행 방법

```bash
python main.py
```

실행 후 로컬 로깅 여부를 선택하고, 대화형으로 질문(및 필요 시 문서 경로)을 입력하면 답변을 반환합니다. `quit`/`exit`/`q`로 종료합니다.

## FastAPI 백엔드

서버 실행:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

주요 엔드포인트:

- `GET /health`: 헬스 체크
- `POST /api/ask`: 질문 제출 (PDF 문서 업로드 가능), `job_id` 반환
- `GET /api/jobs/{job_id}`: 작업 상태 및 결과 조회
- `GET /api/jobs`: 전체 작업 목록 조회

커맨드라인에서 서버를 테스트하려면:

```bash
python orchestrator.py
```

## 주의사항

- 모델 추론은 로컬 환경(CPU/GPU, 메모리)에 따라 응답 시간이 크게 달라질 수 있습니다.
- `search_rag` 등 RAG 관련 툴은 `database/LawDB`에 Chroma 벡터 DB가 미리 생성되어 있어야 정상 동작합니다 (`setup.py` 참고).
