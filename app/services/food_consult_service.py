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
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0
                }
            }
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


def get_user_health_data(id: float) -> Dict[str, Any]:
    """사용자의 건강 데이터와 목표를 가져옵니다."""
    try:
        with engine.connect() as conn:
            query = text("""
            SELECT 
                COALESCE(pr.diabetes_proba, 0) AS diabetes_proba,
                COALESCE(pr.hypertension_proba, 0) AS hypertension_proba,
                COALESCE(pr.cvd_proba, 0) AS cvd_proba,
                GROUP_CONCAT(DISTINCT dr.food_name) AS recent_foods,
                GROUP_CONCAT(DISTINCT dr.meal_time) AS meal_time,
                SUM(dr.calories) AS total_calories,
                SUM(dr.protein) AS total_protein,
                SUM(dr.carbohydrates) AS total_carbo,
                SUM(dr.fat) AS total_fat,
                SUM(dr.fiber) AS total_fibrin,
                SUM(dr.sugar) AS total_sugar,
                SUM(dr.water) AS total_water,
                SUM(dr.sodium) AS total_sodium,
                COUNT(DISTINCT DATE(dr.consumed_date)) AS days_count,
                m.age,
                m.activity_level,
                m.gender,
                m.height,
                m.weight,
                m.id,
                c.end_date AS end_date,
                c.goal AS goal,
                c.target_weight AS target_weight
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
                LEFT JOIN tb_food_record dr 
                    ON dr.member_id = m.id 
                    AND dr.consumed_date >= DATE_SUB(NOW(), INTERVAL 1 WEEK)
                LEFT JOIN challenge c
                    ON c.member_id = m.id
                    AND c.is_completed = 0
                WHERE m.id = :id
                GROUP BY m.id, m.goal_weight, pr.diabetes_proba, pr.hypertension_proba, pr.cvd_proba, 
                        c.end_date, c.goal, c.target_weight;
                """)
            
            result = pd.read_sql(query, conn, params={"id": id})
            
            if result.empty:
                return {"error": "사용자 데이터를 찾을 수 없습니다."}
            
            # SQL에서 합계를 구한 후 파이썬에서 평균 계산
            data = result.iloc[0].to_dict()
            print("health_data", data)
            
            # 일수로 나누어 평균 계산
            days_count = data.get('days_count', 1)  # 기본값 1로 설정하여 0으로 나누는 오류 방지
            if days_count > 0:
                data['avg_calories'] = data['total_calories'] / days_count
                data['avg_protein'] = data['total_protein'] / days_count
                data['avg_carbo'] = data['total_carbo'] / days_count
                data['avg_fat'] = data['total_fat'] / days_count
                data['avg_fibrin'] = data['total_fibrin'] / days_count
                data['avg_sugar'] = data['total_sugar'] / days_count
                data['avg_water'] = data['total_water'] / days_count
                data['avg_sodium'] = data['total_sodium'] / days_count
            
            # 필요 없는 키 제거
            for key in ['total_calories', 'total_protein', 'total_carbo', 'total_fat', 
                       'total_fibrin', 'total_sugar', 'total_water', 'total_sodium', 'days_count']:
                if key in data:
                    del data[key]
                    
            return data
            
    except Exception as e:
        print(f"❌ 사용자 데이터 조회 중 오류 발생: {str(e)}")
        return {"error": f"데이터 조회 중 오류가 발생했습니다: {str(e)}"}
    
def calculate_tdee(weight, height, age, gender, activity_level):
    # Mifflin-St Jeor 공식 (남성)
    if gender.lower() == 'male':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    # Mifflin-St Jeor 공식 (여성)
    elif gender.lower() == 'female':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    else:
        return None

    activity_factors = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9
    }
    factor = activity_factors.get(activity_level.lower())
    if factor is None:
        return None

    tdee = bmr * factor
    return tdee

