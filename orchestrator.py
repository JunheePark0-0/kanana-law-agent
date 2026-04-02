import requests
import time
from pathlib import Path

# Law Agent API
ASK_URL = "http://localhost:8000/api/ask"

print("=" * 60)
print("⚖️  Legal Agent - 클라이언트")
print("=" * 60)

user_query = input("법률 관련 질문을 입력해주세요 (없으면 Enter): ").strip()
document_input = input("분석할 문서 경로를 입력해주세요 (없으면 Enter): ").strip()

if not user_query and not document_input:
    print("❌ 질문 또는 문서 중 하나 이상 입력해야 합니다.")
    exit(1)

# multipart/form-data 구성
data = {}
files = {}

if user_query:
    data["query"] = user_query

if document_input:
    doc_path = Path(document_input)
    if not doc_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {document_input}")
        exit(1)
    files["document"] = (doc_path.name, open(doc_path, "rb"), "application/octet-stream")

try:
    print("\n📤 에이전트에 요청을 전송 중...")
    response = requests.post(ASK_URL, data=data, files=files if files else None)
    response.raise_for_status()

    resp_json = response.json()
    job_id = resp_json.get("job_id")
    print(f"✅ Job ID : {job_id}")
    print(f"   상태   : {resp_json.get('status')}")

    status_url = f"http://localhost:8000/api/jobs/{job_id}"
    print("\n⏳ 에이전트가 응답을 준비 중입니다. 잠시만 기다려주세요...\n")

    while True:
        res = requests.get(status_url)
        result = res.json()
        status = result.get("status")

        if status == "done":
            answer_data = result.get("result", {})
            print("\n✨ 답변 생성이 완료되었습니다!")
            print("=" * 60)
            print(answer_data.get("answer", ""))
            print("=" * 60)

            risk = answer_data.get("risk_summary", "")
            if risk:
                print(f"\n⚠️  리스크 요약: {risk}")

            sources = answer_data.get("sources", [])
            if sources:
                print("\n📚 참고 출처:")
                for i, src in enumerate(sources, 1):
                    print(f"  [{i}] {src}")
            break

        elif status == "error":
            print(f"\n❌ 에러 발생: {result.get('error')}")
            break

        else:
            print(f"  현재 상태: {status}...", end="\r")
            time.sleep(2)

except requests.exceptions.ConnectionError:
    print("\n❌ 서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인하세요.")
    print("   실행 방법: uvicorn api:app --host 0.0.0.0 --port 8000")
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
finally:
    # 열려 있는 파일 핸들 닫기
    for _, file_tuple in files.items():
        try:
            file_tuple[1].close()
        except Exception:
            pass