import requests
h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36','Referer':'https://finance.daum.net/domestic/futures','Origin':'https://finance.daum.net','Accept':'application/json, text/plain, */*'}
for code in ['KR4101PC0002','KR4101Q30005','KR4101PC0001','KR4101FUK2I']:
 url=f'https://finance.daum.net/api/future/{code}/days?pagination=true&page=1'
 try:
  r=requests.get(url,headers=h,timeout=15)
  j=r.json()
  print(code,r.status_code,j.get('totalCount'),j.get('totalPages'),len(j.get('data',[])),j.get('data',[{}])[0] if j.get('data') else '')
 except Exception as e: print(code,type(e).__name__,str(e)[:100])
