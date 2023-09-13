import secrets
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
security = HTTPBasic()


class AdminAuthDepends:
    """
    Dependency class that raises a 401 unauthorized exception if the provided admin_username
    and admin_userpassword are not correct.
    """

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    async def __call__(self, credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> None:
        is_correct_user = secrets.compare_digest(bytes(self.username, "utf-8"), bytes(credentials.username, "utf-8"))
        is_correct_pass = secrets.compare_digest(bytes(self.password, "utf-8"), bytes(credentials.password, "utf-8"))

        if not (is_correct_pass and is_correct_user):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Unauthorized")
