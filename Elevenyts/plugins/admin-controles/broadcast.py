import os
import asyncio
from typing import List, Tuple

from pyrogram import enums, errors, filters, types

from Elevenyts import app, db, lang


# =========================
# GLOBAL FLAG
# =========================

broadcasting: bool = False


# =========================
# BROADCAST COMMAND
# =========================

@app.on_message(filters.command(["broadcast"]) & app.sudo_filter)
@lang.language()
async def broadcast_message(_, message: types.Message) -> None:

    try:
        await message.delete()
    except:
        pass

    global broadcasting

    if broadcasting:
        return await message.reply_text(message.lang["gcast_active"])

    media_message = None
    media_group = None

    if message.reply_to_message:
        media_message = message.reply_to_message

        if media_message.media_group_id:
            try:
                media_group = await _get_media_group(
                    message.chat.id,
                    media_message
                )
            except:
                pass

    flags, broadcast_text = _parse_broadcast_command(message.text)

    if not broadcast_text and not media_message:
        return await message.reply_text(message.lang["gcast_usage"])

    groups, users = await _get_broadcast_recipients(flags)
    all_chats = groups + users

    if not all_chats:
        return await message.reply_text("❌ No recipients found.")

    broadcasting = True

    sent = await message.reply_text(message.lang["gcast_start"])

    await _log_broadcast_start(message)
    await asyncio.sleep(2)

    success_groups, success_users, failed_log = await _send_broadcast(
        broadcast_text,
        groups,
        users,
        sent,
        media_message,
        flags,
        message.lang,
        media_group
    )

    broadcasting = False

    await _send_broadcast_completion(
        message,
        sent,
        success_groups,
        success_users,
        failed_log,
        media_message
    )


# =========================
# STOP BROADCAST
# =========================

@app.on_message(
    filters.command(["stop_gcast", "stop_broadcast"])
    & app.sudo_filter
)
@lang.language()
async def stop_broadcast(_, message: types.Message) -> None:

    global broadcasting

    try:
        await message.delete()
    except:
        pass

    if not broadcasting:
        return await message.reply_text(message.lang["gcast_inactive"])

    broadcasting = False
    await message.reply_text(message.lang["gcast_stop"])


# =========================
# GET MEDIA GROUP
# =========================

async def _get_media_group(chat_id: int, message: types.Message):

    if not message.media_group_id:
        return None

    media_group_id = message.media_group_id
    messages = []

    try:
        start_id = max(1, message.id - 20)
        end_id = message.id + 20

        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await app.get_messages(chat_id, msg_id)
                if (
                    msg
                    and hasattr(msg, "media_group_id")
                    and msg.media_group_id == media_group_id
                ):
                    messages.append(msg)
            except:
                continue

        messages.sort(key=lambda x: x.id)
        return messages if messages else None

    except:
        return None


# =========================
# PARSE COMMAND
# =========================

def _parse_broadcast_command(text: str) -> Tuple[List[str], str]:

    if not text:
        return [], ""

    parts = text.split(None, 1)

    if len(parts) < 2:
        return [], ""

    remaining_text = parts[1]
    flags = []
    lines = remaining_text.split("\n")
    first_line_parts = lines[0].split()
    message_start_index = 0

    for i, part in enumerate(first_line_parts):
        if part.startswith("-"):
            flags.append(part)
            message_start_index = i + 1
        else:
            break

    if message_start_index > 0:
        first_line_without_flags = " ".join(first_line_parts[message_start_index:])
        message_text = (
            first_line_without_flags + "\n" + "\n".join(lines[1:])
            if len(lines) > 1
            else first_line_without_flags
        )
    else:
        message_text = remaining_text

    return flags, message_text.strip()


# =========================
# GET RECIPIENTS
# =========================

async def _get_broadcast_recipients(flags: List[str]) -> Tuple[List[int], List[int]]:

    groups = []
    users = []

    if "-nochat" not in flags:
        groups = await db.get_chats()

    if "-user" in flags:
        users = await db.get_users()

    return groups, users


# =========================
# LOG START
# =========================

async def _log_broadcast_start(message: types.Message):

    try:
        log_message = await app.send_message(
            chat_id=app.logger,
            text=message.lang["gcast_log"].format(
                message.from_user.id,
                message.from_user.mention,
                message.text,
            )
        )
        try:
            await log_message.pin(disable_notification=False)
        except:
            pass
    except:
        pass


# =========================
# EXTRACT REPLY MARKUP (buttons)
# =========================

def _get_reply_markup(msg: types.Message):
    """Extract inline keyboard buttons from a message to forward."""
    try:
        if msg.reply_markup and isinstance(msg.reply_markup, types.InlineKeyboardMarkup):
            return msg.reply_markup
    except:
        pass
    return None


