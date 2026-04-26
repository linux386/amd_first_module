# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import json
import time
import re
#import plaidml.keras
import plotly.offline as offline
import plotly.graph_objs as go
import os,glob,shutil,io,sys
import pykrx as pykrx
from pykrx.stock.api import *
from fake_useragent import UserAgent
ua = UserAgent(browsers=['edge', 'chrome'])
ua.random
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import datetime as dt
from keras.models import Sequential
from keras.layers import Dense, Activation, Dropout,LSTM
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime,timedelta
from urllib.request import urlopen
import urllib.request as req
import sqlalchemy 
import pymysql
from matplotlib import font_manager, rc
from matplotlib import pyplot as plt
plt.rcParams.update({'figure.max_open_warning': 0})
plt.rcParams['axes.unicode_minus'] = False
plt.rc('axes', unicode_minus=False)
font_name = font_manager.FontProperties(fname="c:/Windows/Fonts/malgun.ttf").get_name()
rc('font', family=font_name)
import mplfinance as mpf
import talib.abstract as ta
from talib import RSI, BBANDS

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning) 
#from pandas.core.common import SettingWithCopyWarning
#warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

today =datetime.now()
str_yesterday = (today-timedelta(1)).strftime('%Y-%m-%d')
str_today = today.strftime('%Y-%m-%d')
#date_list = ['2008-01-01','2013-01-01','2018-01-01','2019-01-01']
three_period=['day','week','month']

# MySQL connection configuration
host = "localhost"
port = 3306
user = "root"
password = "leaf2027"
database = "stock"

# Connect to MySQL
connection = pymysql.connect(host=host, port=port, user=user, password=password, database=database)

#now = dt.datetime.today().strftime('%Y-%m-%d')
engine = sqlalchemy.create_engine('mysql+pymysql://root:leaf2027@localhost/stock?charset=utf8',encoding='utf-8')
conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
curs = conn.cursor()

stock_last_day = pd.read_sql("select Date from market where Name='삼성전자' order by Date desc limit 1",engine)
stock_last_day['Date'] = pd.to_datetime(stock_last_day['Date']).dt.strftime('%Y-%m-%d')
stock_last_day = stock_last_day['Date'].to_list()[0]
stock_last_day

path_test = 'C:/Users/linux/OneDrive/stockdata/test_data/'
path_down = 'C:/Users/linux/OneDrive/stockdata/period_down/'
path_depress = 'C:/Users/linux/OneDrive/stockdata/depress/'
path_depress_d = 'C:/Users/linux/OneDrive/stockdata/depress/depress_day_'
path_depress_w = 'C:/Users/linux/OneDrive/stockdata/depress/depress_week_'
path_depress_m = 'C:/Users/linux/OneDrive/stockdata/depress/depress_month_'
path_vote_stock = 'C:/Users/linux/OneDrive/stockdata/vote_stock/'
path_price = 'C:/Users/linux/OneDrive/stockdata/vote_stock/detect_stock_with_price_'
path_volume = 'C:/Users/linux/OneDrive/stockdata/vote_stock/detect_stock_with_volume_'
path_close_2008 = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_close_2008-01-01_'
path_close_2019 = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_close_2019-01-01_'
path_ma_2008 = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_ma_2008-01-01_'
path_ma_2019 = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_ma_2019-01-01_'
path_ma = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_ma_'
path_close = 'C:/Users/linux/OneDrive/stockdata/close_ma120/total_close_'
path_close_ma120 = 'C:/Users/linux/OneDrive/stockdata/close_ma120/'

kospi_final_day_df = pd.read_sql("select Date from kospi order by Date desc limit 1", engine)
final_day = kospi_final_day_df
kospi_final_day_df = pd.to_datetime(kospi_final_day_df['Date'])
kospi_next_df = kospi_final_day_df + timedelta(1) ##  최종날짜 다음날짜
kospi_next_df = str(kospi_next_df)
kospi_next_df = kospi_next_df[4:14]                ## 2020-07-13
kospi_next_day_no_hypyen = kospi_next_df.replace('-','')   ## 20200713

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

def kospi_kosdaq(lastday='20251231', market='1001'):
    if market == '1001':
        df = get_index_ohlcv_by_date(kospi_next_day_no_hypyen, lastday, market)
        df.index.names = ['Date']
        df = df.iloc[:,[0,1,2,3,4]]
        df.columns  = ['Open','High','Low','Close','Volume']
        df['Market']='kospi'
        df.to_sql(name='kospi', con=engine, if_exists='append')
    elif market == '2001':
        df = get_index_ohlcv_by_date(kospi_next_day_no_hypyen, lastday, market)
        df.index.names = ['Date']
        df = df.iloc[:,[0,1,2,3,4]]
        df.columns  = ['Open','High','Low','Close','Volume']        
        df['Market']='kosdaq'
        df.to_sql(name='kosdaq', con=engine, if_exists='append')
    #kospi_kosdaq( market='코스피')

