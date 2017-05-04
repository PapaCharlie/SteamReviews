import os
basedir = os.path.abspath(os.path.dirname(__file__))

# Different environments for the app to run in

class Config(object):
    DEBUG = False
    CSRF_ENABLED = True
    CSRF_SESSION_KEY = "secret"
    SECRET_KEY = "not_this"
    DYNAMO_REGION = os.environ.get("DYNAMO_REGION", "us-west-2")
    DYNAMO_DATABASE_URI = os.environ.get("DYNAMO_URL", "http://localhost:8000")
    GAME_CACHE_SIZE = os.environ.get("GAME_CACHE_SIZE", 1000)
    GAME_CACHE_PULL_ON_LOAD = int(os.environ.get("GAME_CACHE_PULL_ON_LOAD", 1)) == 1
    UPDATE_GAME_ON_GET = int(os.environ.get("UPDATE_GAME_ON_GET", 0)) == 1
    STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "not_a_real_key")
    MAX_SPIDER_FEATURES = int(os.environ.get("MAX_SPIDER_FEATURES", 20))

class ProductionConfig(Config):
    DEBUG = False
    DYNAMO_DATABASE_URI = os.environ.get("DYNAMO_URL", "https://dynamodb.us-west-2.amazonaws.com")
    GAME_CACHE_PULL_ON_LOAD = int(os.environ.get("GAME_CACHE_PULL_ON_LOAD", 1)) == 1

class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True

class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
