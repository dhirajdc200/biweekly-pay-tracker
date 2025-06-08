from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from calendar import monthrange

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# DB config
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://paytracker_db_user:pjU3ATEfvRDlj00uz5NqBenfFPu9pDCJ@dpg-d12absruibrs73f19tcg-a/paytracker_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Constants
HOURLY_RATE = 18.0
TAX_RATE = 0.17

# Database models
class WorkEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

class PayPeriodStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String, unique=True)
    is_paid = db.Column(db.Boolean, default=False)
    paid_on = db.Column(db.Date)

# Helpers
def get_pay_period(d):
    if 1 <= d.day <= 15:
        label = f"{d.year} {d.month:02d} 01 to 15"
        pay_day = date(d.year, d.month, 20)
    else:
        last_day = monthrange(d.year, d.month)[1]
        label = f"{d.year} {d.month:02d} 16 to {last_day}"
        pay_day = date(d.year + 1, 1, 5) if d.month == 12 else date(d.year, d.month + 1, 5)
    return label, pay_day

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        work_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form['start'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end'], '%H:%M').time()
        entry = WorkEntry(work_date=work_date, start_time=start_time, end_time=end_time)
        db.session.add(entry)
        db.session.commit()
        return redirect('/')

    entries = WorkEntry.query.order_by(WorkEntry.work_date).all()
    summary = {}
    for entry in entries:
        label, payday = get_pay_period(entry.work_date)
        start_dt = datetime.combine(entry.work_date, entry.start_time)
        end_dt = datetime.combine(entry.work_date, entry.end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        hours = (end_dt - start_dt).total_seconds() / 3600

        if label not in summary:
            summary[label] = {'total_hours': 0.0, 'payday': payday}
        summary[label]['total_hours'] += hours

    unpaid_periods = []
    paid_periods = []

    for label, data in summary.items():
        gross = data['total_hours'] * HOURLY_RATE
        net = gross * (1 - TAX_RATE)
        data['gross'] = round(gross, 2)
        data['net'] = round(net, 2)

        status = PayPeriodStatus.query.filter_by(label=label).first()
        if status and status.is_paid:
            paid_periods.append({
                'label': label,
                'total_hours': round(data['total_hours'], 2),
                'gross': data['gross'],
                'net': data['net'],
                'payday': data['payday'],
                'paid_on': status.paid_on.strftime('%Y-%m-%d')
            })
        else:
            unpaid_periods.append({
                'label': label,
                'total_hours': round(data['total_hours'], 2),
                'gross': data['gross'],
                'net': data['net'],
                'payday': data['payday']
            })

    return render_template('index.html', unpaid_periods=unpaid_periods, paid_periods=paid_periods, today=date.today())

@app.route('/mark_paid/<period_label>', methods=['POST'])
def mark_paid(period_label):
    status = PayPeriodStatus.query.filter_by(label=period_label).first()
    if not status:
        status = PayPeriodStatus(label=period_label)
    status.is_paid = True
    status.paid_on = date.today()
    db.session.add(status)
    db.session.commit()
    return redirect('/')

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
def edit_entry(entry_id):
    entry = WorkEntry.query.get_or_404(entry_id)
    if request.method == 'POST':
        entry.work_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        entry.start_time = datetime.strptime(request.form['start'], '%H:%M').time()
        entry.end_time = datetime.strptime(request.form['end'], '%H:%M').time()
        db.session.commit()
        return redirect('/')
    return render_template('edit.html', entry=entry)

@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    entry = WorkEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=10000)
