# -*- coding: utf-8 -*-
"""Legacy KRX stock-analysis utilities with safer initialization and DB access.

Configure STOCK_DB_HOST, STOCK_DB_PORT, STOCK_DB_USER, STOCK_DB_PASSWORD,
STOCK_DB_NAME, and optionally STOCKDATA_DIR before importing this module.
Database connections are created lazily; importing this file does not query KRX
or MariaDB. Legacy report/scraping APIs are retained where practical.
"""
from __future__ import annotations

import atexit
from contextlib import redirect_stderr, redirect_stdout
import datetime as dt
import glob
import io
import json
import logging
import math
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen
import urllib.request as req

import numpy as np
import pandas as pd
import requests
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)
_session = requests.Session()

# Optional integrations are isolated so a missing scraper/chart package does not
# prevent importing the core stock-data helpers.
_pykrx_output = io.StringIO()
with redirect_stdout(_pykrx_output), redirect_stderr(_pykrx_output):
    try:
        from pykrx import stock, bond
        from pykrx.stock import get_index_ohlcv_by_date
    except ImportError:
        stock = bond = get_index_ohlcv_by_date = None
if _pykrx_output.getvalue():
    logger.debug('pykrx import notice: %s', _pykrx_output.getvalue().strip())

try:
    from fake_useragent import UserAgent
    ua = None  # Instantiate only when a caller actually needs a user agent.
except ImportError:
    UserAgent = None
    ua = None

try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    import pyodbc
except ImportError:
    pyodbc = None

try:
    import plotly.offline as offline
    import plotly.graph_objs as go
except ImportError:
    offline = go = None

try:
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, rc
except ImportError:
    plt = None
    font_manager = rc = None

try:
    from IPython.display import display
except ImportError:
    display = print

try:
    from sklearn.preprocessing import MinMaxScaler
except ImportError:
    class MinMaxScaler:
        """Small NumPy fallback for legacy fit_transform callers."""
        def fit_transform(self, values):
            array = np.asarray(values, dtype=float)
            minimum = np.nanmin(array, axis=0)
            span = np.nanmax(array, axis=0) - minimum
            span = np.where(span == 0, 1.0, span)
            return (array - minimum) / span


# DB credentials are supplied through the environment; no secrets are stored here.
@dataclass(frozen=True)
class DBConfig:
    host: str = os.getenv('STOCK_DB_HOST', '127.0.0.1')
    port: int = int(os.getenv('STOCK_DB_PORT', '3307'))
    user: str = os.getenv('STOCK_DB_USER', 'root')
    password: str = os.getenv('STOCK_DB_PASSWORD', '')
    database: str = os.getenv('STOCK_DB_NAME', 'stock')

DB = DBConfig()
engine = None
connection = None
conn = None
curs = None
stock_last_day = datetime.now().strftime('%Y-%m-%d')


def get_engine():
    """Return a lazily-created SQLAlchemy engine, or None until configured."""
    global engine
    if engine is not None:
        return engine
    if not DB.password:
        return None
    try:
        url = URL.create(
            'mysql+pymysql', username=DB.user, password=DB.password,
            host=DB.host, port=DB.port, database=DB.database,
            query={'charset': 'utf8mb4'},
        )
        engine = sqlalchemy.create_engine(
            url, connect_args={'connect_timeout': 5}, pool_pre_ping=True,
        )
    except Exception as exc:
        logger.warning('MariaDB engine creation failed: %s', exc)
        engine = None
    return engine


def _require_engine():
    eng = get_engine()
    if eng is None:
        raise ConnectionError(
            'MariaDB is not configured. Set STOCK_DB_PASSWORD and optional STOCK_DB_* variables.'
        )
    return eng


def get_conn():
    """Lazily create one PyMySQL connection for legacy cursor-based operations."""
    global connection, conn, curs
    if conn is not None:
        return connection, conn, curs
    if pymysql is None:
        raise ImportError('Install PyMySQL to use cursor-based database operations.')
    if not DB.password:
        raise ConnectionError('Set STOCK_DB_PASSWORD before using database operations.')
    connection = pymysql.connect(
        host=DB.host, port=DB.port, user=DB.user, password=DB.password,
        database=DB.database, connect_timeout=5, charset='utf8mb4',
    )
    conn = connection
    curs = connection.cursor()
    return connection, conn, curs


def _close_db_connections():
    global connection, conn, curs, engine
    if curs is not None:
        try:
            curs.close()
        except Exception:
            logger.debug('Cursor close failed', exc_info=True)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            logger.debug('DB connection close failed', exc_info=True)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            logger.debug('SQLAlchemy engine dispose failed', exc_info=True)
    connection = conn = curs = engine = None


atexit.register(_close_db_connections)

now = datetime.now()
today = now
str_yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
str_today = now.strftime('%Y-%m-%d')
three_period = ['day', 'week', 'month']
final_day = pd.DataFrame({'Date': [str_today]})
kospi_next_day_no_hypyen = (now + timedelta(days=1)).strftime('%Y%m%d')

STOCKDATA_DIR = Path(os.getenv('STOCKDATA_DIR', str(Path.home() / 'OneDrive' / 'stockdata')))
path_test = str(STOCKDATA_DIR / 'test_data') + os.sep
path_down = str(STOCKDATA_DIR / 'period_down') + os.sep
path_depress = str(STOCKDATA_DIR / 'depress') + os.sep
path_depress_d = str(STOCKDATA_DIR / 'depress' / 'depress_day_')
path_depress_w = str(STOCKDATA_DIR / 'depress' / 'depress_week_')
path_depress_m = str(STOCKDATA_DIR / 'depress' / 'depress_month_')
path_vote_stock = str(STOCKDATA_DIR / 'vote_stock') + os.sep
path_price = str(STOCKDATA_DIR / 'vote_stock' / 'detect_stock_with_price_')
path_volume = str(STOCKDATA_DIR / 'vote_stock' / 'detect_stock_with_volume_')
path_close_2008 = str(STOCKDATA_DIR / 'close_ma120' / 'total_close_2008-01-01_')
path_close_2019 = str(STOCKDATA_DIR / 'close_ma120' / 'total_close_2019-01-01_')
path_ma_2008 = str(STOCKDATA_DIR / 'close_ma120' / 'total_ma_2008-01-01_')
path_ma_2019 = str(STOCKDATA_DIR / 'close_ma120' / 'total_ma_2019-01-01_')
path_ma = str(STOCKDATA_DIR / 'close_ma120' / 'total_ma_')
path_close = str(STOCKDATA_DIR / 'close_ma120' / 'total_close_')
path_close_ma120 = str(STOCKDATA_DIR / 'close_ma120') + os.sep


def refresh_market_dates():
    """Refresh module date globals on demand, rather than querying during import."""
    global stock_last_day, final_day, kospi_next_day_no_hypyen
    eng = _require_engine()
    stock_df = pd.read_sql_query(
        text("SELECT `Date` FROM `market` WHERE `Name`=:name ORDER BY `Date` DESC LIMIT 1"),
        eng, params={'name': '삼성전자'},
    )
    if not stock_df.empty:
        stock_last_day = pd.to_datetime(stock_df.iloc[0]['Date']).strftime('%Y-%m-%d')
    index_df = pd.read_sql_query(
        text("SELECT `Date` FROM `kospi` ORDER BY `Date` DESC LIMIT 1"), eng,
    )
    if not index_df.empty:
        latest = pd.to_datetime(index_df.iloc[0]['Date'])
        final_day = index_df
        kospi_next_day_no_hypyen = (latest + pd.Timedelta(days=1)).strftime('%Y%m%d')
    return {'stock_last_day': stock_last_day, 'kospi_next_day': kospi_next_day_no_hypyen}


# Engine creation is lazy and performs no network request. Queries happen only
# when a public function is called.
engine = get_engine()


def login_krx(login_id: str, login_pw: str) -> bool:
    """
    KRX data.krx.co.kr 로그인 후 세션 쿠키(JSESSIONID)를 갱신합니다.
    Example: login_krx(login_id, login_pw)
    """
    _LOGIN_PAGE = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001.cmd"
    _LOGIN_JSP  = "https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc"
    _LOGIN_URL  = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd"
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    try:
        # 초기 세션 발급
        _session.get(_LOGIN_PAGE, headers={"User-Agent": _UA}, timeout=15)
        _session.get(_LOGIN_JSP, headers={"User-Agent": _UA, "Referer": _LOGIN_PAGE}, timeout=15)

        payload = {
            "mbrNm": "", "telNo": "", "di": "", "certType": "",
            "mbrId": login_id, "pw": login_pw,
        }
        headers = {
            "User-Agent": _UA,
            "Referer": _LOGIN_PAGE,
            "X-Requested-With": "XMLHttpRequest"
        }

        # 로그인 POST
        resp = _session.post(_LOGIN_URL, data=payload, headers=headers, timeout=15)
        data = resp.json()
        error_code = data.get("_error_code", "")

        # CD011 중복 로그인 처리
        if error_code == "CD011":
            payload["skipDup"] = "Y"
            resp = _session.post(_LOGIN_URL, data=payload, headers=headers, timeout=15)
            data = resp.json()
            error_code = data.get("_error_code", "")

        if error_code == "CD001":
            print("✅ KRX 로그인 성공")
            return True
        else:
            print(f"❌ KRX 로그인 실패: {data.get('_error_message', error_code)}")
            return False
    except Exception as e:
        print(f"❌ 로그인 중 오류 발생: {e}")
        return False        
        
        
def compare_graph(path_name, day,from_day, subject, count=5):
    name = pd.read_excel(path_name+day+'.xlsx')
    name.columns = map(str.lower, name.columns)
    name = name['name']
    print('all:', name.shape[0])
    name = name.iloc[count:count+5]
    name = name.to_list()
    
    df1 = pd.DataFrame()

    for x in  name:
        df = select_stock(x, from_day)
        df = df[['Date',subject]]
        df.columns=['Date',x]
        
        if df1.empty:
            df1 = df
        elif df.empty:  ##  종목이 상장폐지되어 없어진것은 merge하지 않는다
            pass
        else:
            df1 = pd.merge (df,df1,on='Date')
    df1=df1.set_index('Date')
    df1 = df1[df1.columns[::-1]]  ##  그래프 생성시 legend를 순서대로 나오게하기위해  columns를  재구성
    name=df1.columns.tolist() ##  df에서  상장폐지되어 df1에 없어진 columnes를 수정하여 현행화한 name list
    
    plt.figure(figsize=(12,5))
    for i in range(len(name)):
        plt.plot(df1[name[i]]/df1[name[i]].iloc[0]*100)
        plt.legend(name,loc=0)
        plt.grid(True,color='0.7',linestyle=':',linewidth=2)

def kospi_kosdaq(start_date, lastday='20251231', market='1001'):
    if market == '1001':
        df = stock.get_index_ohlcv_by_date(start_date, lastday, market)
        df.index.names = ['Date']
        df = df.iloc[:,[0,1,2,3,4]]
        df.columns  = ['Open','High','Low','Close','Volume']
        df['Market']='kospi'
        df.to_sql(name='kospi', con=engine, if_exists='append')
    elif market == '2001':
        df = stock.get_index_ohlcv_by_date(start_date, lastday, market)
        df.index.names = ['Date']
        df = df.iloc[:,[0,1,2,3,4]]
        df.columns  = ['Open','High','Low','Close','Volume']        
        df['Market']='kosdaq'
        df.to_sql(name='kosdaq', con=engine, if_exists='append')

    #kospi_kosdaq( market='코스피')

    


