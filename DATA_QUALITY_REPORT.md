# stock DB 데이터 품질 보고서

생성일: 2026-09-24

## 테이블별 요약
### market
- 행 수: 12,011,860
- 기간: 1995-05-02 ~ 2026-09-23
- distinct 날짜: 7912
- 중복 그룹: 0
- NULL 수: {'Date': 0, 'Code': 0, 'Close': 0}
### kospi
- 행 수: 8,006
- 기간: 1995-01-03 ~ 2026-09-23
- distinct 날짜: 8006
- 중복 그룹: 0
- NULL 수: {'Date': 0, 'Close': 0}
### kosdaq
- 행 수: 7,561
- 기간: 1996-07-01 ~ 2026-09-23
- distinct 날짜: 7561
- 중복 그룹: 0
- NULL 수: {'Date': 0, 'Close': 0}
### kpi200
- 행 수: 4,704
- 기간: 2006-01-03 ~ 2026-09-23
- distinct 날짜: 4704
- 중복 그룹: 0
- NULL 수: {'Date': 0, 'kpi200': 0}
### moneytrend
- 행 수: 6,005
- 기간: 2002-05-03 ~ 2026-09-21
- distinct 날짜: 6005
- 중복 그룹: 0
- NULL 수: {'Date': 0, '고객예탁금': 0, '신용잔고': 0}
### investortrend
- 행 수: 5,171
- 기간: 2005-01-03 ~ 2026-09-23
- distinct 날짜: 5171
- 중복 그룹: 0
- NULL 수: {'Date': 0}
### programtrend
- 행 수: 4,426
- 기간: 2005-01-03 ~ 2022-12-15
- distinct 날짜: 4426
- 중복 그룹: 0
- NULL 수: {}
### future
- 행 수: 1,603
- 기간: 2020-03-13 ~ 2026-09-23
- distinct 날짜: 1603
- 중복 그룹: 0
- NULL 수: {'Date': 0, 'Future': 0}
### limitup_futures_index_daily
- 행 수: 2,768
- 기간: 2015-06-15 ~ 2026-09-23
- distinct 날짜: 2768
- 중복 그룹: 0
- NULL 수: {'trade_date': 0, 'close_price': 0}
### limitup_futures_investor_daily
- 행 수: 1,579
- 기간: 2020-04-17 ~ 2026-09-23
- distinct 날짜: 1579
- 중복 그룹: 0
- NULL 수: {'trade_date': 0, 'personal_net_flow': 0}
### limitup_derivative_daily
- 행 수: 24,800
- 기간: 2026-09-23 ~ 2026-09-23
- distinct 날짜: 1
- 중복 그룹: 0
- NULL 수: {'trade_date': 0, 'open_interest': 1577}
### limitup_krx_daily_features
- 행 수: 2,763
- 기간: 2026-09-23 ~ 2026-09-23
- distinct 날짜: 1
- 중복 그룹: 0
- NULL 수: {'trade_date': 0, 'code': 0}

## 해석 메모
- `min/max/distinct`로 시작일·최신일 존재만으로 이력이 완성됐다고 판단하지 않는다.
- 중간 날짜 누락은 거래일 달력과 대조해 별도 확인이 필요하다.
- NULL은 미수집/미제공이며 0과 다르게 취급한다.
- moneytrend는 startIdx 페이지 번호 오류 수정 전 자료에 구간 누락이 있을 수 있다.
