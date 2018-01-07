from bittrex import Bittrex
import pprint
import pandas as pd
import numpy as np
import time
from datetime import datetime
import json

# /DEFINE API KEY & SECRET PAIR
API_key='d8144fb29c354a71bccce4a16dcd28d2'
API_secret=
# DEFINE API KEY & SECRET PAIR/

# /MATCH FUNCTIONS
def log_weights(indexes):
	"""
	Returns logarithmic weights of given range argument.
	"""
	indexes=[index+1 for index in indexes]
	log_sum=max(np.log(2),sum([np.log(index) for index in indexes[1:]]))
	indexes_w=np.append([0],[np.log(index)/log_sum for index in indexes[1:]])
	if sum(indexes_w)==0:
		indexes_w=lin_weights(indexes)
	
	return(indexes_w)

def lin_weights(indexes):
	"""
	Returns linear weights of given range argument.
	"""	
	lin_sum=sum(indexes)
	indexes_w=[index/lin_sum for index in indexes]
	
	return(indexes_w)

def exp_weights(indexes):
	"""
	Returns exponential weights of given range argument.
	"""	
	exp_sum=sum([np.exp(index) for index in indexes])
	indexes_w=[np.exp(index)/exp_sum for index in indexes]
	
	return(indexes_w)
# MATCH FUNCTIONS/

# /PURE BITTREX API FUNCTIONS
def get_market_base_volume(market_name):
	"""
	Gets market's base volume.
	"""	
	# market summary
	market_summary_dict=br.get_marketsummary(market_name)['result']
	if (market_summary_dict is not None):
		base_volume=market_summary_dict[0]['BaseVolume']
	else:
		base_volume=0
	
	return base_volume
# PURE BITTREX API FUNCTIONS/