def compare_graph_with_name(name):
    select_query = "select Date,Close,Volume from market where Name= "
    date_query =  "Date >"
    df_Close = pd.DataFrame()
    df_Volume = pd.DataFrame()
    dfc = pd.DataFrame()
    dfv = pd.DataFrame()
    #name=['엘아이에스']
    date = '2020-01-01'

    for x in name:
        var = select_query +"'"+x+"'"+" "+"&&"+" "+date_query+"'"+date+"'"
        df = pd.read_sql(var ,engine)
        df_Close = df[['Date', 'Close']]
        df_Close.columns=['Date',x]
        df_Close = df_Close.set_index('Date')
        dfc = pd.concat([dfc,df_Close], axis=1)
        df_Volume = df[['Date', 'Volume']]
        df_Volume.columns=['Date',x]
        df_Volume = df_Volume.set_index('Date')
        dfv = pd.concat([dfv,df_Volume], axis=1)

    plt.figure(figsize=(16,5))

    for i in range(len(name)):
        plt.plot(dfc[name[i]]/dfc[name[i]].loc[df['Date'][0]]*100)
        #plt.plot(dfv[name[i]]/dfv[name[i]].loc[df['Date'][0]]*100)        
    plt.legend(name,loc=0)
    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
    plt.figure(figsize=(16,5))
    for i in range(len(name)):
        #plt.plot(dfc[name[i]]/dfc[name[i]].loc[df['Date'][0]]*100)
        plt.plot(dfv[name[i]]/dfv[name[i]].loc[df['Date'][0]]*100)        
    plt.legend(name,loc=0)
    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
    
def aggregate_data(df, freq):
    df['Date'] = pd.to_datetime(df['Date'])
    grouped = df.groupby(pd.Grouper(key='Date', freq=freq))

    aggregated_data = []
    for _, group in grouped:
        if not group.empty:
            aggregated_data.append([
                group.iloc[-1]['Date'],
                group.iloc[0]['Open'],
                max(group['High']),
                min(group['Low']),
                group.iloc[-1]['Close'],
                sum(group['Volume'])
            ])

    return pd.DataFrame(aggregated_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])

def day_week_month_data(market='kospi', from_day='2020-01-01', to_day='2024-01-01', period='month'):
    if market in ['kospi', 'kosdaq']:
        df = select_market_period(market, from_day, to_day)  # 함수 구현 필요
    else:
        df = select_stock(market, from_day, to_day)  # 함수 구현 필요

    if period == 'day':
        return df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    elif period == 'month':
        return aggregate_data(df, 'M')
    elif period == 'week':
        return aggregate_data(df, 'W')

def depress(period='day', to_day=str_today):
    
    ''' depress(period) : period = ['day', 'week', 'month'] '''
    
    path_depress = 'C:/Users/linux/OneDrive/stockdata/depress/depress_'
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
    
def candle_graph( market='kospi', from_day = '2020-01-01',period ='week' ):
    df = day_week_month_data(market, from_day ,period )

    df = df[['Date','Open','High','Low','Close']]
    
    offline.init_notebook_mode(connected = True)

    trace = go.Candlestick(x=df.Date, open=df.Open, high=df.High, low=df.Low, close = df.Close,increasing_line_color= 'red', decreasing_line_color= 'blue')
    data =[trace]

    layout=go.Layout(title=market)
    fig = go.Figure(data=data, layout=layout)
    offline.iplot(fig,filename='candlestick')
    
def bokeh_chart(market='kospi',from_day = '2019-01-01', period ='month'):
    from math import pi
    from bokeh.io import output_notebook, show
    from bokeh.plotting import figure
    from bokeh.layouts import gridplot

    output_notebook()
    
    df = day_week_month_data(market, from_day, period)
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
    
    engine.execute("TRUNCATE TABLE badstock")
    
    url = 'https://finance.naver.com/sise/management.nhn'
    source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
    source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
    data = []

    path = 'd:\\stockdata\\관리종목\\'+str_today+'.xlsx'
    body = source.find('body')
    trs = body.find_all('tr')
    name = []
    for tr in trs:
        tds = tr.find_all('a',{'class':"tltle"})
        for td in tds:
            name.append(td.text.strip())

    df = pd.DataFrame(name)
    df['Date']=str(str_today)
    df = df.set_index('Date')
    df.columns=['Name']
    df.to_excel(path)
    df = pd.read_excel(path)
    df.to_sql(name='badstock', con=engine, if_exists='append', index = False)
    return df
    
