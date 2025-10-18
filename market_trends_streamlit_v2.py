import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import datetime as dt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="📊 Market Trends — US & KR", layout="wide")
st.title("📊 미국·한국 주식시장 동향 (실시간)")
st.caption("데이터 출처: Yahoo Finance (yfinance) · 대시보드 새로고침 시 최신 데이터 반영")

# ----- Settings -----
periods = st.multiselect(
    "기간 선택",
    ["1D", "1W", "1M", "3M", "6M", "YTD"],
    default=["1D", "1W", "1M", "YTD"]
)

INDEX_TICKERS = {"^GSPC":"S&P 500","^IXIC":"NASDAQ","^DJI":"Dow Jones","^KS11":"KOSPI","^KQ11":"KOSDAQ"}
SECTOR_US = {"XLB":"Materials","XLE":"Energy","XLF":"Financials","XLI":"Industrials","XLK":"Technology",
             "XLP":"Consumer Staples","XLRE":"Real Estate","XLU":"Utilities","XLV":"Health Care",
             "XLY":"Consumer Discretionary","XLC":"Communication Services"}
COMMODITIES_FX = {"GC=F":"Gold Futures","CL=F":"WTI Crude","BZ=F":"Brent Crude","DX-Y.NYB":"US Dollar Index","KRW=X":"USD/KRW"}
THEME_KR = {"KR_Shipbuilding":{"name":"KR Shipbuilding (조선)","tickers":["329180.KS","010140.KS","042660.KS","267250.KS"]},
            "KR_Semiconductors":{"name":"KR Semiconductors (반도체)","tickers":["005930.KS","000660.KS"]},
            "KR_SecondaryBatteries":{"name":"KR Secondary Batteries (2차전지)","tickers":["373220.KS","006400.KS","096770.KS"]},
            "KR_Internet":{"name":"KR Internet (인터넷)","tickers":["035420.KS","035720.KS"]},
            "KR_Biotech":{"name":"KR Biotech (바이오)","tickers":["068270.KS","207940.KS"]}}

# ----- Data -----
@st.cache_data(ttl=600)
def get_prices(tickers):
    end = dt.date.today()
    start = end - dt.timedelta(days=450)
    data = yf.download(tickers, start=start, end=end+dt.timedelta(days=1), auto_adjust=True, progress=False, group_by="ticker")
    if isinstance(data.columns, pd.MultiIndex):
        close = data.loc[:, (slice(None), "Close")]
        close.columns = [c[0] for c in close.columns]
        return close
    else:
        return data["Close"].to_frame()

def pct_change(df, days):
    if len(df) <= days: return pd.Series(np.nan, index=df.columns)
    return (df.iloc[-1] / df.iloc[-(days+1)] - 1.0) * 100

def returns_table(df, symbol_to_name):
    periods_map = {"1D":1,"1W":5,"1M":21,"3M":63,"6M":126}
    out = {}
    for p in periods:
        if p == "YTD":
            start_year = df[df.index.year==dt.date.today().year]
            if not start_year.empty:
                out[p] = (df.iloc[-1]/start_year.iloc[0]-1)*100
        else:
            out[p] = pct_change(df, periods_map[p])
    result = pd.DataFrame(out).round(2)
    # keep order same as dict
    result = result.reindex(symbol_to_name.keys())
    result.index = [symbol_to_name[k] for k in result.index]
    return result

def style_table(df):
    styled = df.style.format("{:+.2f}%") \
        .map(lambda v: 'color:red;' if v>0 else ('color:deepskyblue;' if v<0 else 'color:gray;'))
    return styled

def trend_summary(df, title):
    if "1D" not in df.columns or df["1D"].dropna().empty:
        return ""
    top = df["1D"].idxmax(); bot = df["1D"].idxmin()
    return f"💬 {title}: **{top}**({df.loc[top,'1D']:+.2f}%) 강세 · **{bot}**({df.loc[bot,'1D']:+.2f}%) 약세"