def depress(period='day', to_day=str_today):
    
    ''' depress(period) : period = ['day', 'week', 'month'] '''
    
    path_depress = str(STOCKDATA_DIR / 'depress' / 'depress_')
    global from_day
    time_to_day = pd.to_datetime(to_day)
    
    if period == 'day':
        from_day = (time_to_day - timedelta(days=60)).strftime('%Y-%m-%d')
        from_day = str(from_day)

    elif period == 'week':
        from_day = (time_to_day - timedelta(days=180)).strftime('%Y-%m-%d')
        from_day = str(from_day)

    elif period == 'month':
        from_day = (time_to_day - timedelta(days=365*2)).strftime('%Y-%m-%d')
        from_day = str(from_day)
        
    else:
        print("depress( ['day', 'week', 'month'] )  ")
        pass

    df = select_stock('all', stock_last_day, stock_last_day)
    df = df['Name']
    name = df.to_list()

    count = 0
    depress = []
    for i in name:
        df = day_week_month_data(market=i, from_day=from_day, to_day = to_day,  period=period)

        df['yesterday'] = df.Close.shift(1)
        df['minus'] = (df['Close']-df['yesterday']) < 0
        df1 = df.sort_values(by=['Date'], axis=0,
                             ascending=False, ignore_index=True)
        minus = df1.minus.values

        for i in minus:
            if i == True:
                count += 1

            else:
                break

        # print(count)
        depress.append(count)
        count = 0

    df2 = pd.DataFrame()
    df2['name'] = name
    df2['count'] = depress
    df3 = df2.sort_values(by=['count'], axis=0, ascending=False, ignore_index=True)
    if period == 'month':
        df3 = df3.iloc[:100]
    elif period == 'week':
        df3 = df3.iloc[:200]
    elif period == 'day':
        df3 = df3.iloc[:300]
    else:
        pass
    df3 = df3.rename(columns={'name': 'Name'})
    df3.to_excel(path_depress+period+str_today+'.xlsx')
    
def candle_graph(market='kospi', from_day='2020-01-01', to_day=str_today, period='week'):
    df = day_week_month_data(market, from_day, to_day, period)

    df = df[['Date','Open','High','Low','Close']]
    
    offline.init_notebook_mode(connected = True)

    trace = go.Candlestick(x=df.Date, open=df.Open, high=df.High, low=df.Low, close = df.Close,increasing_line_color= 'red', decreasing_line_color= 'blue')
    data =[trace]

    layout=go.Layout(title=market)
    fig = go.Figure(data=data, layout=layout)
    offline.iplot(fig,filename='candlestick')
    
def bokeh_chart(market='kospi', from_day='2019-01-01', to_day=str_today, period='month'):
    from math import pi
    from bokeh.io import output_notebook, show
    from bokeh.plotting import figure
    from bokeh.layouts import gridplot

    output_notebook()
    
    df = day_week_month_data(market, from_day, to_day, period)
    df = df.set_index(df['Date'], drop=True)
    df.rename(columns = {'Date' : 'Date1'}, inplace = True)  ##  Bokeh_Chart에서 Date index를사용하기위해 Colume명 Date를 Date1으로변경    
    mids = (df.Open + df.Close)/2
    spans = abs(df.Close-df.Open)

    inc = df.Close >= df.Open
    dec = df.Open > df.Close

    TOOLS = "pan,wheel_zoom,box_zoom,reset,save,crosshair"

    p_candlechart = figure(x_axis_type="datetime", tools=TOOLS, plot_width=900, plot_height=200, toolbar_location="left",title = market)
    p_candlechart.xaxis.major_label_orientation = pi/4
    p_candlechart.segment(df.index[inc], df.High[inc], df.index[inc], df.Low[inc], color="red")
    p_candlechart.segment(df.index[dec], df.High[dec], df.index[dec], df.Low[dec], color="blue")
    p_candlechart.vbar(df.index[inc], 0.5, df.Open[inc], df.Close[inc], fill_color="red", line_color="red",line_width=10)
    p_candlechart.vbar(df.index[dec], 0.5, df.Open[dec], df.Close[dec], fill_color="blue", line_color="blue",line_width=10)

    p_volumechart = figure(x_axis_type="datetime", tools=TOOLS, plot_width=900, plot_height=200, toolbar_location="left")
    p_volumechart.vbar(df.index, 0.5, df.Volume, fill_color="black", line_color="black",line_width=10)

    p = figure(tools='crosshair', plot_width=900, toolbar_location="left")
    p = gridplot([[p_candlechart], [p_volumechart]], toolbar_location='left')
    show(p)


def bad_stock():
    """Fetch and refresh the bad-stock table; network/DB work is on explicit call."""
    return _refresh_bad_stock_table()

def from_excel_analysis(path,file_day,from_date):
    df = pd.read_excel(path+file_day+'.xlsx')
    df.columns = map(str.lower, df.columns) ## columns 명을 소문자로 
    df = df['name']

    name=df.to_list()
    for i in name:
        df=select_stock(i,from_date,)
        close_ma_vol(df, 'ma60')
        
def last_page(source):
    # pgRR 태그가 있는지 먼저 확인합니다.
    pg_rr = source.find('td', class_='pgRR')
    
    # 만약 끝 페이지 버튼이 없다면, 현재 페이지가 마지막(1페이지)입니다.
    if not pg_rr:
        return 1
        
    last = pg_rr.find('a')['href']
    last = last.split('page')[1]
    last = last.split('=')[1]
    return int(last)








def make_name_list(path_name=path_depress, arg = "*day*.*" , num=0, degree=30):
    '''make_name_list(path_vote_stock, arg = '*price*.*', num=3, degree=30)'''
    
    files = glob.glob(os.path.join(path_name , arg))

    try:
        aa = re.findall(r'\d+', files[num])
        bb=[aa[0]+'-'+aa[1]+'-'+aa[2] ]
    except Exception:
        pass
    df = pd.read_excel(files[num], index_col=0)
    
    if len(df) > 50:
        
        name = df['Name'][:degree]
        
    else:
        name = df['Name'] 
        
    name.tolist()
    
    try:
        print(bb)
    except:
        pass
    
    return name



##  종목을 date_list에 있는 시점에서  ex: date_list=['2020-01-01','2020-06-30','2021-01-01']  graph 변화를 볼수 있다
def stock_volume_graph(name, date_list):  
    for i in name:
        for j in date_list:
            df = select_stock(i, j,)
            close_ma_vol(df,'ma60','ma120','volume')
        
def stock_close_graph(name, date_list):
    for i in name:
        for j in date_list:
            df = select_stock(i, j,)
            close_ma(df,'ma60','ma120')
            
##  market(kospi, kosdaq)을 date_list에 있는 시점에서  ex: date_list=['2020-01-01','2020-06-30','2021-01-01']  graph 변화를 볼수 있다
def market_volume_graph(name, date_list):  
    for i in name:
        for j in date_list:
            df = select_market(i, j,)
            market_ma_vol(df,'ma60','ma120','volume')
        
def market_close_graph(name, date_list):
    for i in name:
        for j in date_list:
            df = select_market_period(i, j)
            market_ma(df,'ma60','ma120')            
    

        
###  buysell_products 중복입력중에서 최종  bsdate만 남기고 delete하는 코드

def delete_duplication(oname, *, confirm=False):
    """Compatibility wrapper; destructive Access cleanup requires explicit opt-in."""
    if not confirm:
        raise PermissionError('삭제 작업입니다. 검토 후 delete_duplication(oname, confirm=True)로 실행하세요.')
    return _delete_duplication_access(oname)



    
def make_dataset(name,date):
    col = ['ma5', 'ma10', 'ma15', 'ma20', 'ma30', 'ma60', 'ma120','volume', 'close']
    df = select_stock(name,from_date,)

    ma(df)
    df = df.iloc[120:]
    title=df['name'][120]

    source = MinMaxScaler()
    data = source.fit_transform(df[col].values.astype(float))
    df1 = pd.DataFrame(data)
    df1.columns=['ma5', 'ma10', 'ma15', 'ma20', 'ma30', 'ma60', 'ma120','volume', 'close']
    df1 = df1.set_index(df['date'])
    return df1  

def select_graph(path_name, day, from_day='2019-01-01', count=30, method=None, fix=1):
    #choice_date = day
    if method is None:
        method = close_ma_vol
    name = pd.read_excel(path_name+day+'.xlsx')
    name.columns = map(str.lower, name.columns)
    name = name['name']
    print('all:', name.shape[0])
    if fix==1:
        name = name.iloc[:count]
    else:
        name = name.iloc[count:count+5]
    name = name.to_list()
    
    for i in name:
        #df = select_stock(i,'2008-01-01','2020-01-02')
        df = select_stock(i,from_day)
        df.columns = map(str.lower, df.columns)
        #close_ma(df,'ma60','ma120')
        #rsi(df)
        #obv(df)
        method(df)

def period_down(from_day, to_day):
    start = time.time()

    df_date = pd.read_sql_query(
        text("SELECT `Date` FROM `market` WHERE `Name`=:name ORDER BY `Date` DESC LIMIT 1"),
        _require_engine(), params={'name': 'hrs'},
    )
    df_date = pd.to_datetime(df_date['Date'])
    #df = df + timedelta(1)          ##  최종날짜 다음날짜
    df_date = str(df_date)
    standard = df_date[4:14]                ## 2020-07-13

    query = text(
        "SELECT `Name`, MIN(`Close`) AS `min_close` FROM `market` "
        "WHERE `Date` > :from_day AND `Date` <= :to_day GROUP BY `Name`"
    )
    df = pd.read_sql_query(
        query, _require_engine(),
        params={'from_day': _normalize_date(from_day), 'to_day': _normalize_date(to_day)},
    )

    df1 = select_stock('all', standard, )
    df1_last = df1[['Name','Close']]

    df2 = pd.merge(df, df1_last, on="Name")
    df2['diff'] = df2['Close'] / df2['min_close'].replace(0, np.nan)
    df2 = df2.sort_values(by=['diff'], ascending=True)
    df2 = df2.reset_index(drop=True)
    #display(df2)
    df2.to_excel(path_down+standard+'.xlsx')

def get_naver_stock_list(market='KOSPI'):
    base_url = "https://finance.naver.com/sise/sise_market_sum.naver"
    params = {'sosok': 0 if market == 'KOSPI' else 1}
    
    tickers = []
    names = []
    
    page = 1
    while True:
        params['page'] = page
        response = requests.get(base_url, params=params)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'class': 'type_2'})
        if not table:
            break
        
        rows = table.find_all('tr')[1:]
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                ticker_link = cols[1].find('a')
                if ticker_link:
                    ticker = ticker_link['href'].split('=')[-1]
                    name = cols[1].text.strip()
                    tickers.append(ticker)
                    names.append(name)
        
        next_page = soup.find('a', {'href': f'?sosok={params["sosok"]}&page={page+1}'})
        if not next_page:
            break
        page += 1
        
        if page > 50:  # 최대 50페이지 제한
            break
    
    return pd.DataFrame({'티커': tickers, '종목명': names})
    

