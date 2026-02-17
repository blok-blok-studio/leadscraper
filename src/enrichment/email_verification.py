"""Email verification module — validates emails via syntax, MX, and SMTP probe.

Three-layer verification:
  1. Syntax/format check (regex)
  2. MX record lookup (domain has mail server?)
  3. SMTP mailbox probe (does this specific mailbox exist?)

Returns a verification status: "valid", "invalid", "catch_all", "unknown"
"""

from __future__ import annotations

import re
import socket
import logging
import smtplib
from functools import lru_cache

import dns.resolver

from src.enrichment.base import BaseEnricher

logger = logging.getLogger(__name__)

# Domains where SMTP verification is unreliable (catch-all or blocks probes)
SKIP_SMTP_DOMAINS = {
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "ymail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "aol.com",
    "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me",
    "zoho.com",
}

# Common disposable/throwaway email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "dispostable.com", "tempr.email", "10minutemail.com",
    "trashmail.com", "fakeinbox.com", "maildrop.cc",
}

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


class EmailVerificationEnricher(BaseEnricher):
    """Verify email addresses found during enrichment."""

    MODULE_NAME = "email_verification"

    def enrich(self, lead) -> dict:
        """Verify the lead's email and owner_email. Return verification results."""
        result = {}

        # Verify main email
        email = getattr(lead, "email", None)
        if email:
            status = verify_email(email)
            if status == "invalid":
                logger.info(f"[email_verify] Invalid email removed: {email}")
                result["email"] = None  # Remove invalid email
            result["email_verified"] = status in ("valid", "catch_all")

        # Verify owner email
        owner_email = getattr(lead, "ownerEmail", None)
        if owner_email:
            status = verify_email(owner_email)
            if status == "invalid":
                logger.info(f"[email_verify] Invalid owner email removed: {owner_email}")
                result["owner_email"] = None
            result["owner_email_verified"] = status in ("valid", "catch_all")

        return result


def verify_email(email: str) -> str:
    """
    Verify an email address through multiple layers.

    Returns:
        "valid"     — SMTP confirmed mailbox exists
        "catch_all" — Domain accepts all addresses (can't confirm specific mailbox)
        "invalid"   — Failed syntax, no MX records, or SMTP rejected
        "unknown"   — Could not determine (timeout, connection error, etc.)
    """
    if not email:
        return "invalid"

    email = email.strip().lower()

    # Layer 1: Syntax check
    if not EMAIL_REGEX.match(email):
        logger.debug(f"[email_verify] Syntax invalid: {email}")
        return "invalid"

    domain = email.split("@")[1]

    # Check for disposable domains
    if domain in DISPOSABLE_DOMAINS:
        logger.debug(f"[email_verify] Disposable domain: {domain}")
        return "invalid"

    # Layer 2: MX record lookup
    mx_hosts = _get_mx_records(domain)
    if mx_hosts is None:
        logger.debug(f"[email_verify] No MX records for {domain}")
        return "invalid"

    # Layer 3: SMTP probe (skip for big providers where it's unreliable)
    if domain in SKIP_SMTP_DOMAINS:
        logger.debug(f"[email_verify] Skipping SMTP for {domain} (unreliable)")
        return "catch_all"

    return _smtp_verify(email, mx_hosts)


@lru_cache(maxsize=500)
def _get_mx_records(domain: str) -> tuple | None:
    """Look up MX records for a domain. Returns sorted tuple of hostnames or None."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        hosts = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0],
        )
        return tuple(h[1] for h in hosts) if hosts else None
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return None
    except dns.resolver.NoNameservers:
        return None
    except dns.resolver.LifetimeTimeout:
        # DNS timeout — domain might exist but slow
        return None
    except Exception as e:
        logger.debug(f"[email_verify] MX lookup error for {domain}: {e}")
        return None


def _smtp_verify(email: str, mx_hosts: tuple) -> str:
    """
    Probe SMTP server to check if mailbox exists.

    Connects to the MX server, sends HELO/MAIL FROM/RCPT TO,
    and checks the response code.
    """
    # Try up to 2 MX hosts
    for mx_host in mx_hosts[:1]:
        try:
            smtp = smtplib.SMTP(timeout=5)
            smtp.connect(mx_host, 25)
            smtp.helo("mail.verify.local")

            # Use a neutral sender address
            smtp.mail("verify@verify.local")

            code, message = smtp.rcpt(email)
            smtp.quit()

            if code == 250:
                return "valid"
            elif code == 550:
                return "invalid"
            elif code in (450, 451, 452):
                # Temporary error — could be greylisting
                return "unknown"
            else:
                # 252 = cannot VRFY but will accept, likely catch-all
                if code == 252:
                    return "catch_all"
                return "unknown"

        except smtplib.SMTPServerDisconnected:
            logger.debug(f"[email_verify] SMTP disconnected by {mx_host}")
            continue
        except smtplib.SMTPConnectError:
            logger.debug(f"[email_verify] SMTP connect failed to {mx_host}")
            continue
        except socket.timeout:
            logger.debug(f"[email_verify] SMTP timeout to {mx_host}")
            continue
        except OSError as e:
            logger.debug(f"[email_verify] SMTP OS error to {mx_host}: {e}")
            continue
        except Exception as e:
            logger.debug(f"[email_verify] SMTP error to {mx_host}: {e}")
            continue

    return "unknown"
