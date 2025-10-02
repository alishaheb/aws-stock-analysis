import json
import random


def lambda_handler(event, context):
    do_warmup: bool = event['do_warmup']

    if do_warmup is True:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "warmup": json.dumps("Warmup successful")
        }

    data = event['body']
    h = event['h']
    d = event['d']
    t = event['t']
    p = event['p']
    r = event['r']
    for raw_data in data:
        data_open, data_high, data_low, data_close, data_adj_close, data_volume = raw_data
        # Append data_buy and data_sell to the raw_data list and substitute the raw_data list with the new list
        raw_data.append(0)  # data_buy
        raw_data.append(0)

    body_threshold = 0.01
    for i in range(2, len(data)):
        data_open, data_high, data_low, data_close, data_adj_close, data_volume, data_buy, data_sell = data[i]
        # Read i-1 and i-2 data
        data_open_1, data_high_1, data_low_1, data_close_1, data_adj_close_1, data_volume_1, data_buy_1, data_sell_1 = \
        data[i - 1]
        data_open_2, data_high_2, data_low_2, data_close_2, data_adj_close_2, data_volume_2, data_buy_2, data_sell_2 = \
        data[i - 2]
        # Trading signal logic
        if (data_close - data_open) >= body_threshold and data_close > data_close_1 and \
                (data_close_1 - data_open_1) >= body_threshold and data_close_1 > data_close_2 and \
                (data_close_2 - data_open_2) >= body_threshold:
            data_buy = 1
        if (data_open - data_close) >= body_threshold and data_close < data_close_1 and \
                (data_open_1 - data_close_1) >= body_threshold and data_close_1 < data_close_2 and \
                (data_open_2 - data_close_2) >= body_threshold:
            data_sell = 1
        data[i] = [data_open, data_high, data_low, data_close, data_adj_close, data_volume, data_buy, data_sell]

    # VAR calculations
    var95_list, var99_list = [], []
    # Profit calculations
    profit_loss_list = []

    for i in range(h, len(data)):
        if data[i][6] == 1:
            data_close_list = [data[j][3] for j in range(i - h, i)]
            percent_change_list = [data_close_list[j] / data_close_list[j - 1] - 1 for j in range(1, h)]
            mean = sum(percent_change_list) / h
            std = (sum([(percent_change_list[j] - mean) ** 2 for j in range(h - 1)]) / h) ** 0.5
            simulated = [random.gauss(mean, std) for _ in range(d)]
            simulated.sort(reverse=True)
            var95 = simulated[int(len(simulated) * 0.95)]
            var99 = simulated[int(len(simulated) * 0.99)]
            var95_list.append(var95)
            var99_list.append(var99)
            # Profit/Loss calculation for p days
            if i + p < len(data):  # Ensure we have enough data
                future_price = data[i + p][3]
                initial_price = data[i][3]
                if t == 'buy':
                    profit_loss = future_price - initial_price
                elif t == 'sell':
                    profit_loss = initial_price - future_price
                profit_loss_list.append(profit_loss)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "history": json.dumps(h),
        "d": json.dumps(d),
        "t": json.dumps(t),
        "p": json.dumps(p),
        "body": json.dumps(data),
        "var95": json.dumps(var95_list),
        "var99": json.dumps(var99_list),
        "profit_loss_list": json.dumps(profit_loss_list)
    }
