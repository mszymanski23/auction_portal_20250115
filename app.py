import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask import session
import random
import time
import csv
from flask import send_file
import io
import locale
from babel.numbers import format_currency, format_number, format_decimal
from decimal import Decimal, ROUND_DOWN
import threading
from datetime import timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'play'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
#locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')

# Set up logging
logger = logging.getLogger()
# Disable werkzeug logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Set to ERROR to suppress INFO logs

#log = logging.getLogger('werkzeug')
#log.setLevel(logging.Error)  # Ustawienie logowania na ERROR, żeby wyciszyć INFO i DEBUG

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Log everything from DEBUG level and above
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# File handler
file_handler = logging.FileHandler('auction_system.log')
#file_handler.setLevel(logging.DEBUG)  # Log everything from DEBUG level and above
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Add both handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Lista użytkowników
users = ['telekom1', 'telekom2', 'telekom3', 'telekom4']
start_price_value = 356000
logged_in_users = {}


auction_data = {
    'round_time': 60,
    'break_time': 5,
    'start_price': 356000,
    'bid_increment': 7120,
    'current_round': 0,
    'status': 'waiting',
    'bids': [],
    'results': [],
    'current_leaders': {block: None for block in ['A', 'B', 'C', 'D', 'E', 'F', 'G']},
    'block_data': {
        'A': {'start_price': start_price_value, 'bid_increment': round(start_price_value * 0.02), 'bid_amount': round(start_price_value * 1.02)},
        'B': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)},
        'C': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)},
        'D': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)},
        'E': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)},
        'F': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)},
        'G': {'start_price': 356000, 'bid_increment': round(356000 * 0.02), 'bid_amount': round(356000 * 1.02)}
    }
}
auction_data['total_bids_left'] = len(logged_in_users) * 2  # Each user has 2 bids

def check_if_all_users_bid():
    """
    Check if all active users have placed their bids in the current round.
    """
    active_users = [user for user, data in logged_in_users.items() if data.get('active', True)]
    current_round_bids = [bid for bid in auction_data['bids'] if bid['round'] == auction_data['current_round']]

    # Check if each active user has placed at least one bid
    for user in active_users:
        user_bids = [bid for bid in current_round_bids if bid['user'] == user]
        if not user_bids:
            return False  # At least one active user hasn't bid yet
    return True  # All active users have bid

@app.route('/')
def index():
    return render_template('index.html',
                           users=users,
                           logged_in_users=logged_in_users,
                           auction_status=auction_data['status'])


@app.route('/login/<username>')
def login(username):
    if username not in users:
        logger.warning(f"Login attempt for non-existent user: {username}")
        return "User does not exist."


    session['username'] = username  # Set the session username
    session['logged_in'] = True

    session.permanent = False  # Sessions expire when the browser is closed
    logger.info(f"User {username} logged in.")
    logged_in_users[username] = {'bids': 0, 'active': True, 'skips': 2}
    logger.warning(logged_in_users )
    return redirect(url_for('user_panel', username=username))

@app.route('/user/<username>')
def user_panel(username):
    # Check if the user is logged in
    session_username = session.get('username')
    if session_username != username or username not in logged_in_users:
        logger.warning(f"L 117 Unauthorized access attempt by user: {username}")
        return redirect(url_for('index'))  # Redirect to the index page

    # if session_username != username or auction_data.get('logout_all', False):
    #     logger.warning(f"L129 Unauthorized access attempt by user: {username}")
    #     return redirect(url_for('index'))  # Redirect to the index page

        # Check if the user is logged in
    if username not in logged_in_users:
        logger.warning(f"L134 Unauthorized access attempt by user: {username}")
        return redirect(url_for('index'))  # Redirect to the index page


    if not logged_in_users[username]['active']:
        return "You have been excluded from the auction for not bidding in the first round."

    #user_bids = [bid for bid in auction_data['bids'] if bid['user'] == username] # passing bids only made by user
    #user_bids = [bid for bid in auction_data['bids'] ] # passing all bids
    #user_bids = [bid for bid in auction_data['bids'] if bid['round'] < auction_data['current_round'] or (bid['user'] == username and bid['round'] == auction_data['current_round'])]
    user_bids = [bid for bid in auction_data['bids'] if (bid['user'] == username and bid['round'] == auction_data['current_round'])] # current bids
    logger.warning(f' L 137 user_bids {user_bids} fro username {username}')

    available_bids = 2
    remaining_time = get_remaining_time()  # Calculate remaining time dynamically

    # Calculate sums
    current_lead_blocks = [block for block, leader in auction_data['current_leaders'].items() if leader == username]
    current_sum = sum(auction_data['block_data'][block]['start_price'] for block in current_lead_blocks)

    previous_round_bids = [bid for bid in auction_data['bids'] if bid['round'] < auction_data['current_round']  and bid['user'] == username]

        # Calculate 2% of start price and 1.02 * start price for each block
    for block, data in auction_data['block_data'].items():
        data['default_bid_increment'] = round(data['start_price'] * 0.02, 2)
        data['default_bid_amount'] = round(data['start_price'] * 1.02, 2)

    return render_template('user.html',
                           user=username,
                           auction_data=auction_data,
                           user_bids=user_bids,
                           user_data=logged_in_users[username],
                           available_bids=available_bids,
                           remaining_time=remaining_time,
                           current_sum=current_sum,
                           previous_round_bids=previous_round_bids,
                           )

