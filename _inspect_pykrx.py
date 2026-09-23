import inspect
from pykrx import stock
for name in ['get_market_trading_value_and_volume_by_ticker','get_market_trading_value_by_investor','get_market_trading_volume_by_investor','get_shorting_volume_by_ticker','get_exhaustion_rates_of_foreign_investment_by_ticker','get_market_cap_by_ticker']:
 f=getattr(stock,name)
 print('\n',name,inspect.signature(f))
 print('\n'.join((inspect.getdoc(f) or '').splitlines()[:14]))
