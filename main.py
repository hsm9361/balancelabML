import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import hPrediction_router, diet_recommendation_router
from app.routers import diet_analysis_router
from app.routers import meal_analysis_router
from app.routers import nutrition_calculate_router
from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")
app = FastAPI(
    title="Health Prediction API",
    description="건강 상태(당뇨, 고혈압, 심혈관질환) 예측 서비스",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.0.66:3000", "http://localhost:3000"],  # 프론트엔드 출처 추가
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(hPrediction_router.router)
app.include_router(diet_analysis_router.router)
app.include_router(meal_analysis_router.router)
app.include_router(diet_recommendation_router.router)
app.include_router(nutrition_calculate_router.router)

@app.get("/")
async def root():
    return {"message": "Health Prediction API Running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
