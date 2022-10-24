from argparse import ArgumentError
from base64 import urlsafe_b64decode
import re
import urllib.parse
from urllib.parse import parse_qs, urlparse
import requests
from datetime import datetime

# TODO
# load faster if cache playlist not master?


class NhlTv:
    auth_token = ''
    auth_code_cache: dict[str, tuple[str, int]] = {}
    hls_cache: dict[str, tuple[str, int]] = {}

    def __init__(self, username, password, proxy=None):
        if not username:
            print('USERNAME is null')
            exit(1)

        if not password:
            print('PASSWORD is null')
            exit(1)

        # request defaults
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0',
            'Origin': 'https://nhltv.nhl.com',
            'Referer': 'https://nhltv.nhl.com/',
        })
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

        self.auth_token = self.get_auth_token(username, password)

    def get_auth_token(self, username, password):
        url = 'https://nhltv.nhl.com/api/v3/sso/nhl/sign-in'
        data = {'email': username, 'password': password, 'code': None, 'CaptchaResponse': None}
        res = self.session.post(url, json=data)
        res.raise_for_status()
        return res.json()['token']

    def get_schedule(self, start_timestamp, end_timestamp):
        # 2022-10-19T09:26:46-04:00
        url = f'https://nhltv.nhl.com/api/v2/events?date_time_from={start_timestamp}&date_time_to={end_timestamp}&sort_direction=asc&limit=100'
        res = self.session.get(url)
        res.raise_for_status()
        return res.json()

    def get_auth_code(self, content_id):
        if content_id in self.auth_code_cache:
            # found in cache
            auth_code, exp = self.auth_code_cache[content_id]
            unix_now = int(datetime.utcnow().timestamp())

            if exp < unix_now:
                # cache age ok
                return auth_code

        # request new auth code
        url = f'https://nhltv.nhl.com/api/v3/contents/{content_id}/check-access'
        data = {'type': 'nhl'}
        cookies = {'token': self.auth_token}
        res = self.session.post(url, json=data, cookies=cookies)
        res.raise_for_status()
        auth_code: str = res.json()['data']
        jwt = urlsafe_b64decode(auth_code + '=' * (-len(auth_code) % 4))
        m = re.search(rb'"exp":(\d+)', jwt)
        assert m
        exp = int(m.group(1).decode())

        # cache new auth code
        self.auth_code_cache[content_id] = auth_code, exp

        return auth_code

    def get_hls(self, content_id):
        if content_id in self.hls_cache:
            # found in cache
            hls_url, exp = self.hls_cache[content_id]
            unix_now = int(datetime.utcnow().timestamp())

            if exp < unix_now:
                # cache age ok
                return hls_url

        # request new hls url
        player_settings_url = f'https://nhltv.nhl.com/api/v3/contents/{content_id}/player-settings'
        player_settings_res = self.session.get(player_settings_url)
        player_settings_res.raise_for_status()
        player_settings = player_settings_res.json()
        assert player_settings['streamAccess'] == player_settings['streamUrlProviderInfo']['data']['streamAccessUrl']

        auth_code = self.get_auth_code(content_id)

        stream_access_url = player_settings['streamAccess']
        parts = urlparse(stream_access_url)
        query = parse_qs(parts.query)
        query.update({'authorization_code': [urllib.parse.quote_plus(auth_code)]})

        stream_access_res = self.session.post(stream_access_url, params=query)
        stream_access_res.raise_for_status()
        assert stream_access_res.json()['status'] != 'error'

        hls_url: str = stream_access_res.json()['data']['stream']
        m = re.search(r'exp=(\d+)', hls_url)
        assert m
        exp = int(m.group(1))

        # cache new hls url
        self.hls_cache[content_id] = hls_url, exp

        return self.hls_cache[content_id][0]
