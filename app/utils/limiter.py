from redis.asyncio import Redis
from pyrate_limiter import Rate, Duration, RedisBucket, Limiter

from app.core.config import setting

redis_url = setting.REDIS_URL
redis_connection = Redis.from_url(redis_url)

def get_rpm_limiter():
    rpm_rates = [
        Rate(100, Duration.Minute)
    ]
    bucker_factory = RedisBucket.init(rates=rpm_rates, redis=redis_connection, bucker_factory="llm_rpm_limit")
    rpm_limiter = Limiter(bucker_factory)

    return rpm_limiter

def get_tpm_limiter():
    tpm_rates = [
        Rate(3500, Duration.Minute)
    ]
    bucker_factory = RedisBucket.init(rates=tpm_rates, redis=redis_connection, bucker_factory="llm_tpm_limit")
    tpm_limiter = Limiter(bucker_factory)
    
    return tpm_limiter

def get_api_limiter():
    rates = [
        Rate(60, Duration.Minute)
    ]
    bucker_factory = RedisBucket.init(rates=rates, redis=redis_connection, bucker_factory="simple_api_limit")
    api_limiter = Limiter(bucker_factory)
    
    return api_limiter

rpm_limier = get_rpm_limiter()
tpm_limiter = get_tpm_limiter()
ap_limiter = get_api_limiter()