# WOLFBOT CLASS DEFINITION
class WolfBot(object):
	"""
	Trades on defined markets when met with certain conditions.
	"""
	
	def __init__(self,Bittrex_object,market_revire, pocket_money):
		"""
		Sets up bot instance with: 
			* bittrex client
			* operational revire
			* pocket money for all markets in revire
			* empty order log
		"""
		self.bittrex=Bittrex_object
		self.market_revire=market_revire
		self.pocket_money={market_dict['MarketCurrency']:0.0 for market,market_dict in markets.items()}
		self.pocket_money={**self.pocket_money,**pocket_money}
		self.name='Woofie'
		self.orders={}
	
	def save_orders(self,filename):
		"""
		Appends (non-incremental) bot's orders dictionary to filename file.
		"""
		with open(filename, 'a') as writer:
			json.dump(self.orders, writer)
		print("Orders data appended to {} file".format(filename))
	
	def assign_all_available_funds(self):
		"""
		Sets up bot instance with all money on related Bittrex account.
		"""        
		all_available_funds={wallet['Currency']:wallet['Balance'] for wallet in self.bittrex.get_balances()['result']}
		
		self.pocket_money={**self.pocket_money,**all_available_funds}
		print('WARNING: The BOT has beed given all money on related Bittrex account!')
		
	
	def get_market_history_df(self,market):
		"""
		Gets pandas DataFrame of given market's last 100 orders (partial included).
		"""        
		count=0
		timeout=5
		
		market_history_dict_list=self.bittrex.get_market_history(market['MarketName'])['result']
		# try to get history
		while (count<timeout and (market_history_dict_list is None or market_history_dict_list == [] or 'TimeStamp' not in market_history_dict_list[0])):
			market_history_dict_list=self.bittrex.get_market_history(market['MarketName'])['result']
			count+=1
		if not (market_history_dict_list is None or market_history_dict_list == [] or 'TimeStamp' not in market_history_dict_list[0]):
			market_history_df=pd.DataFrame.from_dict(market_history_dict_list)
			market_history_df.sort_values('TimeStamp',inplace=True)
			market_history_df.reset_index(inplace=True)
		else:
			market_history_df=pd.DataFrame()

		return market_history_df
	
	def trade_buy(self,market,price,amount,buy_rule_dict={}):        
		"""
		Place an order to buy amount*price worth of stock on a given market.
		"""
		# assert market in bot's market_revire
		assert (market['MarketName'] in self.market_revire), "Trading at %r market not in WolfBot's competence!" % market['MarketName']
		
		# check if bot has required funds for transaction
		if (price*amount <= self.pocket_money['BTC']):
			response=self.bittrex.buy_limit(market=market['MarketName'], quantity=amount, rate=price)
			while (response is None or response['result'] is None):
				print('API request failed, trying again...')
				response=self.bittrex.buy_limit(market=market['MarketName'], quantity=amount, rate=price)
			assert(response['message']!='INSUFFICIENT_FUNDS'), "The Bittrex account is out of money!"
			self.orders[response['result']['uuid']]={'time_created':str(datetime.now()),'status':'open','market':market['MarketName'],
													 'amount':amount,'price':price,'value':amount*price,'type':'buy','buy_rule_dict':buy_rule_dict}
		else:
			print("Sorry, the WolfBot is out of money for this trade. The remaining credit is {credit}."
			"The order price is {price} and the amount is {amount}, yelding order value {order_value}."
			"The order will not proceed"
			"".format(credit=self.pocket_money['BTC'],amount=amount,price=price,order_value=price*amount))
			response = {'success':False}
		return response
	
	def trade_sell(self,market,price,amount):        
		"""
		Place an order to sell amount*price worth of stock on a given market.
		"""
		market_currency=market['MarketCurrency']
		# assert market in market_revire
		assert (market['MarketName'] in self.market_revire), "Trading at %r market not in WolfBot's competence!" % market['MarketName']
		
		# check if bot has required funds for transaction
		if (price*amount <= self.pocket_money[market_currency]):
			response=self.bittrex.sell_limit(market=market['MarketName'], quantity=amount, rate=price)
			while (response['message']=='NO_API_RESPONSE'):
				print('API request failed, trying again...')
				response=self.bittrex.buy_limit(market=market['MarketName'], quantity=amount, rate=price)            
			if (response['message']=='INSUFFICIENT_FUNDS'):
				print('API request returned \'INSUFFICIENT_FUNDS\'...')                
				response = {'success':False}
			else:
				self.orders[response['result']['uuid']]={'time_created':str(datetime.now()),'status':'open','market':market['MarketName'],'amount':amount,'price':price,'value':amount*price,'type':'sell'}
		else:
			print("Sorry, the WolfBot is out of money for this trade. The remaining credit is {credit}."
			"The order price is {price} and the amount is {amount}, yelding order value {order_value}."
			"The order will not proceed"
			"".format(credit=self.pocket_money['BTC'],amount=amount,price=price,order_value=price*amount))
			response = {'success':False}
		return response
	
	def get_market_buy_ratio(self,market):
		"""
		Gets log-weighted ratio of BUY-type orders in last 100 orders (partial orders included) on 
		given market.
		"""        
		order_type_df=self.get_market_history_df(market)
		if not order_type_df.empty:
			order_type_df=order_type_df[['TimeStamp','OrderType']].copy()
			order_type_df['OrderTypeIsBuy']=(order_type_df['OrderType']=='BUY')
			order_type_df['w']=log_weights(order_type_df.index)
			buy_ratio=np.average(order_type_df['OrderTypeIsBuy'], weights=order_type_df.w)
		else:
			buy_ratio=0

		return buy_ratio
	
	def get_incr_median_perc(self,market):
		"""
		Gets ratio of log-weighted percentage increases (with threshold of 0.05% as an increase) in 
		minute medians of price for last 100 orders (partial orders included).
		"""        
		# market history DF
		market_history_df=self.get_market_history_df(market)
		if not market_history_df.empty:
			# get median of traded price by minute
			times=pd.to_datetime(market_history_df['TimeStamp'])
			prices_df=pd.DataFrame(market_history_df.groupby([times.dt.hour,times.dt.minute]).Price.median())
			prices_df['pct_change']=prices_df['Price'].pct_change()
			prices_df.index.rename(['hour','min'],inplace=True)
			prices_df.reset_index(inplace=True)
			prices_df['w']=log_weights(prices_df.index)
			incr_median_perc=np.average((prices_df['pct_change']>0.0005), weights=prices_df.w)
		else:
			incr_median_perc=0
			prices_df=pd.DataFrame()

		return incr_median_perc,prices_df    

	def get_incr_max_perc(self,market):
		"""
		Gets ratio of log-weighted percentage increases (with threshold of 0.05% as an increase) in 
		second maximax of price for last 100 orders (partial orders included).
		"""        
		# market history DF
		market_history_df=self.get_market_history_df(market)
		if not market_history_df.empty:
			# get maxima of traded price by seconds
			times=pd.to_datetime(market_history_df['TimeStamp'])
			prices_df=pd.DataFrame(market_history_df.groupby([times.dt.hour,times.dt.minute,times.dt.second]).Price.max())
			prices_df['pct_change']=prices_df['Price'].pct_change()
			prices_df.index.rename(['hour','min','sec'],inplace=True)
			prices_df.reset_index(inplace=True)
			prices_df['w']=log_weights(prices_df.index)
			incr_max_perc=np.average((prices_df['pct_change']>0.0005), weights=prices_df.w)
		else:
			incr_max_perc=0
			prices_df=pd.DataFrame()

		return incr_max_perc,prices_df    
	
	def check_buy_rule1(self,market,threshold):
		"""
		Checks whether incr_max_perc value on given market is above threshold arg.
		"""        
		buy_continues,prices=self.get_incr_max_perc(market)
		#print("Short-time increase of trades' maxima on {market} market is {increase}%".format(market=market['MarketName'],increase=round(100*incr_max_perc,2)))
		if (buy_continues>=threshold):
			buy_boolean=True
		else:
			buy_boolean=False
		return buy_boolean,buy_continues
	
	def check_buy_rule2(self,market,threshold):
		"""
		Checks whether incr_median_perc value on given market is above threshold arg.
		"""        
		buy_continues,prices=self.get_incr_median_perc(market)
		buy_continues*=min(1,prices.shape[0]/6)
		
		if (buy_continues>=threshold):
			buy_boolean=True
		else:
			buy_boolean=False
		return buy_boolean,buy_continues

	def check_buy_rule3(self,market,threshold):
		"""
		Checks whether get_market_buy_ratio value on given market is above threshold arg.
		"""        
		buy_continues=self.get_market_buy_ratio(market)
		
		if (buy_continues>=threshold):
			buy_boolean=True
		else:
			buy_boolean=False
		return buy_boolean,buy_continues    
	
	
	def check_buy_rule(self,market,threshold):
		"""
		Makes a linear combination of all buy check rulles and thresholds.
		"""        
		w1=0.5
		w2=0.2
		w3=0.3
		
		buy_boolean1,buy_continues1=self.check_buy_rule1(market,threshold)
		buy_boolean2,buy_continues2=self.check_buy_rule2(market,threshold)
		buy_boolean3,buy_continues3=self.check_buy_rule3(market,threshold)
		
		buy_continues=w1*buy_continues1+w2*buy_continues2+w3*buy_continues3
		buy_rule_dict={'rule1':buy_continues1,'rule2':buy_continues2,'rule3':buy_continues3,'rule':buy_continues}
		
		if (buy_continues>=threshold):
			buy_boolean=True
		else:
			buy_boolean=False
			
		print(buy_rule_dict)
		
		return buy_boolean,buy_rule_dict
	
	def check_sell_rule1(self,market,threshold):
		"""
		Checks whether incr_max_perc value on given market is below threshold arg.
		"""        
		incr_max_perc,prices=self.get_incr_max_perc(market)
		print("Short-time increase of trades' maxima on {market} market is {increase}%".format(market=market['MarketName'],increase=round(100*incr_max_perc,2)))
		if (incr_max_perc<=threshold):
			sell=True
			print(prices)
		else:
			sell=False
		return sell
	
	def check_sell_rule2(self,market,order_id):
		"""
		Checks whether given order has positive margin.
		"""        
		bittrex_fee=0.0025
		sell_price=self.current_sell_price(market,head=3)
		# what would be the margin of a trade when sold for current sell price
		order_margin=self.orders[order_id]['amount']*sell_price*(1-bittrex_fee)-self.orders[order_id]['value']*(1+bittrex_fee)
		print("Current order_margin : {order_margin}".format(order_margin=order_margin))
		if (order_margin>=0):
			sell=True
		else:
			sell=False
		return sell

	def current_sell_price(self,market,head=5):
		"""
		Gets median of top head market sell offers, which represents current sell price.
		"""        
		orderbook_head=self.bittrex.get_orderbook(market['MarketName'],'sell')['result'][0:head]
		rates_head=[x['Rate'] for x in orderbook_head]
		rates_median=np.median(rates_head)

		return rates_median

	def current_buy_price(self,market,head=5):
		"""
		Gets median of top head market buy offers, which represents current sell price.
		"""        
		orderbook_head=self.bittrex.get_orderbook(market['MarketName'],'buy')['result'][0:head]
		rates_head=[x['Rate'] for x in orderbook_head]
		rates_median=np.median(rates_head)

		return rates_median

	def observe_order_status(self,market,order_id,time_limit):
		"""
		Gets given order's details and checks whether it was sold within time_limit seconds. Writes
		status to bot's order dict.
		
		:param market: dict record for the market {'MarketCurrency': 'LTC','MarketName': 'BTC-LTC',...}.
		:type market: dict
		:param order_id: string literal for given Bittrex order.
		:type order_id: str
		:param time_limit: number of seconds, for which the order is trying to be closed before timeout.
		:type time_limit: int
		
		:return order_status: 'sold' if order has been successfully closed. 'canceled' if order
		has been canceled.
		:type order_status: str
		"""        
		bittrex_fee=0.0025
		order=self.bittrex.get_order(order_id)
		while (order is None) or (order['result'] is None):
			print('Retrying to get order details...')
			order=self.bittrex.get_order(order_id)
		
		if (order['result']['CancelInitiated']==True):
			order_status='canceled'
		else:
			check_id=0
			# while the order is open and did not expire
			while (check_id < time_limit) and (order['result']['IsOpen']==True):
				order=self.bittrex.get_order(order_id)
				while order is None or order['result'] is None:
					print('Retrying to get order details...')
					order=self.bittrex.get_order(order_id)
				time.sleep(1)
				check_id+=1

			if (order['result']['IsOpen']==True):
				cancel_response=self.bittrex.cancel(order_id)
				while cancel_response['success']!=True:
					cancel_response=self.bittrex.cancel(order_id)
				self.orders[order_id]['status']='canceled'
				order_status='canceled'
				print('The order has been canceled, due to it\'s time limit expiration.')            
			else:
				# the transaction has proceeded => lower the WolfBot's pocket money 
				if (self.orders[order_id]['type']=='buy'):
					self.pocket_money['BTC']=self.pocket_money['BTC']-order['result']['Quantity']*order['result']['Limit']*(1+bittrex_fee)
					self.pocket_money[market['MarketCurrency']]=self.pocket_money[market['MarketCurrency']]+order['result']['Quantity']
				else:
					self.pocket_money['BTC']=self.pocket_money['BTC']+order['result']['Quantity']*order['result']['Limit']*(1-bittrex_fee)
					self.pocket_money[market['MarketCurrency']]=self.pocket_money[market['MarketCurrency']]-order['result']['Quantity']
				self.orders[order_id]['status']='sold'
				order_status='sold'
		
		return order_status    
	
	
	def bite(self,market,trade_units=1,aggressivness=0.9,buy_rule_dict={}):
		"""
		Places a buy order to given market. The price is derived as median from last X orders, where
		X is determined on the basis of aggressivness parameter. The value of order is based on 
		trade_units param.
		
		:param market: dict record for the market {'MarketCurrency': 'LTC','MarketName': 'BTC-LTC',...}
		:type market: dict
		:param trade_units: Defines minimal trancaction value multiplicator for money spent on the order.
		:type trade_units: float
		:param aggressivness: Placeholder for probability of quick successful closure of the trade.
		Value 1...will be sold quickly, value 0... will be sold after a long while.
		:type aggressivness: float
		
		:return order_buy_response: Response of Bittrex API to buy order placement.
		:type order_buy_response: dict
		:return order_value: Value of order placed
		:type order_value: float
		"""
		head=int(max(1,(1-aggressivness)*100))
		buy_price=self.current_buy_price(market,head)
		
		# place a buy order for minimal alowed amount * trade_units
		unconstrained_order_value=trade_units*0.0010001
		order_volume=max(market['MinTradeSize'],unconstrained_order_value/buy_price)
		order_value=order_volume*buy_price
		order_buy_response=self.trade_buy(market,buy_price,order_volume,buy_rule_dict)
		
		return order_buy_response, order_value
	

	
	def let_go(self,market,order_id):
		"""
		Tries to sell given order on the market with profit and minimal losses. First checks whether
		the order is in profit and sells. If order is not in profit, steps down from zero-margin price 
		to current sell price and tries to place orders until it is closed.
		
		:param market: dict record for the market {'MarketCurrency': 'LTC','MarketName': 'BTC-LTC',...}
		:type market: dict
		:param order_id: string literal for given Bittrex order.
		:type order_id: str
		
		:return order_status: Response of Bittrex API to sell order placement or boolean False
		in case of order placement failure.
		:type order_status: dict     
		"""        
		bittrex_fee=0.0025
		# try to wait for good moment for 30 mins & sells
		counter_timeout=30/5
		profit_pump_timeout=2
		counter=0
		# do checker whether the sell order has proceeded & lower price & try again if False
		order_value=self.orders[order_id]['value']*(1+2*bittrex_fee)
		order_amount=self.orders[order_id]['amount']
		
		
		Pass=False
		while (not Pass) and (counter<counter_timeout and self.check_sell_rule1(market,0.2)==False and (counter<=profit_pump_timeout or self.check_sell_rule2(market,order_id)==False)):
			print("The order is not good for trade yet. Rule1:{rule1}, Rule2:{rule2}".format(rule1=self.check_sell_rule1(market,0.2),rule2=self.check_sell_rule2(market,order_id)))
			time.sleep(5)
			counter+=1

		zero_profit_price=order_value/order_amount
		current_sell_price=self.current_sell_price(market,5)
		w_delta=0.1
		w1=1.0
		w2=0.0
		sell_price=max(current_sell_price,zero_profit_price)
		order_sell_response=self.trade_sell(market,sell_price,order_amount)
		if order_sell_response!=False:
			print('Initial sell try...')
			print("w1:{w1},w2:{w2},sell_price:{sell_price},current_sell_price:{current_sell_price},zero_profit_price:{zero_profit_price}"
				  "".format(w1=w1,w2=w2,sell_price=sell_price,current_sell_price=current_sell_price,zero_profit_price=zero_profit_price))        
			print(order_sell_response)
			while order_sell_response['success']==False:
				print('Order sell failed, trying again...')
				order_sell_response=self.trade_sell(market,sell_price,order_amount)            
			order_status=self.observe_order_status(market,order_sell_response['result']['uuid'],5)
			
			while (order_status=='canceled'):                
				current_sell_price=self.current_sell_price(market,1)
				if (current_sell_price>=zero_profit_price):
					sell_price=current_sell_price
				else:
					w1=max(0,w1-w_delta)
					w2=min(1,w2+w_delta)
					sell_price=current_sell_price*w2+zero_profit_price*w1
				print('Commencing new sell try...')
				print("w1:{w1},w2:{w2},sell_price:{sell_price},current_sell_price:{current_sell_price},zero_profit_price:{zero_profit_price}"
					  "".format(w1=w1,w2=w2,sell_price=sell_price,current_sell_price=current_sell_price,zero_profit_price=zero_profit_price))
				order_sell_response=self.trade_sell(market,sell_price,order_amount)
				while order_sell_response['success']==False:
					print('Order sell failed, trying again...')
					order_sell_response=self.trade_sell(market,sell_price,order_amount)
				print(order_sell_response)
				order_status=self.observe_order_status(market,order_sell_response['result']['uuid'],5)
		else:
			order_status=False
		return order_status
	
	def bite_and_let_go(self,market,buy_rule_dict):
		"""
		Buy the increasing stock and sells if market starts to fall + tries to make profit.
		"""
		order_status='unplaced'
		while (self.check_buy_rule(market,0.5)==True and order_status!='sold'):
			order_buy_response,order_value=self.bite(market=market,trade_units=1,aggressivness=0.99,buy_rule_dict=buy_rule_dict)
			if (order_buy_response['success']!=True):
				print("Error: The order did not proceed to the Bittrex order book.")
				order_status='unplaced'
			else:
				print(order_buy_response)
				order_status=self.observe_order_status(market,order_buy_response['result']['uuid'],10)
		
		if (order_status=='sold'):
			self.let_go(market,order_buy_response['result']['uuid'])
		else:
			pass
	
	def patrol(self,market,threshold=0.5):
		"""
		Scan the market for chance to bite_and_let_go().
		"""
		buy_rule_boolean,buy_rule_dict=self.check_buy_rule(market,threshold)
		if buy_rule_boolean:
			print("The there is a chance of scoring on market {market}. Proceeding to bite algorithm.".format(market=market['MarketName']))
			self.bite_and_let_go(market,buy_rule_dict)
		else:
			print("The there is nothing going on on market {market}.)".format(market=market['MarketName']))
			pass

