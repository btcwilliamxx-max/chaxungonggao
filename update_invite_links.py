# -*- coding: utf-8 -*-
"""
update_invite_links.py - 拉所有查询群的 invite_link, 写进 G:\餐补\群组映射表.json

为什么: chaxungonggao 跳转群用 tg://resolve?domain=c/chat_id 不是 Telegram 官方
支持的格式 (只打开 app 不跳群); 正确做法是用 https://t.me/+{invite_hash} 这种
跨平台 invite link。需要从 s2 session 拉每个群的 exported_invite。

用法:
  cd G:/餐补/chaxungonggao
  python -X utf8 update_invite_links.py                # 拉全部 561 查询群
  python -X utf8 update_invite_links.py --create-new   # 没 invite link 的群自动创建新邀请
"""
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetExportedChatInvitesRequest, ExportChatInviteRequest
from telethon.tl.types import ChatInviteExported
from telethon.errors import FloodWaitError, ChatAdminRequiredError

ROOT = Path(__file__).resolve().parent
MAPPING = Path(r'G:\餐补\群组映射表.json')
ENV_PATH = Path(r'G:\kefu_audit\.env')


def load_env():
    """从 kefu_audit/.env 读 s1 (TG_SESSION_STRING) 凭据 (server 才是群管理员)"""
    if not ENV_PATH.exists():
        raise RuntimeError(f'.env 不存在: {ENV_PATH}')
    env = {}
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()
    return (
        int(env.get('TG_API_ID', '0')),
        env.get('TG_API_HASH', ''),
        env.get('TG_SESSION_STRING', ''),  # s1 - server, 群管理员
    )


def to_input_chat_id(chat_id):
    s = str(chat_id)
    if s.startswith('-100'):
        return int(s)
    return int(f'-100{s}')


async def fetch_invite(client, chat_id, create_new=False):
    """拉单个群的 invite_link; 没 invite 时如果 create_new=True 则创建"""
    cid = to_input_chat_id(chat_id)
    try:
        # 先列已存在的 invite
        result = await client(GetExportedChatInvitesRequest(
            peer=cid,
            admin_id='me',  # 自己
            limit=1,
        ))
        if result.invites and len(result.invites) > 0:
            inv = result.invites[0]
            if isinstance(inv, ChatInviteExported) and not inv.revoked:
                return inv.link, 'existing'
    except (ChatAdminRequiredError, Exception) as e:
        # 没权限列 invite (非管理员), 跳过
        return None, f'no-admin:{type(e).__name__}'

    if not create_new:
        return None, 'no-invite'

    # 创建新 invite
    try:
        new_inv = await client(ExportChatInviteRequest(peer=cid))
        if isinstance(new_inv, ChatInviteExported):
            return new_inv.link, 'created'
    except Exception as e:
        return None, f'create-failed:{type(e).__name__}'

    return None, 'unknown'


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--create-new', action='store_true', help='没 invite 的群自动创建新邀请')
    ap.add_argument('--limit', type=int, default=0, help='限制处理群数 (0=全部)')
    args = ap.parse_args()

    api_id, api_hash, s1 = load_env()
    if not s1:
        print('X  TG_SESSION_STRING 不存在 (s1 - server 群管理员)')
        return

    with MAPPING.open(encoding='utf-8') as f:
        raw = json.load(f)

    chaxun_items = [(title, info) for title, info in raw.items()
                    if ('查询' in title or '查詢' in title) and info.get('chat_id')]
    if args.limit > 0:
        chaxun_items = chaxun_items[:args.limit]
    print(f'[*] 待处理: {len(chaxun_items)} 个查询群')

    client = TelegramClient(StringSession(s1), api_id, api_hash)
    await client.connect()
    me = await client.get_me()
    print(f'[*] 登录: @{me.username or me.first_name}')

    updated = 0
    skipped = 0
    no_invite = []
    for i, (title, info) in enumerate(chaxun_items, 1):
        cid = str(info.get('chat_id'))
        if i % 50 == 0 or i == 1:
            print(f'[{i}/{len(chaxun_items)}] {title[:30]} ...')
        try:
            link, status = await fetch_invite(client, cid, create_new=args.create_new)
            if link:
                if info.get('invite_link') != link:
                    info['invite_link'] = link
                    updated += 1
            else:
                no_invite.append((title, status))
                skipped += 1
        except FloodWaitError as e:
            print(f'  FloodWait {e.seconds}s, skip {title}')
            await asyncio.sleep(e.seconds + 1)
            skipped += 1
        except Exception as e:
            print(f'  ERR {title}: {type(e).__name__}: {e}')
            skipped += 1
        await asyncio.sleep(0.3)  # 避免触发 flood

    await client.disconnect()

    # 写回
    with MAPPING.open('w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f'\n[OK] 更新: {updated}, 跳过: {skipped}')
    if no_invite:
        print(f'\n[!] 没有 invite link 的群 ({len(no_invite)}):')
        for title, status in no_invite[:10]:
            print(f'  {title}: {status}')
        if len(no_invite) > 10:
            print(f'  ... 还有 {len(no_invite)-10} 个')


if __name__ == '__main__':
    asyncio.run(main())