class analysis:
    """Analysis/report helpers. Database access occurs on construction or method call."""
    select_start_a = '2019-01-01'
    select_start_b = '2008-01-01'

    def __init__(self, date_limit=250, load_dates=True):
        self.name = []
        self.datelist = []
        self.from_day = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        self.to_day = stock_last_day
        if load_dates:
            try:
                refresh_market_dates()
                self.to_day = stock_last_day
                ref = select_stock('hrs', self.from_day, self.to_day)
                if not ref.empty and 'Date' in ref:
                    self.datelist = pd.to_datetime(ref['Date']).drop_duplicates().sort_values().tail(date_limit).tolist()
            except Exception as exc:
                logger.warning('Analysis date initialization skipped: %s', exc)

    def search_stock_long_period_graph(self, path, select_day, select_start=None, to_day=None):
        start = select_start or self.select_start_a
        end = to_day or self.to_day
        source = pd.read_excel(str(path) + str(select_start or self.select_start_a) + '_' + str(select_day) + '.xlsx')
        name_col = next((c for c in source.columns if str(c).lower() == 'name'), None)
        if name_col is None:
            raise ValueError('Input Excel must contain a Name column.')
        for symbol in source[name_col].dropna().astype(str):
            frame = select_stock(symbol, start, end)
            if not frame.empty:
                close_ma_vol(frame)

    def search_stock_long_period(self, name, select_start, from_day=None, to_day=None):
        start = from_day or select_start
        end = to_day or self.to_day
        symbols = [name] if isinstance(name, str) else list(name)
        frames = []
        for symbol in symbols:
            frame = select_stock(str(symbol), start, end)
            if frame.empty:
                continue
            frame = ma(frame)
            required = {'date', 'close', 'ma60', 'ma120', 'volume'}
            if not required.issubset(frame.columns):
                continue
            frame = frame[['date', 'close', 'ma60', 'ma120', 'volume']].copy()
            for column in ('close', 'ma60', 'ma120', 'volume'):
                values = pd.to_numeric(frame[column], errors='coerce')
                span = values.max() - values.min()
                frame[column] = (values - values.min()) / span if pd.notna(span) and span else 0.0
            frame['name'] = str(symbol)
            frames.append(frame)

        if not frames:
            return pd.DataFrame(columns=['date', 'close', 'ma60', 'ma120', 'volume', 'name'])
        combined = pd.concat(frames, ignore_index=True)
        dates = self.datelist or sorted(combined['date'].dropna().unique())[-250:]
        output = {}
        Path(path_ma).parent.mkdir(parents=True, exist_ok=True)
        Path(path_close).parent.mkdir(parents=True, exist_ok=True)
        for day in dates:
            day_frame = combined[combined['date'] == day].copy()
            if day_frame.empty:
                continue
            low_close = day_frame[day_frame['close'] < 0.1].sort_values('close')
            rising_trend = day_frame[
                (day_frame['ma120'] < 0.1)
                & (day_frame['close'] > day_frame['ma60'])
                & (day_frame['ma60'] > day_frame['ma120'])
            ].sort_values('ma120')
            label = pd.Timestamp(day).strftime('%Y-%m-%d')
            low_close.to_excel(f'{path_close}{select_start}_{label}.xlsx', index=False)
            rising_trend.to_excel(f'{path_ma}{select_start}_{label}.xlsx', index=False)
            output[label] = {'low_close': low_close, 'rising_trend': rising_trend}
        return output


class to_report:
    select_query = "select * from market where Date >="
    volume_query = "&& Volume >  10000"
    def stock_select_with_Volume_Close(self,choice = 1):
    
        if choice == 1:
            from_day = input("어제날짜를 입력하세요 : sample: '2019-02-07'  ") or str_yesterday
            to_day = input("오늘날짜를 입력하세요 : sample: '2019-02-07'  ") or str_today
        
        else:
            day_df = pd.read_sql("select Date from market where Name='삼성전자' order by Date desc limit 2", engine)
            from_day = str(day_df['Date'][1])
            to_day = str(day_df['Date'][0])
            
        df  =select_stock('all', from_day, )
        df = df[df['Volume'] >  300000]
        df = df.reset_index(drop=True)
        #display(df)

        df1 = df[df['Date'].astype(str) == from_day]
        df1 = df1[['Name','Volume','Close']]
        df1.columns = ['Name','yester_Volume','yester_Close']
        #display(df1)


        df2 = df[df['Date'].astype(str) == to_day]
        df2 = df2[['Name','Volume','Close']]
        df2.columns = ['Name','today_Volume','today_Close']
        #display(df2)

        df3 = pd.merge(df1,df2,on='Name')
        df3['Close'] = df3['today_Close'].div(df3['yester_Close'].replace(0, np.nan))
        df3['Volume'] = df3['today_Volume'].div(df3['yester_Volume'].replace(0, np.nan))
        df3 = df3.sort_values(by=['Volume','Close'],ascending=False)
        df4 = df3.sort_values(by=['Close','Volume'],ascending=False)
        df3 = df3.reset_index(drop=True)

        df3 = df3[:15]
        df4 = df4.reset_index(drop=True)
        df4 = df4[:15]
        df3.to_excel(f"{path_volume}{str_today}.xlsx")
        df4.to_excel(f"{path_price}{str_today}.xlsx")       
        display(df3)
        display(df4)        

        
        
        
    def get_graph(self, choice=1):
        graph_name_list=['stock','money', 'program','future']
        #today = datetime.now()        
        date='2019-01-01'
        future_date='2019-12-11'  ##  선물마감 하루전
        global today

        if choice == 1:
            graph = input("그래프종류를 입력하세요 sample: 'money' or 'program' or 'stock' or 'future':  ")
            date = input("날짜를 입력하세요 sample: '2019-01-10':") or '2019-01-01'

            if graph == 'money' :
                money_name = ['kpi200', '거래량', '고객예탁금', '신용잔고']
                money_query = text("SELECT * FROM `kpi_with_money` WHERE `Date` > :date ORDER BY `Date`")
                money_df = pd.read_sql_query(money_query, _require_engine(), params={'date': _normalize_date(date)})

                money_df.columns=['Date','kpi200', '거래량', '고객예탁금', '신용잔고', '주식형펀드', '혼합형펀드', '채권형펀드']
                money_df = money_df.set_index('Date')
                df1 = money_df[money_name]
                #return df1

                plt.figure(figsize=(16,4))         
                colors = ['red','green','blue','black']
                for i in range(len(money_name)):
                    plt.subplot(2,2,i+1)
                    plt.plot(df1[money_name[i]]/df1[money_name[i]].loc[money_df.index[0]]*100, color=colors[i])
                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    #plt.show()

            elif graph == 'program' :
                program_name = ['차익', '비차익', '전체']
                program_query = text("SELECT * FROM `programtrend` WHERE `Date` > :date ORDER BY `Date`")
                program_df = pd.read_sql_query(program_query, _require_engine(), params={'date': _normalize_date(date)})

                program_df.columns=['Date','차익', '비차익', '전체']
                program_df = program_df.set_index('Date')
                df1=program_df[program_name]
                #return df1

                plt.figure(figsize=(16,4))        
                colors = ['red','green','blue','black']
                for i in range(len(program_name)):

                    plt.subplot(2,2,i+1)
                    plt.plot(df1[program_name[i]],color=colors[i])

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    #plt.show()

            elif graph == 'stock' :
                name = input('주식이름을 입력하세요:').split()
                series_frames = []
                for symbol in name:
                    frame = select_stock(symbol, date, stock_last_day)
                    if frame.empty:
                        continue
                    series_frames.append(
                        frame[['Date', 'Volume', 'Close']].rename(
                            columns={'Volume': f'{symbol}거래량', 'Close': symbol}
                        )
                    )
                if not series_frames:
                    logger.info('No stock rows found for the requested comparison.')
                    return
                df1 = series_frames[0]
                for frame in series_frames[1:]:
                    df1 = pd.merge(df1, frame, on='Date', how='inner')
                df1 = df1.set_index('Date').sort_index()
                size = len(df1.index)

                plt.figure(figsize=(16,4))
                for symbol in name:
                    if symbol not in df1:
                        continue
                    base = df1[symbol].dropna().iloc[0]
                    if base:
                        plt.plot(df1.index, df1[symbol] / base * 100, label=symbol)
                plt.legend(loc=0)
                plt.grid(True,color='0.7',linestyle=':',linewidth=1)

                plt.figure(figsize=(16,4))
                for symbol in name:
                    volume_column = f'{symbol}거래량'
                    if volume_column not in df1 or size == 0:
                        continue
                    volume_average = df1[volume_column].mean()
                    if pd.notna(volume_average) and volume_average:
                        plt.plot(df1.index, df1[volume_column] / volume_average, label=symbol)
                plt.legend(loc=0)
                plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    
            elif graph == 'future' :

                #name = input("항목을 입력하세요: 선택항목: 'kpi200', '거래량', '고객예탁금', '신용잔고', '주식형펀드', '혼합형펀드', '채권형펀드'").split()
                #date = input("날짜를 입력하세요 sample: '2019-01-10':")

                query = text("SELECT * FROM `future` WHERE `Date` > :date ORDER BY `Date`")
                query1 = text("SELECT * FROM `basis` WHERE `Date` > :date ORDER BY `Date`")

                name=['Close', '미결제약정', '외국인', '기관', '개인']
                name1=['Close','미결제약정']
                name2=['외국인', '기관', '개인']
                basis_name=['kpi200','Future']

                #tuple_name=tuple(name)
                df1 = pd.DataFrame()
                basis_df1 = pd.DataFrame()

                df = pd.read_sql_query(query, _require_engine(), params={'date': _normalize_date(future_date)})
                basis_df = pd.read_sql_query(query1, _require_engine(), params={'date': _normalize_date(future_date)})

                df.columns=['Date', 'Close', '미결제약정', '외국인', '기관', '개인']
                df = df.set_index('Date')
                df1=df[name]

                basis_df = basis_df.set_index('Date')
                basis_df1=basis_df[basis_name]

                colors = ['red','green','blue','black']
                plt.figure(figsize=(16,4))    
                for i in range(len(basis_name)):
                    plt.plot(basis_df1[basis_name[i]]/basis_df1[basis_name[i]].loc[basis_df.index[0]]*100)

                plt.legend(loc=0)
                plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                plt.show()
                
                plt.figure(figsize=(16,4))    
                for i in range(len(name1)):
                    #plt.subplot(2,2,i+1)
                    plt.plot(df1[name1[i]]/df1[name1[i]].loc[df.index[0]]*100)

                plt.legend(loc=0)
                plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                plt.show()

                plt.figure(figsize=(16,4)) 
                for i in range(len(name2)):
                    plt.subplot(2,2,i+1)
                    plt.plot(df1[name2[i]]/df1[name2[i]].loc[df.index[0]]*100,color = colors[i])

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
 
            else : 
                print('\n input error\n')

                
        else:
            raise ValueError('choice=0 batch mode had hard-coded dates and outputs; run explicit routines instead.')
