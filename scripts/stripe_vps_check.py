#!/usr/bin/env python3
"""
Stripe VPS Configuration Diagnostic

Run this on the VPS where SHIOL-PLUS is deployed. It validates:
 - Required environment variables for Stripe
 - Feature flag for billing
 - Outbound connectivity to api.stripe.com:443
 - Stripe API access using configured secret key (optional, safe, redacted)
 - Price ID existence check (if configured)

Exit code is non-zero if any critical checks fail.

Usage:
  python scripts/stripe_vps_check.py [--no-stripe-api]

Notes:
 - Secrets are masked when printed.
 - The Stripe API check only runs if STRIPE_SECRET_KEY looks valid and is not the fallback test value.
"""

from __future__ import annotations

import os
import sys
import socket
import ssl
from dataclasses import dataclass
from typing import List


def mask_secret(value: str | None, show: int = 6) -> str:
    if not value:
        return "<missing>"
    if len(value) <= show:
        return "*" * len(value)
    return f"{'*' * (len(value)-show)}{value[-show:]}"


@dataclass
class CheckResult:
    name: str
    ok: bool
    info: str = ""


def check_env_vars() -> List[CheckResult]:
    required = [
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_ID_ANNUAL",
    ]
    results: List[CheckResult] = []
    for key in required:
        val = os.getenv(key)
        masked = mask_secret(val)
        ok = bool(val and not val.endswith("_NOT_SET"))
        results.append(CheckResult(f"env:{key}", ok, f"{masked}"))

    feature = os.getenv("FEATURE_BILLING_ENABLED", "true").lower() in {"true", "1", "yes", "on"}
    results.append(CheckResult("feature:FEATURE_BILLING_ENABLED", feature, str(feature)))
    results.append(CheckResult("env:ENVIRONMENT", True, os.getenv("ENVIRONMENT", "development")))
    return results


def check_egress(host: str = "api.stripe.com", port: int = 443, timeout: float = 4.0) -> CheckResult:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                pass  # TLS handshake succeeded
        return CheckResult("network:egress_tls", True, f"Connected to {host}:{port}")
    except Exception as e:
        return CheckResult("network:egress_tls", False, f"{type(e).__name__}: {e}")


def check_stripe_api() -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        import stripe  # type: ignore
    except Exception as e:
        return [CheckResult("python:stripe_lib", False, f"{e}")]

    secret = os.getenv("STRIPE_SECRET_KEY")
    price_id = os.getenv("STRIPE_PRICE_ID_ANNUAL")
    if not secret or secret.endswith("_NOT_SET"):
        return [CheckResult("stripe:api_key_present", False, "Missing or fallback key; skipping API call")] 

    stripe.api_key = secret
    # Basic account ping: retrieve current account
    try:
        acct = stripe.Account.retrieve()
        results.append(CheckResult("stripe:account", True, f"{acct.get('id','unknown')}, {acct.get('charges_enabled','?')}"))
    except Exception as e:
        results.append(CheckResult("stripe:account", False, f"{type(e).__name__}: {e}"))

    # Price existence check (non-destructive)
    if price_id:
        try:
            price = stripe.Price.retrieve(price_id)
            results.append(CheckResult("stripe:price", True, f"{price.get('id','unknown')} currency={price.get('currency','?')}"))
        except Exception as e:
            results.append(CheckResult("stripe:price", False, f"{type(e).__name__}: {e}"))
    else:
        results.append(CheckResult("stripe:price", False, "STRIPE_PRICE_ID_ANNUAL not set"))

    return results


def main() -> int:
    no_api = "--no-stripe-api" in sys.argv

    results: List[CheckResult] = []
    results.extend(check_env_vars())
    results.append(check_egress())
    if not no_api:
        results.extend(check_stripe_api())
    else:
        results.append(CheckResult("stripe:api_checks", True, "skipped"))

    # Pretty print
    print("\n=== Stripe VPS Diagnostics ===")
    width = max(len(r.name) for r in results) + 2
    failures = 0
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        if not r.ok:
            failures += 1
        print(f"{r.name.ljust(width)} {status}  - {r.info}")

    print("\nSummary:")
    print(f"  Total checks: {len(results)} | Failures: {failures}")
    print("\nTips:")
    print(" - If network egress fails, open outbound TCP 443 to api.stripe.com in your firewall.")
    print(" - Ensure ENV vars are exported in your systemd service or container env (not only your shell).")
    print(" - Use the new success_url (activate-via-redirect) so the server sets the premium cookie.")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
