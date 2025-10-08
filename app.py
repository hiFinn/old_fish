# app.py
import random
import requests
import pandas as pd
import ccxt
import streamlit as st
import plotly.graph_objects as go
from typing import List, Tuple, Dict

# === 基本設定 ===
st.set_page_config(page_title="USDT-M 5m 隨機K線（可直接在圖上畫）", layout="wide")
TIMEFRAME = "5m"
TZ = "Asia/Taipei"

# -----------------------------------------------------------
# 連線：先嘗試 Binance Futures；失敗則自動 fallback 到 Binance Spot
# -----------------------------------------------------------
@st.cache_resource
def get_binance_client():
    """
    先嘗試連 Binance Futures；若被封鎖（或其他原因）則自動改用現貨 Spot。
    回傳 (exchange_instance, mode)；mode 會是 'futures' 或 'spot'
    """
    try:
        ex = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
        ex.load_markets()
        return ex, "futures"
    except Exception:
        # Futures 失敗就退回現貨
        ex = ccxt.binance({
            "enableRateLimit": True,
        })
        ex.load_markets()
        return ex, "spot"

@st.cache_data(ttl=3600)
def get_top10_non_stable_bases() -> List[str]:
    stable_symbols = {
        "USDT","USDC","BUSD","TUSD","DAI","FDUSD","PYUSD",
        "USDD","GUSD","PAX","EURS","LUSD","USDP","FRAX"
    }
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = dict(vs_currency="usd", order="market_cap_desc",
                  per_page=60, page=1, sparkline=False)
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        top = []
        for coin in data:
            sym = str(coin.get("symbol","")).upper()
            if sym in stable_symbols:
                continue
            if sym not in top:
                top.append(sym)
            if len(top) >= 10:
                break
        if top:
            return top[:10]
    except Exception:
        pass
    return ["BTC","ETH","BNB","SOL","XRP","TON","DOGE","ADA","TRX","AVAX"]

@st.cache_data(ttl=1800)
def build_symbol_choices() -> Tuple[List[str], Dict[str, str], str]:
    ex, mode = get_binance_client()
    markets = list(ex.markets.values())

    if mode == "futures":
        # USDT 線性永續
        usdt_markets = [
            m for m in markets
            if m.get("contract") and m.get("linear")
            and (m.get("swap") or m.get("type") == "swap")
            and m.get("quote") == "USDT" and m.get("symbol")
            and (m.get("active", True) is True)
        ]
    else:
        # Spot fallback：抓可交易的 USDT 現貨
        usdt_markets = [
            m for m in markets
            if m.get("spot") and m.get("quote") == "USDT"
            and m.get("symbol") and (m.get("active", True) is True)
        ]

    display_to_ccxt: Dict[str, str] = {}
    for m in usdt_markets:
        base = m.get("base","").upper()
        display = f"{base}/USDT"
        full = m["symbol"]
        display_to_ccxt[display] = full

    bases = get_top10_non_stable_bases()
    ordered_display: List[str] = []
    for base in bases:
        disp = f"{base}/USDT"
        if disp in display_to_ccxt:
            ordered_display.append(disp)

    for must in ["BTC/USDT","ETH/USDT"]:
        if must in display_to_ccxt and must not in ordered_display:
            ordered_display.insert(0, must)

    seen = set()
    ordered_unique: List[str] = []
    for d in ordered_display:
        if d not in seen:
            ordered_unique.append(d)
            seen.add(d)

    if len(ordered_unique) < 4:
        for d in display_to_ccxt.keys():
            if d not in seen:
                ordered_unique.append(d)
                seen.add(d)
            if len(ordered_unique) >= 12:
                break
    return ordered_unique, display_to_ccxt, mode

def fetch_random_segment(symbol_for_api: str, seg_len: int, timeframe: str = TIMEFRAME,
                         tz: str = TZ, window_days: int = 365, max_retries: int = 5) -> pd.DataFrame:
    ex, _ = get_binance_client()
    bar_ms = ex.parse_timeframe(timeframe) * 1000
    now_ms = ex.milliseconds()
    max_end = now_ms - bar_ms
    window_ms = window_days * 24 * 60 * 60 * 1000
    min_end = max(0, max_end - window_ms)

    for _ in range(max_retries):
        end_ms = random.randint(min_end, max_end)
        since_ms = end_ms - (seg_len - 1) * bar_ms
        try:
            ohlcv = ex.fetch_ohlcv(symbol_for_api, timeframe=timeframe, since=since_ms, limit=seg_len)
        except Exception:
            ohlcv = []
        if ohlcv and len(ohlcv) >= seg_len:
            df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(tz)
            return df.iloc[:seg_len].copy()

    st.error("取得隨機 K 線段落時發生問題，請再試一次。")
    return pd.DataFrame(columns=["ts","open","high","low","close","volume"])

