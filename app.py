from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, send_file
from flask_socketio import SocketIO

from db_models.payment import Payment
from payments.pix import Pix
from repository.database import db

app = Flask(__name__)

app.config["SECRET_KEY"] = "test"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

db.init_app(app)
socketio = SocketIO(app)


@app.route("/payments/pix", methods=['POST'])
def create_payment_pix():
    data = request.get_json()

    if "value" not in data:
        return jsonify({"message": "Invalid value"}), 400

    expiration_date = datetime.now() + timedelta(minutes=30)

    new_payment = Payment(value=data["value"], expiration_date=expiration_date)

    pix_obj = Pix()
    data_payment_pix = pix_obj.create_payment()
    new_payment.bank_payment_id = data_payment_pix["bank_payment_id"]
    new_payment.qr_code = data_payment_pix["qr_code_path"]

    new_payment.save()

    return jsonify({
        "message": "The payment has been created",
        "payment": new_payment.to_dict()
    }), 201


@app.route("/payments/pix/qr_code/<file_name>", methods=["GET"])
def get_qr_code(file_name):
    return send_file(f"static/img/{file_name}.png", mimetype="image/png"), 200


@app.route("/payments/pix/confirmation", methods=['POST'])
def pix_confirmation():
    data = request.get_json()
    bank_payment_id = data.get("bank_payment_id")
    value = data.get("value")

    if not bank_payment_id and not value:
        return jsonify({"message": "Invalid bank_payment_id"}), 400

    payment = Payment.query.filter_by(bank_payment_id=bank_payment_id).first()

    if not payment or payment.paid:
        return jsonify({"message": "Payment not found"}), 404

    if value != payment.value:
        return jsonify({"message": "Invalid value"}), 400

    payment.paid = True
    db.session.commit()
    socketio.emit(f"payment-confirmed-{payment.id}")

    return jsonify({"message": "The payment has been confirmed"}), 200


@app.route("/payments/pix/<int:payment_id>", methods=['GET'])
def payment_pix_page(payment_id):
    payment = Payment.query.get(payment_id)
    print(payment)

    if not payment:
        return render_template("404.html"), 404

    if payment.paid:
        return render_template(
            "confirmed_payment.html",
            payment_id=payment.id,
            value=payment.value
        ), 200

    return render_template(
        "payment.html",
        payment_id=payment.id,
        value=payment.value,
        qr_code=payment.qr_code
    ), 200


# websockets
@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(app, debug=True)
