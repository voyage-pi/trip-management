from typing import Dict, Any
from pydantic import BaseModel

class ResponseBody(BaseModel):
    status_code: int
    message: str
    response: Dict[str, Any]

    def __init__(self, response: Dict[str, Any], message: str = "", status_code: int = 200):
        super().__init__(response=response, message=message, status_code=status_code)

    def set_status_code(self, code: int):
        self.status_code = code

    def set_message(self, message: str):
        self.message = message
