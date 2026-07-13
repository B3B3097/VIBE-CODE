from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Load environment variables
AD_PARTNER_URL = os.getenv('AD_PARTNER_URL')
FK_WALLET_API_KEY = os.getenv('FK_WALLET_API_KEY')

@app.route('/view_ad', methods=['POST'])
def view_ad():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400
    
    # Simulate viewing an ad
    ad_viewed = True
    
    if ad_viewed:
        return jsonify({'message': 'Ad viewed successfully'}), 200
    else:
        return jsonify({'error': 'Failed to view ad'}), 500

@app.route('/request_withdrawal', methods=['POST'])
def request_withdrawal():
    user_id = request.json.get('user_id')
    amount = request.json.get('amount')
    
    if not user_id or not amount:
        return jsonify({'error': 'User ID and amount are required'}), 400
    
    # Simulate withdrawal request
    withdrawal_successful = True
    
    if withdrawal_successful:
        # Notify admin about the withdrawal request
        notify_admin(user_id, amount)
        
        return jsonify({'message': 'Withdrawal request submitted successfully'}), 200
    else:
        return jsonify({'error': 'Failed to submit withdrawal request'}), 500

def notify_admin(user_id, amount):
    # Simulate sending a notification to the admin
    print(f"Admin Notification: User {user_id} requested withdrawal of {amount}")

if __name__ == '__main__':
    app.run(debug=True)