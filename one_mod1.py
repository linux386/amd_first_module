# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import FinanceDataReader as fdr
import pandas as pd
from bs4 import BeautifulSoup
import datetime as dt
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime,timedelta
from urllib.request import urlopen
from pykrx import stock
import sqlalchemy 
import pymysql
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from matplotlib import font_manager, rc
font_name = font_manager.FontProperties(fname="c:/Windows/Fonts/malgun.ttf").get_name()
rc('font', family=font_name)

today = datetime.now()
real_yesterday = (today-timedelta(1)).strftime('%Y-%m-%d')
real_today = today.strftime('%Y-%m-%d')

now = dt.datetime.today().strftime('%Y-%m-%d')
engine = sqlalchemy.create_engine('mysql+pymysql://kkang:leaf2027@localhost/stock?charset=utf8',encoding='utf-8')
conn = pymysql.connect(host = 'localhost', user = 'kkang', password = 'leaf2027' ,db = 'stock')
curs = conn.cursor()

def last_page(source):
    last = source.find('td',class_='pgRR').find('a')['href']
    last = last.split('page')[1]
    last = last.split('=')[1]
    last = int(last)
    print(last)
    return last

class to_report:
    select_query = "select * from market_good where Date >="
    volume_query = "&& Volume >  500000"
    def stock_select_with_Volume_Close(self,choice = 1):
    
        if choice == 1:
            yesterday = input("어제날짜를 입력하세요 : sample: '2019-02-07'  ") or real_yesterday
            today = input("오늘날짜를 입력하세요 : sample: '2019-02-07'  ") or real_today
        
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 2", engine)
            yesterday = str(kpi200_df['Date'][1])
            today = str(kpi200_df['Date'][0])
            
        select_query = self.select_query
        volume_query =self.volume_query
    
        var = select_query +"'"+yesterday+"'"+ volume_query
        df = pd.read_sql(var ,engine)

        df1 = df[df['Date'].astype(str) == yesterday]
        df1 = df1[['Name','Volume','Close']]
        df1.columns = ['Name','yester_Volume','yester_Close']
        #display(df1)

        df2 = df[df['Date'].astype(str) == today]
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
        df3.to_excel('d:\\detect_stock_with_volume.xlsx', encoding='utf-8')
        df4.to_excel('d:\\detect_stock_with_price.xlsx', encoding='utf-8')        
        display(df3)
        display(df4)

    def get_graph(self, choice=1):
        graph_name_list=['stock','money', 'program','future']
        date='2019-01-01'
        future_date='2019-09-12'

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
            for i in graph_name_list:
                if i == 'stock' :
                    name = pd.read_excel('d:\\detect_stock_with_volume.xlsx', encoding='utf-8')
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

                    for i in name_all:
                        var = select_query +"'"+i+"'"+" "+"&&"+" "+date_query+"'"+date+"'" 
                        df = pd.read_sql(var, engine)

                        source = MinMaxScaler()
                        data = source.fit_transform(df[['Close','Volume']].values.astype(float))
                        df1 = pd.DataFrame(data)
                        df1.columns=['Close','Volume']
                        df1 = df1.set_index(df['Date'])
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
                        plt.plot(df1[money_name[i]]/df1[money_name[i]].loc[money_df.index[0]]*100, color=colors[i])
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
                        plt.plot(df1[program_name[i]],color=colors[i])

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
                        plt.plot(basis_df1[basis_name[i]]/basis_df1[basis_name[i]].loc[basis_df.index[0]]*100)

                    plt.legend(loc=0)
                    plt.grid(True,color='0.7',linestyle=':',linewidth=1)
                    plt.show()

                    plt.figure(figsize=(16,4))    
                    for i in range(len(name1)):
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
                         
                        
class to_sql:
    excel_name_list=['kpi200.xlsx', 'investor_trend.xlsx','program_trend.xlsx','money_trend.xlsx','market.xlsx']
    sql_table_name_list=['kpi200','investortrend','programtrend','moneytrend','market.xlsx']
    
    def excel_to_sql(self, choice = 1):
        excel_name_list=self.excel_name_list
        sql_table_name_list=self.sql_table_name_list

        if choice == 1:
        
            file_name = input('파일이름을 입력하세요:')

            df=pd.read_excel('d:\\'+ file_name)
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

            elif file_name=='market.xlsx':
                data = pd.read_excel('d:\\market.xlsx')
                start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")

                code_list = data['종목코드'].tolist()
                code_list = [str(item).zfill(6) for item in code_list]
                name_list = data['종목명'].tolist()

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
                    data = pd.read_excel('d:\\market.xlsx')
                    market_df = pd.read_sql("select Date from market order by Date desc limit 1", engine)
                    market_df = str(market_df['Date'])
                    print(market_df)
                    start_date =  market_df[5:15]
                    year = start_date.split('-')[0]
                    mm = start_date.split('-')[1]
                    dd = start_date.split('-')[2]
                    dd = int(dd)+1
                    dd = str(dd)
                    
                    #year=year[2:]
                    start_date = year+'-'+mm+'-'+dd
                    print('\n market start_date:{}'.format(start_date))

                    code_list = data['종목코드'].tolist()
                    code_list = [str(item).zfill(6) for item in code_list]
                    name_list = data['종목명'].tolist()

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
                    df=pd.read_excel('d:\\'+ i)
                    print(table_name)
                    df = df.rename(columns = {'Unnamed: 0': 'Date'})
                    df.to_sql(name=table_name, con=engine, if_exists='append', index = False)

                    print(df)
                a += 1
    
                
                
    ###  fdr을 통해 별도로 data수집
    def insert_all_stock(self, end_date=now):
        
        file_name = input('파일이름을 입력하세요:')
        toward = input('저장 방식을 입력하세요 : sample: excel, sql ')
        start_date = input("시작날자를 입려하세요 : sample: '2015-01-01'")
        table_name = input("table명을 입력하세요 : sample: market")
    
        data=pd.read_excel('d:\\'+ file_name)
   
        code_list = data['종목코드'].tolist()
        code_list = [str(item).zfill(6) for item in code_list]
        name_list = data['종목명'].tolist()

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
                
    def insert_individual_stock(self, end_date=now):
        
        Code = input('주식 Code를 입력하세요')
        Name = input('주식이름을 입력하세요')

        query = "delete from  market where Name = "+"'"+Name+"'"
        curs.execute(query)
        conn.commit()
        conn.close()

        df = fdr.DataReader(Code, '1995')
        df.to_excel('d:\\'+Code+'.xlsx', encoding='UTF-8')

        df = pd.read_excel('d:\\'+Code+'.xlsx')
        df['Code']= Code
        df['Name']= Name

        df = df[['Date','Code','Name','Open', 'High', 'Low', 'Volume','Close']]

        df.to_sql(name='market', con=engine, if_exists='append', index = False)
        

