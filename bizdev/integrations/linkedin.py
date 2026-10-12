"""LinkedIn: capability-based, manual-send by default.

Findings (from LinkedIn's public developer documentation, as of this build):
- Sign In with LinkedIn (OpenID Connect: openid, profile, email) is self-serve.
- Share on LinkedIn (w_member_social) lets an app post to the member's own feed.
- Messaging, connection requests, and profile search of *other* members are NOT
  available to general apps. They require partner programs (e.g. Sales Navigator
  Application Platform / SNAP, Talent Solutions) that LinkedIn grants by contract.
- LinkedIn's User Agreement prohibits scraping and browser-automation bots.

So this module never sends messages or connection requests itself. Unless an
approved partner capability is recorded (by an admin, with evidence of the
partner agreement), every LinkedIn message becomes MANUAL_PENDING: a drafted,
personalised note plus the verified profile URL, which the admin sends by hand
and then confirms in the dashboard.
"""
from __future__ import annotations

KNOWN_CAPABILITIES = {"sign_in", "share_own_feed", "partner_messaging", "partner_profile_lookup"}
DEFAULT_CAPS = {"sign_in": False, "share_own_feed": False, "partner_messaging": False, "partner_profile_lookup": False}


class LinkedInActionBlocked(Exception):
    pass


class LinkedInIntegration:
    def __init__(self, capabilities: dict | None = None):
        self.caps = {**DEFAULT_CAPS, **(capabilities or {})}

    def can(self, cap: str) -> bool:
        return bool(self.caps.get(cap))

    def send_message(self, profile_url: str, text: str) -> str:
        if not self.can("partner_messaging"):
            raise LinkedInActionBlocked("LinkedIn messaging is not authorized for this integration; use manual send.")
        # A partner integration would be implemented here against the contracted API.
        raise LinkedInActionBlocked("Partner messaging adapter not implemented; no partner contract configured.")

    def send_connection_request(self, *_a, **_k):
        raise LinkedInActionBlocked("Automated connection requests are not permitted.")

    def scrape_profile(self, *_a, **_k):
        raise LinkedInActionBlocked("Profile scraping is prohibited by LinkedIn's terms.")
