"""Send a test email using backend/.env SMTP settings.

Usage:
    cd backend
    .venv/bin/python test_mail.py you@qq.com
"""
from __future__ import annotations

import asyncio
import sys

import config
import mailer


async def main() -> None:
    to = sys.argv[1] if len(sys.argv) > 1 else config.SMTP_FROM
    if not to:
        print("请提供收件人：python test_mail.py you@qq.com")
        return
    if not mailer.is_configured():
        print(
            "SMTP 未配置：请在 backend/.env 设置 "
            "SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM"
        )
        return
    ok = await mailer.send_email(
        to,
        "Atoms Demo SMTP 测试",
        "这是一封来自 Atoms Demo 的 SMTP 测试邮件。",
        "<p>这是一封来自 Atoms Demo 的 SMTP 测试邮件。</p>",
    )
    print("发送成功" if ok else "发送失败，请检查 SMTP 配置和后端日志")


if __name__ == "__main__":
    asyncio.run(main())
