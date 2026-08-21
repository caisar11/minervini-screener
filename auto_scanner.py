import os
import requests
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from vcp_detector import analyze_vcp_pattern

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[경고] 텔레그램 환경변수가 설정되지 않았습니다.")
        print(message)
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ 텔레그램 발송 성공")
        else:
            print(f"❌ 텔레그램 발송 실패: {res.text}")
    except Exception as e:
        print(f"❌ 텔레그램 통신 오류: {e}")

def run_scanner(scan_limit=150):
    today_str = datetime.today().strftime('%Y-%m-%d')
    print(f"[{today_str}] 마크 미너비니 일일 자동 스크리너 가동...")
    
    df_krx = fdr.StockListing('KRX')
    if 'Marcap' in df_krx.columns:
        df_krx = df_krx.sort_values(by='Marcap', ascending=False)
    target_stocks = df_krx.head(scan_limit)
    
    qualified = []
    
    for _, row in target_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        try:
            start_date = (datetime.today() - timedelta(days=420)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start=start_date)
            if len(df) < 200:
                continue
                
            df['SMA_50'] = df['Close'].rolling(50).mean()
            df['SMA_150'] = df['Close'].rolling(150).mean()
            df['SMA_200'] = df['Close'].rolling(200).mean()
            df['52w_high'] = df['Close'].rolling(250).max()
            df['52w_low'] = df['Close'].rolling(250).min()
            
            latest = df.iloc[-1]
            prev_1m = df.iloc[-22]
            
            c = latest['Close']
            s50, s150, s200 = latest['SMA_50'], latest['SMA_150'], latest['SMA_200']
            h52, l52 = latest['52w_high'], latest['52w_low']
            
            # 8대 트렌드 템플릿 검증
            cond_pass = (
                c > s150 and c > s200 and
                s150 > s200 and
                s200 > prev_1m['SMA_200'] and
                s50 > s150 and s50 > s200 and
                c > s50 and
                c >= (l52 * 1.30) and
                c >= (h52 * 0.75)
            )
            
            if cond_pass:
                vcp_data = analyze_vcp_pattern(df)
                qualified.append({
                    "name": name,
                    "code": code,
                    "price": int(c),
                    "dist_52h": round(((h52 - c) / h52) * 100, 1),
                    "reb_52l": round(((c - l52) / l52) * 100, 1),
                    "vcp": vcp_data
                })
        except Exception:
            continue
            
    if qualified:
        msg = f"🏆 <b>[{today_str}] 마크 미너비니 추세추종 종목 ({len(qualified)}건)</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        for item in qualified:
            v = item['vcp']
            vcp_badge = "✅VCP돌파임박" if v.get('is_vcp') else f"📊{v.get('stage', '수축중')}"
            vol_badge = "💧거래량감소" if v.get('is_vol_dryup') else "일반거래량"
            
            msg += (
                f"🔥 <b>{item['name']}</b> ({item['code']})\n"
                f"• 현재가: <b>{item['price']:,}원</b> (52주고점대비 -{item['dist_52h']}%)\n"
                f"• 패턴상태: {vcp_badge} | {vol_badge}\n"
                f"• 피벗돌파선: <b>{v.get('pivot_price', 0):,}원</b>\n"
                f"• 손절선: {v.get('stop_loss', 0):,}원 (-{v.get('risk_pct', 0)}%)\n"
                f"• 1:2 목표가: {v.get('target_2r', 0):,}원\n"
                f"────────────────────\n"
            )
    else:
        msg = f"ℹ️ [{today_str}] 오늘의 미너비니 조건 만족 종목이 없습니다."
        
    send_telegram(msg)

if __name__ == "__main__":
    run_scanner(scan_limit=150)