@app.route('/admin')
def admin():
    logger.info("Rendering admin panel.")
    return render_template('admin.html', auction_data=auction_data, logged_in_users=logged_in_users)

# Update start_auction to use the background version
@app.route('/start_auction', methods=['GET', 'POST'])
def start_auction():
    if request.method == 'POST':
        delay = request.form.get('delay', type=int, default=0)
        round_time = request.form.get('round_time', type=int, default=60)

        if delay > 0:
            logger.info(f"Delaying auction start for {delay} seconds...")
            time.sleep(delay)

        auction_data['round_time'] = round_time

    logger.info("Starting a new auction.")
    auction_data['current_round'] = 1
    auction_data['status'] = 'running'
    auction_data['bids'] = []
    auction_data['results'] = []
    auction_data['current_leaders'] = {block: None for block in ['A', 'B', 'C', 'D', 'E', 'F', 'G']}
    auction_data['round_start_time'] = time.time()
    auction_data['total_bids_left'] = len(logged_in_users) * 2

    initial_start_price = 356000
    initial_bid_increment = 7120
    for block in auction_data['block_data']:
        auction_data['block_data'][block]['start_price'] = initial_start_price
        auction_data['block_data'][block]['bid_increment'] = initial_bid_increment

    logger.warning(f"Auction data reset: {auction_data}")
    auction_data['active_bidders'] = list(logged_in_users.keys())

    # Schedule the round end using the background version
    non_blocking_delay(auction_data['round_time'], end_round_background)

    return redirect(url_for('admin'))

@app.route('/place_bid', methods=['POST'])
def place_bid():
    user = request.form['user']
    block = request.form['block']
    bid_percentage = int(request.form.get('bid_percentage', 2))  # Default to 2% if not provided

    # Step 2: Calculate the bid amount
    start_price = auction_data['block_data'][block]['start_price']
    bid_increment = round(start_price * (bid_percentage / 100))
    amount = round(start_price + bid_increment)


    if logged_in_users[user]['bids'] < 2:
        auction_data['bids'].append({'user': user, 'block': block, 'amount': amount, 'round': auction_data['current_round']})
        logged_in_users[user]['bids'] += 1
        auction_data['current_leaders'][block] = user

        logger.warning(f"User {user} placed a bid of {amount} on block {block}.")
        auction_data['total_bids_left'] -= 1
        print(f"--------------------------------------------------------------------------Total bids left: {auction_data['total_bids_left']}")
        logger.warning(f"Total bids left: {auction_data['total_bids_left']}")

        #return jsonify(success=False, message="You have reached your bid limit.")
        # Check if all bids have been used
        # Check if all bids have been used and the round number is greater than 1
        if auction_data['total_bids_left'] == 0:

        #if auction_data['total_bids_left'] == 0 and auction_data['current_round'] > 1:
            logger.info("All bids have been used. Ending the round after a 5-second delay.")
            end_round()

        # Check if all users have bid   # old solution
        #if check_if_all_users_bid():
        #    logger.warning("All users have placed their bids. Ending the round.")
        #    end_round()

    return redirect(url_for('user_panel', username=user))

@app.route('/skip_round/<username>')
def skip_round(username):
    # Check if the user has skips remaining
    if logged_in_users[username]['skips'] > 0:
        logged_in_users[username]['skips'] -= 1
        logger.info(f"User {username} skipped the round. Remaining skips: {logged_in_users[username]['skips']}")

        # Add a special bid to indicate skipping
        auction_data['bids'].append({
            'user': username,
            'block': 'A',
            'amount': 0,
            'round': auction_data['current_round'],
            'is_success': 'skipped'
        })
    else:
        logger.warning(f"User {username} attempted to skip but has no skips left.")

    return redirect(url_for('user_panel', username=username))

@app.route('/send_results')
def send_results():
    auction_data['status'] = 'running'
    auction_data['round_start_time'] = time.time()

    for user in logged_in_users:
        logged_in_users[user]['bids'] = 0

    # Calculate total_bids_left based on current leaders
    total_bids_left = 0
    for user in logged_in_users:
        blocks_led = sum(1 for block, leader in auction_data['current_leaders'].items() if leader == user)
        bids_left_for_user = 2 - blocks_led
        total_bids_left += bids_left_for_user

    auction_data['total_bids_left'] = total_bids_left
    logger.info(f"Auction results sent and auction reset. Total bids left: {total_bids_left}")

    # Schedule the next round end in a background thread
    non_blocking_delay(auction_data['round_time'], end_round_background)

    return jsonify(success=True)  # Return a JSON response instead of redirecting

