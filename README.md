
# BalanceLab ML

**AI 기반 식단 분석 및 건강 예측 시스템 - 모델 서버 레포지토리**

이 저장소는 BalanceLab 프로젝트의 머신러닝/딥러닝 모델 관련 코드를 관리합니다.  
FastAPI 기반 API 서버와 nutrition 데이터 캐싱 모델이 포함되어 있습니다.

---

## 🛠️ 사용 기술

- Python 3.10
- FastAPI
- Uvicorn
- Pickle (데이터 캐시 저장)
- Shell Script (자동 설치 스크립트)

---

## 🚀 설치 및 실행 방법

### 1. 저장소 클론
```bash
git clone https://github.com/hsm9361/balancelabML.git
cd balancelabML
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # 윈도우: venv\Scripts\activate
```

### 3. 의존성 설치 및 서버 실행
```bash
./install.sh
chmod +x install.sh
uvicorn main:app --reload --port 8000
```

서버가 `http://localhost:8000` 에서 실행됩니다.

---

## 📂 프로젝트 구조

```bash
balancelabML/
├── app/                   # FastAPI 라우터 및 서비스 코드
├── nutrition_cache.pkl     # 사전 생성된 영양소 데이터 캐시
├── main.py                 # 서버 실행 파일
├── install.sh              # 패키지 설치 스크립트
├── requirements.txt        # 필요 패키지 목록
└── README.md               # 리드미 파일
```

---

## 📌 주요 기능

- 사용자 식단 입력에 대한 영양소 분석 모델 제공
- FastAPI 서버를 통한 API 서비스
- nutrition_cache.pkl을 통한 빠른 응답 캐싱
- 간편한 설치 스크립트 제공 (`install.sh`)

---

## 🔗 관련 저장소

- [BalanceLab FE (프론트엔드)](https://github.com/hsm9361/balancelabFE)
- [BalanceLab BE (백엔드)](https://github.com/hsm9361/balancelabBE)

---

## 📢 주의사항

- 서버 실행 시 기본 포트는 `8000`입니다. 필요에 따라 `--port` 옵션으로 변경 가능합니다.
- nutrition_cache.pkl 파일이 필요하며, 미포함 시 API 응답이 정상적으로 동작하지 않을 수 있습니다.

---

# ✨ About

BalanceLab 프로젝트는 AI 기술을 활용하여 식습관 개선과 건강 관리를 지원하는 서비스를 목표로 합니다.
