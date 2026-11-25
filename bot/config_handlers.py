"""
bot/config_handlers.py

Runtime introspection: /config and /chatid. Everything the bot can only know
about itself once it is running — which .env was actually read, where the data
is, how stale it is, who automatic messages reach.

Nothing warns at startup any more — this is the one place that reports state,
and only when you ask. /config answers "is the setup sane?" in one message,
from the phone, without a terminal.

It never prints a secret: the token is reported as set or unset, and chat ids
are counted rather than listed (/chatid shows the one you are standing in).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import env, paths
from config import telegram as tg
from config.instruments import DORMANT, GROUPS, INSTRUMENTS
from config.sheet_keys import SHEET_TO_KEY
from config.spreads import SPREADS

OK, BAD = "O", "X"


def _env_block() -> list[str]:
    loaded = sorted(env.LOADED)
    return [".env",
            f"  {env.ENV_PATH}",
            f"  읽은 키 {len(loaded)}개: {', '.join(loaded) if loaded else '(없음)'}"]


def _paths_block() -> list[str]:
    out = ["경로"]
    for name, p, pattern, optional in (
        ("RAW_DIR", paths.RAW_DIR, "*.xls*", False),
        ("PROCESSED_DIR", paths.PROCESSED_DIR, "*.csv", False),
        ("MACRO_DIR", paths.MACRO_DIR, "*.csv", True),
    ):
        if p.exists():
            n = len([f for f in p.glob(pattern) if not f.name.startswith("~$")])
            out.append(f"  {OK} {name}: {n}개  {p}")
        else:
            tag = " (선택)" if optional else ""
            out.append(f"  {BAD} {name}: 없음{tag}  {p}")
    if paths.EXTRA_BOOKS:
        found = sum(1 for b in paths.EXTRA_BOOKS if b.exists())
        out.append(f"  EXTRA_BOOKS: {found}/{len(paths.EXTRA_BOOKS)}개 접근 가능")
    return out


def _data_block() -> list[str]:
    """Freshness per book. A stale book is the usual cause of a stale command."""
    from storage.loader import DATE_COL, load_market

    files = sorted({i.get("file", name) for name, i in INSTRUMENTS.items()})
    stamps: list[tuple[str, object]] = []
    missing: list[str] = []
    for key in files:
        try:
            df = load_market(key)
            stamps.append((key, df[DATE_COL].max()))
        except Exception:  # noqa: BLE001  report it, never raise out of /config
            missing.append(key)

    out = ["데이터"]
    if stamps:
        stamps.sort(key=lambda s: s[1])
        oldest, newest = stamps[0], stamps[-1]
        out.append(f"  최신: {newest[1]:%Y-%m-%d} ({newest[0]})")
        out.append(f"  최후행: {oldest[1]:%Y-%m-%d} ({oldest[0]})")
        if oldest[1] != newest[1]:
            lag = (newest[1] - oldest[1]).days
            out.append(f"  편차 {lag}일 — 해당 북이 갱신 안 됐을 수 있음")
    if missing:
        out.append(f"  {BAD} 읽기 실패: {', '.join(missing)} (/update 필요)")

    # CSVs nothing produces any more — usually left behind when a key in
    # config/sheet_keys.py was renamed. Harmless, but they go stale silently
    # and look like live data to anyone browsing the folder.
    if paths.PROCESSED_DIR.exists():
        produced = set(SHEET_TO_KEY.values())
        orphans = sorted(f.stem for f in paths.PROCESSED_DIR.glob("*.csv")
                         if f.stem not in produced)
        if orphans:
            shown = ", ".join(orphans[:6]) + (" …" if len(orphans) > 6 else "")
            out.append(f"  고아 CSV {len(orphans)}개 (생성되지 않음): {shown}")
    return out


def _telegram_block(chat_id) -> list[str]:
    registered = str(chat_id) in tg.CHAT_IDS
    return ["텔레그램",
            f"  토큰: {'설정됨' if tg.TOKEN else '미설정'}",
            f"  자동 발송: {len(tg.CHAT_IDS)}개 채팅",
            f"  이 대화방: {'등록됨' if registered else '미등록 (/chatid 참고)'}"]


def _registry_block() -> list[str]:
    from research.registry import iter_commands
    n = len(list(iter_commands(INSTRUMENTS, GROUPS)))
    return ["레지스트리",
            f"  instruments {len(INSTRUMENTS)} · groups {len(GROUPS)} · "
            f"commands {n}",
            f"  spreads {len(SPREADS)} · dormant {len(DORMANT)}"]


def build_report(chat_id) -> str:
    blocks = [["[설정 점검]"], _env_block(), _paths_block(),
              _data_block(), _telegram_block(chat_id), _registry_block()]
    return "\n\n".join("\n".join(b) for b in blocks)


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        text = build_report(chat_id)
    except Exception as e:  # noqa: BLE001
        text = f"[설정 점검 실패] {type(e).__name__}: {e}"
    await context.bot.send_message(chat_id=chat_id, text=text)


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report this chat's id — the only practical way to find a group's id.

    Add the bot to the room, send /chatid there, then put both ids in
    TELEGRAM_CHAT_ID separated by a comma and restart. Group ids are negative;
    the minus sign is part of the id.
    """
    chat = update.effective_chat
    known = "등록됨" if str(chat.id) in tg.CHAT_IDS else "미등록"
    await context.bot.send_message(chat_id=chat.id, text="\n".join([
        f"chat_id: {chat.id}",
        f"type: {chat.type}",
        f"자동 발송 대상: {known}",
        "",
        f"현재 등록: {', '.join(tg.CHAT_IDS) or '(없음)'}",
        f".env 의 TELEGRAM_CHAT_ID 에 쉼표로 추가 후 재시작: {env.ENV_PATH}",
    ]))


def register_config_handlers(app: Application):
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("chatid", chatid_command))
