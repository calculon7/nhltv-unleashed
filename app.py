from nhltv import NhlTv
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
import os
from dateutil.tz.tz import tzlocal
from urllib.parse import urljoin
from flask import Flask, render_template
from flask.wrappers import Response
import m3u8

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
PROXY = os.getenv('PROXY')

nhltv = NhlTv(USERNAME, PASSWORD, PROXY)


app = Flask(__name__)
app.static_folder = 'static'
app.template_folder = 'templates'
app.templates_auto_reload = True


@app.template_filter()
def local_time(timestamp):
    utc_time = datetime.fromisoformat(timestamp)
    local_time = utc_time.astimezone(tzlocal())
    t = local_time.strftime('%I:%M %p').lstrip('0')
    return t


@app.get('/')
def index():
    date = datetime.now().astimezone(tzlocal()).strftime('%Y-%m-%d')
    return schedule(date)


@app.get('/date/<date>')
def schedule(date):
    day = datetime.strptime(date, '%Y-%m-%d').astimezone(tzlocal()) + timedelta(hours=4)
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()
    schedule = nhltv.get_schedule(start, end)
    games = schedule['data']

    today = datetime.strptime(date, '%Y-%m-%d')
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    prev = yesterday.strftime('%Y-%m-%d')
    next = tomorrow.strftime('%Y-%m-%d')

    return render_template('schedule.html', games=games, date=date, prev=prev, next=next)


@app.get('/play/<content_id>')
def play(content_id):
    src = nhltv.get_hls(content_id)
    return render_template('player.html', src=src)


@app.get('/hls/<content_id>')
def hls(content_id):
    url = nhltv.get_hls(content_id)
    text = nhltv.session.get(url).text
    playlist = m3u8.loads(text)

    if playlist.is_variant:
        url = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth).absolute_uri
        text = nhltv.session.get(url).text
        playlist = m3u8.loads(text)

    lines = text.splitlines()

    new_text = ''

    for line in lines:
        if '.ts' in line:
            abs_url = urljoin(url, line)
            abs_url_encoded = urlsafe_b64encode(abs_url.encode()).decode()
            line = f'http://localhost:3000/segment/{abs_url_encoded}'

        new_text += line + '\n'

    return Response(new_text, content_type='application/x-mpegURL')


@app.get('/segment/<segment_url>')
def segment(segment_url):
    segment_url = urlsafe_b64decode(segment_url).decode()
    segment_res = nhltv.session.get(segment_url)
    assert segment_res.headers['content-type'].lower() == 'video/MP2T'.lower()
    return Response(segment_res.content, content_type='video/MP2T')
