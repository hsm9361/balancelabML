# app/routers/hPrediction_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import numpy as np
import joblib
from tensorflow.keras.models import load_model

router = APIRouter(prefix="/predict", tags=["predict"])  # router 객체 정의

# 모델 로드
dia_model = load_model("app/model/diabetes_predict.h5")
hpt_model = load_model("app/model/hypertension_predict.h5")
cdv_model = load_model("app/model/cardiovascular_predict.h5")
scaler = joblib.load("app/model/scaler.pkl")

# 입력 데이터 검증을 위한 Pydantic 모델
class PredictRequest(BaseModel):
    memberId:float
    age: float
    gender: int
    height: float
    weight: float
    historyDiabetes: int
    historyHypertension: int
    historyCardiovascular: int
    smokeDaily: int
    drinkWeekly: int
    exerciseWeekly: int
    dailyCarbohydrate: float
    dailySugar: float
    dailyFat: float
    dailySodium: float
    dailyFibrin: float
    dailyWater: float

@router.post("/health")
async def predict_health(request: PredictRequest):
    try:
        # BMI 계산
        bmi = request.weight / ((request.height / 100) ** 2)

        # 입력 데이터 배열 생성
        input_data = np.array([[
            request.age,
            request.gender,
            request.historyDiabetes,
            request.historyHypertension,
            request.historyCardiovascular,
            request.smokeDaily,
            request.drinkWeekly,
            request.exerciseWeekly,
            request.dailyCarbohydrate,
            request.dailySugar,
            request.dailyFat,
            request.dailySodium,
            request.dailyFibrin,
            request.dailyWater,
            bmi
        ]])
        
        print(PredictRequest)

        # 데이터 스케일링
        input_data_scaled = scaler.transform(input_data)

        # 예측
        dia_proba = dia_model.predict(input_data_scaled, verbose=0)[0][0]
        hpt_proba = hpt_model.predict(input_data_scaled, verbose=0)[0][0]
        cdv_proba = cdv_model.predict(input_data_scaled, verbose=0)[0][0]

        return {
            "diabetes": float(dia_proba),
            "hypertension": float(hpt_proba),
            "cardiovascular": float(cdv_proba)
        }

    except Exception as e:
        print("예측 중 예외 발생:", e)
        raise HTTPException(status_code=500, detail=str(e))