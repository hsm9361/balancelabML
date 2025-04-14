import gradio as gr
import pandas as pd
from langchain_community.chat_message_histories import SQLChatMessageHistory
from sqlalchemy import create_engine, text
import re  # 텍스트 패턴을 정의 (텍스트를 검색, 치환, 분리)
from typing import Dict, Any  # 타입을 명시적으로 지정하여 코드의 가독성과 안정성을 높임
import json
import os
from datetime import datetime
import requests  # requests 라이브러리 추가
from dotenv import load_dotenv

load_dotenv()
gemini_apikey = os.environ.get("GEMINI_API_KEY")
root = os.environ.get("root")

# DB 연결 설정
DB_URL = "mysql+pymysql://root:"+root+"@192.168.0.32:3306/balancelab"
engine = create_engine(DB_URL)

# DB 연결 설정 (본인의 환경에 맞게 수정)
engine = create_engine(DB_URL)
session_id = "example_session"


class EnhancedQueryGenerator:
    """Gemini API를 사용한 SQL 쿼리 생성 및 결과 분석"""

    def __init__(self):
        """Gemini API 키 설정 확인"""
        if not os.environ.get("GEMINI_API_KEY") or os.environ["GEMINI_API_KEY"] == "your-gemini-api-key-here":
            raise ValueError("❌ Gemini API 키가 설정되지 않았습니다.")

        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": os.environ["GEMINI_API_KEY"]
        }

    def generate_query(self, question: str, schema_info: str, feedback_info: str = "") -> str:
        """질문에 대한 SQL 쿼리를 Gemini API로 생성"""
        cur_time = datetime.now().strftime('%Y.%m.%d- %H:%M:%S')
        prompt = f"""
        당신은 MySQL 전문가입니다. 다음 데이터베이스 스키마를 기반으로 사용자의 질문에 적절한 SQL 쿼리를 생성하세요.

        데이터베이스 스키마 정보:
        {schema_info}

        이전 피드백 정보:|
        {feedback_info}

        질문: {question}
        
        현시각: {cur_time}

        **규칙**:
        - SQL 쿼리만 반환하세요. 설명은 필요하지 않습니다.
        - `SELECT` 문으로 시작하고 세미콜론(;)으로 끝나야 합니다.
        - SQL 인젝션 공격을 방지하기 위해 파라미터 바인딩을 사용하지 마세요.
        - 정확한 값 매칭은 `=` 연산자를 사용하세요.
        - 유사 검색은 `LIKE '%키워드%'` 형식을 사용하세요.
        - LIKE문에 모든 단어를 넣지 마세요.
        - LIKE문에 최대한 and 대신 or을 사용해 넓은 범위를 수색해주세요.
        - 날짜를 조건문에 사용할땐 date(`날짜 문자열`)이 아닌 `날짜 문자열` 그대로 사용하세요
        - 예시 쿼리:
        SELECT * FROM tsla_stock WHERE currentdate = '2010-06-29';
        - 날짜 비교 시에는 BETWEEN 연산자를 사용하고, 날짜 문자열은 작은따옴표('')로 묶으세요.
        - 날짜를 비교할 때 DATE_SUB 함수를 사용하지 마세요.
        - 서브쿼리는 되도록이면 in을 사용하세요

        결과:
        """

        response = self._call_gemini_api(prompt)
        return self._extract_sql_query(response)

    def generate_answer(self, question: str, query: str, result: any, chat_history: str="") -> str:
        """쿼리 실행 결과를 기반으로 자연어 설명을 생성"""
        cur_time = datetime.now().strftime('%Y.%m.%d- %H:%M:%S')
        if isinstance(result, pd.DataFrame):
            result_str = result.to_json(orient="records")  # DataFrame을 JSON으로 변환
        elif isinstance(result, str):  # 오류 메시지인 경우
            return result  # 오류 메시지 그대로 반환
        else:
            result_str = json.dumps(result, ensure_ascii=False)

        prompt = f"""
        사용자의 질문에 답변하세요. 이전 대화 내용을 고려하세요.

        **이전 대화 내용**:
        {chat_history}

        **질문**: {question}
        **실행된 쿼리**: {query}
        **쿼리 결과**:
        {result_str}
        **현시각**:{cur_time}

        **규칙**:
        - 이전 대화 내용에서 사용자가 언급한 정보를 우선적으로 활용하세요.
        - 이전 대화 내용에서 정보를 찾을 수 없는 경우에만 쿼리 결과를 활용하세요.
        - 결과를 자연스러운 한국어로 설명하세요.
        - 숫자 데이터가 있다면 적절한 단위를 포함하세요.
        - 결과가 없으면 이전 대화 내용을 기반으로 답변하거나, 정보가 없음을 명확히 알리세요.
        - date는 반드시 `xxxx년 xx월 xx일`로 출력하세요
        """

        return self._call_gemini_api(prompt)

    def _call_gemini_api(self, prompt: str) -> str:
        """Gemini API 호출"""
        try:
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(self.api_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"❌ Gemini API 호출 오류: {str(e)}")  # 로깅 추가
            return f"❌ Gemini API 호출 오류: {str(e)}"

    @staticmethod
    def _extract_sql_query(response: str) -> str:
        """Gemini API 응답에서 SQL 쿼리만 추출"""
        response = response.replace("```sql", "").replace("```", "").strip()
        match = re.search(r"SELECT\s+.*?\s+;", response, re.DOTALL | re.IGNORECASE)  # 더 엄격한 정규 표현식
        if match:
            return match.group(0).strip()
        else:
            print(f"❌ SQL 쿼리 추출 실패: {response}")  # 로깅 추가
            return response.strip()  # 또는 예외 발생

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

