"""Official Instagram Graph API (Content Publishing + Insights). No scraping, no unofficial APIs."""
import time

import requests


class IG:
    def __init__(self, user_id, token, version):
        self.uid, self.token = user_id, token
        self.base = f"https://graph.facebook.com/{version}"

    def _post(self, path, **params):
        r = requests.post(f"{self.base}/{path}", data={**params, "access_token": self.token}, timeout=120)
        if r.status_code >= 400:
            raise RuntimeError(f"Graph API {path}: {r.status_code} {r.text}")
        return r.json()

    def _get(self, path, **params):
        r = requests.get(f"{self.base}/{path}", params={**params, "access_token": self.token}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Graph API {path}: {r.status_code} {r.text}")
        return r.json()

    def _wait(self, container_id, timeout=600):
        start = time.time()
        while time.time() - start < timeout:
            status = self._get(container_id, fields="status_code").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"container {container_id} status {status}")
            time.sleep(10)
        raise TimeoutError(container_id)

    def publish_carousel(self, image_urls, caption):
        children = [self._post(f"{self.uid}/media", image_url=u, is_carousel_item="true")["id"] for u in image_urls]
        for c in children:
            self._wait(c)
        parent = self._post(f"{self.uid}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
        self._wait(parent)
        return self._post(f"{self.uid}/media_publish", creation_id=parent)["id"]

    def publish_reel(self, video_url, cover_url, caption):
        cid = self._post(f"{self.uid}/media", media_type="REELS", video_url=video_url, cover_url=cover_url,
                         caption=caption, share_to_feed="true")["id"]
        self._wait(cid, timeout=900)
        return self._post(f"{self.uid}/media_publish", creation_id=cid)["id"]

    def recent_media(self, limit=50):
        return self._get(f"{self.uid}/media", fields="id,caption,media_type,timestamp,like_count,comments_count",
                         limit=limit).get("data", [])

    def insights(self, media_id):
        try:
            data = self._get(f"{media_id}/insights", metric="reach,saved,shares,total_interactions").get("data", [])
            return {m["name"]: m["values"][0]["value"] for m in data}
        except RuntimeError as e:
            return {"error": str(e)[:200]}

    def followers(self):
        return self._get(self.uid, fields="followers_count,media_count")
