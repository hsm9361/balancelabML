from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.food_name_service import FoodNameService
import traceback # 예외 추적을 위해 추가

router = APIRouter(prefix="/analysis", tags=["foodName"])

class FoodNameRequest(BaseModel):
    message: str

@router.post("/foodName", summary="음식 이름 추출 및 영양 분석/제안", description="사용자 메시지에서 음식 이름을 추출하고, 해당 음식들의 영양 정보를 분석한 뒤 다음 식사를 제안합니다.")
async def get_food_name(request: FoodNameRequest):
    """
    사용자 메시지로부터 음식 이름을 추출하고 영양 분석 및 다음 끼니 제안을 수행합니다.

    - **request**: 사용자 메시지 (예: "오늘 점심으로 김밥이랑 라면 먹었어")
    - **return**: 음식 리스트, 영양 분석 결과, 부족 영양소, 다음 끼니 제안 (JSON 형식)
    """
    print(f"\n--- [Router] /analysis/foodName 요청 수신 ---")
    print(f"요청 메시지: {request.message}")
    try:
        # FoodNameService 인스턴스 생성 (오류 발생 가능성 있음, 예: API 키 누락)
        try:
            food_name_service = FoodNameService()
        except Exception as e:
            print(f"[Router] FoodNameService 초기화 중 오류: {e}")
            print(f"--- Traceback ---")
            traceback.print_exc()
            print(f"--- Traceback 끝 ---")
            raise HTTPException(status_code=503, detail=f"서비스 초기화 실패: {e}") # 503 Service Unavailable

        # 1. 음식 이름 추출
        print("[Router] 음식 이름 추출 시도...")
        food_list = food_name_service.extract_food_name(request.message)
        print(f"[Router] 추출된 음식 리스트: {food_list}")

        # 2. 영양 분석 및 제안
        print("[Router] 영양 분석 및 제안 시도...")
        result = food_name_service.analyze_nutrition_and_suggest(food_list)
        print(f"[Router] 최종 분석 결과: {result}")

        print("--- [Router] /analysis/foodName 요청 처리 완료 ---")
        return result

    except HTTPException as http_exc:
        # 이미 HTTPException으로 처리된 경우 그대로 전달
        print(f"[Router] HTTP 예외 발생: Status={http_exc.status_code}, Detail={http_exc.detail}")
        print("--- [Router] /analysis/foodName 요청 오류 종료 (HTTPException) ---")
        raise http_exc
    except ValueError as ve:
        # 서비스 내부에서 발생시킨 특정 오류 (예: JSON 파싱 실패, 모델 응답 문제)
        print(f"[Router] 서비스 처리 중 값 오류 발생: {ve}")
        print(f"--- Traceback ---")
        traceback.print_exc() # 서비스 레벨에서 발생한 오류의 상세 위치 확인
        print(f"--- Traceback 끝 ---")
        print("--- [Router] /analysis/foodName 요청 오류 종료 (ValueError) ---")
        # 클라이언트에게는 일반적인 서버 오류 메시지 또는 구체적인 문제 안내
        raise HTTPException(status_code=500, detail=f"데이터 처리 중 오류 발생: {ve}")
    except Exception as e:
        # 예상치 못한 모든 종류의 오류 처리
        print(f"[Router] 예상치 못한 오류 발생: {type(e).__name__} - {e}")
        print(f"--- Traceback ---")
        traceback.print_exc()
        print(f"--- Traceback 끝 ---")
        print("--- [Router] /analysis/foodName 요청 오류 종료 (General Exception) ---")
        raise HTTPException(status_code=500, detail=f"서버 내부 오류 발생: {type(e).__name__}")
