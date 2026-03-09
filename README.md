# 🤖 AI Edu Automation — Content Ops Pipeline

Automated cross-posting of pre-written educational content to **LinkedIn** and **Instagram** using GitHub Actions.

---

## 📁 Project Structure

```
ai-edu-automation/
├── .github/workflows/
│   └── post.yml            # GitHub Actions: daily cron at 09:00 UTC
├── images/                  # Image assets (served via GitHub raw URLs)
├── content.csv              # Content schedule (source of truth)
├── poster.py                # Main automation script
├── requirements.txt         # Python dependencies
├── .gitignore
└── README.md
```

## 📊 CSV Schema

| Column           | Description                                           |
|------------------|-------------------------------------------------------|
| `scheduled_date` | `YYYY-MM-DD` — the day the post should go live        |
| `platform`       | `linkedin` or `instagram`                             |
| `post_type`      | `text` or `image`                                     |
| `text_content`   | The post body (supports multiline inside quotes)      |
| `image_urls`     | Repo-relative paths, semicolon-separated              |
| `status`         | `pending` → `posted` / `error` (managed by script)    |
| `posted_at`      | ISO timestamp, filled by script on success            |
| `error_log`      | Error message if post failed                          |

## 🔐 GitHub Secrets Setup

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name              | Description                                                  |
|--------------------------|--------------------------------------------------------------|
| `LINKEDIN_ACCESS_TOKEN`  | OAuth 2.0 token from your LinkedIn Developer App             |
| `LINKEDIN_PERSON_URN`    | Your LinkedIn person URN (e.g. `urn:li:person:AbCdEf`)      |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived token from Meta Developer portal                  |
| `INSTAGRAM_USER_ID`      | Your Instagram Business account's numeric User ID            |

> **Note:** `GITHUB_TOKEN` is automatically provided by GitHub Actions — you don't need to create it.

## 🚀 How It Works

1. **GitHub Actions** triggers daily at 09:00 UTC (or manually via `workflow_dispatch`).
2. **`poster.py`** reads `content.csv`, filters rows where `scheduled_date == today` and `status == pending`.
3. For each matching row, it calls the appropriate API (LinkedIn or Instagram).
4. On success → `status = posted`, `posted_at = <timestamp>`.
5. On failure → `status = error`, `error_log = <message>`. Other rows continue processing.
6. The updated CSV is committed and pushed back to the repo.

## 🧪 Local Testing (Dry Run)

```bash
pip install -r requirements.txt
python poster.py --dry-run
```

This logs what *would* be posted without making any API calls.

## 🔑 API Setup Guides

### LinkedIn Developer App
1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/).
2. Click **Create App** → fill in your app name, company page, and logo.
3. Under **Products**, request access to **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
4. Go to **Auth** tab → note your `Client ID` and `Client Secret`.
5. Generate an OAuth 2.0 access token using the 3-legged flow or the Developer Portal's token generator.
6. Find your Person URN by calling `GET https://api.linkedin.com/v2/userinfo` with your token.

### Instagram / Meta Graph API
1. Ensure your Instagram account is a **Business** or **Creator** account linked to a **Facebook Page**.
2. Go to [Meta Developers](https://developers.facebook.com/) → **Create App** → select **Business** type.
3. Add the **Instagram Graph API** product to your app.
4. Use the **Graph API Explorer** to generate a User Token with permissions: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`.
5. Exchange the short-lived token for a [long-lived token](https://developers.facebook.com/docs/instagram-api/getting-started#long-lived-tokens) (valid ~60 days).
6. Find your Instagram User ID via: `GET /me/accounts` → `GET /{page-id}?fields=instagram_business_account`.

---

*Built with 💡 by an automation enthusiast — zero cost, fully open source.*
