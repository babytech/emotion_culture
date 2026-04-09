from pydantic import BaseModel, Field


class BootstrapFeatureFlags(BaseModel):
    auth_gate_required: bool = True
    history_bound_to_wechat_identity: bool = True
    points_bound_to_wechat_identity: bool = True
    membership_bound_to_wechat_identity: bool = True


class BootstrapResponse(BaseModel):
    identity_type: str = "anonymous"
    openid_present: bool = False
    unionid_present: bool = False
    user_bound: bool = False
    features: BootstrapFeatureFlags = Field(default_factory=BootstrapFeatureFlags)
