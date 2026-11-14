"""Transactional email delivery over SMTP.

If SMTP is not configured the caller falls back to a development mode where
the verification / reset URL is returned to the browser and written to the
log. That keeps the whole flow testable without an external mail account.
"""
from __future__ import annotations

import asyncio
import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import config

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def mode() -> str:
    return "smtp" if is_configured() else "dev"


def _send_sync(to: str, subject: str, text: str, html_body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM))
    message["To"] = to
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")

    if config.SMTP_TLS == "ssl":
        with smtplib.SMTP_SSL(
            config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT
        ) as smtp:
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASS)
            smtp.send_message(message)
        return

    with smtplib.SMTP(
        config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT
    ) as smtp:
        smtp.ehlo()
        if config.SMTP_TLS == "starttls":
            smtp.starttls()
            smtp.ehlo()
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASS)
        smtp.send_message(message)


async def send_email(to: str, subject: str, text: str, html_body: str) -> bool:
    if not is_configured():
        logger.info(
            "SMTP 未配置，未发送邮件（收件人 %s，主题 %s）", to, subject
        )
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, text, html_body)
        return True
    except Exception as exc:  # noqa: BLE001 - delivery failure must not crash a request
        logger.warning("发送邮件失败（收件人 %s）：%s", to, exc)
        return False


def _action_email(
    title: str,
    intro: str,
    button_label: str,
    url: str,
    footer: str,
) -> str:
    safe_url = html.escape(url, quote=True)
    return f"""\
<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;padding:32px 16px;background:#F6F6F6;
               font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',
               'Microsoft YaHei',sans-serif;color:#0C0C0C;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="max-width:560px;margin:0 auto;background:#FFFFFF;
                  border-radius:16px;padding:36px 36px 28px;">
      <tr><td>
        <div style="font-size:18px;font-weight:600;letter-spacing:-0.2px;">
          Atoms<span style="color:#4267FF;">.</span>
        </div>
        <h1 style="margin:26px 0 10px;font-size:24px;line-height:1.35;
                   font-weight:600;">{html.escape(title)}</h1>
        <p style="margin:0 0 24px;font-size:14px;line-height:1.7;color:#555555;">
          {html.escape(intro)}
        </p>
        <a href="{safe_url}"
           style="display:inline-block;background:#4267FF;color:#FFFFFF;
                  text-decoration:none;font-size:14px;font-weight:600;
                  padding:12px 24px;border-radius:10px;">
          {html.escape(button_label)}
        </a>
        <p style="margin:24px 0 6px;font-size:12px;line-height:1.6;color:#8A8A8A;">
          如果按钮无法点击，请复制以下链接到浏览器打开：
        </p>
        <p style="margin:0 0 24px;font-size:12px;line-height:1.6;
                  word-break:break-all;color:#4267FF;">{safe_url}</p>
        <hr style="border:none;border-top:1px solid #EEEEEE;margin:0 0 18px;" />
        <p style="margin:0;font-size:12px;line-height:1.6;color:#8A8A8A;">
          {html.escape(footer)}
        </p>
      </td></tr>
    </table>
  </body>
</html>
"""


async def send_verification_email(to: str, url: str) -> bool:
    if not is_configured():
        logger.info("验证链接（开发模式）%s -> %s", to, url)
    title = "验证你的邮箱"
    intro = "欢迎使用 Atoms Demo。点击下方按钮验证邮箱并激活账号。"
    text = (
        f"{intro}\n\n{url}\n\n"
        f"链接 {config.AUTH_VERIFY_TTL_HOURS} 小时内有效。"
        "如果这不是你本人的操作，请忽略此邮件。"
    )
    body = _action_email(
        title,
        intro,
        "验证邮箱",
        url,
        f"链接 {config.AUTH_VERIFY_TTL_HOURS} 小时内有效。"
        "如果这不是你本人的操作，请忽略此邮件。",
    )
    return await send_email(to, "验证你的 Atoms 邮箱", text, body)


async def send_reset_email(to: str, url: str) -> bool:
    if not is_configured():
        logger.info("重置链接（开发模式）%s -> %s", to, url)
    title = "重置密码"
    intro = "我们收到了重置 Atoms Demo 密码的请求。点击下方按钮设置新密码。"
    text = (
        f"{intro}\n\n{url}\n\n"
        f"链接 {config.AUTH_RESET_TTL_MINUTES} 分钟内有效。"
        "如果这不是你本人的操作，请忽略此邮件。"
    )
    body = _action_email(
        title,
        intro,
        "重置密码",
        url,
        f"链接 {config.AUTH_RESET_TTL_MINUTES} 分钟内有效。"
        "如果这不是你本人的操作，请忽略此邮件。",
    )
    return await send_email(to, "重置你的 Atoms 密码", text, body)