def from_excel_analysis(path,file_day,from_date):
    df = pd.read_excel(path+file_day+'.xlsx')
    df.columns = map(str.lower, df.columns) ## columns 명을 소문자로 
    df = df['name']

    name=df.to_list()
    for i in name:
        df=select_stock(i,from_date,)
        close_ma_vol(df, 'ma60')
        
def last_page(source):
    last = source.find('td',class_='pgRR').find('a')['href']
    last = last.split('page')[1]
    last = last.split('=')[1]
    last = int(last)
    print(last)
    return last

def select_market_at(name,at_date):   ###  name='kospi' or 'kosdaq'
    select_query = "select * from "
    date_query = " where Date = "    
    var = select_query + name + date_query+"'"+at_date+"'" 
    df = pd.read_sql(var, engine)
    return df

def select_market_period(name,from_date):   ###  name='kospi' or 'kosdaq'
    select_query = "select * from "
    date_query = " where Date >= "    
    var = select_query + name + date_query+"'"+from_date+"'" 
    df = pd.read_sql(var, engine)
    return df

def select_stock(name, from_date, to_date=str_today):
    ''' name : 'all'(모든주식),  'hrs'(주식이름이 'hrs'),  from_date : 시작날짜,  to_date : 마지막날짜) '''
    if name == 'all':
        select_query = "select * from market where Date >=  "

    else:
        select_query = "select * from market where Name="+"'"+name +"'"+' '+"and  Date >=  "
        
    var = select_query +"'"+from_date+"'"  +" "+ 'and Date <=' + "'"+to_date+"'"
    df = pd.read_sql(var, engine)
    return df


def make_name_list(path_name=path_depress, arg = "*day*.*" , num=0, degree=30):
    '''make_name_list(path_vote_stock, arg = '*price*.*', num=3, degree=30)'''
    
    files = glob.glob(os.path.join(path_name , arg))

    try:
        aa = re.findall('\d+',files[num])
        bb=[aa[0]+'-'+aa[1]+'-'+aa[2] ]
    except:
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

def min_max(df,select):  ## select : Open, High, Low 중 선택
    df.columns=df.columns.str.lower()
    ma(df)
    source = MinMaxScaler()
    data = source.fit_transform(df[['close',select,'volume']].values)
    df1 = pd.DataFrame(data)
    df1.columns=['close',select,'volume']
    df1 = df1.set_index(df['date'])
    return df1

def ma(DataFrame):
    try:
        df = DataFrame
        df.columns=df.columns.str.lower()
        df[['volume','close']] = df[['volume','close']].astype(float) #  TA-Lib로 평균을 구하려면 실수로 만들어야 함

        talib_ma5 = ta.MA(df, timeperiod=5)
        df['ma5'] = talib_ma5

        talib_ma10 = ta.MA(df, timeperiod=10)
        df['ma10'] = talib_ma10    

        talib_ma15 = ta.MA(df, timeperiod=15)
        df['ma15'] = talib_ma15

        talib_ma20 = ta.MA(df, timeperiod=20)
        df['ma20'] = talib_ma20

        talib_ma30 = ta.MA(df, timeperiod=30)
        df['ma30'] = talib_ma30    

        talib_ma60 = ta.MA(df, timeperiod=60)
        df['ma60'] = talib_ma60    

        talib_ma120 = ta.MA(df, timeperiod=120)
        df['ma120'] = talib_ma120
    except:
        pass
    return df

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
    
def close_ma(df,select1='ma60',select2='ma120'):  ##  select1, select2 : ma5, ma10, ma15, ma20, ma30, ma60, ma120 중에 선택
    try:
        ma(df)

        source = MinMaxScaler()
        data = source.fit_transform(df[['close',select1,select2]].values)
        df1 = pd.DataFrame(data)
        df1.columns=['close',select1,select2]
        df1 = df1.set_index(df['date'])
        df1.plot(figsize=(16,4))
        plt.title(df['name'][0])
        plt.grid(True)
        plt.show()
    except:
        pass

