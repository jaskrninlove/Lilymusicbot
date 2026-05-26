import os
import re
import asyncio
from typing import Optional, Union

from pyrogram import enums, types
from youtubesearchpython.__future__ import VideosSearch

from Elevenyts import logger
from Elevenyts.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="

        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        self.search_cache = {}

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        link = None

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""

            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[
                            entity.offset:
                            entity.offset + entity.length
                        ]
                        break

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]

        return None

    async def search(
        self,
        query: str,
        m_id: int,
        video: bool = False
    ) -> Track | None:

        cache_key = f"{query}_{video}"

        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        try:
            results = await VideosSearch(query, limit=1).next()

        except Exception as e:
            logger.warning(
                f"YouTube search failed for '{query}': {e}"
            )
            return None

        if results and results["result"]:
            data = results["result"][0]

            duration = data.get("duration")
            is_live = duration is None or duration == "LIVE"

            track = Track(
                id=data.get("id"),

                channel_name=data.get(
                    "channel",
                    {}
                ).get("name"),

                duration=duration if not is_live else "LIVE",

                duration_sec=0 if is_live else utils.to_seconds(duration),

                message_id=m_id,

                title=data.get("title", "Unknown")[:40],

                thumbnail=data.get(
                    "thumbnails",
                    [{}]
                )[-1].get("url", "").split("?")[0],

                url=data.get("link"),

                view_count=data.get(
                    "viewCount",
                    {}
                ).get("short", "Unknown"),

                is_live=is_live,
                video=video,
            )

            self.search_cache[cache_key] = track

            return track

        return None

    async def playlist(
        self,
        limit: int,
        user: str,
        url: str
    ) -> list[Track]:

        return []

    async def download(
        self,
        video_id: str,
        is_live: bool = False,
        video: bool = False
    ) -> Optional[str]:

        try:
            from pytubefix import YouTube as PYTube

            url = f"https://www.youtube.com/watch?v={video_id}"

            yt = PYTube(url)

            if video:
                stream = (
                    yt.streams
                    .filter(progressive=True, file_extension="mp4")
                    .order_by("resolution")
                    .desc()
                    .first()
                )
            else:
                stream = (
                    yt.streams
                    .filter(only_audio=True)
                    .order_by("abr")
                    .desc()
                    .first()
                )

            if not stream:
                logger.error(f"No stream found for {video_id}")
                return None

            logger.info(f"Streaming: {video_id}")

            return stream.url

        except Exception as e:
            logger.error(
                f"Streaming failed for {video_id}: {e}"
            )

            return None