import os

# Unit/API tests are deterministic and never consume YouTube quota or download models.
os.environ["DEMO_MODE"] = "true"
os.environ["USE_PRETRAINED_MODELS"] = "false"
os.environ["CACHE_PATH"] = "./data/viettubelens-test.db"
