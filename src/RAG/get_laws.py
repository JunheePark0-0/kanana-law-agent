"""
법령 수집: 실제 필요한 법령이 무엇인지 LLM으로 판단하고, 국가법령정보센터 API로 법령 원문을 가져온다.
"""
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class GetAnswersLLM:
    """금융 관련 질문에 답하면서, 근거로 쓰인 법령명/조항을 함께 추출"""

    def __init__(self, llm: str):
        """llm : 'gpt' or 'solar'"""
        self.llm = llm
        self.system_prompt = (
            "당신은 금융 전문가입니다. 사용자의 질문에 대해 정확하고 책임감 있게 답변하세요.\n"
            "만약 질문을 해결하는 데 특정 법률(예: 개인정보 보호법 등)이 필요하다면, 해당 법률명과 관련 조항을 명시하세요.\n"
            "응답은 반드시 다음 JSON 형식을 따르세요:\n"
            "{\n"
            '  "Answer": "...",\n'
            '  "Laws": "...",\n'
            '  "Laws_YN": "..."\n'
            "}\n"
            "JSON 형식의 각 항목에 대한 설명은 다음과 같습니다:\n"
            "Answer 란에는 정답을 입력합니다.\n"
            "Laws 란에는 정답을 찾는 과정에서 사용된 법률 및 조항을 명시합니다. (제 O조 제 O항)\n"
            "Laws_YN 란에는 정답을 찾는 과정에서 법률이 사용되었는지 여부를 나타냅니다. (Yes, No 로 명시)\n"
            "응답은 반드시 위 JSON 형식 그대로만 출력해야 합니다. JSON 외의 추가 텍스트나 설명은 절대 포함하지 마세요."
        )

    def get_api(self) -> str:
        if self.llm == "solar":
            api_key = os.environ.get("SOLAR_API_KEY")
            if not api_key:
                raise EnvironmentError("SOLAR_API_KEY not found in .env")
            return api_key
        if self.llm == "gpt":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY not found in .env")
            return api_key
        raise ValueError(f"Unknown llm: {self.llm}")

    def get_client(self) -> OpenAI:
        api = self.get_api()
        if self.llm == "solar":
            return OpenAI(api_key=api, base_url="https://api.upstage.ai/v1")
        return OpenAI(api_key=api)

    def get_rules(self, question: str) -> str:
        client = self.get_client()
        model_name = "solar-pro2" if self.llm == "solar" else "gpt-4o-mini"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content

    def update_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """질문 목록을 받아 관련 법령명/조항을 채워 넣은 DataFrame 반환"""
        for idx in range(len(data)):
            question = data.loc[idx, "Question"]
            response = self.get_rules(question)
            try:
                parsed = json.loads(response)
            except json.JSONDecodeError:
                parsed = {"Answer": None, "Laws": None, "Laws_YN": None}
            data.loc[idx, "Answer"] = parsed.get("Answer")
            data.loc[idx, "Laws"] = parsed.get("Laws")
            data.loc[idx, "Laws_YN"] = parsed.get("Laws_YN")
        return data


def get_law(laws_org) -> Optional[str]:
    """'개인정보 보호법 제32조...' 같은 문자열에서 '~법/법률' 이름만 추출"""
    if not isinstance(laws_org, str):
        return None
    pattern = re.compile(r"(?:「)?([가-힣\s]+법(?:률)?)(?:」)?")
    matched = pattern.search(laws_org)
    return matched.group(1) if matched else None