def execute_query(query):
    """SQL 쿼리 실행"""
    try:
        with engine.connect() as conn:
            result = pd.read_sql(text(query), conn)
            return result
    except Exception as e:
        print(f"❌ 쿼리 실행 중 오류 발생: {str(e)}")  # 로깅 추가
        return f"❌ 쿼리 실행 중 오류 발생: {str(e)}"

def get_user_health_data(email: str) -> str:
    """사용자의 건강 데이터와 목표를 가져와서 Gemini 프롬프트용 텍스트로 변환합니다."""
    try:
        with engine.connect() as conn:
            # 사용자의 최근 건강 예측, 식단 기록, 영양 기록, 목표를 가져오는 쿼리
            query = f"""
            WITH recent_predict AS (
                SELECT 
                    diabetes_proba,
                    hypertension_proba,
                    cardiovascular_proba,
                    reg_date
                FROM tb_predict_record
                WHERE member_id = (SELECT member_id from tb_members where email = '{email}')
                ORDER BY reg_date DESC
                LIMIT 1
            ),
            recent_diet AS (
                SELECT 
                    food_name,
                    meal_type,
                    reg_date
                FROM tb_daily_diet_record
                WHERE member_id = (SELECT member_id from tb_members where email = '{email}')
                AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
                ORDER BY reg_date DESC
            ),
            recent_nutrition AS (
                SELECT 
                    calories,
                    protein,
                    carbohydrate,
                    fat,
                    fibrin,
                    sugar,
                    water
                    reg_date
                FROM tb_daily_record
                WHERE member_id = (SELECT member_id from tb_members where email = '{email}')
                AND reg_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
                ORDER BY reg_date DESC
            ),
            user_goal AS (
                SELECT 
                    goal
                FROM tb_members
                WHERE member_id = (SELECT member_id from tb_members where email = '{email}')
            )
            SELECT 
                rp.diabetes_proba,
                rp.hypertension_proba,
                rp.cvd_proba,
                rp.reg_date as last_prediction_date,
                GROUP_CONCAT(DISTINCT rd.food_name) as recent_foods,
                GROUP_CONCAT(DISTINCT rd.meal_type) as meal_types,
                AVG(rn.calories) as avg_calories,
                AVG(rn.protein) as avg_protein,
                AVG(rn.carbohydrate) as avg_carbohydrate,
                AVG(rn.fat) as avg_fat,
                ug.goal
            FROM recent_predict rp
            CROSS JOIN recent_diet rd
            CROSS JOIN recent_nutrition rn
            CROSS JOIN user_goal ug
            GROUP BY rp.diabetes_proba, rp.hypertension_proba, rp.cvd_proba, rp.created_at, ug.goal;
            """

            result = pd.read_sql(text(query), conn)
            if result.empty:
                return "사용자 데이터를 찾을 수 없습니다."
            
            data = result.iloc[0]
            return data
    except Exception as e:
        print(f"❌ 사용자 데이터 조회 중 오류 발생: {str(e)}")
        return f"데이터 조회 중 오류가 발생했습니다: {str(e)}"
    
def healthdata_to_text(email: str) -> str:     
    data = get_user_health_data(email)
    # Gemini 프롬프트용 텍스트 생성
    health_data_text = f"""
    사용자의 건강 데이터:
    1. 건강 위험도:
        - 당뇨병 위험도: {data['diabetes_proba']}
        - 고혈압 위험도: {data['hypertension_proba']}
        - 심혈관질환 위험도: {data['cvd_proba']}
    
    2. 최근 식단:
        - 섭취한 음식: {data['recent_foods']}
        - 식사 유형: {data['meal_types']}
    
    3. 영양소 섭취량 (평균):
        - 칼로리: {data['avg_calories']} kcal
        - 단백질: {data['avg_protein']}g
        - 탄수화물: {data['avg_carbohydrate']}g
        - 지방: {data['avg_fat']}g
        - 수분: {data['avg_fat']}g
    
    4. 사용자 목표:
        - {data['goal']}
    """
    
    return health_data_text
            
    

def process_question(question:str, email:str) ->str:
    """사용자의 질문을 처리하고 결과 반환"""
    query_generator = EnhancedQueryGenerator()
    
    # 사용자 건강 데이터 가져오기
    health_data = healthdata_to_text(email)
    
    # Gemini 프롬프트 생성
    prompt = f"""
    당신은 전문 영양사입니다. 다음 사용자의 건강 데이터를 바탕으로 맞춤형 식단을 추천해주세요.

    {health_data}

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
    answer = query_generator._call_gemini_api(prompt)
    
    return answer
