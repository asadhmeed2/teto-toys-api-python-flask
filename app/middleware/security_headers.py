"""
Baseline response hardening.

These are cheap and apply to every response. Note this is a JSON API, so the
headers that matter here are the ones limiting how a browser may *interpret* and
*embed* responses — a full CSP belongs on whatever serves the Angular bundles,
not here, since an API response has no scripts to restrict.

Kept in sync with the C# and node equivalents.
"""

import os

HEADERS = {
    # Stop the browser second-guessing Content-Type. Without it, a JSON response
    # an attacker can influence may be sniffed as HTML and executed.
    'X-Content-Type-Options': 'nosniff',
    # No reason to ever frame an API response; blocks clickjacking on any
    # HTML error page the stack might emit.
    'X-Frame-Options': 'DENY',
    # Don't spill the full URL (which can carry ids or tokens) to third parties.
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    # The API needs none of these device APIs; deny them explicitly.
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
    'X-Permitted-Cross-Domain-Policies': 'none',
}


def register_security_headers(app):
    """Attaches the headers to every response, including error responses."""

    is_production = os.getenv('FLASK_ENV', 'development').lower() == 'production'

    @app.after_request
    def _apply_security_headers(response):
        for header, value in HEADERS.items():
            response.headers.setdefault(header, value)

        # HSTS tells browsers to refuse plain HTTP for this host. Production only —
        # on localhost it would pin the dev machine to HTTPS and break local work.
        if is_production:
            response.headers.setdefault(
                'Strict-Transport-Security', 'max-age=31536000; includeSubDomains'
            )

        # Werkzeug advertises its version by default; no reason to name the stack.
        response.headers['Server'] = 'teto-toys'

        return response
