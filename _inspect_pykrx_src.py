import inspect
from pykrx import stock
for name in ['get_market_net_purchases_of_equities_by_ticker']:
 f=getattr(stock,name)
 print(name,inspect.signature(f))
 print('\n'.join((inspect.getdoc(f) or '').splitlines()[:24]))
 print(inspect.getsource(f)[:2500])