# init bittrex client
br = Bittrex(API_key, API_secret)
# get market names
markets={market['MarketName']:{'MarketName':market['MarketName'],
							   'MarketCurrency':market['MarketCurrency'], 
							   'MinTradeSize':market['MinTradeSize']
							  } for market in br.get_markets()['result'] if market['MarketName'].startswith('BTC')}

# /GET FERTILE MARKETS
print("Getting 0.9 quantile markets with respect to its base volume. This takes few minutes, please wait...")
# assign base_volume to markets
for market,market_dict in markets.items():
	market_name=market_dict['MarketName']
	markets[market_name]['base_volume']=get_market_base_volume(market_dict['MarketName'])

sum_base_volume=sum([market_dict['base_volume'] for market,market_dict in markets.items()])

# assign proxy for liquidity as a fraction of base_volume to markets
for market,market_dict in markets.items():
	market_name=market_dict['MarketName']
	markets[market_name]['liquidity']=markets[market_name]['base_volume']/sum_base_volume

# get top quartile of markets by liquidity   
liquidity_90q=np.percentile([market_dict['liquidity'] for market,market_dict in markets.items()],90)
markets_90q={market:market_dict for market,market_dict in markets.items() if market_dict['liquidity']>liquidity_90q}
# GET FERTILE MARKETS/


