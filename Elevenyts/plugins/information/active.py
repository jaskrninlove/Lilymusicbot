import os
from pyrogram import filters, types
from Elevenyts import app, db, lang, queue


@app.on_message(filters.command(["ac", "activevc"]) & app.sudo_filter)
@lang.language()
async def _activevc(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    if not db.active_calls:
        return await m.reply_text(m.lang["vc_empty"])

    if m.command[0] == "ac":
        return await m.reply_text(m.lang["vc_count"].format(len(db.active_calls)))

    sent = await m.reply_text(m.lang["vc_fetching"])
    text = ""

    for i, chat in enumerate(db.active_calls):
        playing = queue.get_current(chat)
        if playing:
            text += f"\n{i+1}. <code>{chat}</code>\n    ➜ {playing.title[:25]}"

    if len(text) < 4000:
        return await sent.edit_text(m.lang["vc_list"] + text)

    with open("activevc.txt", "w") as f:
        f.write(text)

    try:
        await sent.edit_media(
            media=types.InputMediaDocument(
                media="activevc.txt",
                caption=m.lang["vc_list"],
            )
        )
    finally:
        os.remove("activevc.txt")


@app.on_message(filters.command(["active"]) & app.sudo_filter)
@lang.language()
async def _active_stats(_, m: types.Message):
    try:
        await m.delete()
    except Exception:
        pass

    chats = await db.get_chats()
    users = await db.get_users()

    total_chats = len(chats)
    total_users = len(users)
    active_vc = len(db.active_calls)

    text = (
        f"📊 Bot Statistics\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"💬 Total Chats: `{total_chats}`\n"
        f"🎵 Active Voice Chats: `{active_vc}`\n"
    )

    await m.reply_text(text)


@app.on_message(filters.command(["users"]) & app.sudo_filter)
@lang.language()
async def _user_list(_, m: types.Message):
    """Show full user list as file if too long."""
    try:
        await m.delete()
    except Exception:
        pass

    users = await db.get_users()

    if not users:
        return await m.reply_text("❌ No users found in database.")

    text = f"👥 Total Users: {len(users)}\n\n"
    text += "\n".join([f"{i+1}. `{uid}`" for i, uid in enumerate(users)])

    if len(text) < 4000:
        return await m.reply_text(text)

    with open("users.txt", "w") as f:
        f.write(text)

    try:
        await m.reply_document(
            document="users.txt",
            caption=f"👥 Total Users: `{len(users)}`"
        )
    finally:
        os.remove("users.txt")


@app.on_message(filters.command(["chats"]) & app.sudo_filter)
@lang.language()
async def _chat_list(_, m: types.Message):
    """Show full chat list as file if too long."""
    try:
        await m.delete()
    except Exception:
        pass

    chats = await db.get_chats()

    if not chats:
        return await m.reply_text("❌ No chats found in database.")

    text = f"💬 Total Chats: {len(chats)}\n\n"
    text += "\n".join([f"{i+1}. `{cid}`" for i, cid in enumerate(chats)])

    if len(text) < 4000:
        return await m.reply_text(text)

    with open("chats.txt", "w") as f:
        f.write(text)

    try:
        await m.reply_document(
            document="chats.txt",
            caption=f"💬 Total Chats: `{len(chats)}`"
        )
    finally:
        os.remove("chats.txt")