def close_ma_vol(df,select1='ma60',select2='ma120',select3='volume'):
    try:
        ma(df)

        source = MinMaxScaler()
        data = source.fit_transform(df[['close',select1,select2,select3]].values)
        df1 = pd.DataFrame(data)
        df1.columns=['close',select1,select2,select3]
        df1 = df1.set_index(df['date'])
        df1.plot(figsize=(16,4))
        plt.title(df['name'][0])
        plt.grid(True)
        plt.show()
    except:
        pass

def market_ma(df,select1,select2):
    ma(df)

    source = MinMaxScaler()
    data = source.fit_transform(df[['close',select1,select2]].values)
    df1 = pd.DataFrame(data)
    df1.columns=['close',select1,select2]
    df1 = df1.set_index(df['date'])
    df1.plot(figsize=(16,4))
    plt.title(df['market'][0])
    plt.grid(True)
    plt.show()

def market_ma_vol(df,select1,select2,select3):
    ma(df)

    source = MinMaxScaler()
    data = source.fit_transform(df[['close',select1,select2,select3]].values)
    df1 = pd.DataFrame(data)
    df1.columns=['close',select1,select2,select3]
    df1 = df1.set_index(df['date'])
    df1.plot(figsize=(16,4))
    plt.title(df['market'][0])
    plt.grid(True)
    plt.show()        

    
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

def select_graph(path_name, day, from_day='2019-01-01', count=30, method=close_ma_vol, fix=1):
    #choice_date = day
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

    df_date = pd.read_sql("select Date from market where Name='hrs' order by Date desc limit 1",engine)
    df_date = pd.to_datetime(df_date['Date'])
    #df = df + timedelta(1)          ##  최종날짜 다음날짜
    df_date = str(df_date)
    standard = df_date[4:14]                ## 2020-07-13

    #query = "select Name, min(Close) from market where Name = '동방' and Date > '2020-12-01' and Date < '2020-12-31' group by Name"
    query1 = "select Name, min(Close) from market where Date >" 
    query2 = "and Date <=" 
    query = query1 +"'"+ from_day +"'"+ query2 +"'"+ to_day +"'"+ " group by Name"
    
    df = pd.read_sql(query, engine)

    df1 = select_stock('all', standard, )
    df1_last = df1[['Name','Close']]

    df2 = pd.merge(df, df1_last, on="Name")
    df2['diff']=df2['Close']/df2['min(Close)']
    df2 = df2.sort_values(by=['diff'], ascending=True)
    df2 = df2.reset_index(drop=True)
    #display(df2)
    df2.to_excel(path_down+standard+'.xlsx')       

class analysis:

    df = select_stock('all', '2020-08-03', '2020-08-03')
    df = df['Name']
    name = df.to_list()

    select_start_a = '2019-01-01'
    select_start_b = '2008-01-01'
    
    #someday=date(2021,3,18)
    #from_day = (someday - timedelta(days=365)).strftime('%Y-%m-%d')
    from_day = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    from_day=str(from_day)
    select_query = "select * from market where Name='hrs' and Date >="
    df3 = pd.read_sql(select_query+" " +"'"+from_day+"'" , engine)

    df3 = df3['Date']
    df3 = df3.iloc[:250]
    datelist = df3.to_list()

    def search_stock_long_period_graph(self, path, select_day,select_start=select_start_a , to_day='2021-12-31'):  
        ## default 가 정해진 select_start, to_day 인수가 뒤로간다.
        select_start_a = self.select_start_a
        select_start_b = self.select_start_b        
        df = pd.read_excel(path+select_start+'_'+select_day+'.xlsx')
        df = df['name']
        name = df.to_list()

        for i in name:
            df = select_stock(i,from_date,to_date)
            close_ma_vol(df) 

    def search_stock_long_period(self,name,select_start):
        start=time.time()
        #print(start)
        print(select_start)
        
        self.name = name
        select_start_a = self.select_start_a
        select_start_b = self.select_start_b
        datelist = self.datelist
        
        df2 = pd.DataFrame() 
        for i in name:
            
            df=select_stock(i,from_day, to_day)  ## 종목별 dataframe
            ma(df)

            source = MinMaxScaler()
            data = source.fit_transform(df[['close','ma60','ma120','volume']].values)
            df1 = pd.DataFrame(data)
            df1['name']=i
            df1.columns=['close','ma60','ma120','volume','name']
            df1[['date','code']] = df[['date','code']]
                #print(df1)
            df2 = df2.append(df1)   ## 전종목 close, ma60, ma120, volume 표준화 (MinMaxScaler())

        for i in datelist:
                last_df = df2.loc[df2['date'] == i]  ##  가장최근일자 전종목  (표준화후)  
                last_df = last_df.reset_index(drop=True)

                last_close_df = last_df[last_df['close'] < 0.1]   ##  가장최근종가가 최저가 인경우  (표준화 후)
                last_close_df =  last_close_df.sort_values(["close"],ascending=True)

                mask1 = (last_df.ma120 < 0.1) & (last_df.close >last_df.ma60) & (last_df.ma60 > last_df.ma120) ##  boolen 필터링
                last_ma_df = last_df.loc[mask1, :]   ## 가장최근 120일선이 0.1이하인 경우 & 종가 > ma60 > ma120  (표준화 후)
                last_ma_df =  last_ma_df.sort_values(["ma120"],ascending=True)

                strdate = i.strftime('%Y-%m-%d')

                last_ma_df.to_excel(path_ma+select_start+"_"+strdate+'.xlsx')  ##  표준화 dataframe 중 ma120 < 0.1 and close > ma60 > ma120 (from 2019.01.01)
                last_close_df.to_excel(path_close+select_start+"_"+strdate+'.xlsx')  ##  표준화 dataframe 중 close < 0.1 

        final_day= pd.read_sql("select Date from kospi order by Date desc limit 1", engine)
        final_day = str(final_day['Date'])
        until_date = final_day[10:15]
        until_date = until_date.replace('-','')
        print(path_close_ma120+'2021/'+'2021_06/'+until_date+'/')

        try:
            os.mkdir(path_close_ma120+'2021/'+'2021_06/'+until_date)
        except:
            pass
        for filename in glob.glob(os.path.join(path_close_ma120 , '*.*')):
            shutil.copy(filename, path_close_ma120+'2021/'+'2021_06/'+until_date+'/')
        print('time:', time.time()-start)

            