# =========================
# MAIN BROADCAST SYSTEM
# =========================

async def _send_broadcast(
    text: str,
    groups: List[int],
    users: List[int],
    status_message: types.Message,
    media_message: types.Message | None = None,
    flags: List[str] = None,
    lang: dict = None,
    media_group: List[types.Message] = None,
):
    global broadcasting

    if flags is None:
        flags = []

    success_groups = 0
    success_users = 0
    failed_log = ""

    all_chats = groups + users
    total_chats = len(all_chats)

    # Extract inline buttons from source message
    reply_markup = _get_reply_markup(media_message) if media_message else None

    for index, chat_id in enumerate(all_chats, start=1):

        if not broadcasting:
            try:
                await status_message.edit_text(
                    lang["gcast_stopped"].format(success_groups, success_users)
                )
            except:
                pass
            break

        # Progress update every 20 messages
        if index % 20 == 0:
            try:
                await status_message.edit_text(
                    f"📤 Broadcasting...\n\n"
                    f"Progress: {index}/{total_chats}\n"
                    f"✅ Groups: {success_groups}\n"
                    f"✅ Users: {success_users}"
                )
            except:
                pass

        try:
            # =========================
            # VALIDATE GROUPS/CHANNELS
            # =========================

            if chat_id in groups:
                try:
                    chat = await app.get_chat(chat_id)

                    if not chat:
                        await db.rm_chat(chat_id)
                        failed_log += f"{chat_id} - Invalid chat removed\n"
                        continue

                    allowed_types = [
                        enums.ChatType.GROUP,
                        enums.ChatType.SUPERGROUP,
                        enums.ChatType.CHANNEL
                    ]

                    if chat.type not in allowed_types:
                        failed_log += f"{chat_id} - Unsupported chat type\n"
                        continue

                    me = await app.get_chat_member(chat_id, "me")

                    if chat.type == enums.ChatType.CHANNEL:
                        if not me.privileges or not me.privileges.can_post_messages:
                            failed_log += f"{chat_id} - No permission\n"
                            continue

                except Exception as e:
                    try:
                        await db.rm_chat(chat_id)
                    except:
                        pass
                    failed_log += f"{chat_id} - Removed: {type(e).__name__}\n"
                    continue

            sent_message = None

            # =========================
            # SEND MEDIA GROUP (album)
            # =========================

            if media_group:

                media_list = []

                for idx, msg in enumerate(media_group):
                    caption = text if idx == 0 and text else (msg.caption if idx == 0 else None)

                    if msg.photo:
                        file_id = (
                            msg.photo.file_id
                            if hasattr(msg.photo, "file_id")
                            else msg.photo[-1].file_id
                        )
                        media_list.append(
                            types.InputMediaPhoto(media=file_id, caption=caption)
                        )

                    elif getattr(msg, "video", None):
                        media_list.append(
                            types.InputMediaVideo(media=msg.video.file_id, caption=caption)
                        )

                    elif getattr(msg, "document", None):
                        media_list.append(
                            types.InputMediaDocument(media=msg.document.file_id, caption=caption)
                        )

                    elif getattr(msg, "audio", None):
                        media_list.append(
                            types.InputMediaAudio(media=msg.audio.file_id, caption=caption)
                        )

                if media_list:
                    sent_msgs = await app.send_media_group(chat_id=chat_id, media=media_list)
                    sent_message = sent_msgs[0] if sent_msgs else None
                else:
                    continue

            # =========================
            # SEND SINGLE MEDIA
            # =========================

            elif media_message:

                caption = text if text else (media_message.caption or "")
                caption_entities = None if text else media_message.caption_entities

                # 🖼️ Photo
                if media_message.photo:
                    file_id = (
                        media_message.photo.file_id
                        if hasattr(media_message.photo, "file_id")
                        else media_message.photo[-1].file_id
                    )
                    sent_message = await app.send_photo(
                        chat_id, file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        reply_markup=reply_markup
                    )

                # 🎬 Video
                elif getattr(media_message, "video", None):
                    sent_message = await app.send_video(
                        chat_id, media_message.video.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        reply_markup=reply_markup
                    )

                # 📄 Document
                elif getattr(media_message, "document", None):
                    sent_message = await app.send_document(
                        chat_id, media_message.document.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        reply_markup=reply_markup
                    )

                # 🎵 Audio
                elif getattr(media_message, "audio", None):
                    sent_message = await app.send_audio(
                        chat_id, media_message.audio.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        reply_markup=reply_markup
                    )

                # 🎙️ Voice note
                elif getattr(media_message, "voice", None):
                    sent_message = await app.send_voice(
                        chat_id, media_message.voice.file_id,
                        caption=caption,
                        reply_markup=reply_markup
                    )

                # 📹 Video note (round video)
                elif getattr(media_message, "video_note", None):
                    sent_message = await app.send_video_note(
                        chat_id, media_message.video_note.file_id
                    )

                # 🎞️ GIF / Animation
                elif getattr(media_message, "animation", None):
                    sent_message = await app.send_animation(
                        chat_id, media_message.animation.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        reply_markup=reply_markup
                    )

                # 🎭 Sticker
                elif getattr(media_message, "sticker", None):
                    sent_message = await app.send_sticker(
                        chat_id, media_message.sticker.file_id
                    )

                # 📊 Poll
                elif getattr(media_message, "poll", None):
                    poll = media_message.poll
                    sent_message = await app.send_poll(
                        chat_id,
                        question=poll.question,
                        options=[opt.text for opt in poll.options],
                        is_anonymous=poll.is_anonymous,
                        allows_multiple_answers=poll.allows_multiple_answers,
                    )

                # 📍 Location
                elif getattr(media_message, "location", None):
                    loc = media_message.location
                    sent_message = await app.send_location(
                        chat_id,
                        latitude=loc.latitude,
                        longitude=loc.longitude
                    )

                # 📞 Contact
                elif getattr(media_message, "contact", None):
                    c = media_message.contact
                    sent_message = await app.send_contact(
                        chat_id,
                        phone_number=c.phone_number,
                        first_name=c.first_name,
                        last_name=c.last_name or ""
                    )

                # ✍️ Text with buttons fallback
                else:
                    msg_text = text or media_message.text or media_message.caption or ""
                    entities = media_message.entities or media_message.caption_entities
                    sent_message = await app.send_message(
                        chat_id, msg_text,
                        entities=entities,
                        reply_markup=reply_markup
                    )

            # =========================
            # SEND PLAIN TEXT
            # =========================

            else:
                sent_message = await app.send_message(
                    chat_id, text,
                    reply_markup=reply_markup
                )

            # =========================
            # PIN IF FLAGGED
            # =========================

            if sent_message and chat_id in groups:
                try:
                    if "-pin" in flags:
                        await sent_message.pin(disable_notification=True)
                    elif "-pinloud" in flags:
                        await sent_message.pin(disable_notification=False)
                except:
                    pass

            # =========================
            # COUNT SUCCESS
            # =========================

            if chat_id in groups:
                success_groups += 1
            else:
                success_users += 1

            await asyncio.sleep(0.3)

        # =========================
        # FLOOD WAIT
        # =========================

        except errors.FloodWait as fw:
            await asyncio.sleep(fw.value + 3)
            continue

        # =========================
        # KNOWN FAILURES
        # =========================

        except (
            errors.ChannelPrivate,
            errors.PeerIdInvalid,
            errors.ChatAdminRequired,
            errors.ChatWriteForbidden,
            errors.UserIsBlocked,
            errors.InputUserDeactivated,
            errors.UserDeactivated,
        ) as e:
            try:
                if chat_id in groups:
                    await db.rm_chat(chat_id)
            except:
                pass
            failed_log += f"{chat_id} - {type(e).__name__}\n"
            continue

        # =========================
        # OTHER ERRORS
        # =========================

        except Exception as ex:
            failed_log += f"{chat_id} - {type(ex).__name__}: {str(ex)}\n"
            continue

    return success_groups, success_users, failed_log


