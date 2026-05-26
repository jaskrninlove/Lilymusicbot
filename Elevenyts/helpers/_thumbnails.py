import os
import re
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from Elevenyts import config
from Elevenyts.helpers import Track


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


class Thumbnail:
    def __init__(self):
        try:
            self.title_font = ImageFont.truetype(
                "Elevenyts/helpers/Raleway-Bold.ttf", 40)

            self.regular_font = ImageFont.truetype(
                "Elevenyts/helpers/Inter-Light.ttf", 22)

            self.watermark_font = ImageFont.truetype(
                "Elevenyts/helpers/Raleway-Bold.ttf", 72)

            self.small_font = ImageFont.truetype(
                "Elevenyts/helpers/Inter-Light.ttf", 18)

        except OSError:
            self.title_font = self.regular_font = self.watermark_font = self.small_font = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
        return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}_modern.png"

            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)

            return await asyncio.get_event_loop().run_in_executor(
                None, self._generate_sync, temp, output, song, size
            )

        except Exception:
            return config.DEFAULT_THUMB

    def _generate_sync(self, temp: str, output: str, song: Track, size=(1280, 720)) -> str:
        try:
            with Image.open(temp) as temp_img:
                base = temp_img.resize(size).convert("RGBA")

            bg = Image.new("RGBA", size, (0, 0, 0, 255))
            bg.paste(base, (0, 0), base)
            bg = bg.filter(ImageFilter.GaussianBlur(2))
            draw = ImageDraw.Draw(bg)

            gradient = Image.new("L", (1, 300))
            for i in range(300):
                gradient.putpixel((0, i), int(255 * (i / 300)))

            alpha = gradient.resize((1280, 300))
            black_overlay = Image.new("RGBA", (1280, 300), (0, 0, 0, 200))
            black_overlay.putalpha(alpha)

            bg.paste(black_overlay, (0, 420), black_overlay)

            thumb = base.resize((180, 180))
            mask = Image.new("L", thumb.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, 180, 180), 25, fill=255)
            bg.paste(thumb, (60, 450), mask)

            title = re.sub(r"\W+", " ", song.title).title()

            draw.text(
                (260, 470),
                trim_to_width(title, self.title_font, 800),
                fill="white",
                font=self.title_font
            )

            draw.text(
                (260, 530),
                f"YouTube • {song.view_count or 'Unknown'}",
                fill="lightgray",
                font=self.regular_font
            )

            draw.line([(260, 600), (760, 600)], fill="gray", width=5)
            draw.line([(260, 600), (480, 600)], fill="red", width=6)

            draw.ellipse([(472, 592), (488, 608)], fill="red")

            draw.text((260, 615), "00:00", fill="white", font=self.small_font)
            draw.text(
                (700, 615),
                getattr(song, 'duration', '00:00'),
                fill="white",
                font=self.small_font
            )

            bg.save(output)

            try:
                os.remove(temp)
            except:
                pass

            return output

        except Exception:
            return config.DEFAULT_THUMB
