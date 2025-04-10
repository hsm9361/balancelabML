from pydantic import BaseModel

class FoodNameRequest(BaseModel):
    message: str