class to_sql:
    excel_name_list=['kpi200.xlsx', 'investor_trend.xlsx','money_trend.xlsx','program_trend.xlsx','kospi_sector.xlsx','kosdaq_sector.xlsx','market.xlsx','kospi.xlsx','kosdaq.xlsx']
    sql_table_name_list=['kpi200','investortrend','moneytrend','programtrend','kospi_sector','kosdaq_sector','market','kospi','kosdaq']
    
    
    #excel_name_list=['kpi200.xlsx', 'investor_trend.xlsx','money_trend.xlsx','program_trend.xlsx','market.xlsx']
    #sql_table_name_list=['kpi200','investortrend','moneytrend','programtrend','market']
    
    def excel_to_sql(self, choice = 1):
        global engine
        engine = get_engine()
        if engine is None:
            raise ConnectionError('Configure STOCK_DB_PASSWORD before importing Excel data.')
        excel_name_list=self.excel_name_list
        sql_table_name_list=self.sql_table_name_list

        if choice == 1:
        
            file_name = input('파일이름을 입력하세요:')
            if file_name not in excel_name_list:
                raise ValueError(f'Unsupported input workbook: {file_name}')

            df=pd.read_excel(str(STOCKDATA_DIR.parent / file_name))
            if file_name=='kpi200.xlsx':
                table_name = 'kpi200'
                df.columns=['Date','kpi200','거래량']

            elif file_name=='investor_trend.xlsx':
                table_name = 'investortrend'
                df.columns=['Date', '개인', '외국인','기관']

            elif file_name=='money_trend.xlsx':
                table_name = 'moneytrend'
                df.columns=['Date', '고객예탁금', '신용잔고','주식형펀드','혼합형펀드','채권형펀드']

            elif file_name=='program_trend.xlsx':
                table_name = 'programtrend'
                df.columns=['Date', '차익', '비차익','전체']
           
            elif file_name=='kospi_sector.xlsx':
                table_name = 'kospi_sector'
                df.columns=['Date', 'sectorName', 'changeRate', 'first', 'second']
                
            elif file_name=='kosdaq_sector.xlsx':
                table_name = 'kosdaq_sector'
                df.columns=['Date', 'sectorName', 'changeRate', 'first', 'second']                
        
            elif file_name=='market.xlsx':
                data = pd.read_excel(str(STOCKDATA_DIR.parent / 'market.xlsx'))
                start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")

                code_list = data['code'].tolist()
                code_list = [str(item).zfill(6) for item in code_list]
                name_list = data['name'].tolist()

                # 코스피 상장종목 전체
                stock_dic = dict(list(zip(code_list,name_list)))

                for code in sorted(stock_dic.keys()):
                    df  = fdr.DataReader(code,start_date)
                    print(code,stock_dic[code])
                    df['Code'],df['Name'] = code,stock_dic[code]
                    df = df[['Code','Name','Open','High','Low','Volume','Close']]
                    df.to_sql(name='market', con=engine, if_exists='append')
                return 

            else:
                print('\n file_name error\n')

            df.to_sql(name=table_name, con=engine, if_exists='append', index = False)

            print(df)
            
        else :
            a = 0
            for i in excel_name_list:
                
                if i == 'market.xlsx':
                    data = pd.read_excel(str(STOCKDATA_DIR.parent / 'market.xlsx'))
                    market_df = pd.read_sql("select Date from market order by Date desc limit 1", engine)
                    market_df = str(market_df['Date'])
                    print(market_df)
                    start_date =  market_df[5:15]
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    start_date= (start + timedelta(days=1)).strftime('%Y-%m-%d') ## datetime.timedelta 함수를 사용혀여 3.31 -> 4.1일로 일자변경
                                        
                    print('\n market start_date:{}'.format(start_date))

                    code_list = data['code'].tolist()
                    code_list = [str(item).zfill(6) for item in code_list]  ### 종목코드를 6자리로 밎춤
                    name_list = data['name'].tolist()

                    # 코스피 상장종목 전체
                    stock_dic = dict(list(zip(code_list,name_list)))

                    for code in sorted(stock_dic.keys()):
                        df  = fdr.DataReader(code,start_date)
                        print(code,stock_dic[code])
                        df['Code'],df['Name'] = code,stock_dic[code]
                        df = df[['Code','Name','Open','High','Low','Volume','Close']]
                        #df
                        df.to_sql(name='market', con=engine, if_exists='append')
                    return 
                else :
                    table_name = sql_table_name_list[a]
                    df=pd.read_excel(str(STOCKDATA_DIR.parent / i))
                    print(table_name)
                    df = df.rename(columns = {'Unnamed: 0': 'Date'})
                    df.to_sql(name=table_name, con=engine, if_exists='append', index = False)

                    print(df)
                a += 1
    
                
                
    ###  fdr을 통해 별도로 data수집
    def insert_all_stock(self, end_date=str_today):
        global engine
        engine = get_engine()
        if engine is None:
            raise ConnectionError('Configure STOCK_DB_PASSWORD before inserting stock data.')
        if fdr is None:
            raise ImportError('Install FinanceDataReader to download stock history.')
        
        file_name = input('파일이름을 입력하세요:')
        toward = input('저장 방식을 입력하세요 : sample: excel, sql ')
        start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")
        table_name = input("table명을 입력하세요 : sample: market")
        if table_name != 'market':
            raise ValueError('This downloader only writes to the market table.')
    
        data=pd.read_excel(str(STOCKDATA_DIR.parent / file_name))
   
        code_list = data['종목코드'].tolist()
        code_list = [str(item).zfill(6) for item in code_list]
        name_list = data['종목명'].tolist()

        # 코스피 상장종목 전체
        stock_dic = dict(list(zip(code_list,name_list)))

        for code in sorted(stock_dic.keys()):
            df  = fdr.DataReader(code,start_date,str_today)
            print(code,stock_dic[code])
            df['Code'],df['Name'] = code,stock_dic[code]
            df = df[['Code','Name','Open','High','Low','Volume','Close']]
            if toward == 'excel':
                df.to_excel(str(STOCKDATA_DIR.parent / 'data_set' / 'kospi' / f"{stock_dic[code]}.xlsx"),engine = 'xlsxwriter')
            elif toward == 'sql':
                df.to_sql(name=table_name, con=engine, if_exists='append')
                
    def insert_individual_stock(self, end_date=str_today):
        global engine
        if fdr is None:
            raise ImportError('Install FinanceDataReader to download stock history.')
        engine = get_engine()
        if engine is None:
            raise ConnectionError('Configure STOCK_DB_PASSWORD before inserting stock data.')

        code = input('주식 Code를 입력하세요: ').strip().zfill(6)
        name = input('주식이름을 입력하세요: ').strip()
        if not code.isdigit() or not name:
            raise ValueError('유효한 종목코드와 종목명을 입력하세요.')

        # Download and validate before touching existing rows. Delete+insert is
        # transactional, so a failed download cannot erase the current history.
        frame = fdr.DataReader(code, '1995', end_date)
        if frame is None or frame.empty:
            raise ValueError(f'No price history returned for {code}; existing rows were kept.')
        frame = frame.copy()
        frame.index.name = 'Date'
        frame = frame.reset_index()
        frame['Code'] = code
        frame['Name'] = name
        required = ['Date', 'Code', 'Name', 'Open', 'High', 'Low', 'Volume', 'Close']
        frame = frame[required].dropna(subset=['Date', 'Open', 'High', 'Low', 'Volume', 'Close'])
        if frame.empty:
            raise ValueError(f'No complete OHLCV rows returned for {code}; existing rows were kept.')

        with engine.begin() as transaction:
            transaction.execute(text('DELETE FROM `market` WHERE `Code`=:code'), {'code': code})
            frame.to_sql(name='market', con=transaction, if_exists='append', index=False)
        return {'code': code, 'name': name, 'rows': len(frame)}

    def update_market_incremental(self, end_date=None, full_start='19950101',
                                  table='market', dry_run=False, sleep_sec=0.2,
                                  limit_codes=None):
        """DB에 없는 날짜의 종목 데이터만 KRX(pykrx)에서 읽어와 테이블에 추가한다.

        기존 insert_all_stock / excel_to_sql(시장)은 시작일부터 전 종목을
        매번 전부 다시 받는 방식이라 느리고 중복 위험이 있다. 이 함수는
        종목별 DB 최종일자(MAX(Date)) 다음날부터 최신 거래일까지,
        DB에 이미 있는 날짜는 제외하고 없는 날짜 행만 INSERT 한다.
        → 재실행해도 중복 입력이 생기지 않는다.

        - 상장폐지 추정 코드(DB에만 있고 KRX 목록에 없음)는 건너뛴다.
        - DB에 한 번도 없는 신규 상장 종목은 full_start부터 전 구간 수집한다.
        - 빠른 종목별 조회를 위해 (Code, Date) 인덱스를 최초 1회 생성한다.

        예) to_sql().update_market_incremental(dry_run=True)  # 대상 미리보기
            to_sql().update_market_incremental()               # 실제 업데이트
            to_sql().update_market_incremental(limit_codes=['005930'])  # 특정 종목만
        """
        import time as _time
        if table != 'market':
            raise ValueError('This updater only writes to the market table.')
        if stock is None:
            print('pykrx가 없어서 실행할 수 없습니다. pip install pykrx')
            return None
        if engine is None:
            print('DB(engine)에 연결되어 있지 않습니다.')
            return None

        # 1) 최신 거래일자 결정
        if end_date is None:
            probe = dt.date.today()
            end_date = None
            for _ in range(10):
                s = probe.strftime('%Y%m%d')
                try:
                    _df = stock.get_market_ohlcv(s, s, '005930')
                    if _df is not None and not _df.empty:
                        end_date = s
                        break
                except Exception:
                    pass
                probe -= dt.timedelta(days=1)
            if end_date is None:
                print('최신 거래일자를 찾지 못했습니다.')
                return None
        end_dt = dt.datetime.strptime(end_date, '%Y%m%d').date()
        print(f'업데이트 목표일자: {end_date}')

        # 2) 현재 KRX 상장 목록 (limit_codes가 있으면 그것만)
        if limit_codes:
            listed = [str(c).zfill(6) for c in limit_codes]
        else:
            listed = []
            try:
                for _mkt in ('KOSPI', 'KOSDAQ'):
                    listed += [str(c) for c in
                               stock.get_market_ticker_list(end_date, market=_mkt)]
            except Exception as e:
                print(f'KRX 상장목록 조회 실패: {e}')
                return None
        print(f'KRX 상장 종목 수: {len(listed)}')

        # 3) DB 종목별 최종일자 + 그때의 이름 (서버에서 1회 집계)
        db_max, db_name = {}, {}
        try:
            _g = pd.read_sql_query(
                text(f'SELECT `Code`, `Name`, MAX(`Date`) AS m FROM `{table}` GROUP BY `Code`, `Name`'),
                _require_engine(),
            )
            for _r in _g.itertuples():
                _d = pd.to_datetime(_r.m).date()
                if _r.Code not in db_max or _d > db_max[_r.Code]:
                    db_max[_r.Code] = _d
                    db_name[_r.Code] = _r.Name
        except Exception as e:
            print(f'DB 최종일자 조회 실패: {e}')
            return None

        # DB에 없는 코드(신규 상장 추정)는 KRX에서 이름 조회 (소수라 개별조회로 충분)
        for _code in listed:
            if _code not in db_name:
                try:
                    db_name[_code] = stock.get_market_ticker_name(_code)
                except Exception:
                    db_name[_code] = _code
                _time.sleep(0.1)

        # 4) 종목별 필요 구간 계산 (최종일자 다음날 ~ 목표일자)
        jobs = []  # (code, name, start_date)
        skipped = 0
        for _code in sorted(set(listed)):
            _last = db_max.get(_code)
            if _last is None:
                _start = dt.datetime.strptime(full_start, '%Y%m%d').date()
            else:
                _start = _last + dt.timedelta(days=1)
                if _start > end_dt:
                    skipped += 1
                    continue
            jobs.append((_code, db_name.get(_code, _code), _start))
        n_delisted = len([c for c in db_max if c not in set(listed)])
        print(f'최신 상태(스킵): {skipped}개 / 업데이트 대상: {len(jobs)}개 / '
              f'DB에만 있는 코드(상장폐지 추정, 스킵): {n_delisted}개')

        if dry_run:
            print('--- DRY-RUN: 다운로드/입력 없이 대상만 표시 (상위 20개) ---')
            for _code, _nm, _st in jobs[:20]:
                print(f'  {_code} {_nm}: {_st} ~ {end_dt}')
            if len(jobs) > 20:
                print(f'  ... 외 {len(jobs) - 20}개')
            return {'dry_run': True, 'jobs': len(jobs)}

        # Add a covering index only for a real update; preview mode remains read-only.
        try:
            with engine.begin() as _con:
                _con.execute(sqlalchemy.text(
                    f'CREATE INDEX IF NOT EXISTS idx_{table}_code_date '
                    f'ON {table} (Code, Date)'))
            print(f'index ok: idx_{table}_code_date')
        except Exception as e:
            logger.warning('Could not create the optional Code/Date index: %s', e)

        # 5) KRX에서 없는 구간만 조회 → DB 기존 날짜 제외 → 모아서 1회 입력
        new_frames, done, failed = [], 0, []
        for _i, (_code, _nm, _st) in enumerate(jobs, 1):
            try:
                _df = stock.get_market_ohlcv(_st.strftime('%Y%m%d'), end_date, _code)
                if _df is None or _df.empty:
                    continue
                _df = _df.copy()
                _df.columns = [str(c).strip() for c in _df.columns]
                need = {'시가': 'Open', '고가': 'High', '저가': 'Low',
                        '종가': 'Close', '거래량': 'Volume'}
                if not set(need) <= set(_df.columns):
                    failed.append((_code, 'columns'))
                    continue
                _df = _df.rename(columns=need)[['Open', 'High', 'Low', 'Close', 'Volume']]
                _df = _df.dropna()
                if _df.empty:
                    continue
                _df.index = pd.to_datetime(_df.index).date
                # DB에 이미 있는 날짜 제외 (같은 Code 기준) → 중복 입력 방지
                _have = pd.read_sql_query(
                    text(f'SELECT `Date` FROM `{table}` WHERE `Code`=:code AND `Date`>=:start_date'),
                    _require_engine(),
                    params={'code': _code, 'start_date': _st.strftime('%Y-%m-%d')},
                )
                _have_set = (set(pd.to_datetime(_have['Date']).dt.date)
                             if not _have.empty else set())
                _df = _df[[d not in _have_set for d in _df.index]]
                if _df.empty:
                    continue
                for _col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    _df[_col] = _df[_col].astype(int)
                _df['Code'], _df['Name'] = _code, _nm
                _df.index.names = ['Date']
                new_frames.append(
                    _df[['Code', 'Name', 'Open', 'High', 'Low', 'Volume', 'Close']])
                done += 1
            except Exception as e:
                failed.append((_code, str(e)[:100]))
            if _i % 50 == 0:
                print(f'  진행 {_i}/{len(jobs)} (수집 {done})')
            _time.sleep(sleep_sec)

        if new_frames:
            _all = pd.concat(new_frames)
            _all.to_sql(name=table, con=engine, if_exists='append', chunksize=5000)
            print(f'입력 완료: {len(_all)}행 ({done}종목)')
        else:
            print('새로 받을 데이터가 없습니다.')
        if failed:
            print(f'실패 {len(failed)}건(상위): {failed[:10]}')
        return {'jobs': len(jobs), 'updated': done,
                'rows': sum(len(f) for f in new_frames), 'failed': failed}

    def update_index_incremental(self, end_date=None, start_if_empty='19950103', dry_run=False):
        """Append missing KOSPI/KOSDAQ index OHLCV rows through market's latest date."""
        if engine is None:
            raise ConnectionError('Configure STOCK_DB_PASSWORD before updating index tables.')
        if get_index_ohlcv_by_date is None:
            raise ImportError('Install pykrx to download index OHLCV data.')

        if end_date is None:
            latest_market = pd.read_sql_query(
                text('SELECT MAX(`Date`) AS max_date FROM `market`'), _require_engine()
            )
            if latest_market.empty or pd.isna(latest_market.iloc[0]['max_date']):
                raise RuntimeError('market 테이블에서 최신 거래일을 찾을 수 없습니다.')
            end_date = latest_market.iloc[0]['max_date']
        end_day = pd.Timestamp(end_date).date()
        start_default = pd.to_datetime(start_if_empty, format='%Y%m%d').date()

        results = {}
        for table, market_code in (('kospi', '1001'), ('kosdaq', '2001')):
            latest = pd.read_sql_query(
                text(f'SELECT MAX(`Date`) AS max_date FROM `{table}`'), _require_engine()
            )
            last_date = latest.iloc[0]['max_date'] if not latest.empty else None
            start_day = (pd.Timestamp(last_date).date() + dt.timedelta(days=1)) if pd.notna(last_date) else start_default
            if start_day > end_day:
                results[table] = {'rows': 0, 'status': 'already_current', 'last_date': str(last_date)}
                continue
            if dry_run:
                results[table] = {'rows': 0, 'status': 'preview', 'from': start_day.isoformat(), 'to': end_day.isoformat()}
                continue

            raw = get_index_ohlcv_by_date(
                start_day.strftime('%Y%m%d'), end_day.strftime('%Y%m%d'), market_code
            )
            if raw is None or raw.empty:
                results[table] = {'rows': 0, 'status': 'no_data'}
                continue
            frame = raw.copy()
            frame.columns = [str(column).strip() for column in frame.columns]
            frame = frame.rename(columns={
                '시가': 'Open', '고가': 'High', '저가': 'Low',
                '종가': 'Close', '거래량': 'Volume',
                'open': 'Open', 'high': 'High', 'low': 'Low',
                'close': 'Close', 'volume': 'Volume',
            })
            if 'Date' not in frame.columns:
                frame.index.name = 'Date'
                frame = frame.reset_index()
            required = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            missing = set(required) - set(frame.columns)
            if missing:
                raise ValueError(f'{table} index data missing columns: {sorted(missing)}')
            frame = frame[required].copy()
            frame['Date'] = pd.to_datetime(frame['Date'], errors='coerce').dt.date
            frame = frame.dropna(subset=required)
            if last_date is not None:
                frame = frame[frame['Date'] > pd.Timestamp(last_date).date()]
            frame = frame[frame['Date'] <= end_day].drop_duplicates(subset=['Date'])
            if frame.empty:
                results[table] = {'rows': 0, 'status': 'already_current'}
                continue

            # The stock DB schema has a Market column on both index tables.
            frame['Market'] = table
            with _require_engine().begin() as transaction:
                frame.to_sql(table, con=transaction, if_exists='append', index=False, chunksize=1000)
            results[table] = {
                'rows': int(len(frame)),
                'from': frame['Date'].min().isoformat(),
                'to': frame['Date'].max().isoformat(),
                'status': 'inserted',
            }
        return results

    def update_krx_daily_features(self, end_date=None, start_date=None, max_dates=1, sleep_sec=0.1):
        """Incrementally store per-ticker KRX market-cap/flow/short/foreign features.

        The first run stores the latest available trading date only. Pass
        ``start_date`` and a larger ``max_dates`` for controlled backfill.
        Optional KRX endpoints may be absent; those columns remain NULL.
        """
        import time as _time

        if stock is None:
            raise ImportError('Install pykrx to collect KRX daily features.')
        if max_dates < 1:
            raise ValueError('max_dates must be at least 1')
        eng = _require_engine()

        if end_date is None:
            market_max = pd.read_sql_query(
                text('SELECT MAX(`Date`) AS max_date FROM `market`'), eng
            )
            if market_max.empty or pd.isna(market_max.iloc[0]['max_date']):
                raise RuntimeError('market 테이블에서 최신 거래일을 찾을 수 없습니다.')
            end_day = pd.Timestamp(market_max.iloc[0]['max_date']).date()
        else:
            end_day = pd.Timestamp(end_date).date()

        feature_max = pd.read_sql_query(
            text('SELECT MAX(`trade_date`) AS max_date FROM `limitup_krx_daily_features`'), eng
        )
        last_feature_day = feature_max.iloc[0]['max_date'] if not feature_max.empty else None
        if start_date is not None:
            begin_day = pd.Timestamp(start_date).date()
        elif last_feature_day is None:
            begin_day = end_day  # Avoid an unrequested multi-decade download on first run.
        else:
            begin_day = pd.Timestamp(last_feature_day).date() + dt.timedelta(days=1)
        if begin_day > end_day:
            return {'dates': 0, 'rows': 0, 'status': 'already_current'}

        calendar = pd.read_sql_query(
            text('SELECT `Date` FROM `kospi` WHERE `Market`=:market '
                 'AND `Date`>=:start_date AND `Date`<=:end_date ORDER BY `Date`'),
            eng,
            params={'market': 'kospi', 'start_date': begin_day, 'end_date': end_day},
        )
        trading_dates = [pd.Timestamp(value).date() for value in calendar['Date'].tolist()]
        if not trading_dates and begin_day == end_day:
            trading_dates = [end_day]
        trading_dates = trading_dates[:max_dates]
        print(f'KRX feature dates queued: {len(trading_dates)} ({begin_day} ~ {end_day})')

        def norm_index(frame):
            copy = frame.copy()
            copy.index = pd.Index([str(value).strip().zfill(6) for value in copy.index], name='code')
            return copy

        def pick_column(frame, tokens):
            if frame is None or frame.empty:
                return None
            for column in frame.columns:
                label = str(column).strip().lower()
                if all(token.lower() in label for token in tokens):
                    return column
            return None

        def align_series(frame, column):
            if frame is None or column is None or frame.empty:
                return None
            result = frame[column].copy()
            result.index = pd.Index([str(value).strip().zfill(6) for value in result.index], name='code')
            return pd.to_numeric(result, errors='coerce')

        rows_written = 0
        date_results = []
        for trade_day in trading_dates:
            day_key = trade_day.strftime('%Y%m%d')
            daily_frames = []
            market_errors = []
            for market_name in ('KOSPI', 'KOSDAQ'):
                try:
                    cap = stock.get_market_cap_by_ticker(day_key, market=market_name)
                    if cap is None or cap.empty:
                        raise ValueError('market-cap endpoint returned no rows')
                    cap = norm_index(cap)
                    market_frame = pd.DataFrame(index=cap.index)
                    market_frame['market'] = market_name
                    market_frame['market_cap'] = align_series(cap, pick_column(cap, ('시가총액',)))
                    market_frame['trading_value'] = align_series(cap, pick_column(cap, ('거래대금',)))

                    # Optional enrichments: keep the row and leave fields NULL if an endpoint fails.
                    try:
                        short = stock.get_shorting_volume_by_ticker(day_key, market=market_name)
                        if isinstance(short, pd.Series):
                            short_frame = short.to_frame()
                            short_frame = norm_index(short_frame)
                            short_column = short_frame.columns[0]
                        else:
                            short_frame = norm_index(short)
                            short_column = pick_column(short_frame, ('거래량',)) or pick_column(short_frame, ('공매도',))
                        market_frame['short_volume'] = align_series(short_frame, short_column)
                    except Exception as exc:
                        logger.warning('%s short-volume fetch failed for %s: %s', market_name, day_key, exc)

                    try:
                        foreign = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(
                            day_key, market=market_name
                        )
                        foreign = norm_index(foreign)
                        foreign_column = pick_column(foreign, ('지분율',))
                        market_frame['foreign_ownership_pct'] = align_series(foreign, foreign_column)
                    except Exception as exc:
                        logger.warning('%s foreign-ownership fetch failed for %s: %s', market_name, day_key, exc)

                    flow_api = getattr(stock, 'get_market_net_purchases_of_equities_by_ticker', None)
                    if flow_api is None:
                        flow_api = getattr(stock, 'get_market_trading_value_and_volume_by_ticker', None)
                    for investor, output_column in (
                        ('외국인', 'foreign_net_volume'),
                        ('기관합계', 'institution_net_volume'),
                        ('개인', 'individual_net_volume'),
                    ):
                        try:
                            flow = flow_api(day_key, day_key, market_name, investor=investor) if flow_api else None
                            if flow is not None and not flow.empty:
                                flow = norm_index(flow)
                                flow_column = pick_column(flow, ('순매수', '거래량'))
                                market_frame[output_column] = align_series(flow, flow_column)
                        except Exception as exc:
                            logger.warning('%s %s flow fetch failed for %s: %s', market_name, investor, day_key, exc)

                    market_frame['trade_date'] = trade_day
                    market_frame['code'] = market_frame.index.astype(str)
                    market_frame['official_upper_limit_price'] = None
                    market_frame['source'] = 'pykrx'
                    columns = [
                        'trade_date', 'code', 'market', 'market_cap', 'trading_value',
                        'foreign_net_volume', 'institution_net_volume', 'individual_net_volume',
                        'short_volume', 'foreign_ownership_pct', 'official_upper_limit_price', 'source',
                    ]
                    for optional_column in columns:
                        if optional_column not in market_frame.columns:
                            market_frame[optional_column] = None
                    daily_frames.append(market_frame[columns].reset_index(drop=True))
                except Exception as exc:
                    market_errors.append((market_name, str(exc)[:180]))
                _time.sleep(sleep_sec)

            if market_errors:
                date_results.append({'date': trade_day.isoformat(), 'status': 'skipped', 'errors': market_errors})
                print(f'{day_key}: skipped because a required KRX market snapshot failed: {market_errors}')
                continue
            if not daily_frames:
                date_results.append({'date': trade_day.isoformat(), 'status': 'no_data', 'rows': 0})
                continue

            complete_day = pd.concat(daily_frames, ignore_index=True)
            with eng.begin() as transaction:
                transaction.execute(
                    text('DELETE FROM `limitup_krx_daily_features` WHERE `trade_date`=:trade_date'),
                    {'trade_date': trade_day},
                )
                complete_day.to_sql(
                    'limitup_krx_daily_features', con=transaction,
                    if_exists='append', index=False, chunksize=2000,
                )
            rows_written += len(complete_day)
            date_results.append({'date': trade_day.isoformat(), 'status': 'written', 'rows': len(complete_day)})
            print(f'{day_key}: wrote {len(complete_day):,} per-stock KRX feature rows')

        return {'dates': len(trading_dates), 'rows': rows_written, 'results': date_results}


