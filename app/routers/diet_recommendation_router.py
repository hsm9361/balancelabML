from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.food_consult_service import process_question
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/diet",
    tags=["diet"],
    responses={404: {"description": "Not found"}},
)

class DietRecommendationRequest(BaseModel):
    email: str
    question: Optional[str] = "건강한 식단을 추천해주세요."

@router.post("/recommendation", summary="개인 맞춤형 식단 추천", description="사용자의 건강 데이터를 기반으로 맞춤형 식단을 추천합니다.")
async def get_diet_recommendation(request: DietRecommendationRequest):
    """
    사용자의 건강 데이터를 기반으로 맞춤형 식단을 추천합니다.
    
    - **email**: 사용자 이메일
    - **question**: (선택적) 식단 추천에 대한 질문
    
    Returns:
        맞춤형 식단 추천 내용
    """
    try:
        # 식단 추천 생성
        
        recommendation = process_question(request.question, request.email)
        
        return JSONResponse(content={"data":recommendation})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"식단 추천 생성 중 오류가 발생했습니다: {str(e)}"
        ) 