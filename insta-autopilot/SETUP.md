# Insta Autopilot: one-time setup (about 1–2 hours in total)

Meta requires a real person to create the accounts and the app. Doing it by bot breaks the Terms and gets accounts banned, so these steps are yours. After this, everything runs on its own.

## 1. Create the 7 Instagram accounts (10 min each)

| id in config | Suggested name idea | Language |
|---|---|---|
| funfacts | e.g. `@daily.mindblown` | English |
| econstories | e.g. `@money.stories.daily` | English |
| itihaas | e.g. `@itihaas.ki.kahaniyan` | Hindi |
| techai | e.g. `@ai.tips.daily` | English |
| telugutravel | e.g. `@telugu.yatra` | Telugu |
| telugucooking | e.g. `@amma.vanta` | Telugu |
| aiinfluencer | e.g. `@myra.virtual` | English |

For each account:
1. Sign up in the Instagram app. One phone can hold up to 5 accounts, so use a second phone or email for the rest.
2. Go to **Settings → Account type → Switch to professional → Creator** (or Business).
3. Add a profile picture, bio and link-in-bio. The AI influencer's bio must say **"AI-generated virtual creator"**.
4. Create a **Facebook Page** for it and link it: **Instagram Settings → Accounts Center → Add Facebook Page**.
5. Put the handle into `config/pages.yaml` (`handle:`).
6. **Warm up the account for 5–7 days before turning automation on.** Post 2–3 times by hand, fill in the profile and follow a few accounts in your niche. Brand-new accounts that post through the API on day 1 get restricted.

## 2. Create the Meta developer app (once, 20 min)
1. Go to https://developers.facebook.com → **My Apps → Create App** → use case **"Manage messaging & content on Instagram"** (type: Business).
2. Add the product **Instagram → API setup with Facebook login**.
3. Under **App roles**, make sure your Facebook user is Admin.
4. Open **Tools → Graph API Explorer**. Select your app, then **Get User Access Token** with these permissions:
   `instagram_basic, instagram_content_publish, instagram_manage_insights, pages_show_list, pages_read_engagement, business_management`
5. Swap the short-lived token for a **long-lived** one (60 days):
   `https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
6. Get the Page token and IG user id. Call `GET /me/accounts`, which gives each Page's `access_token` (this one doesn't expire) and `id`. Then call
   `GET /{page-id}?fields=instagram_business_account` to get the **IG user id**.
7. You can publish to your **own** accounts while the app is in Development mode, because you are the app admin. You don't need App Review for that.

## 3. Add GitHub secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from https://console.anthropic.com (writes the posts and checks them against the policy rules) |
| `PEXELS_API_KEY` | free key from https://www.pexels.com/api (royalty-free background photos) |
| `IG_FUNFACTS_USER_ID` / `IG_FUNFACTS_TOKEN` | IG user id / Page access token |
| … one pair per page id: `ECONSTORIES`, `ITIHAAS`, `TECHAI`, `TELUGUTRAVEL`, `TELUGUCOOKING`, `AIINFLUENCER` | |

A page with no secrets is skipped, so you can add accounts one at a time.

## 4. Repo settings
- **Settings → Actions → General → Workflow permissions:** set **Read and write** and tick **Allow GitHub Actions to create and approve pull requests**.
- **The repo must be public.** Instagram downloads the media from `raw.githubusercontent.com`. If you want to stay private, tell Claude and it will switch the media hosting to Netlify or Cloudflare R2.
- Merge this branch into `main`. Schedules only run from the default branch.

## 5. AI influencer images
Generate 20–40 consistent photos of "Myra" (same face, different scenes) with Higgsfield's AI Influencer tool. Claude can do this for you in a session. Put them in `pages/aiinfluencer/assets/`. That page stays paused until the folder has images.

## Daily routine (first 2 weeks)
At about 9 AM IST a PR called **"Review tomorrow's Instagram posts"** appears.
- **Merge it** to approve the posts and schedule them.
- **Close it** to reject them all.
- **Delete one post's folder** on the branch to drop just that post.

After `approval_until` in `config/pages.yaml` passes, posts go live without review. Change that date if you want to keep reviewing longer.

## Monthly cost estimate (₹)
| Item | Cost |
|---|---|
| Claude API (14 posts/day, writing + review) | ~₹1,500–3,000 |
| GitHub Actions (public repo) | free |
| Pexels, edge-tts voices | free |
| Higgsfield credits (AI influencer images, optional AI video) | ~₹2,000–5,000 |
| **Total** | **~₹3.5K–8K** |

## Maintenance
- **Page tokens:** Page tokens from a long-lived user token don't expire. If you change your Facebook password, generate new ones.
- **Weekly report:** `state/REPORT.md` updates every Monday. The writer uses your best-performing topics automatically.
- **Monetization checklist:** see `README.md`.