class to_excel:
    investor_trend_url = 'http://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=20220601&sosok=&page='
    money_trend_url = 'http://finance.naver.com/sise/sise_deposit.nhn?&page='
    kpi200_url = 'https://finance.naver.com/sise/sise_index_day.nhn?code=KPI200&page='
    program_trend_url = 'https://finance.naver.com/sise/programDealTrendDay.nhn?bizdate=20221215&sosok=&page='    
    future_url = 'http://finance.daum.net/api/future/KR4101PC0002/days?pagination=true&page='
    kospi_sector_url = "http://finance.daum.net/api/quotes/sectors?fieldName=&order=&perPage=&market=KOSPI&page=&changes=UPPER_LIMIT%2CRISE%2CEVEN%2CFALL%2CLOWER_LIMIT"
    kosdaq_sector_url = "http://finance.daum.net/api/quotes/sectors?fieldName=&order=&perPage=&market=KOSDAQ&page=&changes=UPPER_LIMIT%2CRISE%2CEVEN%2CFALL%2CLOWER_LIMIT"

    
    def get_investor_trend(self):
        url  = self.investor_trend_url 

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'investor_trend.xlsx')
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'개인': [],'외국인': [],'기관': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['개인','외국인','기관']


        # count mask
        mask = [1,2,3]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date2','rate_down3','rate_up3']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        date_list.append(date_)
                        
                      
                    elif count in mask:
                        temp = int(count-1)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
        
                    count += 1
                if len(date_list) != len(dictionary['개인']):
                    print(str(i)+ '번째 페이지에서 누락된 값 발생')
                    print('누락된 데이터를 제거합니다')
                    
                    date_list.pop(-1)
                    dictionary['개인'].pop(-1)
                    dictionary['외국인'].pop(-1)
                    dictionary['기관'].pop(-1)
                
        # 개별 list 요소 갯수 파악 
        #print(len(date_list))
        #print(len(dictionary['개인']))
        #print(len(dictionary['외국인']))
        #print(len(dictionary['기관']))

        print(str(i) + '번째 페이지 크롤링 완료')
        df = pd.DataFrame(dictionary,index = date_list)
        df = df.sort_index()
        df = df[['개인','외국인','기관']]
        df.to_excel(path, encoding='utf-8')
        print(df)

    def get_investor_trend_date(self,until_date=str_yesterday,choice=1):
        url  = self.investor_trend_url
        
        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'investor_trend.xlsx')
        
        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or str_yesterday

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%y-%m-%d')
    
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 1", engine)
            kpi200_df = str(kpi200_df['Date'])
            until_date = kpi200_df[5:15]
            start = datetime.strptime(until_date, "%Y-%m-%d")
            until_date= (start + timedelta(days=1)).strftime('%y-%m-%d') ## datetime.timedelta 함수를 사용혀여 3.31 -> 4.1일로 일자변경
    
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'개인': [],'외국인': [],'기관': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['개인','외국인','기관']


        # count mask
        mask = [1,2,3]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date2','rate_down3','rate_up3']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        if date_ <=  until_date :
                            df = pd.DataFrame(dictionary,index = date_list)
                            df = df.sort_index()
                            df = df[['개인','외국인','기관']]
                            #df.to_excel(path, encoding='utf-8')
                            df.to_excel(path)
                            return df   
                        date_list.append(date_)
                        #print(date_list)
                    elif count in mask:
                        temp = int(count-1)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
                    
                    count += 1
    
    def get_money_trend(self):
    
        url = self.money_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'money_trend.xlsx')   
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'고객예탁금': [],'신용잔고': [],'주식형펀드': [],'혼합형펀드': [],'채권형펀드': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['고객예탁금','신용잔고','주식형펀드','혼합형펀드','채권형펀드']


        # count mask
        mask = [1,3,5,7,9]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','rate_down','rate_up']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        date_list.append(date_)
                        
                      
                    elif count in mask:
                        temp = int((count-1)/2)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
        
                    count += 1
                if len(dictionary['고객예탁금']) != len(dictionary['채권형펀드']):
                    print(str(i)+ '번째 페이지에서 누락된 값 발생')
                    print('누락된 데이터를 제거합니다')
                    
                    date_list.pop(-1)
                    dictionary['고객예탁금'].pop(-1)
                    dictionary['신용잔고'].pop(-1)
                    dictionary['주식형펀드'].pop(-1)
                    dictionary['혼합형펀드'].pop(-1)
                
        print(str(i) + '번째 페이지 크롤링 완료')
        df = pd.DataFrame(dictionary,index = date_list)
        df = df.sort_index()
        df.to_excel(path, encoding='utf-8')
        print(df)

    def get_money_trend_date(self,until_date=str_today,choice=1):
        
        url = self.money_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'money_trend.xlsx')

    
        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or str_today

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%y-%m-%d')
    
        else:
                moneytrend_df = pd.read_sql("select Date from moneytrend order by Date desc limit 1", engine)
                moneytrend_df = str(moneytrend_df['Date'])
                until_date = moneytrend_df[5:15]

                start = datetime.strptime(until_date, "%Y-%m-%d")
                until_date= (start + timedelta(days=1)).strftime('%y-%m-%d') ## datetime.timedelta 함수를 사용혀여 3.31 -> 4.1일로 일자변경
    
        #df = DataFrame(columns = ['고객예탁금', '신용잔고','주식형 펀드','혼합형 펀드','채권형 펀드'])

        # 날짜를 받을 리스트
        date_list = []

    
        # 값을 받을 사전
        dictionary = {'고객예탁금': [],'신용잔고': [],'주식형펀드': [],'혼합형펀드': [],'채권형펀드': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['고객예탁금','신용잔고','주식형펀드','혼합형펀드','채권형펀드']


        # count mask
        mask = [1,3,5,7,9]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','rate_down','rate_up']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        if date_ <=  until_date :
                        #if date_ <=  '19-03-05' :
                            df = pd.DataFrame(dictionary,index = date_list)
                            df = df.sort_index()
                            #df.to_excel(path, encoding='utf-8')
                            df.to_excel(path)
                            return df
                        date_list.append(date_)
                    
                    elif count in mask:
                        temp = int((count-1)/2)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
                
       
                    count += 1
            
            
    def get_kpi200(self):
        
        url = self.kpi200_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'kpi200.xlsx')
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'KPI200': [],'거래량': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['KPI200','거래량']


        # count mask
        mask = [1,3]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','number_1']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        date_list.append(date_)
                        
                      
                    elif count in mask:
                        temp = int(count/3)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
        
                    count += 1
                if len(date_list) != len(dictionary['KPI200']):
                    print(str(i)+ '번째 페이지에서 누락된 값 발생')
                    print('누락된 데이터를 제거합니다')
                    
                    date_list.pop(-1)
                    dictionary['KPI200'].pop(-1)
                    dictionary['거래량'].pop(-1)
                
        # 개별 list 요소 갯수 파악 
        #print(len(date_list))
        #print(len(dictionary['개인']))
        #print(len(dictionary['외국인']))
        #print(len(dictionary['기관']))

        print(str(i) + '번째 페이지 크롤링 완료')
        df = pd.DataFrame(dictionary,index = date_list)
        df = df.sort_index()
        df.to_excel(path, encoding='utf-8')
        print(df)
       

    def get_kpi200_date(self,until_date=str_yesterday,choice=1):
    
        url = self.kpi200_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'kpi200.xlsx')

        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or str_yesterday

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%Y-%m-%d')
    
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 1", engine)
            kpi200_df = str(kpi200_df['Date'])
            until_date = kpi200_df[5:15]

            start = datetime.strptime(until_date, "%Y-%m-%d")
            until_date= (start + timedelta(days=1)).strftime('%Y-%m-%d')
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'KPI200': [],'거래량': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['KPI200','거래량']


        # count mask
        mask = [1,3]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','number_1']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        if date_ <=  until_date :
                        #if date_ <=  '19-03-05' :
                            df = pd.DataFrame(dictionary,index = date_list)
                            df = df.sort_index()
                            #df.to_excel(path, encoding='utf-8')
                            df.to_excel(path)
                            return df   
                        date_list.append(date_)
                        #print(date_list)
                    elif count in mask:
                        temp = int(count/3)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
                        #print(dictionary[name_list[temp]])
                    count += 1
                    
                    
    def get_program_trend(self):
        url = self.program_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'program_trend.xlsx')
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'차익': [],'비차익': [],'전체': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['차익','비차익','전체']


        # count mask
        mask = [3,6,9]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','rate_down','rate_up','rate_noc']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        date_list.append(date_)
                        
                      
                    elif count in mask:
                        temp = int((count/3)-1)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
        
                    count += 1
                if len(date_list) != len(dictionary['전체']):
                    print(str(i)+ '번째 페이지에서 누락된 값 발생')
                    print('누락된 데이터를 제거합니다')
                    
                    date_list.pop(-1)
                    dictionary['차익'].pop(-1)
                    dictionary['비차익'].pop(-1)
                    #dictionary['전체'].pop(-1)
                
        # 개별 list 요소 갯수 파악 
        print(len(date_list))
        print(len(dictionary['차익']))
        print(len(dictionary['비차익']))
        print(len(dictionary['전체']))

        print(str(i) + '번째 페이지 크롤링 완료')
        df = pd.DataFrame(dictionary,index = date_list)
        df = df.sort_index()
        df = df[['차익','비차익','전체']]
        df.to_excel(path, encoding='utf-8')
        print(df)
            
    def get_program_trend_date(self,until_date=str_yesterday, choice=1):

        url = self.program_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = str(STOCKDATA_DIR.parent / 'program_trend.xlsx')

        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or str_yesterday

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%y-%m-%d')  ##  'yy-mm-dd' 
    
        else:
            programtrend_df = pd.read_sql("select Date from programtrend order by Date desc limit 1", engine)
            programtrend_df = str(programtrend_df['Date'])
            until_date = programtrend_df[5:15]

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%y-%m-%d')  ##  'yy-mm-dd' 
    
        # 날짜를 받을 리스트
        date_list = []

        # 값을 받을 사전
        dictionary = {'차익': [],'비차익': [],'전체': []}

        # dictionary key 인덱싱을 위한 리스트
        name_list = ['차익','비차익','전체']


        # count mask
        mask = [3,6,9]
    
        for i in range(1,last+1):
        
            source = urlopen(url+ str(i)).read()
            source = BeautifulSoup(source,'lxml')

            #tbody = source.find('div',{'id':'wrap'}).find('div',{'class':'box_type_m'})
            #trs = tbody.find_all('tr')

            body = source.find('body')
            trs = body.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td',{'class':['date','rate_down','rate_up','rate_noc']})
                count = 0
    
                for td in tds:
                    if count == 0:
                        date_ = td.text.strip().replace('.','-')
                        if date_ <=  until_date :
                            df = pd.DataFrame(dictionary,index = date_list)
                            df = df.sort_index()
                            df = df[['차익','비차익','전체']]
                            #df.to_excel(path, encoding='utf-8')
                            df.to_excel(path)
                            return df   
                        date_list.append(date_)
                        #print(date_list)
                    elif count in mask:
                        temp = int((count/3)-1)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
                    
                    count += 1
            
    def future(self, choice = 1):
        path = str(STOCKDATA_DIR.parent / 'future.xlsx')
        if choice ==1:
            # Fake Header 정보
            ua = UserAgent()

            # 헤더 선언
            headers = {
                'User-Agent': ua.ie,
                'referer': 'http://finance.daum.net/domestic/futures'
            }

            url = self.future_url +'1'
            #url = "http://finance.daum.net/api/future/KR4101PC0002/days?pagination=true&page=1"
            res = req.urlopen(req.Request(url, headers=headers)).read().decode('utf-8')

            df1 = pd.DataFrame()
            for i in range(1,7):
                # 다음 주식 요청 URL
                url = "http://finance.daum.net/api/future/KR4101Q30005/days?pagination=true&page="+str(i)

                res = req.urlopen(req.Request(url, headers=headers)).read().decode('utf-8')

                rank_json = json.loads(res)['data']

                df = pd.DataFrame(rank_json)
                df1 = pd.concat([df1, df], ignore_index=True)

            df2 = df1[['date','tradePrice','change', 'changePrice','changeRate','unsettledVolume','foreignSettlement', 'institutionSettlement', 'privateSettlement']]
            df2.columns=('Date','Future','change','가격변동','등락률','미결제약정','외국인','기관','개인')
            df2['Date'] = pd.to_datetime(df2['Date']).dt.date
            #df2['Date'] = pd.to_datetime(df2['Date']).apply(lambda x: x.date())
            #df2['Date'] = pd.to_datetime(df2['Date'], format = '%Y-%m-%d') # yyyy-mm-dd hh:mm:ss -> yyyy-mm-dd (속성은그대로 보여주는 형식만 변경)
            df2 =df2[['Date','Future','미결제약정','외국인','기관','개인']]
            #df2 = df2[df2.Date > until_date]
            df2.to_sql(name='future', con=engine, if_exists='append', index = False)
            df2 = df2.set_index('Date')
            df2.to_excel(path, encoding='utf-8')
            #df2
        else:
            future_df = pd.read_sql("select Date from future order by Date desc limit 1", engine)
            future_df = str(future_df['Date'])
            until_date = future_df[5:15]

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%Y-%m-%d')  ##  'yy-mm-dd' 
            until_date = datetime.strptime(until_date, '%Y-%m-%d').date() ## str 을  datetime.date로 type 변경

            # Fake Header 정보
            ua = UserAgent()

            # 헤더 선언
            headers = {
                'User-Agent': ua.ie,
                'referer': 'http://finance.daum.net/domestic/futures'
            }


            url = "http://finance.daum.net/api/future/KR4101Q30005/days?pagination=true&page=1"  #KR4011PC002 "선물 코스피 200지수 12월물" 코드는 구글검색이용
            res = req.urlopen(req.Request(url, headers=headers)).read().decode('utf-8')

            df1 = pd.DataFrame()
            for i in range(1,3):
                # 다음 주식 요청 URL
                url = "http://finance.daum.net/api/future/KR4101Q30005/days?pagination=true&page="+str(i)

                res = req.urlopen(req.Request(url, headers=headers)).read().decode('utf-8')

                rank_json = json.loads(res)['data']

                df = pd.DataFrame(rank_json)
                df1 = pd.concat([df1, df], ignore_index=True)
            df2 = df1[['date','tradePrice','change', 'changePrice','changeRate','unsettledVolume','foreignSettlement', 'institutionSettlement', 'privateSettlement']]
            df2.columns=('Date','Future','change','가격변동','등락률','미결제약정','외국인','기관','개인')
            df2['Date'] = pd.to_datetime(df2['Date']).dt.date
            #df2['Date'] = pd.to_datetime(df2['Date']).apply(lambda x: x.date())
            #df2['Date'] = pd.to_datetime(df2['Date'], format = '%Y-%m-%d') # yyyy-mm-dd hh:mm:ss -> yyyy-mm-dd (속성은그대로 보여주는 형식만 변경)
            df2 =df2[['Date','Future','미결제약정','외국인','기관','개인']]
            df2 = df2[df2.Date > until_date]
            df2.to_sql(name='future', con=engine, if_exists='append', index = False)
            df2 = df2.set_index('Date')
            df2.to_excel(path, encoding='utf-8')
            #df2            

    def sector(self):
        
        # Fake Header 정보
        ua = UserAgent()
        
        # 헤더 선언
        headers = {
            'User-Agent': ua['google chrome'],
            'referer': 'http://finance.daum.net/domestic/all_stocks'
        }        
        
        kospi_sector_url=self.kospi_sector_url
        kosdaq_sector_url=self.kosdaq_sector_url
        
        # 요청
        kospi_sector_res = req.urlopen(req.Request(kospi_sector_url, headers=headers)).read().decode('utf-8')
        try:
            kosdaq_sector_res = req.urlopen(req.Request(kosdaq_sector_url, headers=headers)).read().decode('utf-8')
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            print(f"Error content: {e.read().decode('utf-8')}")
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
        # 응답 데이터 확인(Json Data)
        # print('res', res)

        # 응답 데이터 str -> json 변환 및 data 값 저장
        kospi_sector = json.loads(kospi_sector_res)['data']
        kosdaq_sector = json.loads(kosdaq_sector_res)['data']
        # 중간 확인
        #print('중간 확인 : ', rank_json, '\n')

        #for elm in rank_json:
            # print(type(elm)) #Type 확인
            #print('순위 : {}, 금액 : {}, 회사명 : {}'.format(elm['rank'], elm['tradePrice'], elm['name']), )

        kospi_sector_df = pd.DataFrame(kospi_sector)
        kosdaq_sector_df = pd.DataFrame(kosdaq_sector)

        kospi_name=[]
        kosdaq_name=[]

        for i in range(len(kospi_sector_df.index)):
            stock_name = [kospi_sector_df['includedStocks'][i][0]['name'],kospi_sector_df['includedStocks'][i][1]['name']]
            kospi_name.append(stock_name)
        kospi_name_df=pd.DataFrame(kospi_name)

        kospi_sector_df = kospi_sector_df[['date','sectorName','change','changeRate']]
        kospi_sector_df['changeRate'] = kospi_sector_df['changeRate']*100

        kospi_sector_df = kospi_sector_df.sort_values(['change','changeRate'], ascending=[False,False])

        for i in range(len(kosdaq_sector_df.index)):
            stock_name = [kosdaq_sector_df['includedStocks'][i][0]['name'],kosdaq_sector_df['includedStocks'][i][1]['name']]
            kosdaq_name.append(stock_name)
        kosdaq_name_df=pd.DataFrame(kosdaq_name)

        kosdaq_sector_df = kosdaq_sector_df[['date','sectorName','change','changeRate']]
        kosdaq_sector_df['changeRate'] = kosdaq_sector_df['changeRate']*100


        kospi_sector_df = kospi_sector_df.join(kospi_name_df)
        kosdaq_sector_df = kosdaq_sector_df.join(kosdaq_name_df)

        kospi_sector_df.columns=('date', 'sectorName', 'change', 'changeRate', 'first', 'second')
        kosdaq_sector_df.columns=('date', 'sectorName', 'change', 'changeRate', 'first', 'second')

        kosdaq_sector_df = kosdaq_sector_df.sort_values(['change','changeRate'], ascending=[False,False])

        #display(kospi_sector_df.set_index('date')) 
        #display(kosdaq_sector_df.set_index('date')) 


        ##########  업종별시세 column중에 changeRate 'FALL' data를 일관되게 -수치로 바꾸는 code

        kospi = kospi_sector_df.set_index('change')  ##  index롤 분류하기위한 indeㅌing
        kosdaq = kosdaq_sector_df.set_index('change')  ##  index롤 분류하기위한 indeㅌing

        for i in [kospi,kosdaq]:
            cols = i.index.difference(['RISE'])      ## cols는 DateFrame이 아닌 change값이 FALL을 가리키는 객체
            b = i.loc[cols]
            b['changeRate']=i.loc[cols]['changeRate'].mul(-1)
            i.loc[cols]=b        ## a change 값이 FALL인 행을 chageRate값을 -로 바꾼 b로 치환   

        kospi_sector = kospi.set_index('date')
        kosdaq_sector = kosdaq.set_index('date')
        kospi_df =  kospi_sector.sort_values(["changeRate"],ascending=False)
        kosdaq_df =  kosdaq_sector.sort_values(["changeRate"],ascending=False)
        
        kospi_df.to_excel(str(STOCKDATA_DIR.parent / 'kospi_sector.xlsx'))
        kosdaq_df.to_excel(str(STOCKDATA_DIR.parent / 'kosdaq_sector.xlsx'))   
        #kospi_df.to_sql(name='kospi_sector', con=engine, if_exists='append')
        #kosdaq_df.to_sql(name='kosdaq_seotor', con=engine, if_exists='append')
        

    def kospi_kosdaq(self):
        
        kospi_df = pd.read_sql("select Date from kospi order by Date desc limit 1", engine)
        kospi_df = str(kospi_df['Date'])
        kospi_date = kospi_df[5:15]

        kosdaq_df = pd.read_sql("select Date from kosdaq order by Date desc limit 1", engine)
        kosdaq_df = str(kosdaq_df['Date'])
        kosdaq_date = kosdaq_df[5:15]


        start_kospi = datetime.strptime(kospi_date , "%Y-%m-%d")
        kospi_date= (start_kospi + timedelta(days=1)).strftime('%Y%m%d')

        start_kosdaq = datetime.strptime(kosdaq_date , "%Y-%m-%d")
        kosdaq_date= (start_kosdaq + timedelta(days=1)).strftime('%Y%m%d')


        df_kospi = get_index_ohlcv_by_date(kospi_date, "20250228", "코스피")
        df_kospi.index.names = ['Date']
        df_kospi.columns  = ('Open','High','Low','Close','Volume')
        df_kospi['Market']='kospi'
        #df_kospi.to_sql(name='kospi', con=engine, if_exists='append')
        df_kospi.to_excel(str(STOCKDATA_DIR.parent / 'kospi.xlsx'))

        df_kosdaq = get_index_ohlcv_by_date(kosdaq_date, "20250228", "코스닥")
        df_kosdaq.index.names = ['Date']
        df_kosdaq.columns  = ('Open','High','Low','Close','Volume')
        df_kosdaq['Market']='kosdaq'
        #df_kosdaq.to_sql(name='kosdaq', con=engine, if_exists='append')
        df_kosdaq.to_excel(str(STOCKDATA_DIR.parent / 'kosdaq.xlsx'))
   
            