@app.route('/end_round')
def end_round():
    """Handle end of round state changes."""
    auction_data['status'] = 'break'
    auction_data['current_round'] += 1
    logger.info(f"Round {auction_data['current_round']} ended. Determining winners...")
    determine_winners()

    # Update block_data to store bids from the last round
    for block in auction_data['block_data']:
        previous_round_bids = [bid for bid in auction_data['bids']
                            if bid['round'] == auction_data['current_round'] - 1
                            and bid['block'] == block]
        auction_data['block_data'][block]['bids_last_round'] = len(previous_round_bids)

    previous_round_bids = [bid for bid in auction_data['bids']
                          if bid['round'] == max(auction_data['current_round'] - 1, 1)]

    if not previous_round_bids:
        logger.info("No bids were placed during the last round. Ending the auction.")
        auction_data['status'] = 'finished'
        return redirect(url_for('admin'))

    update_auction_table()
    auction_data['round_start_time'] = time.time()
    logger.info("Round results updated, auction table refreshed.")

    # Run the break and send_results in a background thread
    def background_task():
        time.sleep(auction_data['break_time'])
        try:
            with app.app_context():
                send_results()
        except Exception as e:
            logger.error(f"Error in background task: {e}")

    # Start the background thread
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()

    return redirect(url_for('admin'))

def end_round_background():
    """Version of end_round for background thread that doesn't return HTTP response."""
    auction_data['status'] = 'break'
    auction_data['current_round'] += 1
    logger.info(f"Round {auction_data['current_round']} ended. Determining winners...")
    determine_winners()

    # Update block_data to store bids from the last round
    for block in auction_data['block_data']:
        previous_round_bids = [bid for bid in auction_data['bids']
                            if bid['round'] == auction_data['current_round'] - 1
                            and bid['block'] == block]
        auction_data['block_data'][block]['bids_last_round'] = len(previous_round_bids)

    previous_round_bids = [bid for bid in auction_data['bids']
                          if bid['round'] == max(auction_data['current_round'] - 1, 1)]

    if not previous_round_bids:
        logger.info("No bids were placed during the last round. Ending the auction.")
        auction_data['status'] = 'finished'
        return

    update_auction_table()
    auction_data['round_start_time'] = time.time()
    logger.info("Round results updated, auction table refreshed.")

    time.sleep(auction_data['break_time'])
    try:
        with app.app_context():
            send_results()
    except Exception as e:
        logger.error(f"Error in background thread send_results: {str(e)}")

def determine_winners():
    results = {}
    # Only consider bids from the previous round
    previous_round_bids = [bid for bid in auction_data['bids'] if bid['round'] == auction_data['current_round'] - 1]

    for bid in previous_round_bids:
        bid['is_success'] = "no"
        block = bid['block']
        if block not in results:
            results[block] = []
        results[block].append(bid)

    auction_data['results'] = []
    for block, bids in results.items():
        if len(bids) == 0:
            auction_data['current_leaders'][block] = None
        else:
            # Sort bids in descending order of amount
            sorted_bids = sorted(bids, key=lambda x: x['amount'], reverse=True)
            max_amount = sorted_bids[0]['amount']
            highest_bids = [bid for bid in sorted_bids if bid['amount'] == max_amount]

            # Handle ties by selecting a random winner
            if len(highest_bids) > 1:
                winner = random.choice(highest_bids)
            else:
                winner = highest_bids[0]

            for bid in bids:
                if bid == winner:
                    bid['is_success'] = "yes"

            auction_data['results'].append(winner)
            auction_data['current_leaders'][block] = winner['user']

def determine_bidders():
    """Calculate how many bids each user still needs to place for the current round."""
    required_bids_per_user = {}

    for user, user_data in logged_in_users.items():
        total_bids_auction_attempt = len([bid for bid in auction_data['bids'] if bid['round'] == auction_data['current_round']])

        return required_bids_per_user

def update_auction_table():
    for result in auction_data['results']:
        block = result['block']
        # Aktualizuj cenę początkową i przyrost dla konkretnego bloku
        auction_data['block_data'][block]['start_price'] = result['amount']
        auction_data['block_data'][block]['bid_increment'] = round(result['amount'] * 0.02)
        logger.debug(f"Updated auction table for block {block}: Start Price = {auction_data['block_data'][block]['start_price']}, Bid Increment = {auction_data['block_data'][block]['bid_increment']}")

