from t18_common.config import cfg, paths
print("ENV:", cfg("ENV"))
print("TZ:", cfg("TZ"))
print("DB_PATH:", paths()["db"])