# === 側邊欄 ===
st.sidebar.header("設定")
choices, display_to_ccxt, data_mode = build_symbol_choices()
default_index = choices.index("BTC/USDT") if "BTC/USDT" in choices else 0
display_symbol = st.sidebar.selectbox("合約標的", options=choices, index=default_index)
ccxt_symbol = display_to_ccxt[display_symbol]
window_days = st.sidebar.slider("隨機範圍（天）", 7, 2000, 750, 1)
seg_len     = st.sidebar.slider("K棒數量（根）", 20, 300, 120, 1)

source_label = "Binance Futures" if data_mode == "futures" else "Binance Spot（fallback）"
st.sidebar.write(f"來源：{source_label} / {display_symbol} / {TIMEFRAME}")
st.sidebar.caption("會從『過去所選天數』內，隨機抓取一段連續的 K 棒。")
if data_mode == "spot":
    st.sidebar.info("目前部署環境無法連線到 Binance Futures，已自動改用現貨資料（K 線與永續可能略有差異）。")

# === 狀態 ===
def need_refresh() -> bool:
    if "seg" not in st.session_state: return True
    if st.session_state.get("last_symbol_display") != display_symbol: return True
    if st.session_state.get("last_window_days") != window_days: return True
    if st.session_state.get("last_seg_len") != seg_len: return True
    if st.session_state.get("last_data_mode") != data_mode: return True
    return False

if need_refresh():
    st.session_state.seg = fetch_random_segment(ccxt_symbol, seg_len=seg_len, window_days=window_days)
    st.session_state.last_symbol_display = display_symbol
    st.session_state.last_window_days = window_days
    st.session_state.last_seg_len = seg_len
    st.session_state.last_data_mode = data_mode

col1, col2 = st.columns([1, 1])
with col1:
    if st.button(f"下一段 {seg_len} 根", use_container_width=True):
        st.session_state.seg = fetch_random_segment(ccxt_symbol, seg_len=seg_len, window_days=window_days)
# 一鍵清空前端標記：改變 key 重新掛載圖表
if "plot_key" not in st.session_state:
    st.session_state.plot_key = 0
with col2:
    if st.button("清除圖上標記", use_container_width=True):
        st.session_state.plot_key += 1

seg = st.session_state.seg
if seg.empty: st.stop()

start, end = seg["ts"].iloc[0], seg["ts"].iloc[-1]

# === 下載檔名：標的 + 起訖時間 ===
def make_download_filename(symbol_display: str) -> str:
    safe_symbol = symbol_display.replace("/", "-").replace(":", "-")
    return f"{safe_symbol}_{start.strftime('%Y%m%d-%H%M')}_{end.strftime('%Y%m%d-%H%M')}"

filename = make_download_filename(display_symbol)

title = f"{display_symbol}（{source_label}）— 5分K（{seg_len} 根）"
fig = go.Figure(data=[go.Candlestick(
    x=seg["ts"], open=seg["open"], high=seg["high"], low=seg["low"], close=seg["close"],
    increasing_line_color="#ef5350", decreasing_line_color="#26a69a", line_width=1
)])

# 🔴 重點：預設進入「畫矩形」模式（而非 Zoom），並保留可正常使用橡皮擦
fig.update_layout(
    title=title,
    xaxis_title=f"{start.strftime('%Y-%m-%d %H:%M')}  →  {end.strftime('%Y-%m-%d %H:%M')} ({TZ})",
    yaxis_title="Price (USDT)",
    xaxis_rangeslider_visible=False,
    margin=dict(l=40, r=20, t=60, b=40),
    hovermode="closest",          # 讓橡皮擦正常
    dragmode="drawrect",          # 預設工具 = 畫矩形
    newshape=dict(                # 新繪圖的預設樣式（可依喜好調整或刪除）
        line_color="#ef5350",
        fillcolor="rgba(239,83,80,0.15)",
        opacity=1.0,
        line_width=2,
    ),
)

# 高度放大 1.5 倍
current_height = fig.layout.height or 450
fig.update_layout(height=int(current_height * 1.5))

# x 軸只顯示起訖時間
fig.update_xaxes(
    tickmode="array",
    tickvals=[start, end],
    ticktext=[start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")]
)

plotly_config = dict(
    modeBarButtonsToAdd=["drawline", "drawopenpath", "drawrect", "drawcircle", "eraseshape"],
    displaylogo=False,
    editable=True,
    edits={"shapePosition": True},
    toImageButtonOptions={"format": "png", "filename": filename, "scale": 2},
)

st.plotly_chart(
    fig, use_container_width=True, config=plotly_config, key=f"plot-{st.session_state.plot_key}"
)
