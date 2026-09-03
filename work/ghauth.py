"""Drive GitHub's OAuth device flow and hand the token straight to `gh`.

`gh auth login --web` needs a terminal to press Enter at, which this session
does not have. The device flow is the same OAuth grant without that prompt:
ask for a code, the user approves it in a browser, then poll until GitHub
hands back a token.

The token is piped into `gh auth login --with-token` on stdin and never
written to disk or printed.
"""
import json, sys, time, urllib.parse, urllib.request, subprocess, os

# GitHub CLI's own public OAuth app id -- the same one `gh auth login` uses
CLIENT_ID = '178c6fc778ccc68e1d6a'
SCOPES = 'repo read:org gist workflow'
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ghdevice.json')


def post(url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Accept': 'application/json',
        'User-Agent': 'claude-code-device-flow',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def request_code():
    r = post('https://github.com/login/device/code',
             {'client_id': CLIENT_ID, 'scope': SCOPES})
    if 'device_code' not in r:
        raise SystemExit('device code request failed: %r' % r)
    json.dump(r, open(STATE, 'w'))
    print('USER_CODE=%s' % r['user_code'])
    print('VERIFY_URL=%s' % r.get('verification_uri', 'https://github.com/login/device'))
    print('EXPIRES_IN=%s' % r.get('expires_in'))
    return r


def poll():
    r = json.load(open(STATE))
    interval = max(int(r.get('interval', 5)), 5)
    deadline = time.time() + int(r.get('expires_in', 900))
    while time.time() < deadline:
        time.sleep(interval)
        try:
            t = post('https://github.com/login/oauth/access_token', {
                'client_id': CLIENT_ID,
                'device_code': r['device_code'],
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            })
        except Exception as e:
            print('poll error (retrying): %s' % e, flush=True)
            continue
        err = t.get('error')
        if err == 'authorization_pending':
            continue
        if err == 'slow_down':
            interval += int(t.get('interval', 5))
            continue
        if err:
            raise SystemExit('AUTH_FAILED: %s (%s)' % (err, t.get('error_description')))
        token = t.get('access_token')
        if not token:
            raise SystemExit('AUTH_FAILED: no token in %r' % {k: v for k, v in t.items()
                                                              if k != 'access_token'})
        gh = r'C:\Program Files\GitHub CLI\gh.exe'
        p = subprocess.run([gh, 'auth', 'login', '--hostname', 'github.com',
                            '--git-protocol', 'https', '--with-token'],
                           input=token, capture_output=True, text=True)
        print('gh auth login rc=%d' % p.returncode)
        if p.stdout.strip():
            print(p.stdout.strip())
        if p.stderr.strip():
            print(p.stderr.strip())
        subprocess.run([gh, 'auth', 'setup-git'], capture_output=True, text=True)
        try:
            os.remove(STATE)
        except OSError:
            pass
        print('AUTH_OK' if p.returncode == 0 else 'AUTH_FAILED: gh rejected the token')
        return
    raise SystemExit('AUTH_FAILED: the code expired before it was approved')


if __name__ == '__main__':
    {'request': request_code, 'poll': poll}[sys.argv[1]]()