if __name__ == "__main__":
    print("This is Module")


# --- Safer public API overrides (these preserve the legacy function names). ---
_MARKET_TABLES = {'kospi', 'kosdaq'}


def _normalize_date(value):
    if value is None:
        return None
    return pd.Timestamp(value).date().isoformat()


def select_market_at(name, at_date):
    table = str(name).lower()
    if table not in _MARKET_TABLES:
        raise ValueError("name must be 'kospi' or 'kosdaq'")
    query = text(f"SELECT * FROM `{table}` WHERE `Date`=:at_date ORDER BY `Date`")
    return pd.read_sql_query(query, _require_engine(), params={'at_date': _normalize_date(at_date)})


def select_market_period(name, from_date, to_date=None):
    table = str(name).lower()
    if table not in _MARKET_TABLES:
        raise ValueError("name must be 'kospi' or 'kosdaq'")
    start = _normalize_date(from_date)
    end = _normalize_date(to_date)
    if end and end < start:
        raise ValueError('to_date must be on or after from_date')
    query = f"SELECT * FROM `{table}` WHERE `Date` >= :from_date"
    params = {'from_date': start}
    if end:
        query += " AND `Date` <= :to_date"
        params['to_date'] = end
    query += " ORDER BY `Date`"
    return pd.read_sql_query(text(query), _require_engine(), params=params)


