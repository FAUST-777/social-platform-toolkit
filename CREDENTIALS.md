# Credentials Setup

所有機敏憑證（API keys、tokens、service account）存放在獨立的私有 repo：

**👉 https://github.com/FAUST-777/private-credentials-repo（私有）**

---

## 快速設定

```bash
# 1. Clone 憑證 repo
git clone https://github.com/FAUST-777/private-credentials-repo.git ~/private-credentials-repo

# 2. 複製 .env 到主專案
cp ~/private-credentials-repo/tiktok-marketing-api/.env \
   ~/social-platform-toolkit/tiktok-marketing-api/.env

# 3. 複製 tokens
cp -r ~/private-credentials-repo/tiktok-marketing-api/.tokens \
      ~/social-platform-toolkit/tiktok-marketing-api/.tokens
```

---

## 需要哪些憑證

| 變數 | 在哪裡取得 |
|---|---|
| `TIKTOK_APP_ID` | [TikTok Developer Portal](https://developers.tiktok.com/apps/) |
| `TIKTOK_APP_SECRET` | 同上 |
| `TIKTOK_ACCESS_TOKEN` | 執行 `python auth_advertiser.py` |
| `ANTHROPIC_API_KEY` | [platform.anthropic.com/settings/keys](https://platform.anthropic.com/settings/keys) |
| `GOOGLE_SHEET_ID` | TK大表 URL 中間段 |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `~/private-credentials-repo/google/service_account_key.json` |

詳細說明見 [private-credentials-repo/README.md](https://github.com/FAUST-777/private-credentials-repo)
