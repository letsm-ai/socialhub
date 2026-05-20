"""
Email service powered by Resend.

Enabled when RESEND_API_KEY is set in env. Falls back to a no-op + log line
when missing, so the app still runs in environments without email configured
(useful for local dev).

Sender defaults to `info@letsm.io`; override with SENDER_EMAIL env var.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import resend

logger = logging.getLogger(__name__)


def _api_key() -> str:
    return (os.environ.get("RESEND_API_KEY") or "").strip()


def _sender() -> str:
    return (os.environ.get("SENDER_EMAIL") or "info@letsm.io").strip()


def is_configured() -> bool:
    return bool(_api_key())


def _ensure_configured() -> None:
    if not is_configured():
        raise RuntimeError("RESEND_API_KEY is not configured")
    resend.api_key = _api_key()


# ---------- Generic send -------------------------------------------------

async def send_email(
    *,
    to: str | list[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> dict:
    """Non-blocking send via resend SDK. Returns Resend response dict."""
    if not is_configured():
        logger.warning("Email skipped (RESEND_API_KEY not set): to=%s subject=%s", to, subject)
        return {"skipped": True, "reason": "not_configured"}

    resend.api_key = _api_key()
    params: dict = {
        "from": _sender(),
        "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    if reply_to:
        params["reply_to"] = reply_to

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info("Email sent: id=%s to=%s subject=%r", result.get("id"), to, subject[:60])
        return {"sent": True, "id": result.get("id")}
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to, e)
        raise


# ---------- HTML wrapper -------------------------------------------------

_BRAND_COLOR = "#10b981"  # SocialHub green


def render_layout(*, title: str, preheader: str, body_html: str, lang: str = "en") -> str:
    """A minimal, email-client-safe HTML wrapper with the SocialHub brand."""
    direction = "rtl" if lang == "ar" else "ltr"
    footer_text = (
        "أرسلت من SocialHub · letsm AI" if lang == "ar"
        else "Sent by SocialHub · letsmAI"
    )
    return f"""<!doctype html>
<html lang="{lang}" dir="{direction}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{title}</title>
  </head>
  <body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#0f172a;">
    <span style="display:none !important;visibility:hidden;mso-hide:all;font-size:0;line-height:0;max-height:0;max-width:0;opacity:0;overflow:hidden;">{preheader}</span>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f5f5f4;padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <tr>
              <td style="padding:28px 32px 0 32px;">
                <div style="font-size:24px;font-weight:800;letter-spacing:-0.5px;">
                  <span style="color:#0f172a;">letsm</span><span style="color:{_BRAND_COLOR};">AI</span>
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 32px 32px;font-size:15px;line-height:1.6;color:#1f2937;">
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px;border-top:1px solid #f1f5f9;color:#94a3b8;font-size:12px;">
                {footer_text}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


# ---------- Templates ----------------------------------------------------

async def send_password_reset(*, to: str, name: str, reset_url: str, lang: str = "en") -> dict:
    if lang == "ar":
        subject = "إعادة تعيين كلمة المرور — SocialHub"
        body = f"""
          <p>مرحباً {name}،</p>
          <p>تلقّينا طلباً لإعادة تعيين كلمة المرور لحسابك في SocialHub.</p>
          <p style="text-align:center;margin:28px 0;">
            <a href="{reset_url}" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">إعادة تعيين كلمة المرور</a>
          </p>
          <p>الرابط صالح لمدة <b>30 دقيقة</b>. إذا لم تطلب ذلك، تجاهل هذه الرسالة.</p>
          <p style="color:#94a3b8;font-size:12px;">إذا لم يعمل الزر، انسخ الرابط التالي إلى متصفّحك:<br>{reset_url}</p>
        """
        preheader = "أعد تعيين كلمة المرور خلال 30 دقيقة"
    else:
        subject = "Reset your SocialHub password"
        body = f"""
          <p>Hi {name},</p>
          <p>We received a request to reset your SocialHub password.</p>
          <p style="text-align:center;margin:28px 0;">
            <a href="{reset_url}" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">Reset password</a>
          </p>
          <p>The link is valid for <b>30 minutes</b>. If you didn't request this, ignore this email.</p>
          <p style="color:#94a3b8;font-size:12px;">If the button doesn't work, paste this URL into your browser:<br>{reset_url}</p>
        """
        preheader = "Reset your password within 30 minutes"

    html = render_layout(title=subject, preheader=preheader, body_html=body, lang=lang)
    return await send_email(to=to, subject=subject, html=html)