class to_report:
    select_query = "select * from market where Date >="
    volume_query = "&& Volume >  10000"
    def stock_select_with_Volume_Close(self,choice = 1):
    
        if choice == 1:
            yesterday = input("어제날짜를 입력하세요 : sample: '2019-02-07'  ") or str_yesterday
            today = input("오늘날짜를 입력하세요 : sample: '2019-02-07'  ") or str_today
        
        else:
            day_df = pd.read_sql("select Date from market where Name='삼성전자' order by Date desc limit 2", engine)
            from_day = str(day_df['Date'][1])
            to_day = str(day_df['Date'][0])
            
        df  =select_stock('all', from_day, )
        df = df[df['Volume'] >  300000]
        df.reset_index(drop=True)
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
        df3['Close']=df3['today_Close']/df3['yester_Close']
        df3['Volume']=df3['today_Volume']/df3['yester_Volume']
        df3 = df3.sort_values(by=['Volume','Close'],ascending=False)
        df4 = df3.sort_values(by=['Close','Volume'],ascending=False)
        df3 = df3.reset_index(drop=True)

        df3 = df3[:15]
        df4 = df4.reset_index(drop=True)
        df4 = df4[:15]
        df3.to_excel(path_volume+to_day+'.xlsx')
        df4.to_excel(path_price+to_day+'.xlsx')        
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
                money_query = "select * from kpi_with_money where Date >"+"'"+date+"'"
                money_df = pd.read_sql(money_query ,engine)

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
                program_query = "select * from programtrend where Date >"+"'"+date+"'"
                program_df = pd.read_sql(program_query ,engine)

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
                #date = input("날짜를 입력하세요 sample: '2019-01-10':")

                select_query = "select Date,Volume,Close from market where Name= "
                date_query = "Date > "


                tuple_name=tuple(name)
                df1 = pd.DataFrame()

                for x in tuple_name:
                    var = select_query +"'"+x+"'"+" "+"&&"+" "+date_query+"'"+date+"'"
                    df = pd.read_sql(var ,engine)
                    df.columns=['Date',x+'거래량',x]
                    if df1.empty:
                        df1 = df
                    else:
                        df1 = pd.merge (df,df1,on='Date')
                df1=df1.set_index('Date')
                size = len(df1.index)

                plt.figure(figsize=(16,4))
                for i in range(len(name)):
                    plt.plot(df1[name[i]]/df1[name[i]].loc[df['Date'][0]]*100)

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)

                plt.figure(figsize=(16,4))
                for i in range(len(name)):
                    volume_average = df1[name[i]+'거래량'].sum(axis=0)/size
                    plt.plot(df1[name[i]+'거래량']/volume_average)
                    #plt.plot(df1[name[i]+'거래량']/df1[name[i]+'거래량'].loc[df['Date'][0]]*100, label =[name[i]+'거래량'] )
                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    
            elif graph == 'future' :

                #name = input("항목을 입력하세요: 선택항목: 'kpi200', '거래량', '고객예탁금', '신용잔고', '주식형펀드', '혼합형펀드', '채권형펀드'").split()
                #date = input("날짜를 입력하세요 sample: '2019-01-10':")

                #query = "select * from future where Date > '2019-06-13'"+"'"+date+"'"
                query = "select * from future where Date >"+"'"+future_date+"'"
                query1 = "select * from basis where Date >"+"'"+future_date+"'"

                name=['Close', '미결제약정', '외국인', '기관', '개인']
                name1=['Close','미결제약정']
                name2=['외국인', '기관', '개인']
                basis_name=['kpi200','Future']

                #tuple_name=tuple(name)
                df1 = pd.DataFrame()
                basis_df1 = pd.DataFrame()

                df = pd.read_sql(query ,engine)
                basis_df = pd.read_sql(query1 ,engine)

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

                
        else :
            pass
  
          
            for i in three_period:
                depress(i)
                
            #bad_stock( )
            
            period_down('2020-02-01', '2020-03-31')
            
            kpi200_df = pd.read_sql("select Date from market where Name='hrs' order by Date desc limit 2", engine)
            yesterday = str(kpi200_df['Date'][1])
            today = str(kpi200_df['Date'][0])
            
            for i in graph_name_list:
                if i == 'stock' :
                    #name = pd.read_excel(path_volume+today+'.xlsx', encoding='utf-8')
                    name = pd.read_excel(path_volume+today+'.xlsx')                    
                    name_all = name['Name']
                    name_all = name_all.to_list()
                    name = name[:5]
                    name = name['Name']
                    name = name.to_list()

                    select_query = "select Date,Volume,Close from market where Name= "
                    date_query = "Date > "


                    tuple_name=tuple(name)
                    df1 = pd.DataFrame()

                    for x in tuple_name:
                        var = select_query +"'"+x+"'"+" "+"&&"+" "+date_query+"'"+date+"'"
                        df = pd.read_sql(var ,engine)
                        df.columns=['Date',x+'거래량',x]
                        if df1.empty:
                            df1 = df
                        else:
                            df1 = pd.merge (df,df1,on='Date')
                    df1=df1.set_index('Date')
                    size = len(df1.index)


                    plt.figure(figsize=(16,4))
                    for i in range(len(name)):
                        try:
                            plt.plot(df1[name[i]]/df1[name[i]].loc[df['Date'][0]]*100,label=name[i])
                            plt.legend(loc=0)
                            plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                            
                        except:
                            pass

                    plt.figure(figsize=(16,4))
                    for i in range(len(name)):
                        try:
                            volume_average = df1[name[i]+'거래량'].sum(axis=0)/size
                            plt.plot(df1[name[i]+'거래량']/volume_average, label=name[i])
                            #plt.plot(df1[name[i]+'거래량']/df1[name[i]+'거래량'].loc[df['Date'][0]]*100, label =[name[i]+'거래량'] )
                            plt.legend(loc=0)
                            plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                            
                        except:
                            pass                        

                    for i in name:
                        var = select_query +"'"+i+"'"+" "+"&&"+" "+date_query+"'"+date+"'" 
                        df = pd.read_sql(var, engine)
                        df[['Volume','Close']] = df[['Volume','Close']].astype(float) #  TA-Lib로 평균을 구하려면 실수로 만들어야 함
                        df.columns=df.columns.str.lower()
                        
                        talib_ma120 = ta.MA(df, timeperiod=120)
                        df['ma120'] = talib_ma120
                        
                        source = MinMaxScaler()
                        data = source.fit_transform(df[['close','volume','ma120']].values)
                        df1 = pd.DataFrame(data)
                        df1.columns=['close','volume','ma120']
                        df1 = df1.set_index(df['date'])
                        df1.plot(figsize=(16,2))
                        plt.title(i)
                        plt.show()
                
                elif i == 'money' :
                    money_name = ['kpi200', '거래량', '고객예탁금', '신용잔고']
                    money_query = "select * from kpi_with_money where Date >"+"'"+date+"'"
                    money_df = pd.read_sql(money_query ,engine)

                    money_df.columns=['Date','kpi200', '거래량', '고객예탁금', '신용잔고', '주식형펀드', '혼합형펀드', '채권형펀드']
                    money_df = money_df.set_index('Date')
                    df1 = money_df[money_name]
                    #return df1

                    plt.figure(figsize=(16,4))         
                    colors = ['red','green','blue','black']
                    for i in range(len(money_name)):
                        plt.subplot(2,2,i+1)
                        plt.plot(df1[money_name[i]]/df1[money_name[i]].loc[money_df.index[0]]*100, color=colors[i],label=money_name[i])
                        plt.legend(loc=0)
                        plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                        #plt.show()

                elif i == 'program' :
                    program_name = ['차익', '비차익', '전체']
                    program_query = "select * from programtrend where Date >"+"'"+date+"'"
                    program_df = pd.read_sql(program_query ,engine)

                    program_df.columns=['Date','차익', '비차익', '전체']
                    program_df = program_df.set_index('Date')
                    df1=program_df[program_name]
                    #return df1

                    plt.figure(figsize=(16,4))        
                    colors = ['red','green','blue','black']
                    for i in range(len(program_name)):

                        plt.subplot(2,2,i+1)
                        plt.plot(df1[program_name[i]],color=colors[i],label=program_name[i])

                        plt.legend(loc=0)
                        plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                        #plt.show()
                        
                elif i == 'future' :
                    query = "select * from future where Date >"+"'"+future_date+"'"
                    query1 = "select * from basis where Date >"+"'"+future_date+"'"
                    name=['Close', '미결제약정', '외국인', '기관', '개인']
                    name1=['Close','미결제약정']
                    name2=['외국인', '기관', '개인']
                    basis_name=['kpi200','Future']

                    df1 = pd.DataFrame()
                    basis_df1 = pd.DataFrame()

                    df = pd.read_sql(query ,engine)
                    basis_df = pd.read_sql(query1 ,engine)

                    df.columns=['Date', 'Close', '미결제약정', '외국인', '기관', '개인']
                    df = df.set_index('Date')
                    df1=df[name]

                    basis_df = basis_df.set_index('Date')
                    basis_df1=basis_df[basis_name]

                    colors = ['red','green','blue','black']
                    plt.figure(figsize=(16,4))    
                    for i in range(len(basis_name)):
                        plt.plot(basis_df1[basis_name[i]]/basis_df1[basis_name[i]].loc[basis_df.index[0]]*100,label=basis_name[i])

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    plt.show()

                    plt.figure(figsize=(16,4))    
                    for i in range(len(name1)):
                        plt.plot(df1[name1[i]]/df1[name1[i]].loc[df.index[0]]*100,label=name1[i])

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    plt.show()

                    plt.figure(figsize=(16,4)) 
                    for i in range(len(name2)):
                        plt.subplot(2,2,i+1)
                        plt.plot(df1[name2[i]]/df1[name2[i]].loc[df.index[0]]*100,color = colors[i],label=name2[i])

                        plt.legend(loc=0)
                        plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                         
                        
