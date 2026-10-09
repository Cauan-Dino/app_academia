import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')
w = os.getenv('e')#[h.strip() for h in os.getenv("e", "").split(",") if h.strip()]
print(type(w))
print(w)