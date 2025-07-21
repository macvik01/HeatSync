# -*- coding: utf-8 -*-
# smart_floor_simulator.py

"""
Flask app for Smart Floor heating simulation with a multi-page dashboard.
Features:
- 24h floor heating simulation with interactive charts
- Environment Stats page with animated stats and gradient background
- About page with SNUG project and Østfold UC details
- CSV/JSON download of simulation data
"""
import os
from flask import Flask, render_template, jsonify, Response
import numpy as np
import pandas as pd
from io import StringIO

app = Flask(__name__)

def simulate(desired_temp=22, outdoor_temp=5):
    np.random.seed(0)
    prices = np.random.uniform(0.15, 0.25, 24)
    for h in [7, 8, 17, 18, 19]: prices[h] += 0.15
    room_vol, power, pcm_cap = 50, 2, 5
    loss_coeff, dt = 0.3, 1
    temps, storage = [outdoor_temp], [pcm_cap]
    grid, pcm_use = [], []
    cost = 0.0
    for hour in range(24):
        t, s, p = temps[-1], storage[-1], prices[hour]
        loss = loss_coeff * room_vol * (t - outdoor_temp) / 1000
        if t < desired_temp:
            if s > 0:
                use = min(power, s)
                s -= use
                heat = use
                grid_heat = 0
            else:
                use = 0
                grid_heat = power
                cost += grid_heat * p * dt
                heat = grid_heat
        else:
            heat = use = grid_heat = 0
        new_t = t + (heat - loss) * 0.5
        temps.append(new_t)
        storage.append(s)
        grid.append(grid_heat)
        pcm_use.append(use)
    df = pd.DataFrame({
        'Hour': list(range(24)),
        'Temperature (C)': np.round(temps[:-1], 2),
        'Grid Heating (kW)': grid,
        'PCM Use (kW)': pcm_use,
        'Price (EUR per kWh)': np.round(prices, 3)
    })
    total_cost = round(cost, 2)
    co2_saved = round(sum(pcm_use) * 0.233, 2)
    trees_equiv = round(co2_saved / 21, 2)
    return df, total_cost, co2_saved, trees_equiv

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats')
def stats():
    df, cost, co2, trees = simulate()
    table_html = df.to_html(index=False, classes='data')
    return render_template('stats.html', table_html=table_html, co2_saved=co2, trees_equiv=trees)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/data/json')
def data_json():
    df, cost, co2, trees = simulate()
    payload = df.to_dict(orient='list')
    payload.update({'Total Cost (EUR)': cost, 'CO2 Saved (kg)': co2, 'Trees Equivalent': trees})
    return jsonify(payload)

@app.route('/data/csv')
def data_csv():
    df, cost, co2, trees = simulate()
    df['Total Cost (EUR)'] = cost
    df['CO2 Saved (kg)'] = co2
    df['Trees Equivalent'] = trees
    buf = StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment;filename=simulation_report.csv'})

