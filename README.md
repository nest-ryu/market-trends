# 📊 Market Trends — Streamlit Cloud (v2)

실시간 미국·한국 주식시장 대시보드입니다. (Streamlit Community Cloud 배포용)
- 상승/하락 색상 표시
- 섹션별 자동 동향 요약
- 세부 추세 그래프 (Plotly)
- **HTML/PDF 리포트 다운로드 버튼** 포함

## 🚀 배포
1. GitHub에 새 저장소 생성: `market-trends`
2. 아래 파일 업로드
   - `market_trends_streamlit_v2.py`
   - `requirements.txt`
   - `README.md`
3. https://share.streamlit.io → New app
   - Repository: `nest-ryu/market-trends`
   - Main file path: `market_trends_streamlit_v2.py`
4. Deploy 클릭

## 🧩 로컬 실행
```bash
pip install -r requirements.txt
streamlit run market_trends_streamlit_v2.py
```

## 📥 리포트 다운로드
- HTML: 대시보드 표를 스타일링하여 단일 HTML 파일로 생성
- PDF: reportlab + kaleido로 표와 상위 차트 이미지를 포함한 PDF 생성
  - Cloud에서 kaleido가 동작하지 않는 경우, PDF는 텍스트 기반으로 대체될 수 있습니다.