async def send_welcome(*, to: str, name: str, lang: str = "en") -> dict:
    if lang == "ar":
        subject = "أهلاً بك في SocialHub 👋"
        body = f"""
          <p>أهلاً {name}،</p>
          <p>تم إنشاء حسابك بنجاح في SocialHub — منصة العمليّات الموحّدة للواتساب وإنستقرام وفيسبوك.</p>
          <p>هديتك الترحيبية: <b>٥٠ رسالة مجانية</b> + تجربة كاملة لمدة <b>٧ أيام</b>.</p>
          <p style="margin:24px 0;">
            <a href="https://app.letsm.io/dashboard" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">ابدأ الآن</a>
          </p>
        """
        preheader = "هديتك: 50 رسالة + 7 أيام تجربة مجانية"
    else:
        subject = "Welcome to SocialHub 👋"
        body = f"""
          <p>Hi {name},</p>
          <p>Your SocialHub account is ready — the unified ops platform for WhatsApp, Instagram and Facebook.</p>
          <p>Welcome gift: <b>50 free messages</b> + a full <b>7-day trial</b>.</p>
          <p style="margin:24px 0;">
            <a href="https://app.letsm.io/dashboard" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">Open Dashboard</a>
          </p>
        """
        preheader = "Your gift: 50 messages + 7-day trial"

    html = render_layout(title=subject, preheader=preheader, body_html=body, lang=lang)
    return await send_email(to=to, subject=subject, html=html)


async def send_payment_receipt(*, to: str, name: str, amount_omr: float, description: str, lang: str = "en") -> dict:
    if lang == "ar":
        subject = f"تأكيد الدفع — {amount_omr:.3f} ر.ع."
        body = f"""
          <p>مرحباً {name}،</p>
          <p>تم استلام دفعتك بنجاح. التفاصيل:</p>
          <table cellpadding="0" cellspacing="0" border="0" style="width:100%;margin:18px 0;font-size:14px;">
            <tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;color:#64748b;">الوصف</td><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;text-align:end;">{description}</td></tr>
            <tr><td style="padding:10px 0;color:#64748b;">المبلغ</td><td style="padding:10px 0;text-align:end;font-weight:700;color:{_BRAND_COLOR};">{amount_omr:.3f} ر.ع.</td></tr>
          </table>
          <p style="color:#94a3b8;font-size:12px;">شكراً لاستخدامك SocialHub.</p>
        """
        preheader = f"تم استلام {amount_omr:.3f} ر.ع."
    else:
        subject = f"Payment received — {amount_omr:.3f} OMR"
        body = f"""
          <p>Hi {name},</p>
          <p>Your payment has been received. Details:</p>
          <table cellpadding="0" cellspacing="0" border="0" style="width:100%;margin:18px 0;font-size:14px;">
            <tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;color:#64748b;">Description</td><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;text-align:end;">{description}</td></tr>
            <tr><td style="padding:10px 0;color:#64748b;">Amount</td><td style="padding:10px 0;text-align:end;font-weight:700;color:{_BRAND_COLOR};">{amount_omr:.3f} OMR</td></tr>
          </table>
          <p style="color:#94a3b8;font-size:12px;">Thank you for choosing SocialHub.</p>
        """
        preheader = f"{amount_omr:.3f} OMR payment received"

    html = render_layout(title=subject, preheader=preheader, body_html=body, lang=lang)
    return await send_email(to=to, subject=subject, html=html)


async def send_trial_ending(*, to: str, name: str, days_left: int, lang: str = "en") -> dict:
    if lang == "ar":
        subject = f"تبقّى {days_left} أيام من تجربتك المجانية"
        body = f"""
          <p>مرحباً {name}،</p>
          <p>فترة التجربة المجانية لحسابك في SocialHub ستنتهي خلال <b>{days_left} أيام</b>.</p>
          <p>للاستمرار في استقبال الرسائل وإدارة محادثاتك بدون انقطاع، اختر الباقة المناسبة.</p>
          <p style="margin:24px 0;">
            <a href="https://app.letsm.io/dashboard/billing" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">عرض الباقات</a>
          </p>
        """
        preheader = f"{days_left} أيام متبقية من التجربة"
    else:
        subject = f"{days_left} days left in your free trial"
        body = f"""
          <p>Hi {name},</p>
          <p>Your SocialHub free trial will end in <b>{days_left} days</b>.</p>
          <p>To keep your conversations and channels running, pick a plan that fits.</p>
          <p style="margin:24px 0;">
            <a href="https://app.letsm.io/dashboard/billing" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">View plans</a>
          </p>
        """
        preheader = f"{days_left} days left in your trial"

    html = render_layout(title=subject, preheader=preheader, body_html=body, lang=lang)
    return await send_email(to=to, subject=subject, html=html)
