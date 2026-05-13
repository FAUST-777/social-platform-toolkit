# 開發歷程：social-platform-toolkit

> 從 TikTok 廣告帳戶設定 → API 申請 → 數據抓取的完整旅程記錄

---

## 📌 一句話總結
從「**幫公司加入廣告帳戶**」開始，一路解決 Business Center 邀請卡住、Email 網域不一致、權限分層、App 申請被拒、OAuth callback URL 部署等問題，準備建立 TikTok 廣告 + 直播數據的雙路徑 Pipeline。

---

## 🎯 整體需求

來自 [TikTok BC 與 App 申請](e0734753-86d3-487e-90c3-dccbad8beb1c)（590 個 TikTok 關鍵字命中）

**業務情境**：
- 公司有 **1 個 TikTok 頻道**（@舉手電商 或類似）
- 找 **多位 KOL 進來在公司頻道開直播**（KOL 不用個人帳號）
- 商品買賣導到**其他電商平台**（非 TikTok Shop）
- 要追蹤：觀看人數、停留時間、留言、分享、轉換等

**技術需求**：
1. 拉廣告投放成效（Marketing API）
2. 拉直播觀眾數據（TikTok Accounts API）
3. 寫進 Google Sheet 報表
4. 後續做 Looker Studio 視覺化

---

## 🛤️ 開發階段

### 階段 1：加入公司廣告帳戶（2026-05-05 起）

**問題**：同事用 Admin 權限邀請，按 mail 確認後**沒有進到 Business Center**，重發三次都卡 Pending。

**原因**：**Email 不一致** — 同事邀請的 email 跟使用者登入 TikTok Business Center 的 email 不一樣。

**踩坑歷程**：
1. 同事重發 3 次邀請 → 仍然 Pending
2. 嘗試各種「接受邀請」流程
3. 最後發現：**TikTok 邀請會用收件 email 註冊新 BC**，如果跟現有 email 不符就會永遠 Pending
4. 解法：確認 email 一致後，按一次就進去了

**踩坑 1（解 Email 後）**：進去 BC 但**廣告帳戶看不到**
- 原因：BC Admin ≠ 自動有 Ad Account 權限（兩層獨立）
- 解法：請同事在 BC → Accounts → 選 Ad Account → Users → Add User，把使用者單獨指派為 Admin

**踩坑 2**：使用者帳號操作畫面看不到「Add User」按鈕
- 原因：同事不是「該廣告帳戶」的 Admin，只是 BC Admin
- 解法：用替代路徑 Users → 點使用者名 → Assets → Assign assets

---

### 階段 2：TikTok For Developers App 申請（一次被拒）

**目標**：申請 Marketing API + Business API access

**第一次被拒**：

```
Rejected fields: Account type, Company Name, Company Website, ...
Rejection Reason:
  "we require developers to use a verified company email address 
   as a communication email, and the email domain should match 
   the company website domain in profile."
```

**根因**：**1 個問題**被標到所有欄位 → email 網域必須等於 Company Website 網域。

例如：
- ❌ `william@gmail.com` + `https://abc.com.tw`
- ✅ `william@abc.com.tw` + `https://abc.com.tw`

**解法**：
1. 確認公司網域 email
2. 在 TikTok Developer Profile 設 communication email = 公司 email
3. Company Website = 同網域
4. 通過驗證後 resubmit

---

### 階段 3：選擇正確的 API（從錯誤申請學到）

對話中曾混淆兩個 API：

| API | 用途 | 是否符合本專案需求 |
|---|---|---|
| **TikTok Business API** | 廣告投放 / Marketing | ✅ 是我們要的 |
| **TikTok Shop Partner API** | 電商商品資料 | ❌ 我們不用 TikTok Shop |

**最終確認需求**：要 **TikTok Marketing API**（廣告 / 直播成效）

---

### 階段 4：權限選擇（最小化原則）

從一長串權限選清單中，採取「**只勾 Read，盡量少**」策略：

**勾的（必要）**：
- ✅ `Ad Account Management → Read Ad Account Information`
- ✅ `Ads Management → 所有 Read` (campaign / adgroup / ad 結構)
- ✅ `Reporting → 所有 Read` (核心：成效報表)
- ✅ `TikTok Accounts → 所有 Read` (拿公司頻道直播數據 ← 重要)

**討論後不勾**：
- ❌ Lead Generation（電商不做名單廣告）
- ❌ DPA Catalog Management（不用 TikTok Shop 商品目錄）
- ❌ Pixel Management（Pixel 是裝 JS code 在外部網站，不用 API 管）
- ❌ TikTok Creator Marketplace（KOL 不用自己帳號）
- ❌ Audience / Creative Management
- ❌ 所有 `/bc/...` Business Center 內部管理 API

**權限分析的關鍵發現**：
> Pixel 帶來的轉換數據（購買、ROAS）**會自動出現在 Reporting API 的結果裡**，不用單獨勾 Pixel Management。

---

### 階段 5：Redirect URL 部署選擇

**TikTok App 表單要求**：
- **Advertiser Redirect URL** — 廣告主授權回呼
- **TikTok account holder Redirect URL** — TikTok 帳號擁有者授權回呼

**評估的方案**：

| 方案 | 評估結果 |
|---|---|
| localhost:8080 | ❌ TikTok 要求 HTTPS，localhost 不穩 |
| ngrok 免費版 | ❌ URL 每次變，TikTok 備案 URL 會失效 |
| Render / Railway 免費 | ❌ 閒置會休眠 |
| **Vercel 免費** | ✅ 永久 URL，5 分鐘部署 |
| Cloudflare Pages | ✅ 也可，但 Vercel 簡單 |
| 公司自有網域 + Vercel | ⭐ 最正規，未來再升級 |

