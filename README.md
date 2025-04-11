# balancelabML
밸런스랩 모델관련


## 1. Python 가상환경 생성 (선택)

```bash
python -m venv venv
source venv/bin/activate  # 윈도우는 venv\Scripts\activate

./install.sh
chmod +x install.sh

uvicorn main:app --reload --port 8000