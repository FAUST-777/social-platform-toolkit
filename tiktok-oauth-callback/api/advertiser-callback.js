// Vercel Serverless Function
// 處理 TikTok Marketing API（廣告主授權）的 OAuth callback
// 對應 TikTok App 設定的 "Advertiser Redirect URL"

export default function handler(req, res) {
  const { auth_code, code, state, error, error_description } = req.query;

  // TikTok Marketing API 通常用 auth_code，部分流程用 code
  const finalCode = auth_code || code;

  res.setHeader("Content-Type", "text/html; charset=utf-8");

  if (error) {
    return res.status(400).send(renderHTML({
      status: "error",
      title: "授權失敗",
      message: `Error: ${error}`,
      detail: error_description || "請聯絡管理員",
    }));
  }

  if (!finalCode) {
    return res.status(400).send(renderHTML({
      status: "error",
      title: "找不到授權碼",
      message: "URL 上沒有 auth_code 或 code 參數",
      detail: "請從 TikTok 授權頁面正常跳轉過來",
    }));
  }

  return res.status(200).send(renderHTML({
    status: "success",
    title: "廣告主授權成功",
    message: "請複製下方的授權碼，貼到你的程式中換取 access_token",
    code: finalCode,
    state: state || "(none)",
    type: "Advertiser (Marketing API)",
  }));
}

function renderHTML({ status, title, message, detail, code, state, type }) {
  const statusColor = status === "success" ? "#10b981" : "#ef4444";
  const statusIcon = status === "success" ? "✓" : "✗";

  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title} | Jushou TikTok OAuth</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: #fff;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .card {
      background: rgba(255, 255, 255, 0.05);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 16px;
      padding: 40px;
      max-width: 600px;
      width: 100%;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: ${statusColor};
      color: #fff;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 20px;
    }
    h1 { font-size: 28px; margin-bottom: 12px; }
    .message { color: #cbd5e1; margin-bottom: 24px; line-height: 1.6; }
    .field { margin-bottom: 20px; }
    .label {
      display: block;
      font-size: 12px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }
    .value {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 14px 16px;
      border-radius: 8px;
      font-family: "SF Mono", Consolas, monospace;
      font-size: 14px;
      word-break: break-all;
      position: relative;
    }
    .copy-btn {
      background: #3b82f6;
      color: #fff;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      margin-top: 8px;
      transition: background 0.2s;
    }
    .copy-btn:hover { background: #2563eb; }
    .copy-btn.copied { background: #10b981; }
    .footer {
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      font-size: 12px;
      color: #64748b;
    }
    .warn {
      background: rgba(245, 158, 11, 0.1);
      border-left: 3px solid #f59e0b;
      padding: 12px 16px;
      border-radius: 4px;
      font-size: 13px;
      color: #fbbf24;
      margin-top: 16px;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">${statusIcon} ${status === "success" ? "Success" : "Error"}</div>
    <h1>${title}</h1>
    <p class="message">${message}</p>

    ${code ? `
      <div class="field">
        <span class="label">Authorization Code</span>
        <div class="value" id="authCode">${code}</div>
        <button class="copy-btn" onclick="copyCode()">複製授權碼</button>
      </div>

      <div class="field">
        <span class="label">Type</span>
        <div class="value">${type || ""}</div>
      </div>

      <div class="field">
        <span class="label">State</span>
        <div class="value">${state || "(none)"}</div>
      </div>

      <div class="warn">
        ⚠️ 此授權碼只能使用 <strong>1 次</strong>，且有效期約 <strong>10 分鐘</strong>。請盡快用它向 TikTok 換取 access_token。
      </div>
    ` : `
      <div class="field">
        <span class="label">Detail</span>
        <div class="value">${detail || ""}</div>
      </div>
    `}

    <div class="footer">
      Jushou E-commerce · TikTok OAuth Callback · Powered by Vercel
    </div>
  </div>

  <script>
    function copyCode() {
      const code = document.getElementById('authCode').innerText;
      navigator.clipboard.writeText(code).then(() => {
        const btn = document.querySelector('.copy-btn');
        btn.classList.add('copied');
        btn.innerText = '已複製 ✓';
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerText = '複製授權碼';
        }, 2000);
      });
    }
  </script>
</body>
</html>`;
}