def process_goal(id:float) -> str:
    """사용자의 질문을 처리하고 결과 반환"""
    try:
        # 사용자 건강 데이터 가져오기
        health_data = get_user_health_data(id)
        
        if isinstance(health_data, dict) and "error" in health_data:
            return health_data["error"]
        
        # health_data 내용 검증
        if not all(key in health_data for key in ['weight', 'height']):
            return "사용자 정보가 누락되었습니다."
        
        tdee_value = calculate_tdee(
            health_data['weight'],
            health_data['height'],
            health_data['age'],
            health_data['gender'],
            health_data['activity_level']
        )
        
        # Gemini 프롬프트 생성
        prompt = f"""
        당신은 전문 영양사입니다. 다음 사용자의 건강 데이터를 바탕으로 맞춤형 목표 영양소를 설정해주세요.

        사용자의 건강 데이터:
        1. 사용자 정보:
           - 현재 나이: {health_data['age']}
           - 현재 성별: {health_data['gender']}
           - 현재 키: {health_data['height']}cm
           - 현재 체중: {health_data['weight']}kg
           - TDEE 기반 예측 칼로리 소모량: {tdee_value:.2f} kcal
        
        2. 사용자 챌린지
           - 목표체중: {health_data['target_weight']}
           - 챌린지 종료 날짜: {health_data['end_date']}

        다음 사항을 고려하여 추천해주세요:
        1. 사용자 정보를 통해 tdee 기반 예측 칼로리 소모량을 확인
        2. 현재 체중과 목표 체중 비교
        3. 목표 체중 도달을 챌린지 종료 날짜까지 도달하기 위해 섭취해야 할 칼로리
        4. 건강한 체중 조절을 위한 탄/단/지 의 조합
        5. tdee는 제공된 tdee 기반 칼로리 소모량을 그대로 넣으시오
        
        !!!
        다음 형식으로 응답을 **반드시 .json형식**으로 작성해주세요.
        
        ### 출력 예시:
        ```json
        {{
            "tdee":2500,
            "calories": 2200,
            "carb": 300,
            "protein": 112,
            "fat": 50
        }}
        """
        
        query_generator = EnhancedQueryGenerator()
        answer = query_generator._call_gemini_api(prompt)
        print(f"🧪 Gemini 응답 내용: {answer}")
        
        return answer
        
    except Exception as e:
        print(f"❌ process_goal 중 예외 발생: {e}")
        return f"process_goal 중 오류가 발생했습니다: {str(e)}"
    

def process_question(id: float) -> str:
    """사용자의 질문을 처리하고 결과 반환"""
    try:
        # 사용자 건강 데이터 가져오기
        health_data = get_user_health_data(id)
        
        if isinstance(health_data, dict) and "error" in health_data:
            return health_data["error"]
        
        # health_data 내용 검증
        required_keys = ['activity_level', 'gender', 'weight', 'height', 'age']
        
        if not all(key in health_data and health_data[key] is not None for key in required_keys):
            missing_info = [key for key in required_keys if key not in health_data or health_data[key] is None]
            return {"error": f"필수 사용자 정보가 누락되었습니다 (키, 몸무게 등 개인정보를 먼저 입력해 주세요!)"}
        
        tdee_value = calculate_tdee(
            health_data['weight'],
            health_data['height'],
            health_data['age'],
            health_data['gender'],
            health_data['activity_level']
        )
        
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
        
        3. 영양소 섭취량 (최근 일주일 평균):
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
           - 현재 키: {health_data['height']}cm
           - 현재 체중: {health_data['weight']}kg
           - TDEE 기반 예측 칼로리 소모량: {tdee_value:.2f} kcal
        
        5. 사용자 챌린지
           - 목표체중(목표가 체중변화일때): {health_data['target_weight']}
           - 목표날짜: {health_data['end_date']}

        다음 사항을 고려하여 추천해주세요:
        1. 사용자의 건강 위험도에 따른 식단 조절
        2. 부족한 영양소 보충
        3. 사용자 챌린지를 기반으로 목표 체중을 목표 날짜까지 도달하기 위한 칼로리를 계산 (사용자 챌린지에 내용이 없으면 챌린지를 하도록 권유)
        4. 건강한 체중조절을 위한 건강한 식단으로 추천
        5. 최근 섭취한 음식을 고려한 다양성 확보
        6. 아침, 점심, 저녁, 간식에 대한 구체적인 추천
        7. 주의사항 및 권장사항
        
        !!!
        다음 형식으로 응답을 **반드시 .json형식**으로 작성해주세요.
        
        ```json
        {{
            "건강 위험도 분석": "여기에 건강 위험도 분석 결과 작성"(위험도는 %로 출력하고 30%이하는 확률 낮음, 60%까지는 주의, 그 이상은 위험으로 출력 / 저장된 내용이 없으면 예측 권장),
            "목표 기반 추천": "사용자 챌린지를 기반으로 목표 체중을 목표 날짜까지 도달하기 위한 칼로리를 계산 (사용자 챌린지에 내용이 없으면 챌린지를 하도록 권유),
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
