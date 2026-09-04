import app

c = app.app.test_client()
c.get('/')
with c.session_transaction() as s:
    s['user_id'] = 1
    pass  # sessao incompleta, so user_id
r = c.get('/')
print('STATUS:', r.status_code)
print('LEN:', len(r.data))
