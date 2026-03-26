from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SendEmailRequest(BaseModel):
    to_email: str = Field(min_length=5, max_length=320)
    analysis_request_id: Optional[str] = None
    thoughts: Optional[str] = Field(default=None, max_length=4000)
    poem_text: Optional[str] = Field(default=None, max_length=20000)
    comfort_text: Optional[str] = Field(default=None, max_length=8000)
    user_image_path: Optional[str] = None
    user_image_url: Optional[str] = None
    user_image_file_id: Optional[str] = None
    poet_image_path: Optional[str] = None
    poet_image_file_id: Optional[str] = None
    guochao_image_path: Optional[str] = None
    guochao_image_file_id: Optional[str] = None

    @field_validator("to_email")
    @classmethod
    def validate_to_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("to_email must contain '@'.")
        domain = value.split("@", maxsplit=1)[1]
        if "." not in domain:
            raise ValueError("to_email domain is invalid.")
        return value


class SendEmailResponse(BaseModel):
    request_id: Optional[str] = None
    success: bool
    message: str
    error_code: Optional[str] = None
    retryable: bool = False