# =========================
# COMPLETION
# =========================

async def _send_broadcast_completion(
    message: types.Message,
    status_message: types.Message,
    success_groups: int,
    success_users: int,
    failed_log: str,
    media_message: types.Message | None = None,
):
    media_type = "text"

    if media_message:
        if media_message.photo:                              media_type = "photo"
        elif getattr(media_message, "video", None):         media_type = "video"
        elif getattr(media_message, "audio", None):         media_type = "audio"
        elif getattr(media_message, "document", None):      media_type = "document"
        elif getattr(media_message, "animation", None):     media_type = "animation"
        elif getattr(media_message, "sticker", None):       media_type = "sticker"
        elif getattr(media_message, "voice", None):         media_type = "voice"
        elif getattr(media_message, "video_note", None):    media_type = "video_note"
        elif getattr(media_message, "poll", None):          media_type = "poll"
        elif getattr(media_message, "location", None):      media_type = "location"
        elif getattr(media_message, "contact", None):       media_type = "contact"

    completion_text = message.lang["gcast_end"].format(success_groups, success_users)

    if media_message:
        completion_text += f"\n📎 Media type: `{media_type}`"

    if failed_log:
        error_file = "errors.txt"
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(failed_log)
        await message.reply_document(document=error_file, caption=completion_text)
        os.remove(error_file)

    try:
        await status_message.edit_text(completion_text)
    except:
        pass