class FetchLaws:
    """법령명으로 국가법령정보센터 Open API에서 법령 원문(JSON)을 가져온다"""

    def __init__(self):
        self.API = os.environ.get("LAW_API_OC", "")
        self.PAGE = "http://www.law.go.kr/DRF"

    def fetch_law_id(self, i: int, law_name: str) -> Optional[dict]:
        """법 이름 하나 받아서 법 정보 반환. 정확히 일치하는 항목이 없으면 검색 1순위로 대체"""
        url = (
            f"{self.PAGE}/lawSearch.do?OC={self.API}&target=law&type=JSON"
            f"&query={urllib.parse.quote(law_name)}&display=10&search=1"
        )
        contents = requests.get(url, timeout=15)
        contents.raise_for_status()
        items = contents.json().get("LawSearch", {}).get("law", [])
        if isinstance(items, dict):
            items = [items]

        if not items:
            print(f"❌ [{i}. {law_name}] 매칭 실패..")
            return None

        for item in items:
            if item.get("법령명한글") == law_name:
                print(f"✅ [{i}. {law_name}] 매칭 완료 !")
                return {"ID": item.get("법령ID"), "MST": item.get("법령일련번호"), "law": item.get("법령명한글")}

        print(f"🔁 [{i}. {law_name}] -> [{items[0].get('법령명한글')}](으)로 대체..")
        return {"ID": items[0].get("법령ID"), "MST": items[0].get("법령일련번호"), "law": items[0].get("법령명한글")}

    def fetch_law_text(self, law_id: str) -> dict:
        """법 ID 받아서 법 본문(조/항/호/목 구조) 반환"""
        url = f"{self.PAGE}/lawService.do"
        params = {"OC": self.API, "target": "law", "ID": law_id, "type": "JSON"}
        contents = requests.get(url, params=params, timeout=20)
        contents.raise_for_status()
        return contents.json()


if __name__ == "__main__":
    # 금융보안원 AI Challenge 테스트 문항에서 실제로 필요한 법령을 뽑아 최종 목록으로 정리
    laws_to_fetch = [
        "개인정보 보호법", "국가보안법", "지능정보화 기본법",
        "금융소비자 보호에 관한 법률", "금융위원회의 설치 등에 관한 법률",
        "금융회사의 지배구조에 관한 법률", "민법", "보험업법", "상호저축은행법",
        "신용정보의 이용 및 보호에 관한 법률", "신용협동조합법", "여신전문금융업법",
        "은행법", "자본시장과 금융투자업에 관한 법률", "전기통신사업법", "전자금융거래법",
        "전자문서 및 전자거래 기본법", "전자서명법", "전자정부법", "정보통신기반 보호법",
        "정보통신망 이용촉진 및 정보보호 등에 관한 법률", "주민등록법", "청소년 보호법",
        "클라우드컴퓨팅 발전 및 이용자 보호에 관한 법률",
        "특정 금융거래정보의 보고 및 이용 등에 관한 법률", "한국은행법",
        "한국자산관리공사 설립 등에 관한 법률", "형법", "주택임대차보호법",
        "부동산 실권리자명의 등기에 관한 법률", "부동산 거래신고 등에 관한 법률",
        "소득세법", "상속세 및 증여세법", "조세특례제한법", "근로기준법",
        "근로자퇴직급여 보장법", "예금자보호법", "대부업 등의 등록 및 금융이용자 보호에 관한 법률",
        "이자제한법", "약관의 규제에 관한 법률", "상법", "채권의 공정한 추심에 관한 법률",
        "국민건강보험법", "산업재해보상보험법", "고용보험법", "국민연금법",
        "자동차손해배상 보장법", "교통사고처리 특례법", "화재로 인한 재해보상과 보험가입에 관한 법률",
        "재난 및 안전관리 기본법", "우체국예금ㆍ보험에 관한 법률", "새마을금고법", "농업협동조합법",
    ]

    fetcher = FetchLaws()
    out_dir = Path("data/Laws/Raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, law_name in enumerate(laws_to_fetch, 1):
        meta = fetcher.fetch_law_id(i, law_name)
        if meta is None:
            continue
        law_id = meta.get("ID")
        contents = fetcher.fetch_law_text(law_id)
        with open(out_dir / f"{meta.get('law')}.json", "w", encoding="utf-8") as f:
            json.dump(contents, f, ensure_ascii=False, indent=4)
