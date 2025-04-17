from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import traceback # 예외 추적을 위해 추가
from typing import List
from fastapi.responses import JSONResponse
from app.services.nutrition_calculate_service import process_question

router = APIRouter(prefix="/nutrition", tags=["nutrition"])

class FoodItem(BaseModel):
    name: str
    amount: float
    unit: str

class NutritionRequest(BaseModel):
    foodList: List[FoodItem]
    date: str

    
@router.post("/calculate", summary="음식 이름으로 영양소 계산", description="저장된 음식 이름과 날짜를 받아 해당 날짜 영양소 합산을 계산합니다")
async def get_diet_recommendation(request: NutritionRequest):
    """
    사용자의 하루 식단을 통해 하루 섭취 영양소를 계산합니다.
    
    - FoodItem 
        1) name : 음식이름
        2) amount : 양
        3) unit : 단위
    - foodList : FoodItem의 리스트
    - date: 날짜
    
    Returns:
        그날 하루 식단의 총 영양소
    """
    try:
        
        result = process_question(request.foodList, request.date)
        
        return JSONResponse(content={"data":result})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"식단 추천 생성 중 오류가 발생했습니다: {str(e)}"
        ) 