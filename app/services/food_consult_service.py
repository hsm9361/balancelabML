import pandas as pd
from sqlalchemy import create_engine, text
import os
import requests  # requests 라이브러리 추가
from dotenv import load_dotenv
from typing import Any, Dict

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

    def _call_gemini_api(self, prompt: str) -> str:
        """Gemini API 호출"""
        try:
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(self.api_url, headers=self.headers, json=data)

            print("📡 상태 코드:", response.status_code)
            print("📩 응답 내용:", response.text)

            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

            result = response.json()

            try:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                print(f"❌ 응답 파싱 오류: {e}")
                return "Gemini 응답 파싱 중 문제가 발생했습니다."

        except requests.exceptions.RequestException as e:
            print(f"❌ Gemini API 호출 오류 (네트워크/HTTP): {e}")
            return f"Gemini API 호출 오류: {e}"
        except Exception as e:
            print(f"❌ Gemini API 호출 오류 (기타): {str(e)}")
            return f"Gemini API 호출 오류: {str(e)}"

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
                (SELECT COALESCE(diabetes_proba, 0) FROM tb_predict_record 
                    WHERE member_id = m.id ORDER BY reg_date DESC LIMIT 1) AS diabetes_proba,
                (SELECT COALESCE(hypertension_proba, 0) FROM tb_predict_record 
                    WHERE member_id = m.id ORDER BY reg_date DESC LIMIT 1) AS hypertension_proba,
                (SELECT COALESCE(cvd_proba, 0) FROM tb_predict_record 
                    WHERE member_id = m.id ORDER BY reg_date DESC LIMIT 1) AS cvd_proba,
                (SELECT GROUP_CONCAT(DISTINCT food_name) FROM dailydiet_record 
                    WHERE user_id = m.id AND ins_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS recent_foods,
                (SELECT GROUP_CONCAT(DISTINCT category) FROM dailydiet_record 
                    WHERE user_id = m.id AND ins_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS category,
                (SELECT AVG(calories) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_calories,
                (SELECT AVG(protein) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_protein,
                (SELECT AVG(carbo) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_carbo,
                (SELECT AVG(fat) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_fat,
                (SELECT AVG(fibrin) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_fibrin,
                (SELECT AVG(sugar) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_sugar,
                (SELECT AVG(water) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_water,
                (SELECT AVG(sodium) FROM tb_daily_record 
                    WHERE member_id = m.id AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)) AS avg_sodium,
                goal,
                id
            FROM tb_members m
            WHERE m.email = :email
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
        
        4. 사용자 목표:
           - {health_data['goal']}

        다음 사항을 고려하여 추천해주세요:
        1. 사용자의 건강 위험도에 따른 식단 조절
        2. 부족한 영양소 보충
        3. 사용자의 목표 달성을 위한 식단 구성
        4. 최근 섭취한 음식을 고려한 다양성 확보
        5. 아침, 점심, 저녁, 간식에 대한 구체적인 추천
        6. 주의사항 및 권장사항

        추천은 다음 형식으로 작성해주세요:
        1. 건강 위험도 분석 (당뇨, 고혈압, 심혈관질환 확률이 만약 75%가 넘는다면 같이 출력)
        2. 목표 기반 추천
        3. 식단 추천 (아침, 점심, 저녁, 간식)
        4. 주의사항
        """
        
        # Gemini API로 답변 생성
        query_generator = EnhancedQueryGenerator()
        answer = query_generator._call_gemini_api(prompt)
        
        return answer
        
    except Exception as e:
        print(f"❌ process_question 중 예외 발생: {e}")
        return f"process_question 중 오류가 발생했습니다: {str(e)}"