def select_market(name, from_date, to_date=str_today):
    return select_market_period(name, from_date, to_date)


def select_stock(name, from_date, to_date=str_today):
    start = _normalize_date(from_date)
    end = _normalize_date(to_date)
    if end and end < start:
        raise ValueError('to_date must be on or after from_date')
    query = "SELECT * FROM `market` WHERE `Date` >= :from_date"
    params = {'from_date': start}
    if str(name).lower() != 'all':
        query += " AND `Name` = :name"
        params['name'] = str(name)
    if end:
        query += " AND `Date` <= :to_date"
        params['to_date'] = end
    query += " ORDER BY `Date`"
    return pd.read_sql_query(text(query), _require_engine(), params=params)


def aggregate_data(df, freq):
    columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    data = df.copy()
    data.columns = [str(column).strip().title() for column in data.columns]
    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(f'Missing OHLCV columns: {sorted(missing)}')
    data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
    data = data.dropna(subset=['Date']).sort_values('Date').set_index('Date')
    if freq in ('M', 'ME', 'month'):
        freq = 'ME'
    elif freq in ('W', 'week'):
        freq = 'W-FRI'
    result = data.resample(freq).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last',
        'Volume': lambda values: values.sum(min_count=1),
    }).dropna(subset=['Open', 'High', 'Low', 'Close'])
    return result.reset_index()[columns]


