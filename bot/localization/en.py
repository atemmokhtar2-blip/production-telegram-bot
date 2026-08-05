from __future__ import annotations

MESSAGES = {
    "start": (
        "👋 Hello, {name}!\n\n"
        "Welcome to the production-ready Telegram bot.\n"
        "Use the menu below or type /help to see available commands."
    ),
    "help": (
        "📖 <b>Available commands</b>\n\n"
        "/start — Start the bot and register\n"
        "/help — Show this help message\n"
        "/profile — View your profile\n"
        "/stats — Show bot statistics (admin only)\n"
        "/users — List recent users (admin only)\n\n"
        "You can also use the reply keyboard buttons."
    ),
    "profile": (
        "👤 <b>Your profile</b>\n\n"
        "ID: <code>{telegram_id}</code>\n"
        "Username: {username}\n"
        "Name: {full_name}\n"
        "Admin: {is_admin}\n"
        "Registered: {created_at}"
    ),
    "stats": "📊 <b>Bot statistics</b>\n\nTotal users: <b>{total_users}</b>",
    "echo": "🔁 You said:\n\n{text}",
    "unknown": "❓ I don't understand that command. Type /help for available commands.",
    "admin_only": "🔒 This command is available only to administrators.",
    "users_list_header": "👥 <b>Recent users</b> (showing up to 20):\n\n",
}