class to_sql:
    excel_name_list=['kpi200.xlsx', 'investor_trend.xlsx','money_trend.xlsx','program_trend.xlsx','kospi_sector.xlsx','kosdaq_sector.xlsx','market.xlsx','kospi.xlsx','kosdaq.xlsx']
    sql_table_name_list=['kpi200','investortrend','moneytrend','programtrend','kospi_sector','kosdaq_sector','market','kospi','kosdaq']
    
    
    #excel_name_list=['kpi200.xlsx', 'investor_trend.xlsx','money_trend.xlsx','program_trend.xlsx','market.xlsx']
    #sql_table_name_list=['kpi200','investortrend','moneytrend','programtrend','market']
    
    def excel_to_sql(self, choice = 1):
        excel_name_list=self.excel_name_list
        sql_table_name_list=self.sql_table_name_list

        if choice == 1:
        
            file_name = input('파일이름을 입력하세요:')

            df=pd.read_excel('C:/Users/linux/OneDrive/'+ file_name)
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
                data = pd.read_excel('C:/Users/linux/OneDrive/market.xlsx')
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
                    data = pd.read_excel('C:/Users/linux/OneDrive/market.xlsx')
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
                    df=pd.read_excel('C:/Users/linux/OneDrive/'+ i)
                    print(table_name)
                    df = df.rename(columns = {'Unnamed: 0': 'Date'})
                    df.to_sql(name=table_name, con=engine, if_exists='append', index = False)

                    print(df)
                a += 1
    
                
                
    ###  fdr을 통해 별도로 data수집
    def insert_all_stock(self, end_date=str_today):
        
        file_name = input('파일이름을 입력하세요:')
        toward = input('저장 방식을 입력하세요 : sample: excel, sql ')
        start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")
        table_name = input("table명을 입력하세요 : sample: market")
    
        data=pd.read_excel('C:/Users/linux/OneDrive/'+ file_name)
   
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
                df.to_excel('C:/Users/linux/OneDrive/data_set/kospi/'+ stock_dic[code] +'.xlsx',engine = 'xlsxwriter')
            elif toward == 'sql':
                df.to_sql(name=table_name, con=engine, if_exists='append')
                
    def insert_individual_stock(self, end_date=str_today):
        
        Code = input('주식 Code를 입력하세요')
        Name = input('주식이름을 입력하세요')

        query = "delete from  market where Name = "+"'"+Name+"'"
        curs.execute(query)
        conn.commit()
        conn.close()

        df = fdr.DataReader(Code, '1995')
        df.to_excel('C:/Users/linux/OneDrive/'+Code+'.xlsx', encoding='UTF-8')

        df = pd.read_excel('C:/Users/linux/OneDrive/'+Code+'.xlsx')
        df['Code']= Code
        df['Name']= Name

        df = df[['Date','Code','Name','Open', 'High', 'Low', 'Volume','Close']]

        df.to_sql(name='market', con=engine, if_exists='append', index = False)
        