@app.route('/get_auction_data')
def get_auction_data():
    # Calculate total_bids_left and user_bids_left
    total_bids_left = 0
    user_bids_left = {}
    for user in logged_in_users:
        # Count the number of blocks where the user is the current leader
        blocks_led = sum(1 for block, leader in auction_data['current_leaders'].items() if leader == user)
        # Each user has 2 bids, but they cannot bid on blocks they are already leading
        bids_left_for_user = 2 - blocks_led
        user_bids_left[user] = bids_left_for_user
        total_bids_left += bids_left_for_user

    return jsonify({
        'status': auction_data['status'],
        'current_round': auction_data['current_round'],
        'results': auction_data['results'],
        'bids': auction_data['bids'],
        'block_data': auction_data['block_data'],
        'current_leaders': auction_data['current_leaders'],
        'logged_in_users': logged_in_users,
        'total_bids_left': total_bids_left,  # Add total_bids_left to the response
        'user_bids_left': user_bids_left  # Add user_bids_left to the response
    })

@app.route('/check_status')
def check_status():
    return jsonify(status=auction_data['status'], round=auction_data['current_round'])

def get_remaining_time():

    if 'round_start_time' not in auction_data or auction_data['status'] in ['finished', 'waiting']:
        return 0  # No active round
    elapsed_time = time.time() - auction_data['round_start_time']
    if auction_data['status'] == 'running':
        remaining = max(0, auction_data['round_time'] - int(elapsed_time))
    elif auction_data['status'] == 'break':
        remaining = max(0, auction_data['break_time'] - int(elapsed_time))
    else:
        remaining = 0  # Default case if status is unexpected

    logger.info(f"remaining time: {remaining}")
    return remaining

@app.route('/export_auction_table')
def export_auction_table():
    # Create a CSV file with the auction table
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['Block', 'Final Price', 'Winner']) # Header row
    for block, data in auction_data['block_data'].items():
        writer.writerow([block, data['start_price'], auction_data['current_leaders'][block]])

    # Prepare the in-memory file for sending
    csv_buffer.seek(0)  # Move the cursor to the start of the file
    return send_file(
        io.BytesIO(csv_buffer.getvalue().encode('utf-8')),  # Convert StringIO content to bytes
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"auction_table_results.csv"
    )

@app.route('/logout', methods=['POST'])
def logout():
    username = session.get('username')
    # Clear the session variables related to the user
    session.pop('username', None)
    session.pop('logged_in', None)
    # Optionally, remove the user from logged_in_users

    if username in logged_in_users:
        del logged_in_users[username]
    logger.info("User logged out.")
    print(f'username {username} has logout')
    return redirect(url_for('index'))

@app.route('/logout_all_users', methods=['POST'])
def logout_all_users():
    auction_data['logout_all'] = True # is it necessary?
    logged_in_users.clear()
    auction_data['status'] = 'break'
    logger.info("Admin logged out all users.")
    print("Admin logged out all users.")
    auction_data['logout_all'] = False
    return redirect(url_for('admin'))

@app.route('/check_logout_status')
def check_logout_status():
    return jsonify({'logout_all': auction_data.get('logout_all', False)})

@app.route('/get_logged_in_users')
def get_logged_in_users():
    return jsonify(logged_in_users)

@app.route('/export_my_bids/<username>')
def export_my_bids(username):
    # Validate the username
    if username not in logged_in_users:
        logger.warning(f"Export attempt for non-existent user: {username}")
        #return abort(404, description="User does not exist.")

    # Filter the user's bids
    user_bids = [bid for bid in auction_data['bids']]
    if not user_bids:
        logger.info(f"No bids found for user: {username}")
        #return abort(404, description="No bids available for export.")

    # Create an in-memory CSV file
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['Round', 'Block', 'Amount', 'User', 'Status'])  # Header row
    for bid in user_bids:
        writer.writerow([bid['round'], bid['block'], bid['amount'], bid['user'], bid['is_success']])

    # Prepare the in-memory file for sending
    csv_buffer.seek(0)  # Move the cursor to the start of the file
    return send_file(
        io.BytesIO(csv_buffer.getvalue().encode('utf-8')),  # Convert StringIO content to bytes
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"{username}_bids.csv"
    )

def format_price(price):
    price_str = str(price)
    price_clean = price_str.split('.')[0]
    # Format the string with a space before the last three digits
    formatted_number = f"{price_clean[:-3]} {price_clean[-3:]} zł"
    return formatted_number

@app.template_filter('format_price')
def format_price_filter(value):
    return format_price(value)


def non_blocking_delay(duration, callback):
    """Run a delay without blocking the main thread."""
    def delayed_execution():
        time.sleep(duration)
        try:
            with app.app_context():
                callback()
        except Exception as e:
            logger.error(f"Error in delayed execution: {e}")

    thread = threading.Thread(target=delayed_execution)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    app.run(debug=True)
