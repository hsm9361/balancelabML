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

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

# 운영 체제별 기본 경로 설정
if not ALLOWED_IMAGE_DIR:
    if platform.system() == "Windows":
        ALLOWED_IMAGE_DIR = Path("C:/Uploads")
    else:  # macOS, Linux
        ALLOWED_IMAGE_DIR = Path("/Users/hongsamyung/uploads")
else:
    ALLOWED_IMAGE_DIR = Path(ALLOWED_IMAGE_DIR)

# ALLOWED_IMAGE_DIR 처리
ALLOWED_IMAGE_DIR = ALLOWED_IMAGE_DIR.resolve()
if not ALLOWED_IMAGE_DIR.exists():
    ALLOWED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)  # 디렉토리 자동 생성
if not ALLOWED_IMAGE_DIR.is_dir():
    raise ValueError(f"ALLOWED_IMAGE_DIR은 디렉토리가 아닙니다: {ALLOWED_IMAGE_DIR}")

print(f"Using ALLOWED_IMAGE_DIR: {ALLOWED_IMAGE_DIR}")  # 디버깅용

# Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# 파일 경로 검증
def validate_file_path(file_path: str) -> str:
    try:
        full_path = Path(file_path).resolve()
        base_dir = Path(ALLOWED_IMAGE_DIR).resolve()
        if not full_path.is_relative_to(base_dir):
            raise ValueError(f"파일 경로가 허용된 디렉토리({base_dir}) 내에 있어야 합니다.")
        if not full_path.exists():
            raise FileNotFoundError(f"파일 {file_path}을 찾을 수 없습니다.")
        if not full_path.is_file():
            raise ValueError(f"{file_path}은 파일이 아닙니다.")
        if full_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            raise ValueError("지원되지 않는 파일 형식입니다. JPG 또는 PNG만 허용됩니다.")
        return str(full_path)
    except Exception as e:
        raise ValueError(f"파일 경로 검증 실패: {str(e)}")

# 식단 분석 함수
def analyze_meal(file_path: str) -> list:
    # 파일 경로 검증
    file_path = validate_file_path(file_path)

    # 이미지 열기
    try:
        image = Image.open(file_path)
        image.verify()  # 이미지 유효성 검증
        image = Image.open(file_path)  # verify 후 재오픈
    except Exception as e:
        raise ValueError(f"유효하지 않은 이미지 파일입니다: {str(e)}")

    # Gemini API 호출
    prompt = """
    이 식단 이미지를 분석하여 다음 정보를 JSON 형식으로 제공해 주세요:
    [
        {
            "food_name": "음식 이름",
            "calories": 숫자,
            "nutrients": {
                "carbohydrates": 숫자,
                "fat": 숫자,
                "sugar": 숫자,
                "sodium": 숫자,
                "fiber": 숫자,
                "water": 숫자
            }
        }
    ]
    단위는 grams(g) 또는 milligrams(mg)로, 1인분 기준으로 추정해 주세요.
    음식이 여러 개라면 배열에 각 음식별로 추가해 주세요.
    다른 텍스트나 코멘트는 포함시키지 마세요.
    """
    try:
        response = model.generate_content([prompt, image])
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        diet_analysis = json.loads(response_text)
        return diet_analysis
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini 응답을 JSON으로 파싱하지 못했습니다: {str(e)}")
    except Exception as e:
        raise Exception(f"Gemini API 호출 실패: {str(e)}")