def ensure_template():
    base = os.path.dirname(__file__)
    tpl_dir = os.path.join(base, 'templates')
    os.makedirs(tpl_dir, exist_ok=True)
    # INDEX
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Smart Floor Dashboard</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { margin:0; font-family: Arial, sans-serif; background:#e8f5e9; color:#2e3a32; }
    header { background:#388e3c; color:#fff; padding:1rem; text-align:center; }
    header nav a { color:#fff; margin:0 1rem; text-decoration:none; }
    .container { padding:2rem; max-width:1200px; margin:auto; }
    .controls { text-align:right; margin-bottom:1rem; }
    button { background:#66bb6a; color:#fff; padding:0.7rem 1.2rem; border:none; border-radius:4px; cursor:pointer; }
    .info { font-size:1.2rem; margin-bottom:1rem; }
    .charts { display:grid; gap:1.5rem; grid-template-columns:1fr; }
    @media(min-width:768px){ .charts{ grid-template-columns:1fr 1fr;} }
    canvas { background:#fff; border-radius:8px; height:300px; }
  </style>
</head>
<body>
  <header>
    <h1>Smart Floor Live Dashboard</h1>
    <nav><a href="/">Home</a><a href="/stats">Stats</a><a href="/about">About</a></nav>
  </header>
  <div class="container">
    <div class="controls">
      <button onclick="location='/data/csv'">Download CSV</button>
      <button onclick="location='/data/json'">Download JSON</button>
    </div>
    <div class="info"><strong>Total Cost (EUR):</strong> <span id="cost">--</span></div>
    <div class="charts">
      <canvas id="chartTemp"></canvas>
      <canvas id="chartHeat"></canvas>
      <canvas id="chartPCM"></canvas>
      <canvas id="chartPrice"></canvas>
    </div>
  </div>
  <script>
    async function fetchData(){ const r = await fetch('/data/json'); return r.json(); }
    function renderChart(id, key, color) {
      const ctx = document.getElementById(id);
      fetchData().then(data => {
        new Chart(ctx, {type:'line', data:{labels:data.Hour, datasets:[{label:key, data:data[key], borderColor:color, fill:false, tension:0.2}]}, options:{responsive:true}});
      });
    }
    window.onload = () => {
      fetchData().then(d=>{ document.getElementById('cost').textContent = d['Total Cost (EUR)']; });
      renderChart('chartTemp', 'Temperature (C)', '#2e7d32');
      renderChart('chartHeat', 'Grid Heating (kW)', '#ff8f00');
      renderChart('chartPCM', 'PCM Use (kW)', '#0288d1');
      renderChart('chartPrice', 'Price (EUR per kWh)', '#d32f2f');
    };
  </script>
</body>
</html>'''
    with open(os.path.join(tpl_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    # STATS
    stats_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Environment Stats</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css">
  <style>
    body { margin:0; font-family: Arial, sans-serif;
      background: linear-gradient(135deg,#a8e063 0%,#56ab2f 100%);
      color:#fff;
    }
    header { background: rgba(34,139,34,0.85); padding:1rem; text-align:center; }
    header nav a { color:#fff; margin:0 1rem; text-decoration:none; }
    .container { background: rgba(0,0,0,0.6); padding:2rem; margin:2rem auto; max-width:800px; border-radius:8px; }
    .stats { display:flex; justify-content:space-around; margin-bottom:1rem; }
    .stat-card { background: rgba(255,255,255,0.2); padding:1rem; border-radius:8px; width:45%; text-align:center; }
    .stat-card h3 { margin:0; font-size:2.5rem; color:#ffd600; }
    table { width:100%; border-collapse:collapse; background:#fff; color:#000; }
    th,td { border:1px solid #ccc; padding:8px; text-align:center; }
    th { background:#f0f0f0; }
  </style>
</head>
<body>
  <header><h1>Environment Impact</h1><nav><a href="/">Home</a><a href="/stats">Stats</a><a href="/about">About</a></nav></header>
  <div class="container">
    <div class="stats">
      <div class="stat-card"><h3>{{ co2_saved }}</h3><p>kg CO₂ saved</p></div>
      <div class="stat-card"><h3>{{ trees_equiv }}</h3><p>Trees equivalent</p></div>
    </div>
    <h2>Simulation Readings</h2>
    {{ table_html|safe }}
  </div>
</body>
</html>'''
    with open(os.path.join(tpl_dir, 'stats.html'), 'w', encoding='utf-8') as f:
        f.write(stats_html)
    # ABOUT
    about_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>About SNUG & Østfold</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css">
  <style>
    body { margin:0; font-family: Arial, sans-serif; background:#f5f5f5; color:#333; }
    header { background:#2e7d32; color:#fff; padding:1rem; text-align:center; }
    header nav a { color:#fff; margin:0 1rem; text-decoration:none; }
    .hero { display:flex; align-items:center; justify-content:center; background:#aed581; height:250px; }
    .hero h1 { color:#1b5e20; font-size:2.5rem; }
    .container { padding:2rem; max-width:1000px; margin:auto; }
    .cards { display:grid; grid-gap:2rem; grid-template-columns:1fr; }
    @media(min-width:768px){ .cards{grid-template-columns:1fr 1fr;} }
    .card { background:#fff; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); overflow:hidden; }
    .card-content { padding:1rem; }
    .card-content h3 { margin-bottom:0.5rem; color:#2e7d32; }
    .card-content p { line-height:1.5; }
    .section { margin-top:2rem; }
    .section img { max-width:200px; margin-bottom:1rem; }
  </style>
</head>
<body>
  <header>
    <h1>SNUG Project & Østfold UC</h1>
    <nav><a href="/">Home</a><a href="/stats">Stats</a><a href="/about">About</a></nav>
  </header>
  <div class="hero"><h1>Smart Materials for Sustainable Buildings</h1></div>
  <div class="container">
    <div class="cards">
      <div class="card">
        <div class="card-content">
          <h3>SNUG Goals</h3>
          <p>Enhance building efficiency using PCM, IoT, and digital twins.</p>
        </div>
      </div>
      <div class="card">
        <div class="card-content">
          <h3>Østfold UC</h3>
          <img src="https://upload.wikimedia.org/wikipedia/commons/2/2f/%C3%98stfold_University_College_logo.png" alt="ØUC Logo">
          <p>Research in circular economy, comfort, and sustainable materials.</p>
        </div>
      </div>
    </div>
    <div class="section">
      <h2>Impact Highlights</h2>
      <ul>
        <li>Reduces peak grid load via passive storage.</li>
        <li>Optimizes energy cost with next-day price signals.</li>
        <li>Contributes to circular economy in construction materials.</li>
      </ul>
    </div>
  </div>
</body>
</html>'''
    with open(os.path.join(tpl_dir, 'about.html'), 'w', encoding='utf-8') as f:
        f.write(about_html)

if __name__ == '__main__':
    ensure_template()
    app.run(debug=True)

    ensure_template()
    app.run(debug=True)
""
