from datetime import timedelta

from kombu import Exchange, Queue

from posthog.constants import AnalyticsDBMS
from posthog.settings.base_variables import TEST
from posthog.settings.data_stores import PRIMARY_DB, REDIS_URL
from posthog.settings.ee import EE_AVAILABLE

# Only listen to the default queue "celery", unless overridden via the cli
# NB! This is set to explicitly exclude the "posthog-plugins" queue, handled by a nodejs process
CELERY_QUEUES = (Queue("celery", Exchange("celery"), "celery"),)
CELERY_DEFAULT_QUEUE = "celery"
CELERY_IMPORTS = []
CELERY_BROKER_URL = REDIS_URL  # celery connects to redis
CELERY_BEAT_MAX_LOOP_INTERVAL = 30  # sleep max 30sec before checking for new periodic events
CELERY_RESULT_BACKEND = REDIS_URL  # stores results for lookup when processing
CELERY_IGNORE_RESULT = True  # only applies to delay(), must do @shared_task(ignore_result=True) for apply_async
CELERY_RESULT_EXPIRES = timedelta(days=4)  # expire tasks after 4 days instead of the default 1
REDBEAT_LOCK_TIMEOUT = 45  # keep distributed beat lock for 45sec

if PRIMARY_DB == AnalyticsDBMS.CLICKHOUSE and EE_AVAILABLE:
    CELERY_IMPORTS.append("ee.tasks.materialized_columns")

if TEST:
    import celery

    celery.current_app.conf.CELERY_ALWAYS_EAGER = True
    celery.current_app.conf.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
