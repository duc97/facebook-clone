from __future__ import annotations

from fastapi import APIRouter

from fb.presentation.rest.v1.auth import router as auth_router
from fb.presentation.rest.v1.feed import router as feed_router
from fb.presentation.rest.v1.friends import router as friends_router
from fb.presentation.rest.v1.media import router as media_router
from fb.presentation.rest.v1.messages import router as messages_router
from fb.presentation.rest.v1.streaming import router as streaming_router
from fb.presentation.rest.v1.notifications import router as notifications_router
from fb.presentation.rest.v1.posts import router as posts_router
from fb.presentation.rest.v1.users import router as users_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(posts_router)
v1_router.include_router(friends_router)
v1_router.include_router(feed_router)
v1_router.include_router(notifications_router)
v1_router.include_router(messages_router)
v1_router.include_router(media_router)
v1_router.include_router(streaming_router)