class to_excel:
    investor_trend_url = 'http://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=20220601&sosok=&page='
    money_trend_url = 'http://finance.naver.com/sise/sise_deposit.nhn?&page='
    kpi200_url = 'https://finance.naver.com/sise/sise_index_day.nhn?code=KPI200&page='
    program_trend_url = 'https://finance.naver.com/sise/programDealTrendDay.nhn?bizdate=20221215&sosok=&page='    
    future_url = 'http://finance.daum.net/api/future/KR4101PC0002/days?pagination=true&page='
    kospi_sector_url = "http://finance.daum.net/api/quotes/sectors?fieldName=&order=&perPage=&market=KOSPI&page=&changes=UPPER_LIMIT%2CRISE%2CEVEN%2CFALL%2CLOWER_LIMIT"
    kosdaq_sector_url = "http://finance.daum.net/api/quotes/sectors?fieldName=&order=&perPage=&market=KOSDAQ&page=&changes=UPPER_LIMIT%2CRISE%2CEVEN%2CFALL%2CLOWER_LIMI"

    
    def get_investor_trend(self):
        url  = self.investor_trend_url 

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'C:/Users/linux/OneDrive/investor_trend.xlsx'
    
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
        path = 'C:/Users/linux/OneDrive/investor_trend.xlsx'
        
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
        path = 'C:/Users/linux/OneDrive/money_trend.xlsx'   
    
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
        path = 'C:/Users/linux/OneDrive/money_trend.xlsx'

    
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
        path = 'C:/Users/linux/OneDrive/kpi200.xlsx'
    
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
        path = 'C:/Users/linux/OneDrive/kpi200.xlsx'

        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or str_yesterday

            start = datetime.strptime(until_date , "%Y-%m-%d")
            until_date= (start + timedelta(days=0)).strftime('%Y-%m-%d')
    
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 1", engine)
            kpi200_df = str(kpi200_df['Date'])
            until_date = kpi200_df[5:15]

            start = datetime.strptime(until_date , "%Y-%m-%d")
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
        path = 'C:/Users/linux/OneDrive/program_trend.xlsx'
    
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
        path = 'C:/Users/linux/OneDrive/program_trend.xlsx'

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
        path = 'C:/Users/linux/OneDrive/future.xlsx'
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
                df1 = df1.append(df,ignore_index=True)

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
                df1 = df1.append(df,ignore_index=True)
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
        kosdaq_sector_res = req.urlopen(req.Request(kosdaq_sector_url, headers=headers)).read().decode('utf-8')
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
        
        kospi_df.to_excel('C:/Users/linux/OneDrive/kospi_sector.xlsx')
        kosdaq_df.to_excel('C:/Users/linux/OneDrive/kosdaq_sector.xlsx')   
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
        df_kospi.to_excel('C:/Users/linux/OneDrive/kospi.xlsx')

        df_kosdaq = get_index_ohlcv_by_date(kosdaq_date, "20250228", "코스닥")
        df_kosdaq.index.names = ['Date']
        df_kosdaq.columns  = ('Open','High','Low','Close','Volume')
        df_kosdaq['Market']='kosdaq'
        #df_kosdaq.to_sql(name='kosdaq', con=engine, if_exists='append')
        df_kosdaq.to_excel('C:/Users/linux/OneDrive/kosdaq.xlsx')
   
            
if __name__ == "__main__":
    print("This is Module")
    
    
