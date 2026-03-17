import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.project_name = "DeepTrace"
        self.spectral_model_path = os.getenv("SPECTRAL_MODEL_PATH", "deeptrace_fuse_best")
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        self.env_file = os.getenv("ENV_FILE", ".env")
        self.spectral_ai_index = int(os.getenv("SPECTRAL_AI_INDEX", "1"))
        self.spectral_input_size = int(os.getenv("SPECTRAL_INPUT_SIZE", "224"))
        self.spectral_normalize = os.getenv("SPECTRAL_NORMALIZE", "1") == "1"


settings = Settings()
