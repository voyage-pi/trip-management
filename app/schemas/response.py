from typing import Dict, Any
from fastapi.responses import JSONResponse
from fastapi import status 

class ResponseBody(JSONResponse):
    def __init__(self, response: Dict[str, Any], message: str = "", status_code: int = status.HTTP_200_OK):
        content = {
            "status_code": status_code,
            "message": message,
            "response": response
        }
        super().__init__(content=content, status_code=status_code)

    def set_status_code(self, code: status):
        self.status_code = code

    def set_message(self, message: str):
        self.message = message
