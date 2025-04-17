from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.diet_analysis_service import DietAnalysisService
import traceback
from typing import Dict, List
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/analysis", tags=["diet"])

class AnalysisRequest(BaseModel):
    message: str

# 싱글톤 DietAnalysisService 인스턴스 관리
diet_analysis_service_instance = None

def get_diet_analysis_service() -> DietAnalysisService:
    """DietAnalysisService 싱글톤 제공"""
    global diet_analysis_service_instance
    if diet_analysis_service_instance is None:
        print("[Router] DietAnalysisService 싱글톤 초기화...")
        try:
            diet_analysis_service_instance = DietAnalysisService()
            print("[Router] DietAnalysisService 싱글톤 초기화 완료")
        except Exception as e:
            print(f"[Router] DietAnalysisService 초기화 실패: {e}")
            traceback.print_exc()
            raise RuntimeError(f"DietAnalysisService 초기화 실패: {e}")
    return diet_analysis_service_instance

@router.post("/diet", 
             summary="음식 이름 추출 및 영양 분석/제안",
             description="사용자 메시지에서 음식 이름을 추출하고, 각 음식별 영양 정보를 분석한 뒤 다음 식사를 제안합니다.",
             response_model=dict)
async def get_diet_analysis(request: AnalysisRequest, service: DietAnalysisService = Depends(get_diet_analysis_service)):
    """
    사용자 메시지로부터 음식 이름을 추출하고 영양 분석 및 다음 끼니 제안을 수행합니다.

    - **request**: 사용자 메시지 (예: "오늘 점심으로 김밥이랑 라면 먹었어")
    - **return**: 음식 리스트, 각 음식별 영양 분석, 총 영양소, 부족 영양소, 다음 끼니 제안 (JSON 형식)
    """
    print(f"\n--- [Router] /analysis/diet 요청 수신 ---")
    print(f"요청 메시지: {request.message}")

    try:
        # 입력 검증
        if not request.message.strip():
            print("[Router] 입력 메시지가 비어 있음")
            raise HTTPException(status_code=400, detail="메시지가 비어 있습니다. 음식 정보를 입력해주세요.")

        # 1. 음식 이름 추출
        print("[Router] 음식 이름 추출 시도...")
        food_list = service.extract_food_name(request.message)
        print(f"[Router] 추출된 음식 리스트: {food_list}")

        # 음식 리스트 검증
        if not food_list:
            print("[Router] 추출된 음식이 없음")
            return {
                "food_list": [],
                "nutrition_per_food": [],
                "total_nutrition": {"protein": 0, "carbohydrate": 0, "water": 0, "sugar": 0, "fat": 0, "fiber": 0, "sodium": 0},
                "deficient_nutrients": [],
                "next_meal_suggestion": []
            }

        # 2. 영양 분석 및 제안
        print("[Router] 영양 분석 및 제안 시도...")
        result = service.analyze_nutrition_and_suggest(food_list)
        print(f"[Router] 최종 분석 결과: {result}")

        # 결과 검증
        expected_keys = {"food_list", "nutrition_per_food", "total_nutrition", "deficient_nutrients", "next_meal_suggestion"}
        if not all(key in result for key in expected_keys):
            print("[Router] 결과 형식이 올바르지 않음")
            raise ValueError("분석 결과 형식이 올바르지 않습니다.")

        # nutrition_per_food의 각 항목 검증
        for item in result.get("nutrition_per_food", []):
            if not isinstance(item, dict) or "food" not in item or "nutrition" not in item:
                print("[Router] nutrition_per_food 항목 형식이 올바르지 않음")
                raise ValueError("nutrition_per_food 항목 형식이 올바르지 않습니다.")
            nutrition = item["nutrition"]
            expected_nutrients = {"protein", "carbohydrate", "water", "sugar", "fat", "fiber", "sodium"}
            if not all(key in nutrition for key in expected_nutrients):
                print("[Router] nutrition 항목 형식이 올바르지 않음")
                raise ValueError("nutrition 항목 형식이 올바르지 않습니다.")

        print("--- [Router] /analysis/diet 요청 처리 완료 ---")
        return JSONResponse(content=result)

    except HTTPException as http_exc:
        print(f"[Router] HTTP 예외 발생: Status={http_exc.status_code}, Detail={http_exc.detail}")
        print("--- [Router] /analysis/diet 요청 오류 종료 (HTTPException) ---")
        raise http_exc
    except ValueError as ve:
        print(f"[Router] 서비스 처리 중 값 오류 발생: {ve}")
        print(f"--- Traceback ---")
        traceback.print_exc()
        print(f"--- Traceback 끝 ---")
        print("--- [Router] /analysis/diet 요청 오류 종료 (ValueError) ---")
        raise HTTPException(status_code=400, detail=f"데이터 처리 중 오류: {str(ve)}")
    except Exception as e:
        print(f"[Router] 예상치 못한 오류 발생: {type(e).__name__} - {e}")
        print(f"--- Traceback ---")
        traceback.print_exc()
        print(f"--- Traceback 끝 ---")
        print("--- [Router] /analysis/diet 요청 오류 종료 (General Exception) ---")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")
