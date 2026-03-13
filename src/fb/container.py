from __future__ import annotations

from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fb.config import Settings
from fb.infrastructure.auth.jwt_service import JWTTokenService
from fb.infrastructure.auth.password import BcryptPasswordHasher
from fb.infrastructure.cache.cache_service import CacheService
from fb.infrastructure.cache.redis_cache import RedisCache
from fb.infrastructure.cache.redis_client import create_redis_client
from fb.infrastructure.cache.token_blacklist import RedisTokenBlacklist
from fb.infrastructure.database.session import create_session_factory
from fb.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from fb.infrastructure.realtime.connection_manager import ConnectionManager
from fb.infrastructure.realtime.pubsub import RedisPubSub
from fb.domain.profile.services import FileStorage
from fb.infrastructure.repositories.media_repo import SqlAlchemyMediaRepository
from fb.infrastructure.storage.local_storage import LocalFileStorage
from fb.infrastructure.storage.s3_storage import S3FileStorage


@dataclass
class Container:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    password_hasher: BcryptPasswordHasher = field(init=False)
    token_service: JWTTokenService = field(init=False)
    token_blacklist: RedisTokenBlacklist = field(init=False)
    connection_manager: ConnectionManager = field(init=False)
    pubsub: RedisPubSub = field(init=False)
    cache: CacheService = field(init=False)

    def __post_init__(self) -> None:
        self.password_hasher = BcryptPasswordHasher()
        self.token_service = JWTTokenService(self.settings)
        self.token_blacklist = RedisTokenBlacklist(self.redis)
        self.connection_manager = ConnectionManager()
        self.pubsub = RedisPubSub(self.redis, self.connection_manager)
        self.cache = CacheService(RedisCache(self.redis))

    @classmethod
    def create(cls, settings: Settings) -> Container:
        return cls(
            settings=settings,
            session_factory=create_session_factory(settings),
            redis=create_redis_client(settings),
        )

    def create_uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def create_media_repo(self, session) -> SqlAlchemyMediaRepository:
        """Create a SqlAlchemyMediaRepository bound to the given session."""
        return SqlAlchemyMediaRepository(session)

    @property
    def file_storage(self) -> FileStorage:
        """Return the appropriate file storage backend based on settings."""
        if self.settings.storage_backend == "s3":
            return S3FileStorage(
                bucket_name=self.settings.s3_bucket_name,
                region=self.settings.s3_region,
                endpoint_url=self.settings.s3_endpoint_url,
            )
        return LocalFileStorage(self.settings.upload_dir)
