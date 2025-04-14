from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.meal_service import analyze_meal

router = APIRouter()

class ImagePath(BaseModel):
    file_path: str

@router.post("/analyze/image")
async def analyze_meal_endpoint(image_path: ImagePath):
    try:
        result = analyze_meal(image_path.file_path)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="이미지 파일을 찾을 수 없습니다.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")