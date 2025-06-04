from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

HOURLY_RATE = 18.0
TAX_RATE = 0.17

class WorkEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    def __repr__(self):
        return f"<WorkEntry {self.work_date} {self.start_time}-{self.end_time}>"

def get_pay_period(d):
    if 1 <= d.day <= 15:
        pay_day = date(d.year, d.month, 20)
        label = f"{d.strftime('%Y-%m')}-01_to_15"
    else:
        if d.month == 12:
            pay_day = date(d.year + 1, 1, 5)
        else:
            pay_day = date(d.year, d.month + 1, 5)
        label = f"{d.strftime('%Y-%m')}-16_to_end"
    return label, pay_day

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date_str = request.form['date']
        start_str = request.form['start']
        end_str = request.form['end']

        work_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()

        start_dt = datetime.combine(work_date, start_time)
        end_dt = datetime.combine(work_date, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        entry = WorkEntry(work_date=work_date, start_time=start_time, end_time=end_time)
        db.session.add(entry)
        db.session.commit()
        return redirect('/')

    entries = WorkEntry.query.order_by(WorkEntry.work_date).all()
    summary = {}
    day_details = []
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

        day_details.append({
            'id': entry.id,
            'date': entry.work_date.strftime('%b %d'),
            'start': entry.start_time.strftime('%I:%M %p'),
            'end': entry.end_time.strftime('%I:%M %p'),
            'hours': round(hours, 2)
        })

    for period in summary:
        hours = summary[period]['total_hours']
        gross = hours * HOURLY_RATE
        net = gross * (1 - TAX_RATE)
        summary[period]['gross'] = round(gross, 2)
        summary[period]['net'] = round(net, 2)

    today = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', summary=summary, today=today, day_details=day_details)

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
    app.run(debug=True)
