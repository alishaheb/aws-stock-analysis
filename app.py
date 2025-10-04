import io
from typing import List, Optional

from boto3 import ec2
from flask import Flask, render_template
import boto3
from flask import Flask, jsonify, request, send_file, make_response, json
import yfinance as yf
from pandas_datareader import data as pdr
import matplotlib.pyplot as plt
from datetime import date, timedelta
import random
import requests
from threading import Thread
import time  # Importing the time module for tracking

app = Flask(__name__)
yf.pdr_override()
a=1

def global_variable_definition():
    global analyze_storage
    analyze_storage = {
        "date_list": [],
        "sig_profit_loss": [],
        "tot_profit_loss": 0,
        "var95_list": [],
        "var99_list": [],
        "avg95": 0,
        "avg99": 0,
        "time": 0,
        "cost": 0,
        "h": 0,
        "d": 0,
        "t": "",
        "p": 0,
        "warmup_cost": 0,

    }


global_variable_definition()
global service
global SCALE_OUT_FACTOR
global is_terminated
service: str = "lambda"
SCALE_OUT_FACTOR: Optional[int] = None
is_terminated: bool = False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyse', methods=['POST'])
def analyse():
    # curl -X POST 127.0.0.1:8080/analyse -H "Content-Type: application/json" -d "{\"h\":101, \"d\":10000, \"t\":\"sell\", \"p\":5}"

    ##curl -X POST 127.0.0.1:8080/analyse -H "Content-Type: application/json" -d "{\"h\":101, \"d\":10000, \"t\":\"sell\", \"p\":5}"
    # curl http://127.0.0.1:8080/get_sig_vars95991
    # curl http://127.0.0.1:8080/get_sig_profit_loss1
    # curl http://127.0.0.1:8080/get_tot_profit_loss1
    # curl http://127.0.0.1:8080/get_sig_vars95991
    # curl http://127.0.0.1:8080/get_avg_vars95991
    # curl http://127.0.0.1:8080/get_time_cost1


    input = request.get_json()
    h = input.get('h')  # history
    d = input.get('d')  # days
    t = input.get('t')  # type
    p = input.get('p')  # period

    start_time = time.time()  # Start timing
    today = date.today()
    time_past = today - timedelta(days=1000)

    if service is not None and SCALE_OUT_FACTOR is not None:

        try:
            data = pdr.get_data_yahoo("AMZN", start=time_past, end=today)
            analyze_storage["date_list"] = [str(date) for date in data.index]

            url = 'https://xo87wyglig.execute-api.us-east-1.amazonaws.com/default/alico'
            headers = {'Content-Type': 'application/json'}

            ###########
            x = len(data)
            x = x / SCALE_OUT_FACTOR
            part_size = len(data) // SCALE_OUT_FACTOR

            # Split the data into 10 parts
            data_parts = [data[i * part_size:(i + 1) * part_size] for i in range(SCALE_OUT_FACTOR)]  #check if error

            # Optionally, print or work with the split data
            for index, part in enumerate(data_parts):
                print(f"Part {index + 1}:")
                print(len(part))
                print("\n")
                # URL for the POST request

                # all of the arguments should be dynamic for example "h":h####################################
                json_data = {
                    "do_warmup": False,  # Set to True if you want to warm up the service before calling the analysis
                    "body": part.values.tolist(),
                    "h": h,
                    "d": d,
                    "t": t,
                    "p": p
                }

                # Convert the DataFrame to a JSON format. Adjust columns/data as needed.
                # curl - X POST \https: // xo87wyglig.execute - api.us - east - 1.amazonaws.com / default / alico
                # Convert the DataFrame to JSON
                # json_data = json_data.to_json(orient='records')

                response = requests.post(url, headers=headers, data=json.dumps(json_data))
                response_data = response.json()
                var_sig_95 = json.loads(response_data['var95'])
                var_sig_99 = json.loads(response_data['var99'])
                profit_loss_list = json.loads(response_data['profit_loss_list'])
                # print(profit_loss_list)

                analyze_storage["sig_profit_loss"] = analyze_storage["sig_profit_loss"] + profit_loss_list
                analyze_storage["tot_profit_loss"] += sum(profit_loss_list)

                # Merge into a single dictionary
                analyze_storage["var95_list"] = analyze_storage["var95_list"] + var_sig_95
                analyze_storage["var99_list"] = analyze_storage["var99_list"] + var_sig_99
                # analyze_storage["vars9599"] = analyze_storage["vars9599"]+var9599#ERROR
                # analyze_storage["avg95"] = analyze_storage["avg95"] + sum(var_sig_95) / len(var_sig_95) if var_sig_95 else 0
                # analyze_storage["avg99"] = analyze_storage["avg99"] + sum(var_sig_99) / len(var_sig_99) if var_sig_99 else 0

            #
            # Calculate cost based on the elapsed time, assuming a rate (e.g., $0.75 per second)
            # Calculate the avg of analyze_storage["var95_list"]
            # Calculate the avg of analyze_storage["var99_list"]
            analyze_storage["avg95"] = sum(analyze_storage["var95_list"]) / len(analyze_storage["var95_list"]) if analyze_storage[
                "var95_list"] else 0
            analyze_storage["avg99"] = sum(analyze_storage["var99_list"]) / len(analyze_storage["var99_list"]) if analyze_storage[
                "var99_list"] else 0


            cost_per_second = 0.00001667

            elapsed_time = time.time() - start_time  # End timing
            total_cost = elapsed_time * cost_per_second
            analyze_storage["time"] = elapsed_time
            analyze_storage["cost"] = total_cost

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    else:
        return jsonify({"error": "Service type must be specified in warm up befor call analysis"}), 400

    return jsonify({
        "message": "Analyze done", "x": x
    })






