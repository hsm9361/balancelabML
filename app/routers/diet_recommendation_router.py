from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from app.services.food_consult_service import process_question, process_goal
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/diet",
    tags=["diet"],
    responses={404: {"description": "Not found"}},
)

class DietRecommendationRequest(BaseModel):
    id: float

class GoalRequest(BaseModel):
    id: float
    target_weight: float
    end_date: date

@router.post("/recommendation", summary="개인 맞춤형 식단 추천", description="사용자의 건강 데이터를 기반으로 맞춤형 식단을 추천합니다.")
async def get_diet_recommendation(request: DietRecommendationRequest):
    try:
        recommendation = process_question(request.id)
        return JSONResponse(content={"data": recommendation})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"식단 추천 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/goal-nutrition", summary="개인 맞춤형 영양소 추천", description="사용자의 목표를 기반으로 맞춤형 영양소를 추천합니다.")
async def get_goal_nutrition(request: GoalRequest):
    try:
        recommendation = process_goal(
            id=request.id,
            target_weight=request.target_weight,
            end_date=request.end_date
        )
        print(f"Recommendation result: {recommendation}")
        return JSONResponse(content={"data": recommendation})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"영양소 추천 생성 중 오류가 발생했습니다: {str(e)}"
        )