import os
import logging
import asyncpg

DB_POOL = None

async def db_init():
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    await db_migrate()

async def db_migrate():
    """Tự động fix schema nếu constraint cũ bị sai."""
    async with DB_POOL.acquire() as conn:
        # Thêm cột sheet_title nếu chưa có
        await conn.execute("""
            ALTER TABLE user_sheets ADD COLUMN IF NOT EXISTS sheet_title TEXT;
        """)

        # Xoá constraint cũ sai (UNIQUE chỉ trên telegram_user_id)
        old_constraints = await conn.fetch("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'user_sheets'::regclass
              AND contype = 'u'
              AND conname != 'user_sheets_telegram_user_id_sheet_id_key';
        """)
        for row in old_constraints:
            cname = row["conname"]
            logging.info(f"[migrate] Dropping old constraint: {cname}")
            await conn.execute(f'ALTER TABLE user_sheets DROP CONSTRAINT IF EXISTS "{cname}";')

        # Tạo constraint đúng nếu chưa có
        await conn.execute("""
            ALTER TABLE user_sheets
            ADD CONSTRAINT user_sheets_telegram_user_id_sheet_id_key
            UNIQUE (telegram_user_id, sheet_id)
            DEFERRABLE INITIALLY DEFERRED;
        """ if not await conn.fetchval("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'user_sheets'::regclass
              AND conname = 'user_sheets_telegram_user_id_sheet_id_key';
        """) else "SELECT 1;")

        logging.info("[migrate] DB schema OK")

async def db_touch_user(telegram_user_id: int, telegram_chat_id: int):
    if DB_POOL is None:
        return
    q = """
    INSERT INTO bot_users (telegram_user_id, telegram_chat_id, first_seen, last_seen)
    VALUES ($1, $2, NOW(), NOW())
    ON CONFLICT (telegram_user_id)
    DO UPDATE SET telegram_chat_id = EXCLUDED.telegram_chat_id, last_seen = NOW();
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(q, telegram_user_id, telegram_chat_id)

async def db_get_user_sheet(telegram_user_id: int):
    if DB_POOL is None:
        return None
    q = "SELECT sheet_id, sheet_url FROM user_sheets WHERE telegram_user_id = $1;"
    async with DB_POOL.acquire() as conn:
        row = await conn.fetchrow(q, telegram_user_id)
        return dict(row) if row else None

async def db_upsert_user_sheet(
    telegram_user_id: int,
    telegram_chat_id: int,
    sheet_url: str,
    sheet_id: str,
    sheet_title: str,
):
    if DB_POOL is None:
        return
    q = """
    INSERT INTO user_sheets (telegram_user_id, telegram_chat_id, sheet_url, sheet_id, sheet_title, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
    ON CONFLICT (telegram_user_id, sheet_id)
    DO UPDATE SET
        telegram_chat_id = EXCLUDED.telegram_chat_id,
        sheet_url = EXCLUDED.sheet_url,
        sheet_title = EXCLUDED.sheet_title,
        updated_at = NOW();
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(q, telegram_user_id, telegram_chat_id, sheet_url, sheet_id, sheet_title)

async def db_list_user_sheets(telegram_user_id: int):
    if DB_POOL is None:
        return []
    q = """
    SELECT sheet_id, sheet_url, COALESCE(sheet_title, sheet_id) AS sheet_title
    FROM user_sheets
    WHERE telegram_user_id = $1
    ORDER BY updated_at DESC;
    """
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch(q, telegram_user_id)
        return [dict(r) for r in rows]

async def db_get_all_chat_ids():
    if DB_POOL is None:
        return []
    q = "SELECT telegram_chat_id FROM bot_users;"
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch(q)
        return [r["telegram_chat_id"] for r in rows]