@app.route('/get_time_cost')
def get_time_cost():
    time = analyze_storage.get('time', 0)
    cost = analyze_storage.get('cost', 0)
    return jsonify({"get_time": time, "get_cost": cost})




def warmup_thread(data):
    global service
    global SCALE_OUT_FACTOR
    service = data.get('s', None)  # 'lambda' or 'ec2'
    SCALE_OUT_FACTOR = data.get('r', 3)  # scale-out factor

    if not service:
        return jsonify({'error': 'Service type must be specified man'}), 400
    # Depending on the service, perform the necessary warmup operations
    if service.lower() == 'lambda':
        url = 'https://xo87wyglig.execute-api.us-east-1.amazonaws.com/default/alico'
        headers = {'Content-Type': 'application/json'}

        json_data = {
            'do_warmup': True,  # Set to True if you want to warm up the service before calling the analysis
            "body": [],
            "h": 0,
            "d": 0,
            "t": 0,
            "p": 0
        }

        start_time = time.time()
        response = requests.post(url, headers=headers, data=json.dumps(json_data))
        elapsed_time = time.time() - start_time
        analyze_storage["warmup_cost"] = elapsed_time * 0.00001667  # The multiplier is the cost per second

    elif service.lower() == 'ec2':
        print("Warmup for AWS EC2")
        #Warmup for AWS EC2############################################################################################################
        try:
            # Launch a new EC2 instance
            start_time = time.time()
            ec2 = boto3.resource('ec2')
            instances = ec2.create_instances(
                ImageId='ami-04572314f38f20832',  # Replace with your desired AMI ID
                MinCount=1,
                MaxCount=1,
                InstanceType='t2.micro',  # Specify the instance type
                KeyName='Ali'  # Replace with your key pair name
            )
            instance_id = instances[0].id
            print(f'New EC2 instance created with Instance ID: {instance_id}')
            analyze_storage["warmup_cost"] = (time.time() - start_time) * 0.00001667  # The multiplier is the cost per second

        except Exception as e:
            print(f'Error creating EC2 instance: {str(e)}')

    else:
        return jsonify({'error': 'Invalid service type'}), 400


@app.route('/warmup', methods=['POST'])
def warmup():
    # To call this function, use the following command:

    # curl -X POST 127.0.0.1:8080/warmup -H "Content-Type: application/json" -d "{\"s\":\"lambda\", \"r\":3}"
    global service
    global SCALE_OUT_FACTOR
    data = request.get_json()
    Thread(target=warmup_thread, args=(data,)).start()

    return jsonify({"result": "ok"})


@app.route('/scaled_ready', methods=['GET'])
def scaled_ready():
    # Check if the service is ready to handle requests
    global service
    if service is None:
        return jsonify({'error': 'Service type must be specified'}), 400
    elif service.lower() == 'lambda':
        LAMBDA_ENDPOINT = 'https://xo87wyglig.execute-api.us-east-1.amazonaws.com/default/alico'
        try:
            response = requests.get(LAMBDA_ENDPOINT)
            if response.status_code == 200:
                return jsonify({"status": "Lambda is ready", "response": response.json()}), 200
            else:
                return jsonify({"status": "Lambda is not ready", "error": response.text}), response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({"status": "Error", "message": str(e)}), 500
    elif service.lower() == 'ec2':
        pass  # TODO: To be implemented

    # is_warmup = False

    # Check if the service is ready to handle requests
    # TODO: If the service is ready, set is_warmup to True

    # return jsonify({'warm': is_warmup})




@app.route('/get_warmup_cost', methods=['GET'])
def get_warmup_cost():
    warmup_cost = analyze_storage.get('warmup_cost', 0)
    return jsonify({'warmup_cost': warmup_cost})


