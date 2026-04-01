import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import Base and ALL models so Alembic sees them
from app.database import Base
from app.models import audit_log  # noqa: F401
from app.models import user  # noqa: F401
from app.models.site import Site  # noqa: F401
from app.models.crawl import CrawlJob, Page, PageSnapshot  # noqa: F401
from app.models.schedule import CrawlSchedule  # noqa: F401
from app.models.task import SeoTask  # noqa: F401
from app.models.keyword import Keyword, KeywordGroup  # noqa: F401
from app.models.file_upload import FileUpload  # noqa: F401
from app.models.position import KeywordPosition  # noqa: F401
from app.models.oauth_token import OAuthToken  # noqa: F401
from app.models.cluster import KeywordCluster  # noqa: F401
from app.models.wp_content_job import WpContentJob  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.content_plan import ContentPlanItem  # noqa: F401
from app.models.ad_traffic import AdTraffic  # noqa: F401
from app.models.invite import InviteLink  # noqa: F401
from app.models.site_group import SiteGroup, user_site_groups  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # Use SYNC_DATABASE_URL for Alembic (psycopg2, not asyncpg)
    return os.environ["SYNC_DATABASE_URL"]


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
