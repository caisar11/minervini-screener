import numpy as np
import pandas as pd
from scipy.signal import find_peaks

def analyze_vcp_pattern(df: pd.DataFrame) -> dict:
    """
    df: 최소 60영업일 이상 일봉 데이터 ('Close', 'High', 'Low', 'Volume' 포함)
    마크 미너비니의 VCP(변동성 축소 패턴)과 거래량 건조(Volume Dry-up)를 분석합니다.
    """
    if len(df) < 60:
        return {"is_vcp": False, "stage": "데이터 부족", "reason": "최소 60일 이상 필요"}
    
    # 50일 이동평균 거래량
    df['Vol_SMA50'] = df['Volume'].rolling(50).mean()
    
    # 최근 60영업일 (약 3개월 베이스 형성 구간)
    recent_df = df.tail(60).copy()
    highs = recent_df['High'].values
    lows = recent_df['Low'].values
    
    # 스윙 고점/저점 탐색
    peaks, _ = find_peaks(highs, distance=5, prominence=highs.mean() * 0.02)
    troughs, _ = find_peaks(-lows, distance=5, prominence=highs.mean() * 0.02)
    
    # 수축(Contraction) 파동 계산
    contractions = []
    min_len = min(len(peaks), len(troughs))
    for i in range(min_len):
        peak_val = highs[peaks[i]]
        trough_val = lows[troughs[i]]
        if peak_val > 0:
            depth_pct = ((peak_val - trough_val) / peak_val) * 100
            contractions.append(depth_pct)
            
    # 변동성 축소 여부 (최근 파동이 직전 파동보다 작아지는지)
    is_contracting = False
    if len(contractions) >= 2:
        if contractions[-1] < contractions[-2]:
            is_contracting = True
    elif len(contractions) == 1:
        # 단일 파동일 경우 최근 10일 변동폭이 8% 미만이면 수축으로 인정
        recent_10d_range = ((recent_df['High'].tail(10).max() - recent_df['Low'].tail(10).min()) / recent_df['High'].tail(10).max()) * 100
        if recent_10d_range < 8.0:
            is_contracting = True
            
    # 거래량 건조 (Volume Dry-up): 최근 3일 평균 거래량이 50일 이평 대비 85% 이하
    recent_vol_avg = recent_df['Volume'].tail(3).mean()
    vol_sma = recent_df['Vol_SMA50'].iloc[-1] if not pd.isna(recent_df['Vol_SMA50'].iloc[-1]) else recent_vol_avg
    is_vol_dryup = recent_vol_avg < (vol_sma * 0.85) if vol_sma > 0 else False
    
    # 가격 계산
    current_price = float(recent_df['Close'].iloc[-1])
    pivot_price = float(recent_df['High'].tail(15).max())  # 최근 15영업일 고점 돌파선
    recent_low = float(recent_df['Low'].tail(10).min())    # 최근 지지 저점
    
    # 미너비니 기본 손절 규칙: 최근 저점 또는 최대 -7%
    stop_loss = max(recent_low, current_price * 0.93)
    risk_pct = round(((current_price - stop_loss) / current_price) * 100, 2)
    if risk_pct <= 0:
        risk_pct = 5.0
        stop_loss = current_price * 0.95
        
    # 손익비 1:2 및 1:3 목표가
    target_2r = round(current_price * (1 + (risk_pct * 2 / 100)), 0)
    target_3r = round(current_price * (1 + (risk_pct * 3 / 100)), 0)
    
    # T단계 표시 (1T, 2T, 3T, 4T)
    t_count = len(contractions) if len(contractions) > 0 else 1
    stage_str = f"{t_count}T 수축 완료 (돌파 임박)" if is_contracting else f"{t_count}T 수축 진행중"
    
    return {
        "is_vcp": is_contracting and is_vol_dryup,
        "is_contracting": is_contracting,
        "is_vol_dryup": is_vol_dryup,
        "stage": stage_str,
        "contractions": [round(c, 1) for c in contractions[-4:]] if contractions else [round(((recent_df['High'].max() - recent_df['Low'].min()) / recent_df['High'].max()) * 100, 1)],
        "current_price": int(current_price),
        "pivot_price": int(pivot_price),
        "stop_loss": int(stop_loss),
        "risk_pct": risk_pct,
        "target_2r": int(target_2r),
        "target_3r": int(target_3r),
        "vol_ratio": round((recent_vol_avg / vol_sma) * 100, 1) if vol_sma > 0 else 100.0
    }