@app.route('/get_endpoints', methods=['GET'])
def get_endpoints():
    # Function get_stock_var
    get_stock_var_url = request.url_root + 'get_stock_var'

    # Function get_sig_vars9599
    get_sig_vars9599_url = request.url_root + 'get_sig_vars9599'

    # Function get_avg_vars9599
    get_avg_vars9599_url = request.url_root + 'get_avg_vars9599'

    # Function get_sig_profit_loss
    get_sig_profit_loss_url = request.url_root + 'get_sig_profit_loss'

    # Function get_tot_profit_loss
    get_tot_profit_loss_url = request.url_root + 'get_tot_profit_loss'

    # Function get_chart_url
    get_chart_url = request.url_root + 'get_chart_url'

    # Create a dictionary of all endpoints

    all_endpoints_dict = {
        'get_sig_vars9599': get_sig_vars9599_url,
        'get_avg_vars9599': get_avg_vars9599_url,
        'get_sig_profit_loss': get_sig_profit_loss_url,
        'get_tot_profit_loss': get_tot_profit_loss_url,
        'get_chart_url': get_chart_url
    }
    return jsonify(all_endpoints_dict)


@app.route('/get_sig_vars9599', methods=['GET'])
def get_sig_vars9599():
    return jsonify({'var95': analyze_storage['var95_list'], 'var99': analyze_storage['var99_list']})


@app.route('/get_avg_vars9599', methods=['GET'])
def get_avg_vars9599():
    return jsonify({'var95': analyze_storage['avg95'], 'var99': analyze_storage['avg99']})


@app.route('/get_sig_profit_loss', methods=['GET'])
def get_sig_profit_loss():
    return jsonify({'profit_loss': analyze_storage['sig_profit_loss']})


@app.route('/get_tot_profit_loss', methods=['GET'])
def get_tot_profit_loss():
    return jsonify({'profit_loss': analyze_storage['tot_profit_loss']})


@app.route('/get_chart_url', methods=['GET'])
def get_chart_url():
    # return "http://127.0.0.1:8080//plot.png" to get the chart as a format of a link
    # Create an HTML response that includes a clickable link
    html_content = '<p>Click <a href="http://127.0.0.1:8080//plot.png">here</a> to view the chart</p>'
    response = make_response(html_content)
    response.headers['Content-Type'] = 'text/html'
    return response


# @app.route('/get_chart_url', methods=['GET'])
@app.route('/plot.png', methods=['GET'])
def plot_vars():
    # Get the values for var95 and var99 averages as well as lists of var95 and var99 values
    avg_var_dict = get_avg_vars9599().json
    var_list = get_sig_vars9599().json
    avg_var95, avg_var99 = avg_var_dict['var95'], avg_var_dict['var99']
    var95_list, var99_list = var_list['var95'], var_list['var99']

    # Get the date list:
    date_list = analyze_storage['date_list']

    # Plot the chart using matplotlib pyplot
    plt.figure(figsize=(10, 5))
    # plot var95 and var99 values in blue and red respectively
    plt.plot(var95_list, color='blue', label='var95')
    plt.plot(var99_list, color='red', label='var99')
    # plot the average var95 and var99 values in green and magneta respectively
    plt.axhline(y=avg_var95, color='green', linestyle='--', label='avg_var95')
    plt.axhline(y=avg_var99, color='magenta', linestyle='--', label='avg_var99')

    plt.legend()
    plt.title('var95 and var99 values')
    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.grid(True)

    # Save plot to a bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=False)

@app.route('/get_audit', methods=['GET'])
def get_audit():

    # returning all params of the analyze_storage
    return jsonify(analyze_storage)

@app.route('/reset', methods=['GET'])
def reset():
    global_variable_definition()
    return jsonify({'result': 'ok'})
#
#

def termination_thread():
    global is_terminated
    global service
    global SCALE_OUT_FACTOR
    is_terminated = False

    url: str = "https://ny13rp4596.execute-api.us-east-1.amazonaws.com/default/stopallinstances"
    requests.get(url)  # Sending a GET request to the URL

    SCALE_OUT_FACTOR = None
    service = None
    is_terminated = True


@app.route('/terminate', methods=['GET'])
def terminate():
    # Initialize the termination thread on a different Thread
    Thread(target=termination_thread).start()
    return jsonify({'result': 'ok'})




@app.route('/scaled_terminated', methods=['GET'])
def scaled_terminated():
    global is_terminated
    return jsonify({'terminated': is_terminated})


# url = "https://b3st9sygqd.execute-api.us-east-1.amazonaws.com/default/stopec2"
# try:
#     response = requests.get(url)  # Sending a GET request to the URL
#     return response.text  # Returning the response from the external API to the client
# except requests.RequestException as e:
#     return jsonify({'error': str(e)}), 500  # Return an error if the request fails


# Simulation of the scaled state. You would replace this with your actual logic.


if __name__ == '__main__':
    # app.run(debug=True,port=5001)
    app.run(debug=True, port=8080, use_reloader=False)
