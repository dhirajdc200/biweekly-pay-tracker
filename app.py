from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from calendar import monthrange
from flask import flash
# from flask_login import login_required
# from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://paytracker_db_user:pjU3ATEfvRDlj00uz5NqBenfFPu9pDCJ@dpg-d12absruibrs73f19tcg-a/paytracker_db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Constants
HOURLY_RATE = 18.0
TAX_RATE = 0.17

# Models
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
    actual_net_pay = db.Column(db.Float, nullable=True)

# class AgencyShift(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     shift_date = db.Column(db.Date, nullable=False)
#     start_time = db.Column(db.Time, nullable=False)
#     end_time = db.Column(db.Time, nullable=False)
#     location = db.Column(db.String, nullable=False)
#     hourly_rate = db.Column(db.Float, nullable=False)
#     break_minutes = db.Column(db.Integer, default=0)

# Helper functions
def get_pay_period(d):
    if 1 <= d.day <= 15:
        label = f"{d.year} {d.month:02d} 01 to 15"
        pay_day = date(d.year, d.month, 20)
    else:
        last_day = monthrange(d.year, d.month)[1]
        label = f"{d.year} {d.month:02d} 16 to {last_day}"
        pay_day = date(d.year + 1, 1, 5) if d.month == 12 else date(d.year, d.month + 1, 5)
    return label, pay_day

# Routes
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

    entries = WorkEntry.query.order_by(WorkEntry.work_date.desc()).all()
    summary = {}
    day_details = []

    for entry in entries:
        label, payday = get_pay_period(entry.work_date)
        start_dt = datetime.combine(entry.work_date, entry.start_time)
        end_dt = datetime.combine(entry.work_date, entry.end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        hours = (end_dt - start_dt).total_seconds() / 3600

        day_details.append({
            'id': entry.id,
            'date': entry.work_date.strftime('%Y-%m-%d'),
            'start': entry.start_time.strftime('%H:%M'),
            'end': entry.end_time.strftime('%H:%M'),
            'hours': round(hours, 2)
        })

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

    return render_template('index.html', unpaid_periods=unpaid_periods, paid_periods=paid_periods, day_details=day_details, today=date.today())

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

@app.route('/mark_unpaid/<period_label>', methods=['POST'])
def mark_unpaid(period_label):
    status = PayPeriodStatus.query.filter_by(label=period_label).first()
    if status:
        status.is_paid = False
        status.paid_on = None
        db.session.add(status)
        db.session.commit()
    return redirect('/')

@app.route('/update_actual_pay/<period_label>', methods=['POST'])
def update_actual_pay(period_label):
    actual_net = request.form.get('actual_net')
    pay_period = PayPeriodStatus.query.filter_by(label=period_label).first()


    if pay_period:
        pay_period.actual_net_pay = float(actual_net)
        db.session.commit()
        flash(f"Actual pay for {period_label} updated!", "success")
    else:
        flash("Pay period not found.", "danger")

    return redirect(url_for('index'))


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

# @app.route('/agency', methods=['GET', 'POST'])
# def agency():
#     if request.method == 'POST':
#         shift_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
#         start_time = datetime.strptime(request.form['start'], '%H:%M').time()
#         end_time = datetime.strptime(request.form['end'], '%H:%M').time()
#         location = request.form['location']
#         hourly_rate = float(request.form['rate'])
#         break_minutes = int(request.form['break']) if request.form['break'] else 0

#         new_shift = AgencyShift(
#             shift_date=shift_date,
#             start_time=start_time,
#             end_time=end_time,
#             location=location,
#             hourly_rate=hourly_rate,
#             break_minutes=break_minutes
#         )
#         db.session.add(new_shift)
#         db.session.commit()
#         return redirect('/agency')

#     shifts = AgencyShift.query.order_by(AgencyShift.shift_date.desc()).all()
#     weekly_summary = {}

#     for shift in shifts:
#         week_start = shift.shift_date - timedelta(days=shift.shift_date.weekday())
#         week_label = f"{week_start} to {week_start + timedelta(days=6)}"

#         start_dt = datetime.combine(shift.shift_date, shift.start_time)
#         end_dt = datetime.combine(shift.shift_date, shift.end_time)
#         if end_dt <= start_dt:
#             end_dt += timedelta(days=1)
#         total_hours = (end_dt - start_dt).total_seconds() / 3600 - (shift.break_minutes / 60)
#         total_hours = max(0, round(total_hours, 2))
#         gross = total_hours * shift.hourly_rate
#         net = gross * (1 - TAX_RATE)

#         if week_label not in weekly_summary:
#             weekly_summary[week_label] = {
#                 'total_hours': 0.0,
#                 'gross': 0.0,
#                 'net': 0.0,
#                 'shifts': []
#             }

#         weekly_summary[week_label]['total_hours'] += total_hours
#         weekly_summary[week_label]['gross'] += gross
#         weekly_summary[week_label]['net'] += net
#         weekly_summary[week_label]['shifts'].append({
#             'date': shift.shift_date.strftime('%Y-%m-%d'),
#             'location': shift.location,
#             'start': shift.start_time.strftime('%H:%M'),
#             'end': shift.end_time.strftime('%H:%M'),
#             'break': shift.break_minutes,
#             'hours': total_hours,
#             'rate': shift.hourly_rate,
#             'gross': round(gross, 2),
#             'net': round(net, 2)
#         })

#     return render_template('agency.html', weekly=weekly_summary, shifts=shifts)
# @app.route('/edit_agency_shift/<int:shift_id>', methods=['GET', 'POST'])
# def edit_agency_shift(shift_id):
#     shift = AgencyShift.query.get_or_404(shift_id)
#     if request.method == 'POST':
#         shift.shift_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
#         shift.start_time = datetime.strptime(request.form['start'], '%H:%M').time()
#         shift.end_time = datetime.strptime(request.form['end'], '%H:%M').time()
#         shift.location = request.form['location']
#         shift.hourly_rate = float(request.form['rate'])
#         shift.break_minutes = int(request.form['break']) if request.form['break'] else 0
#         db.session.commit()
#         return redirect('/agency')
#     return render_template('edit_agency.html', shift=shift)

# @app.route('/delete_agency_shift/<int:shift_id>', methods=['POST'])
# def delete_agency_shift(shift_id):
#     shift = AgencyShift.query.get_or_404(shift_id)
#     db.session.delete(shift)
#     db.session.commit()
#     return redirect('/agency')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=10000)
