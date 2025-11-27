from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET_KEY: str = ""
    PAYME_CALLBACK_URL: str = ""

    CLICK_MERCHANT_ID: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_CALLBACK_URL: str = ""

    SMS_PROVIDER_API_KEY: str = ""
    SMS_PROVIDER_URL: str = ""

    TIMEZONE: str = "Asia/Tashkent"
    CURRENCY: str = "UZS"

    class Config:
        env_file = ".env"


settings = Settings()