def day_week_month_data(market='kospi', from_day='2020-01-01', to_day=str_today, period='month'):
    market_name = str(market).lower()
    if market_name in _MARKET_TABLES:
        frame = select_market_period(market_name, from_day, to_day)
    else:
        frame = select_stock(market_name, from_day, to_day)
    period = str(period).lower()
    if period == 'day':
        return frame[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
    if period == 'month':
        return aggregate_data(frame, 'ME')
    if period == 'week':
        return aggregate_data(frame, 'W-FRI')
    raise ValueError("period must be 'day', 'week', or 'month'")


def ma(dataframe):
    """Return a copy with simple moving-average columns for available prices."""
    if dataframe is None:
        raise TypeError('dataframe cannot be None')
    frame = dataframe.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if 'close' not in frame:
        raise ValueError("dataframe must contain a 'Close' column")
    frame['close'] = pd.to_numeric(frame['close'], errors='coerce')
    if 'volume' in frame:
        frame['volume'] = pd.to_numeric(frame['volume'], errors='coerce')
    for window in (5, 10, 15, 20, 30, 60, 120):
        column = f'ma{window}'
        frame[column] = frame['close'].rolling(window=window, min_periods=window).mean()
    return frame


def _scale_columns(frame, columns):
    values = frame[columns].apply(pd.to_numeric, errors='coerce')
    spans = values.max() - values.min()
    spans = spans.where(spans != 0, 1.0)
    return (values - values.min()) / spans


def min_max(df, select='low'):
    frame = ma(df)
    column = str(select).lower()
    required = ['close', column, 'volume']
    if not set(required).issubset(frame.columns):
        raise ValueError(f'Required columns are missing: {required}')
    result = _scale_columns(frame, required)
    if 'date' in frame:
        result.index = pd.to_datetime(frame['date'], errors='coerce')
    return result


def close_ma(df, select1='ma60', select2='ma120'):
    frame = ma(df)
    columns = ['close', str(select1).lower(), str(select2).lower()]
    plot_data = _scale_columns(frame, columns)
    if 'date' in frame:
        plot_data.index = pd.to_datetime(frame['date'], errors='coerce')
    _require_plotting()
    ax = plot_data.plot(figsize=(16, 4))
    if 'name' in frame and not frame.empty:
        ax.set_title(str(frame['name'].iloc[0]))
    ax.grid(True)
    plt.show()


def close_ma_vol(df, select1='ma60', select2='ma120', select3='volume'):
    frame = ma(df)
    columns = ['close', str(select1).lower(), str(select2).lower(), str(select3).lower()]
    plot_data = _scale_columns(frame, columns)
    if 'date' in frame:
        plot_data.index = pd.to_datetime(frame['date'], errors='coerce')
    _require_plotting()
    ax = plot_data.plot(figsize=(16, 4))
    if 'name' in frame and not frame.empty:
        ax.set_title(str(frame['name'].iloc[0]))
    ax.grid(True)
    plt.show()


def market_ma(df, select1='ma60', select2='ma120'):
    return close_ma(df, select1, select2)


def market_ma_vol(df, select1='ma60', select2='ma120', select3='volume'):
    return close_ma_vol(df, select1, select2, select3)


_PLOT_CONFIGURED = False


def _require_plotting():
    global _PLOT_CONFIGURED
    if plt is None:
        raise ImportError('Install matplotlib to use chart functions.')
    if not _PLOT_CONFIGURED:
        plt.rcParams.update({'figure.max_open_warning': 0, 'axes.unicode_minus': False})
        font_file = Path(os.getenv('STOCK_FONT_PATH', r'C:\Windows\Fonts\malgun.ttf'))
        if font_file.exists() and font_manager is not None:
            rc('font', family=font_manager.FontProperties(fname=str(font_file)).get_name())
        _PLOT_CONFIGURED = True


def compare_graph_with_name(names, from_date='2020-01-01', to_date=str_today, subject='Close'):
    names = [names] if isinstance(names, str) else list(names)
    series = []
    for symbol in names:
        frame = select_stock(str(symbol), from_date, to_date)
        if frame.empty:
            logger.info('No rows for %s in requested date range', symbol)
            continue
        column = next((c for c in frame.columns if str(c).lower() == str(subject).lower()), None)
        if column is None:
            raise ValueError(f"No '{subject}' column for {symbol}")
        part = frame[['Date', column]].copy()
        part['Date'] = pd.to_datetime(part['Date'])
        part = part.drop_duplicates('Date').set_index('Date')[column].rename(str(symbol))
        series.append(part)
    if not series:
        return pd.DataFrame()
    combined = pd.concat(series, axis=1).sort_index()
    base = combined.apply(lambda col: col.dropna().iloc[0] if col.notna().any() else np.nan)
    normalized = combined.divide(base, axis=1).mul(100)
    _require_plotting()
    ax = normalized.plot(figsize=(16, 5), grid=True)
    ax.set_ylabel('Indexed to first available value (100)')
    plt.show()
    return normalized


def _refresh_bad_stock_table():
    if BeautifulSoup is None:
        raise ImportError('Install beautifulsoup4 to scrape the KRX management list.')
    response = requests.get('https://finance.naver.com/sise/management.nhn', timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    names = [a.get_text(strip=True) for a in soup.select('a.tltle') if a.get_text(strip=True)]
    frame = pd.DataFrame({'Date': [str_today] * len(names), 'Name': names})
    if frame.empty:
        logger.warning('No management-list names parsed; keeping existing table unchanged.')
        return frame
    output_dir = STOCKDATA_DIR / '관리종목'
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_excel(output_dir / f'{str_today}.xlsx', index=False)
    eng = _require_engine()
    with eng.begin() as transaction:
        transaction.execute(text('DELETE FROM `badstock`'))
    frame.to_sql('badstock', con=eng, if_exists='append', index=False)
    return frame


def _delete_duplication_access(oname):
    if pyodbc is None:
        raise ImportError('Install pyodbc to use Access cleanup.')
    access_path = os.getenv('OFFICE_DB_PATH')
    access_password = os.getenv('OFFICE_DB_PASSWORD', '')
    if not access_path:
        raise RuntimeError('Set OFFICE_DB_PATH (and optionally OFFICE_DB_PASSWORD) first.')
    connection_string = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        f'DBQ={access_path};PWD={access_password}'
    )
    connection = pyodbc.connect(connection_string)
    cursor = connection.cursor()
    deleted = 0
    try:
        duplicates = cursor.execute(
            'SELECT p_num FROM buysell_products WHERE o_num=? AND keyindex=? '
            'GROUP BY p_num HAVING COUNT(*)>1', (oname, 89999),
        ).fetchall()
        for row in duplicates:
            product_num = row[0]
            latest_all = cursor.execute(
                'SELECT TOP 1 bsdate FROM buysell_products '
                'WHERE o_num=? AND p_num=? ORDER BY bsdate DESC',
                (oname, product_num),
            ).fetchone()
            latest_special = cursor.execute(
                'SELECT TOP 1 bsdate FROM buysell_products '
                'WHERE o_num=? AND keyindex=? AND p_num=? ORDER BY bsdate DESC',
                (oname, 89999, product_num),
            ).fetchone()
            if not latest_special:
                continue
            if latest_all and latest_all[0] > latest_special[0]:
                cursor.execute(
                    'DELETE FROM buysell_products WHERE o_num=? AND keyindex=? AND p_num=?',
                    (oname, 89999, product_num),
                )
            else:
                cursor.execute(
                    'DELETE FROM buysell_products WHERE o_num=? AND keyindex=? AND p_num=? AND bsdate<?',
                    (oname, 89999, product_num, latest_special[0]),
                )
                latest_num = cursor.execute(
                    'SELECT TOP 1 num FROM buysell_products '
                    'WHERE o_num=? AND keyindex=? AND p_num=? ORDER BY num DESC',
                    (oname, 89999, product_num),
                ).fetchone()
                if latest_num:
                    cursor.execute(
                        'DELETE FROM buysell_products WHERE o_num=? AND keyindex=? AND p_num=? AND num<?',
                        (oname, 89999, product_num, latest_num[0]),
                    )
            deleted += max(cursor.rowcount, 0)
        connection.commit()
        return {'products_checked': len(duplicates), 'rows_deleted': deleted}
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
