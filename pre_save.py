## naver에서 증권거래소상장된 kospi, kosdaq 종목 추출
from mod1 import * 
import requests



def get_naver_stock_list(market='KOSPI'):
    """
    네이버 금융에서 KOSPI 또는 KOSDAQ 종목 리스트를 가져옵니다.
    """
    tickers = []
    names = []
    page = 1
    market_code = 0 if market == 'KOSPI' else 1

    while True:
        url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={market_code}&page={page}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table', {'class': 'type_2'})
        if not table:
            break

        rows = table.find_all('tr')[1:]  # 헤더 제외
        row_count = 0
        for row in rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                ticker_link = cols[1].find('a')
                if ticker_link:
                    ticker = ticker_link['href'].split('=')[-1]
                    name = cols[1].text.strip()
                    tickers.append(ticker)
                    names.append(name)
                    row_count += 1

        if row_count == 0:
            break

        next_page = soup.find('a', href=lambda href: href and f'page={page+1}' in href)
        if not next_page:
            break

        page += 1
        import time
        time.sleep(0.5)

    return pd.DataFrame({'티커': tickers, '종목명': names})

# KOSPI 종목 가져오기
try:
    kospi_df = get_naver_stock_list('KOSPI')
    print(f"KOSPI 종목 수: {len(kospi_df)}")
    print(kospi_df.head())
except Exception as e:
    print(f"KOSPI 가져오기 실패: {e}")

# KOSDAQ 종목 가져오기
try:
    kosdaq_df = get_naver_stock_list('KOSDAQ')
    print(f"KOSDAQ 종목 수: {len(kosdaq_df)}")
    print(kosdaq_df.head())
except Exception as e:
    print(f"KOSDAQ 가져오기 실패: {e}")

# 전체 종목 합치기 (출력 생략)
if 'kospi_df' in locals() and 'kosdaq_df' in locals():
    all_stocks = pd.concat([kospi_df, kosdaq_df], ignore_index=True)
    all_stocks.rename(columns={'티커': 'code', '종목명': 'name'}, inplace=True)
    all_stocks = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()
    all_stocks.sort_values(by='code', ascending=True, inplace=True)
    all_stocks.to_excel('C:/users/linux/OneDrive/all_stocks.xlsx', index=False)
    print(f"전체 종목 수: {len(all_stocks)}")
    print(all_stocks.head(10))
else:
    print("종목 데이터를 가져올 수 없습니다.")
	
###############################################

"""
월별 상장주식 종목 갱신 모듈
- 상장폐지 종목 추출
- 신규상장 종목 추출
"""

import time
import pandas as pd
from pathlib import Path
from typing import Tuple
from pykrx import stock
from mod1 import engine

# 설정
DATA_DIR = Path("C:/users/linux/OneDrive/")
KRX_FILE = DATA_DIR / "all_stocks.xlsx"
MARKET_FILE = DATA_DIR / "market.xlsx"
DROP_FILE = DATA_DIR / "drop.xlsx"
NEW_STOCK_FILE = DATA_DIR / "new_stock.xlsx"


def get_last_market_date() -> str:
    """최근 영업일 조회
    # pykrx가 작동하지 않으므로 하드코딩된 과거 날짜 사용
    last_date = '2026-04-17'  # 알려진 영업일
    print(f"하드코딩된 날짜 사용: {last_date}")
    return last_date"""

    query = "SELECT MAX(Date) FROM kospi"
    curs.execute(query)
    result = curs.fetchone()
    print(f"✅ 쿼리 결과: {result}")
    print(f"✅ kospi 테이블의 최종 Date: {result[0]}")
    return str(result[0].strftime('%Y-%m-%d'))

def fetch_krx_tickers(date: str) -> pd.DataFrame:
    """KRX에서 KOSPI/KOSDAQ 전체 종목 조회 (모의 데이터 사용)"""
    all_stocks = pd.read_excel(KRX_FILE)
    all_stocks['code'] = all_stocks['code'].astype(str)
    df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()
    df.sort_values(by='code', ascending=True, inplace=True)
    #df = pd.DataFrame(sample_data)
    print(f"샘플 KRX 데이터 사용: {len(df)}개 종목")
    return df


