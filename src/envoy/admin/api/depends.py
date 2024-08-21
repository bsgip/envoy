import secrets
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
security = HTTPBasic()


class AdminAuthDepends:
    """
    Dependency class that raises a 401 unauthorized / 403 forbidden exception if the incoming request BASIC
    auth credentials don't match either the admin or readonly user values
    """

    def __init__(
        self, admin_username: str, admin_password: str, read_only_username: str, read_only_keys: list[str]
    ) -> None:
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.read_only_username = read_only_username
        self.read_only_keys = read_only_keys

    async def __call__(self, credentials: Annotated[HTTPBasicCredentials, Depends(security)], request: Request) -> None:
        # If the creds match the admin user
        if secrets.compare_digest(bytes(self.admin_username, "utf-8"), bytes(credentials.username, "utf-8")):
            if secrets.compare_digest(bytes(self.admin_password, "utf-8"), bytes(credentials.password, "utf-8")):
                return  # Authorised admin user

        # If the creds match the readonly user
        if secrets.compare_digest(bytes(self.read_only_username, "utf-8"), bytes(credentials.username, "utf-8")):
            for ro_key in self.read_only_keys:
                if secrets.compare_digest(bytes(ro_key, "utf-8"), bytes(credentials.password, "utf-8")):
                    # At this point we have a valid readonly key
                    # Make sure they are trying to access a readonly resource
                    if request.method == "GET" or request.method == "HEAD":
                        return  # Authorised readonly user
                    else:
                        raise HTTPException(
                            status_code=HTTPStatus.FORBIDDEN, detail="Only GET requests enabled for these credentials"
                        )

        # If no valid creds are matched - bail out with
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Unauthorized")
