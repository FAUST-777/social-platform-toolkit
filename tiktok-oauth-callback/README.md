# Jushou TikTok OAuth Callback Service

Vercel-hosted OAuth callback endpoints for TikTok for Business API integrations.

## 部署方式（網頁拖檔，最簡單）

### Step 1: 註冊 Vercel 帳號
1. 開瀏覽器 → [https://vercel.com/signup](https://vercel.com/signup)
2. 選 **Continue with GitHub**（或 Google / Email 都可）
3. 完成註冊（如果還沒 GitHub 帳號，30 秒可申請一個）

### Step 2: 建立新專案
1. 進到 [https://vercel.com/new](https://vercel.com/new)
2. 點頁面下方 **"Browse all templates →"** 旁邊的 **"deploy from any folder"** 文字連結
3. 或者直接到 [https://vercel.com/new/clone](https://vercel.com/new/clone)

⚠️ Vercel 介面常變，如果找不到「拖檔」入口，請改走 Step 2-Alt。

### Step 2-Alt: 用 GitHub（推薦更穩）
1. 把這個 `tiktok-oauth-callback/` 資料夾推到一個新的 GitHub repo（公開 / 私人都行）
2. 進 Vercel → **Add New Project** → **Import Git Repository**
3. 選你剛建的 repo → **Import**
4. Framework Preset 選 **Other** → **Deploy**
5. 等 30 秒部署完成

### Step 3: 拿到正式 URL
部署成功後 Vercel 會給你一個 URL，例如：
```
https://jushou-tiktok-oauth.vercel.app
```

你的兩個 callback endpoint 就是：
```
Advertiser Redirect URL:
https://jushou-tiktok-oauth.vercel.app/api/advertiser-callback

TikTok Account Holder Redirect URL:
https://jushou-tiktok-oauth.vercel.app/api/account-callback
```

### Step 4: 填回 TikTok App 申請表
把上面兩個 URL **分別** 填進 TikTok 申請表對應的欄位：
- `Advertiser Redirect URL` → 第一條
- `TikTok account holder Redirect URL` → 第二條

## 測試 URL 是否可用
部署完成後，**直接用瀏覽器打開** 兩個 URL，應該各看到一個漂亮的「找不到授權碼」錯誤頁。看到代表 endpoint 在工作。

## 後續維護
- 改檔案後 push 到 GitHub → Vercel 自動重新部署
- 想換成公司網域（例如 `oauth.公司網域.com`）→ Vercel 設定 → Domains → 加 custom domain

## 檔案結構
```
tiktok-oauth-callback/
├── api/
│   ├── advertiser-callback.js   # 廣告主授權 callback
│   └── account-callback.js      # TikTok 帳號擁有者授權 callback
├── index.html                   # 首頁（讓 TikTok 審核員看到正式服務）
├── package.json
├── vercel.json
└── README.md
```