all_tickers = list(INDEX_TICKERS.keys())+list(SECTOR_US.keys())+list(COMMODITIES_FX.keys())
for t in THEME_KR.values(): all_tickers += t["tickers"]
prices = get_prices(all_tickers)

# ----- Sections (tables + charts) -----
def section(title, mapping):
    st.subheader(title)
    table = returns_table(prices[mapping.keys()], mapping)
    st.dataframe(style_table(table), use_container_width=True)
    st.caption(trend_summary(table, title))
    cols = st.columns(2)
    for i,(label,sym) in enumerate(zip(table.index, mapping.keys())):
        s = prices[sym].dropna().tail(60)
        if s.empty: continue
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode='lines', name=label))
        fig.update_layout(title=label, height=220, margin=dict(l=10,r=10,t=30,b=10))
        cols[i%2].plotly_chart(fig, use_container_width=True)
    return table

table_indices = section("주요 지수 (US/KR)", INDEX_TICKERS)
table_sectors = section("미국 섹터 (SPDR)", SECTOR_US)
table_cmdfx = section("원자재/환율", COMMODITIES_FX)

# KR Themes (equal-weight series)
st.subheader("한국 테마 (동일가중 바스켓)")
theme_series = {}
for meta in THEME_KR.values():
    sub = prices[meta["tickers"]].dropna(how="all")
    if sub.empty: continue
    theme_series[meta["name"]] = sub.mean(axis=1)
theme_table = pd.DataFrame(
    {k: {
        p: ((v.iloc[-1]/v.iloc[-(d+1)]-1)*100 if len(v)>d else np.nan) if p!="YTD"
           else ( (v.iloc[-1]/v[v.index.year==dt.date.today().year].iloc[0]-1)*100 if not v[v.index.year==dt.date.today().year].empty else np.nan)
        for p,d in {"1D":1,"1W":5,"1M":21,"3M":63,"6M":126,"YTD":None}.items() if p in periods
      } for k,v in theme_series.items()
    }
).T.round(2)
if not theme_table.empty:
    st.dataframe(style_table(theme_table), use_container_width=True)
    if "1D" in theme_table.columns and not theme_table["1D"].dropna().empty:
        st.caption(trend_summary(theme_table, "한국 테마"))
    cols = st.columns(2)
    for i,(name,series) in enumerate(theme_series.items()):
        s = series.dropna().tail(60)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode='lines', name=name))
        fig.update_layout(title=name, height=220, margin=dict(l=10,r=10,t=30,b=10))
        cols[i%2].plotly_chart(fig, use_container_width=True)

# ----- Report Export (HTML/PDF) -----
st.markdown("---")
st.subheader("📥 리포트 다운로드")

def build_html_report():
    def df_to_html(df, title):
        styled = style_table(df).set_table_attributes('class="tbl"')
        try:
            tbl_html = styled.to_html()
        except Exception:
            tbl_html = df.to_html(classes="tbl", border=0)
        return f'<div class="card"><h2>{title}</h2>{tbl_html}</div>'
    css = """
    <style>
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;background:#0f172a;color:#e5e7eb;margin:0;padding:24px}
    .card{background:#111827;border-radius:14px;padding:16px;margin-bottom:16px}
    .tbl{width:100%;border-collapse:collapse;font-size:14px}
    .tbl th,.tbl td{padding:8px 10px;border-bottom:1px solid #222;text-align:right}
    .tbl th{text-align:right;color:#cbd5e1;font-weight:600}
    </style>
    """
    parts = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>Market Trends Report</title>", css, "</head><body>",
             f"<h1>📊 미국·한국 주식시장 동향 리포트</h1><p>업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"]
    parts.append(df_to_html(table_indices, "주요 지수 (US/KR)"))
    parts.append(df_to_html(table_sectors, "미국 섹터 (SPDR)"))
    parts.append(df_to_html(table_cmdfx, "원자재/환율"))
    if not theme_table.empty:
        parts.append(df_to_html(theme_table, "한국 테마 (동일가중 바스켓)"))
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")

