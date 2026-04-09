from pydantic import BaseModel, Field


class BindWechatPhoneRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)


class BindWechatPhoneResponse(BaseModel):
    identity_type: str = "anonymous"
    openid_present: bool = False
    unionid_present: bool = False
    phone_bound: bool = True
    masked_phone_number: str = ""
    phone_tail: str = ""
    country_code: str = "86"