# Create a WolfBot instance
wolf1=WolfBot(br,markets_90q,{})
print("WolfBot instance successfuly created!")
wolf1.assign_all_available_funds()
#wolf1.orders=save_orders
print("Current WolfBot funds are:{funds}".format(funds={currency:value for currency,value in wolf1.pocket_money.items() if value > 0}))


# Let the wolfbot patrol on given markets
print("The WolfBot instance starts the patrol procedure...")
for test_try in range(500):
	print("Test-try nubmer {}".format(test_try))
	for market,market_dict in markets_90q.items():
		wolf1.patrol(market_dict,0.4)
	wolf1.save_orders('order_data.json') 





# USEFUL WolfBot METHODS:
# get WolfBot's order dict
#wolf1.orders
# manualy sell an order
#wolf1.let_go(markets['BTC-VOX'],'e3f17814-f487-45ed-8edd-6383ab01666f')
# get market orders to find lost order details
#wolf1.bittrex.get_order_history('BTC-VOX')
# manualy assign order details to bot (if an instance is deleted, but order needs to be sold)
#wolf1.orders['e3f17814-f487-45ed-8edd-6383ab01666f']={'amount':24.24297209,'price':0.00004639,'value':0.00004639*24.24297209,}
# manualy buy asset
#wolf1.trade_buy(markets['BTC-NEO'],0.00423129,0.23635817918412588)
# manualy cancel an order
#wolf1.bittrex.cancel('c2721129-716a-4270-b1ea-81b412af0122')    