import pandas as pd
from sqlalchemy import create_engine, text
import os
import requests  # requests 라이브러리 추가
from dotenv import load_dotenv
from typing import Any, Dict, List, Union
import re
import json

load_dotenv(dotenv_path=".env")
gemini_apikey = os.environ.get("GEMINI_API_KEY")
root = os.environ.get("root")

# DB 연결 설정
DB_URL = f"mysql+pymysql://root:{root}@192.168.0.32:3306/balancelab"
engine = create_engine(DB_URL)

# DB 연결 설정 (본인의 환경에 맞게 수정)
engine = create_engine(DB_URL)
session_id = "example_session"


class EnhancedQueryGenerator:
    """Gemini API를 사용한 SQL 쿼리 생성 및 결과 분석"""

    def __init__(self):
        """Gemini API 키 설정 확인"""
        if not gemini_apikey:
            raise ValueError("❌ Gemini API 키가 설정되지 않았습니다.")

        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": gemini_apikey  # .env에서 로드된 API 키 사용
        }

    

    def _call_gemini_api(self, prompt: str) -> dict:
        """Gemini API 호출 및 JSON 파싱"""
        try:
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(self.api_url, headers=self.headers, json=data)

            print("📡 상태 코드:", response.status_code)
            print("📩 응답 내용:", response.text)

            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

            result = response.json()

            try:
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("🧪 Gemini 응답 텍스트:", raw_text[:200], "...")  # 앞부분만 출력

                # 코드블럭 제거
                json_str = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip())

                # JSON 파싱
                parsed_json = json.loads(json_str)
                return parsed_json  # ✅ dict 형태로 반환

            except (KeyError, IndexError) as e:
                print(f"❌ 응답 파싱 오류: {e}")
                return {"error": "Gemini 응답 파싱 중 문제가 발생했습니다."}
            except json.JSONDecodeError as e:
                print(f"❌ JSON 디코딩 오류: {e}")
                return {"error": f"JSON 파싱 실패: {e}"}

        except requests.exceptions.RequestException as e:
            print(f"❌ Gemini API 호출 오류 (네트워크/HTTP): {e}")
            return {"error": f"Gemini API 호출 오류: {e}"}
        except Exception as e:
            print(f"❌ Gemini API 호출 오류 (기타): {str(e)}")
            return {"error": f"Gemini API 호출 오류: {e}"}
        
def process_question(foodList: List[Dict[str, Union[str, float]]]) -> str:
    """사용자의 질문을 처리하고 결과 반환"""
    try:
        # Gemini 프롬프트 생성
        prompt = f"""
        당신은 전문 영양사입니다. 사용자가 먹은 음식과 그 양을 기반으로 하루 총 영양소를 계산해 주세요.

        각 음식에 대한 입력 정보는 다음과 같습니다:
        - 음식 이름 (예: 김밥)
        - 섭취량 (예: 1)
        - 단위 (예: 줄, 개, g 등)

        ### 음식 정보 리스트
        {foodList}

        ### 당신의 역할
        - 각 음식의 영양소 정보를 검색하거나 알고 있다면 활용해서,
        - 음식마다 주어진 양과 단위를 반영한 실제 섭취량을 계산하고
        - 다음 항목의 총합을 계산해 주세요:

        - 탄수화물 (g)
        - 단백질 (g)
        - 지방 (g)
        - 당분 (g)
        - 나트륨 (mg)
        - 식이섬유 (g)
        - 수분 (g)
        - 칼로리 (kcal)

        **중요 지침:**
        - 모든 수치는 각 음식별로 출력
        - 숫자만 출력 (단위 없음)
        - JSON 형식으로 출력 (예시 참고)
        - 설명은 필요 없이, JSON 형식을 엄격히 준수

        ### 출력 예시:
        ```json
        {{
        "입력된 식단": "김밥 1줄",
        "탄수화물": 85.1,
        "단백질": 20.3,
        "지방": 10.2,
        "당분": 15.4,
        "나트륨": 720.5,
        "식이섬유": 5.2,
        "수분": 450.0,
        "칼로리": 2000
        }}
        """

        
        # Gemini API로 답변 생성
        query_generator = EnhancedQueryGenerator()
        answer = query_generator._call_gemini_api(prompt)
        print(f"🧪 Gemini 응답 내용: {answer}")
        
        
        return answer
        
    except Exception as e:
        print(f"❌ process_question 중 예외 발생: {e}")
        return f"process_question 중 오류가 발생했습니다: {str(e)}"

