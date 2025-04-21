import platform
import os
import json
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# 환경 변수 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_IMAGE_DIR = os.getenv("ALLOWED_IMAGE_DIR")

def get_upload_path(upload_dir='uploads') -> Path:
    home_dir = Path.home()
    upload_path = home_dir / upload_dir
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

# 운영 체제별 기본 경로 설정
if not ALLOWED_IMAGE_DIR:
    if platform.system() == "Windows":
        ALLOWED_IMAGE_DIR = get_upload_path()
    else:  # macOS, Linux
        ALLOWED_IMAGE_DIR = get_upload_path()
else:
    ALLOWED_IMAGE_DIR = Path(ALLOWED_IMAGE_DIR)

# ALLOWED_IMAGE_DIR 처리
ALLOWED_IMAGE_DIR = ALLOWED_IMAGE_DIR.resolve()
if not ALLOWED_IMAGE_DIR.exists():
    ALLOWED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
if not ALLOWED_IMAGE_DIR.is_dir():
    raise ValueError(f"ALLOWED_IMAGE_DIR은 디렉토리가 아닙니다: {ALLOWED_IMAGE_DIR}")

print(f"Using ALLOWED_IMAGE_DIR: {ALLOWED_IMAGE_DIR}")

# Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# 파일 경로 검증
def validate_file_path(file_path: str) -> str:
    try:
        input_path = Path(file_path)
        if not input_path.is_absolute():
            input_path = (Path.cwd() / input_path).resolve()
        else:
            input_path = input_path.resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"파일 {file_path}을 찾을 수 없습니다.")
        if not input_path.is_file():
            raise ValueError(f"{file_path}은 파일이 아닙니다.")
        if input_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            raise ValueError("지원되지 않는 파일 형식입니다. JPG 또는 PNG만 허용됩니다.")
        return str(input_path)
    except Exception as e:
        raise ValueError(f"파일 경로 검증 실패: {str(e)}")

# 식단 분석 함수
def analyze_meal(file_path: str) -> dict:
    # 파일 경로 검증
    file_path = validate_file_path(file_path)

    # 이미지 열기
    try:
        image = Image.open(file_path)
        image.verify()
        image = Image.open(file_path)
    except Exception as e:
        raise ValueError(f"유효하지 않은 이미지 파일입니다: {str(e)}")

    # 음식인지 확인하는 프롬프트
    is_food_prompt = """
    이 이미지가 음식을 포함하고 있는지 확인해 주세요.
    음식이 포함되어 있으면 "Yes"를, 그렇지 않으면 "No"를 반환해 주세요.
    다른 텍스트나 코멘트는 포함시키지 마세요.
    """
    try:
        is_food_response = model.generate_content([is_food_prompt, image])
        is_food_text = is_food_response.text.strip()
        if is_food_text == "No":
            return {"error": "음식 사진이 아닙니다. 음식 사진으로 바꿔주세요."}
    except Exception as e:
        raise Exception(f"음식 확인 API 호출 실패: {str(e)}")

    # 식단 분석 프롬프트
    analysis_prompt = """
    이 식단 이미지를 분석하여 다음 정보를 JSON 형식으로 제공해 주세요:
    {
        "nutrition_data": [
            {
                "food": "음식 이름",
                "calories": 숫자,
                "nutrients": {
                    "protein": 숫자,
                    "carbohydrates": 숫자,
                    "fat": 숫자,
                    "sugar": 숫자,
                    "sodium": 숫자,
                    "fiber": 숫자,
                    "water": 숫자
                }
            }
        ],
        "total_nutrition": {
            "calories": 숫자,
            "protein": 숫자,
            "carbohydrates": 숫자,
            "fat": 숫자,
            "sugar": 숫자,
            "sodium": 숫자,
            "fiber": 숫자,
            "water": 숫자
        },
        "deficient_nutrients": [
            "부족한 영양소 이름"
        ],
        "next_meal_suggestion": [
            "다음 식사 제안 음식 이름"
        ]
    }
    단위는 grams(g) 또는 milligrams(mg)로, 1인분 기준으로 추정해 주세요.
    음식이 여러 개라면 nutrition_data 배열에 각 음식별로 추가해 주세요.
    total_nutrition은 모든 음식의 영양소를 합산한 값입니다.
    deficient_nutrients는 부족한 영양소를 분석하여 나열합니다.
    next_meal_suggestion은 부족한 영양소를 보충할 수 있는 음식을 제안합니다.
    음식이름은 한국어로 나타내주세요.
    다른 텍스트나 코멘트는 포함시키지 마세요.
    """
    try:
        response = model.generate_content([analysis_prompt, image])
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        diet_analysis = json.loads(response_text)
        return diet_analysis
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini 응답을 JSON으로 파싱하지 못했습니다: {str(e)}")
    except Exception as e:
        raise Exception(f"Gemini API 호출 실패: {str(e)}")