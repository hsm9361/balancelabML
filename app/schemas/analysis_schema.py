from pydantic import BaseModel

class AnalysisRequest(BaseModel):
    message: str
