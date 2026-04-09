from fastapi import APIRouter, Request

from app.core.user_identity import resolve_user_identity
from app.schemas.bootstrap import BootstrapFeatureFlags, BootstrapResponse


router = APIRouter()


@router.get("/bootstrap", response_model=BootstrapResponse)
def read_bootstrap(request: Request) -> BootstrapResponse:
    identity = resolve_user_identity(request=request)
    return BootstrapResponse(
        identity_type=identity.identity_type,
        openid_present=bool(identity.openid),
        unionid_present=bool(identity.unionid),
        user_bound=identity.identity_type != "anonymous",
        features=BootstrapFeatureFlags(),
    )
