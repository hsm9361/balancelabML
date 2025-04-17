import pandas as pd
from sqlalchemy import create_engine, text
import os
import requests  # requests 라이브러리 추가
from dotenv import load_dotenv
from typing import Any, Dict
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


# 쿼리 결과 반환
def get_schema_info():
    """DB 스키마 정보 가져오기"""
    with engine.connect() as conn:
        tables = pd.read_sql("SHOW TABLES", conn)
        schema_info = []

        for table in tables.iloc[:, 0]:
            columns = pd.read_sql(f"DESCRIBE {table}", conn)
            schema_info.append(f"테이블: {table}")
            schema_info.append("컬럼:")
            for _, row in columns.iterrows():
                schema_info.append(f"- {row['Field']} ({row['Type']})")
            schema_info.append("")

        return "\n".join(schema_info)

def get_user_health_data(email: str) -> Dict[str, Any]:
    """사용자의 건강 데이터와 목표를 가져옵니다."""
    try:
        with engine.connect() as conn:
            query = text("""
            SELECT 
                COALESCE(pr.diabetes_proba, 0) AS diabetes_proba,
                COALESCE(pr.hypertension_proba, 0) AS hypertension_proba,
                COALESCE(pr.cvd_proba, 0) AS cvd_proba,
                GROUP_CONCAT(DISTINCT dr.food_name) AS recent_foods,
                GROUP_CONCAT(DISTINCT dr.category) AS category,
                AVG(tr.calories) AS avg_calories,
                AVG(tr.protein) AS avg_protein,
                AVG(tr.carbo) AS avg_carbo,
                AVG(tr.fat) AS avg_fat,
                AVG(tr.fibrin) AS avg_fibrin,
                AVG(tr.sugar) AS avg_sugar,
                AVG(tr.water) AS avg_water,
                AVG(tr.sodium) AS avg_sodium,
                m.age,
                m.gender,
                m.height,
                m.weight,
                m.goal,
                m.id
            FROM tb_members m
            LEFT JOIN (
                SELECT member_id, diabetes_proba, hypertension_proba, cvd_proba
                FROM tb_predict_record
                WHERE (member_id, reg_date) IN (
                    SELECT member_id, MAX(reg_date)
                    FROM tb_predict_record
                    GROUP BY member_id
                )
            ) pr ON pr.member_id = m.id
            LEFT JOIN dailydiet_record dr 
                ON dr.user_id = m.id 
                AND dr.ins_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
            LEFT JOIN tb_daily_record tr 
                ON tr.member_id = m.id 
                AND tr.reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
            WHERE m.email = :email
            GROUP BY m.id, m.goal, pr.diabetes_proba, pr.hypertension_proba, pr.cvd_proba;
            """)
            
            result = pd.read_sql(query, conn, params={"email": email})
            
            if result.empty:
                return {"error": "사용자 데이터를 찾을 수 없습니다."}
            
            return result.iloc[0].to_dict()
            
    except Exception as e:
        print(f"❌ 사용자 데이터 조회 중 오류 발생: {str(e)}")
        return {"error": f"데이터 조회 중 오류가 발생했습니다: {str(e)}"}

def process_question(question: str, email: str) -> str:
    """사용자의 질문을 처리하고 결과 반환"""
    try:
        # 사용자 건강 데이터 가져오기
        health_data = get_user_health_data(email)
        
        if isinstance(health_data, dict) and "error" in health_data:
            return health_data["error"]
        
        # health_data 내용 검증
        if not all(key in health_data for key in ['diabetes_proba', 'goal']):
            return "건강 데이터에 필요한 정보가 누락되었습니다."
        
        # Gemini 프롬프트 생성
        prompt = f"""
        당신은 전문 영양사입니다. 다음 사용자의 건강 데이터를 바탕으로 맞춤형 식단을 추천해주세요.

        사용자의 건강 데이터:
        1. 건강 위험도:
           - 당뇨병 위험도: {health_data['diabetes_proba']}
           - 고혈압 위험도: {health_data['hypertension_proba']}
           - 심혈관질환 위험도: {health_data['cvd_proba']}
        
        2. 최근 식단:
           - 섭취한 음식: {health_data['recent_foods']}
           - 식사 유형: {health_data['category']}
        
        3. 영양소 섭취량 (평균):
           - 칼로리: {health_data['avg_calories']} kcal
           - 단백질: {health_data['avg_protein']}g
           - 탄수화물: {health_data['avg_carbo']}g
           - 지방: {health_data['avg_fat']}g
           - 수분: {health_data['avg_water']}g
           - 당: {health_data['avg_sugar']}g
           - 섬유질: {health_data['avg_fibrin']}g
        
        4. 사용자 정보:
           - 현재 나이: {health_data['age']}
           - 현재 성별: {health_data['gender']}
           - 현재 키: {health_data['height']}
           - 현재 체중: {health_data['weight']}
           - 목표 체중: {health_data['goal']}

        다음 사항을 고려하여 추천해주세요:
        1. 사용자의 건강 위험도에 따른 식단 조절
        2. 부족한 영양소 보충
        3. 사용자의 현재 몸무게에서 목표 몸무게로 향하기 위한 식단 구성
        4. 최근 섭취한 음식을 고려한 다양성 확보
        5. 아침, 점심, 저녁, 간식에 대한 구체적인 추천
        6. 주의사항 및 권장사항
        
        !!!
        다음 형식으로 응답을 **반드시 .json형식**으로 작성해주세요.
        
        ```json
        {{
            "건강 위험도 분석": "여기에 건강 위험도 분석 결과 작성"(위험도는 %로 출력하고 33%이하는 확률 낮음, 66%까지는 주의, 그 이상은 위험으로 출력 / 저장된 내용이 없으면 예측 권장),
            "목표 기반 추천": "여기에 목표 체중을 위한 식단",
            "식단 추천": {{
                "아침": ["추천 1", "추천 2", ...],
                "점심": ["추천 1", "추천 2", ...],
                "저녁": ["추천 1", "추천 2", ...],
                "간식": ["추천 1", "추천 2", ...]
            }},
            "주의사항": "여기에 주의사항 작성"
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