class to_excel:
    investor_trend_url = 'http://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=2020601&sosok=&page='
    money_trend_url = 'http://finance.naver.com/sise/sise_deposit.nhn?&page='
    kpi200_url = 'https://finance.naver.com/sise/sise_index_day.nhn?code=KPI200&page='
    program_trend_url = 'https://finance.naver.com/sise/programDealTrendDay.nhn?bizdate=20200315&sosok=&page='    
    
    def get_investor_trend(self):
        url  = self.investor_trend_url 

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'd:\\investor_trend.xlsx'
    
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

    def get_investor_trend_date(self,until_date=real_yesterday,choice=1):
        url  = self.investor_trend_url
        
        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'd:\\investor_trend.xlsx'
        
        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or real_yesterday

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 1", engine)
            kpi200_df = str(kpi200_df['Date'])
            until_date = kpi200_df[5:15]

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
    
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
                            df.to_excel(path, encoding='utf-8')
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
        path = 'd:\\money_trend.xlsx'   
    
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

    def get_money_trend_date(self,until_date=real_today,choice=1):
        
        url = self.money_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'd:\\money_trend.xlsx'

    
        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or real_today

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
        else:
            moneytrend_df = pd.read_sql("select Date from moneytrend order by Date desc limit 1", engine)
            moneytrend_df = str(moneytrend_df['Date'])
            until_date = moneytrend_df[5:15]

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
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
                            df.to_excel(path, encoding='utf-8')
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
        path = 'd:\\kpi200.xlsx'
    
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
       

    def get_kpi200_date(self,until_date=real_yesterday,choice=1):
    
        url = self.kpi200_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'd:\\kpi200.xlsx'

        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or real_yesterday

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            #year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
        else:
            kpi200_df = pd.read_sql("select Date from kpi200 order by Date desc limit 1", engine)
            kpi200_df = str(kpi200_df['Date'])
            until_date = kpi200_df[5:15]

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            #year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
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
                            df.to_excel(path, encoding='utf-8')
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
        path = 'd:\\program_trend.xlsx'
    
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
            
    def get_program_trend_date(self,until_date=real_yesterday, choice=1):

        url = self.program_trend_url

        source = urlopen(url).read()   # 지정한 페이지에서 코드 읽기
        source = BeautifulSoup(source, 'lxml')   # 뷰티풀 스프로 태그별로 코드 분류
        last = last_page(source)
        print(last)

        # 사용자의 PC내 폴더 주소를 입력하시면 됩니다.
        path = 'd:\\program_trend.xlsx'

        if choice == 1:
            until_date = input("날짜를 입력하세요 sample: '2019-01-10': ") or real_yesterday

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
        else:
            programtrend_df = pd.read_sql("select Date from programtrend order by Date desc limit 1", engine)
            programtrend_df = str(programtrend_df['Date'])
            until_date = programtrend_df[5:15]

            year = until_date.split('-')[0]
            mm = until_date.split('-')[1]
            dd = until_date.split('-')[2]
            year=year[2:]
            until_date = year+'-'+mm+'-'+dd
    
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
                            df.to_excel(path, encoding='utf-8')
                            return df   
                        date_list.append(date_)
                        #print(date_list)
                    elif count in mask:
                        temp = int((count/3)-1)
                        dictionary[name_list[temp]].append(td.text.strip().replace(',',''))
                    
                    count += 1
            
            

if __name__ == "__main__":
    print("This is Module")
    
    
    
