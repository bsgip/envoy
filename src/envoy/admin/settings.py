from pydantic import BaseSettings


class AdminAppSettings(BaseSettings):
    title: str = "admin"
    version: str = "0.0.0"

    admin_username: str
    admin_password: str

    class Config:
        env_file: str = ".env"
        env_file_encoding: str = "utf-8"


admin_settings = AdminAppSettings()