**最後決定**：**Vercel**（個人帳號免費方案，純內部低流量工具）

對 Vercel Hobby Plan 商用條款的考量：
- 流量極低（一年幾十次 OAuth callback）
- 純內部工具、非對外營利
- 用個人帳號部署 → 等於「個人開發工具借給公司用」，實務上 Vercel 不會管

---

### 階段 6：OAuth 流程理解

中途使用者問：「callback URL 是用來接收 API 數據的嗎？」 — **澄清重要觀念**：

> ❌ **不是。callback URL 不接收 API 數據。**
>
> ✅ **它只是 OAuth 流程裡的「信箱」**，只在「授權當下」收到一次 code，之後拉資料是你的程式**主動**去 call API（用 token）。

OAuth 兩步驟設計的原因（安全考量）：
1. 第一步：給「**一次性、短效**」的 code（10 分鐘有效 + 用一次失效）
2. 第二步：用 code + client_secret（只有 server 知道）換 token
3. token 是 server-to-server 通訊換到的，不經過瀏覽器 → 安全

---

### 階段 7：實驗性方案 — Scrapling 爬蟲（已擱置）

使用者提出：「先用爬蟲方式實作」目標 URL = `https://ads.tiktok.com/i18n/dashboard/?aadvid=...`

**強烈勸退**：
1. 這個 URL **需要登入**，爬蟲拿不到資料
2. 違反 TikTok ToS → 公司帳號被封風險
3. 同樣資料用 Marketing API 合法拿
4. 這個 URL 後面的資料 = Marketing API 給的資料

**建議的爬蟲合理目標**（公開頁，不需登入）：
- 公司 TikTok profile (`tiktok.com/@jushou_official`)
- KOL profile (粉絲數、影片數)
- 公開影片頁（觀看、按讚、留言）
- Hashtag 頁面

**最後決定**：先擱置爬蟲方案，專注 Marketing API 正規路線。

---

## 🧮 關鍵業務理解

### 廣告 vs 自然數據的兩條 API

```
┌─────────────────────────────────────────────────────┐
│  公司 TikTok 頻道                                     │
│                                                      │
│  KOL 進來開直播                                       │
│       │                                              │
│       ├──→ 付費推廣這場直播                            │
│       │      └──→ Marketing API → 廣告成效            │
│       │           (花費, 廣告帶來的觀看, 點擊, 轉換)    │
│       │                                              │
│       └──→ 自然觸及 (粉絲基底進來)                      │
│             └──→ TikTok Accounts API → 直播 insights  │
│                  (總觀看, 平均停留, 留言, 分享, 禮物)    │
│                                                      │
│  兩個合在一起 = 完整直播效益                            │
└─────────────────────────────────────────────────────┘
```

### Pixel 的角色（外部電商網站）

公司用其他電商平台賣商品，所以：
- 在外部電商網站貼 TikTok Pixel JS
- Pixel 回傳「網站行為」給 TikTok（瀏覽、加購、購買）
- TikTok 演算法用這些資料優化廣告
- 報表裡才能看到 ROAS、Conversions

**沒 Pixel = 廣告閉眼睛投**

---

## 💡 關鍵決策回顧

| 時間 | 決策 | 為什麼 |
|---|---|---|
| 2026-05 | 加入公司 BC | 業務需要操作廣告 |
| 2026-05 | 申請 TikTok Marketing API App | 要拿廣告數據 |
| 2026-05 | 第一次被拒 | Email 網域問題 |
| 2026-05 | 改用 Vercel 部署 OAuth callback | 要 HTTPS + 永久 URL |
| 2026-05 | 加勾 TikTok Accounts 權限 | 要拿直播自然觸及數據 |
| 2026-05 | 不走爬蟲方案 | Marketing API 是正路 |

---

## 🧯 踩坑 Top 8（給未來的你避免重複）

1. **TikTok BC 邀請 email 不一致 → 永遠 Pending** — 接受邀請前確認登入的是同一個 email
2. **BC Admin ≠ Ad Account Admin** — 兩層權限獨立，要兩邊都設
3. **App 申請 email 網域必須等於 Company Website 網域** — 不然 100% 被拒
4. **TikTok Business API ≠ TikTok Shop Partner API** — 弄清楚才不會浪費時間
5. **Vercel Hobby plan 是非商用條款** — 低流量內部工具實務上沒事，但要知道
6. **TikTok 後台網頁直接爬會封號** — 用 Marketing API 才是正路
7. **OAuth callback URL 之後可改** — TikTok 後台允許修改，先填 placeholder 也行
8. **Pixel 安裝不需要 API 權限** — 只是貼 JS code 在網站，不需要勾 Pixel Management

---

## 📚 完整對話索引

- [TikTok BC 與 App 申請](e0734753-86d3-487e-90c3-dccbad8beb1c) — 主要對話（590 個 TikTok 關鍵字命中）

---

## 🚧 未完成 / 未來想做

- [ ] 重新提交 TikTok App 申請（修 email 問題）
- [ ] 部署 OAuth callback service 到 Vercel
- [ ] 寫 Python OAuth flow 拿 access_token
- [ ] 寫 Marketing API → Google Sheet 主程式
- [ ] 寫 TikTok Accounts API → Google Sheet 直播數據
- [ ] 設計「KOL 直播效益」儀表板
- [ ] Looker Studio 報表
- [ ] cron 排程
- [ ] Scrapling 公開頁實驗（補充自然觸及數據）
