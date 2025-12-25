from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    PAYME_MERCHANT_ID: str = ""
    PAYME_KEY: str = ""
    PAYME_CALLBACK_URL: str = ""

    CLICK_MERCHANT_ID: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_CALLBACK_URL: str = ""

    SMS_PROVIDER_API_KEY: str = ""
    SMS_PROVIDER_URL: str = ""

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BUCKET_NAME: str = ""
    AWS_REGION: str = "us-east-1"

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    BACKUP_ENABLED: bool = False
    BACKUP_HOUR: int = 3  # Hour of day to run backup (0-23, default 3 AM)

    TIMEZONE: str = "Asia/Tashkent"
    CURRENCY: str = "UZS"

    class Config:
        env_file = ".env"


settings = Settings()
