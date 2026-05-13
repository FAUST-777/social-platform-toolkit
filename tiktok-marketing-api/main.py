"""
TikTok 數據管線 — 主程式

一次執行廣告報表 + 影片數據，全部寫進 Google Sheet。

執行：
  python main.py              # 昨天廣告 + 最新 20 支影片
  python main.py --ad-days 7  # 最近 7 天廣告
  python main.py --video-count 50
  python main.py --dry-run
  python main.py --skip-ads   # 只跑影片數據
  python main.py --skip-videos # 只跑廣告數據
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def run(script: str, extra_args: list[str]) -> bool:
    cmd = [sys.executable, script] + extra_args
    print(f"\n{'='*50}")
    print(f"執行 {script}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, cwd=str(__import__("pathlib").Path(__file__).parent))
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok 數據管線")
    parser.add_argument("--ad-days", type=int, default=1)
    parser.add_argument("--video-count", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-ads", action="store_true")
    parser.add_argument("--skip-videos", action="store_true")
    args = parser.parse_args()

    dry_flag = ["--dry-run"] if args.dry_run else []
    success = True

    if not args.skip_ads:
        ok = run("ad_reports.py", [f"--days={args.ad_days}"] + dry_flag)
        if not ok:
            print("廣告報表失敗（繼續執行影片數據）")
            success = False

    if not args.skip_videos:
        ok = run("account_videos.py", [f"--count={args.video_count}"] + dry_flag)
        if not ok:
            print("影片數據失敗")
            success = False

    print(f"\n{'='*50}")
    print("全部完成" if success else "有部分失敗，請檢查上方錯誤訊息")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