def build_pdf_report():
    # Build small summary PDF with tables and top charts (export Plotly as images via kaleido)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    title = Paragraph("📊 미국·한국 주식시장 동향 리포트", styles['Title'])
    timestamp = Paragraph(f"업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
    flow = [title, Spacer(1,10), timestamp, Spacer(1,16)]

    def table_flow(df, caption):
        if df is None or df.empty: return []
        data = [ [""]+list(df.columns) ]
        for idx,row in df.iterrows():
            data.append([str(idx)] + [f"{v:+.2f}%" if pd.notna(v) else "-" for v in row.values])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR',(0,0),(-1,0), colors.whitesmoke),
            ('ALIGN',(1,1),(-1,-1),'RIGHT'),
            ('ALIGN',(0,0),(0,-1),'LEFT'),
            ('BACKGROUND',(0,1),(-1,-1), colors.HexColor('#111827')),
            ('GRID',(0,0),(-1,-1), 0.25, colors.HexColor('#374151')),
            ('TEXTCOLOR',(0,1),(-1,-1), colors.whitesmoke),
            ('FONT',(0,0),(-1,-1),'Helvetica')
        ]))
        return [Paragraph(f"<b>{caption}</b>", styles['Heading3']), Spacer(1,6), t, Spacer(1,12)]

    flow += table_flow(table_indices, "주요 지수 (US/KR)")
    flow += table_flow(table_sectors, "미국 섹터 (SPDR)")
    flow += table_flow(table_cmdfx, "원자재/환율")
    if not theme_table.empty:
        flow += table_flow(theme_table, "한국 테마 (동일가중 바스켓)")

    # Add a few top charts (top 4 by 1D across sectors to keep PDF size reasonable)
    try:
        import plotly.io as pio
        # collect candidate series
        charts = []
        for mapping, caption in [(INDEX_TICKERS,"지수"), (SECTOR_US,"섹터"), (COMMODITIES_FX,"원자재/환율")]:
            df = returns_table(prices[mapping.keys()], mapping)
            if "1D" in df.columns:
                top_names = df["1D"].dropna().sort_values(ascending=False).head(4).index.tolist()
                for name in top_names:
                    sym = [k for k,v in mapping.items() if v==name][0]
                    s = prices[sym].dropna().tail(120)
                    fig = go.Figure(); fig.add_trace(go.Scatter(x=s.index, y=s.values, mode='lines', name=name))
                    fig.update_layout(title=f"{caption} · {name}", height=300, width=500, margin=dict(l=10,r=10,t=40,b=10))
                    png = pio.to_image(fig, format='png', scale=2)  # needs kaleido
                    charts.append( (name, png) )
        for name, png_bytes in charts:
            flow.append(Spacer(1,12))
            flow.append(Paragraph(name, styles['Heading4']))
            img = ImageReader(BytesIO(png_bytes))
            flow.append(Spacer(1,6))
            # Add image with max width
            flow.append(Table([[img]], colWidths=[500]))
    except Exception as e:
        flow.append(Paragraph("차트 이미지를 생성하지 못했습니다 (kaleido 미설치 또는 제한).", styles['Italic']))

    doc.build(flow)
    pdf_bytes = buf.getvalue(); buf.close()
    return pdf_bytes

col_a, col_b = st.columns(2)
with col_a:
    html_bytes = build_html_report()
    st.download_button("📥 리포트 다운로드 (HTML)", data=html_bytes, file_name="market_trends_report.html", mime="text/html")
with col_b:
    pdf_bytes = build_pdf_report()
    st.download_button("📥 리포트 다운로드 (PDF)", data=pdf_bytes, file_name="market_trends_report.pdf", mime="application/pdf")