def load_data(last_date: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """기존 데이터 로드"""
    # 기준 파일 (market.xlsx)
    market_df = pd.read_excel(MARKET_FILE)
    market_df['code'] = market_df['code'].astype(str).str.zfill(6)
    
    # KRX 데이터
    krx_df = fetch_krx_tickers(last_date)
    krx_df['code'] = krx_df['code'].astype(str).str.zfill(6)
	
    # DB 데이터
    query = f"SELECT * FROM market WHERE Date = '{last_date}'"
    db_df = pd.read_sql(query, engine)
    db_df = db_df.rename(columns={'Code': 'code', 'Name': 'name'})
    
    return market_df, krx_df, db_df


def extract_delisted_stocks(market_df: pd.DataFrame, db_df: pd.DataFrame) -> pd.DataFrame:
    """상장폐지 종목 추출 (market.xlsx에는 있으나 DB에는 없는 종목)"""
    merged = pd.merge(market_df, db_df, how='left', on='code', suffixes=('', '_db'))
    delisted = merged[merged['name_db'].isna()][['code', 'name']]
    
    if not delisted.empty:
        delisted.to_excel(DROP_FILE, index=False)
        print(f"상장폐지 종목: {len(delisted)}개 추출 완료")
    else:
        print("상장폐지 종목 없음")
    
    return delisted


def extract_new_stocks(krx_df: pd.DataFrame, market_df: pd.DataFrame) -> pd.DataFrame:
    """신규상장 종목 추출 (KRX에는 있으나 market.xlsx에는 없는 종목)"""
    merged = pd.merge(krx_df, market_df, how='left', on='code', suffixes=('', '_market'))
    new_stocks = merged[merged['name_market'].isna()][['code', 'name']]
    
    # 특수종목(K, L, M으로 시작) 제외
    new_stocks = new_stocks[~new_stocks['code'].astype(str).str.contains('K|L|M', na=False)]
    
    if not new_stocks.empty:
        new_stocks.to_excel(NEW_STOCK_FILE, index=False)
        print(f"신규상장 종목: {len(new_stocks)}개 추출 완료")
    else:
        print("신규상장 종목 없음")
    
    return new_stocks


def print_statistics(market_df: pd.DataFrame, krx_df: pd.DataFrame, db_df: pd.DataFrame):
    """통계 출력"""
    print("\n=== 종목 통계 ===")
    print(f"기준 종목수 (market.xlsx): {len(market_df):,}개")
    print(f"거래소 상장 종목수 (KRX): {len(krx_df):,}개")
    print(f"DB 등록 종목수: {len(db_df):,}개")


def main():
    """메인 실행 함수"""
    start_time = time.time()
    
    try:
        # 1. 최신 거래일 조회
        last_date = get_last_market_date()
        
        # 2. 데이터 로드
        market_df, krx_df, db_df = load_data(last_date)
        
        # 3. 통계 출력
        print_statistics(market_df, krx_df, db_df)
        
        # 4. 상장폐지 종목 추출
        delisted = extract_delisted_stocks(market_df, db_df)
        print(delisted.head(50))

        # 5. 신규상장 종목 추출
        new_stocks = extract_new_stocks(krx_df, market_df)
        
        # 6. 실행시간 출력
        elapsed_time = time.time() - start_time
        print(f"\n실행시간: {elapsed_time:.2f}초")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()





##################################################

####  신규 등록 종목 stock DB , market table에 입력 수동                               
from mod1 import *                                                                                                                                                                

now = dt.datetime.today().strftime('%Y-%m-%d')
#engine = sqlalchemy.create_engine('mysql+pymysql://kkang:leaf2027@localhost/stock?charset=utf8',encoding='utf-8')
engine = sqlalchemy.create_engine('mysql+pymysql://root:leaf2027@localhost/stock?charset=utf8')
conn = pymysql.connect(host = 'localhost', user = 'root', password = 'leaf2027' ,db = 'stock')
curs = conn.cursor()

## def get_stock_price_from_fdr(end_date=now):  코스피,코스닥 전체종목 입력  , make_date실행중 error났을때 이후분 실행
        
file_name = input('파일이름을 입력하세요: sample: new_stock.xlsx')
toward = input('저장 방식을 입력하세요 : sample: excel, sql ')
start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")
table_name = input("table명을 입력하세요 : sample: market")
data=pd.read_excel('C:/users/linux/OneDrive/stockdata/'+ file_name)
   
code_list = data['code'].tolist()
code_list = [str(item).zfill(6) for item in code_list]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              
name_list = data['name'].tolist()
#now = '2022-06-22'
# 코스피 상장종목 전체
stock_dic = dict(list(zip(code_list,name_list)))

for code in sorted(stock_dic.keys()):
    df  = fdr.DataReader(code,start_date,now)
    print(code,stock_dic[code])
    df['Code'],df['Name'] = code,stock_dic[code]
    df = df[['Code','Name','Open','High','Low','Volume','Close']]
    if toward == 'excel':
        df.to_excel('d:\\data_set\\kospi\\'+ stock_dic[code] +'.xlsx',engine = 'xlsxwriter')
    elif toward == 'sql':
        df.to_sql(name=table_name, con=engine, if_exists='append')
		
########################################################

####  신규 등록 종목 stock DB , market table에 입력 자동


#now = dt.datetime.today().strftime('%Y-%m-%d')
start_date = '2023-01-01'
#engine = sqlalchemy.create_engine('mysql+pymysql://kkang:leaf2027@localhost/stock?charset=utf8',encoding='utf-8')
engine = sqlalchemy.create_engine('mysql+pymysql://kkang:leaf2027@localhost/stock?charset=utf8')
conn = pymysql.connect(host = 'localhost', user = 'kkang', password = 'leaf2027' ,db = 'stock')
curs = conn.cursor()

new_one = pd.read_excel('C:/users/linux/OneDrive/new_stock.xlsx')
new_one['code'] = new_one['code'].astype(str).str.zfill(6)

"""# KOSPI 종목 티커 리스트 (예시: 2023-12-01 기준)
tickers_1 = stock.get_market_ticker_list("20250502", market="KOSPI")
tickers_2 = stock.get_market_ticker_list("20250502", market="KOSDAQ")
tickers = tickers_1 + tickers_2

# 종목명 매핑
ticker_to_name = {ticker: stock.get_market_ticker_name(ticker) for ticker in tickers}

df = pd.DataFrame(data=ticker_to_name, index=[0])
df = (df.T)
df.reset_index(inplace=True)
df.columns = ['code','name']
df['code'] = df['code'].astype(str).str.zfill(6)
df['name'] = df['name'].astype(str)
df = df[df['code'].astype(str).str.contains('K|L|M') == False]
df = df.sort_values(by='code', ascending=True)
df.reset_index(drop=True, inplace=True)

new_one = pd.merge(df, a, how='left', on='code')
new_one = new_one[new_one['name_y'].isna()==True]"""

code_list = new_one['code'].tolist()
name_list = new_one['name_x'].tolist()
stock_dic = dict(list(zip(code_list,name_list)))

for code in code_list:
    df  = fdr.DataReader(code,start_date,'2025-11-21')
    df['Code'],df['Name'] = code,stock_dic[code]
    df = df[['Code','Name','Open','High','Low','Volume','Close']]
    df.to_sql(name='market', con=engine, if_exists='append')
    print(code)
    
###################################

## maria db에서 상장폐지종목 삭제

drop = pd.read_excel('C:/users/linux/OneDrive/drop.xlsx')
drop['code'] = drop['code'].astype(str).str.zfill(6)
drop = np.array(del_stock['code'].values.tolist())
for i in drop:
    query = "DELETE FROM market WHERE Code = "+str(i)
    curs.execute(query)
    conn.commit()