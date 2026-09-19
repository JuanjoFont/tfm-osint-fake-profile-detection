"""Lectura secuencial, variables compatibles con Honduras y ventanas temporales.

No modifica los originales. Salidas comprimidas para limitar uso de disco.
"""
import argparse
import ast
import collections
import datetime as dt
import functools
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

P = Path(__file__).resolve().parent
CHECKSUMS = {
    'honduras': {'bad': 'c6ab84ebd78ba7df78d0266d013b471e', 'good': 'da75759d86993d2c12b1946e59761bb4'},
    'uae': {'bad': 'c216b78629796fd38c08a455625c7d88', 'good': 'ce0f005ad71c13b44f2da064f3332de9'},
}
CUTOFF = {'honduras': '2019-11-10', 'uae': '2019-03-28'}
WINDOW = {'honduras': ('2019-09-10', '2020-01-09'), 'uae': ('2019-01-26', '2019-05-27')}


def as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = ast.literal_eval(value)
    if not isinstance(value, list):
        raise ValueError('Se esperaba lista de entidades')
    return value


@functools.lru_cache(maxsize=30000)
def creation_time(value):
    return dt.datetime.strptime(value[:10], '%Y-%m-%d').replace(tzinfo=dt.timezone.utc).timestamp()


def add(users, d, label, t):
    uid = str(d['userid'])
    if uid not in users:
        users[uid] = [label, 0, t, t, [0]*24, set(), set(), collections.Counter()]
    u = users[uid]
    if u[0] != label:
        u[0] = -1
    u[1] += 1
    u[2] = min(t, u[2]); u[3] = max(t, u[3])
    u[4][int(t//3600) % 24] += 1
    u[5].add(int(t//86400))
    txt = d.get('tweet_text') or ''
    u[6].add(hashlib.blake2b(txt.encode(), digest_size=8).digest())
    s = u[7]
    for feature, field in [('retweet_fraction', 'retweet_tweetid'), ('reply_fraction', 'in_reply_to_tweetid'), ('quote_fraction', 'quoted_tweet_tweetid')]:
        s[feature] += d.get(field) is not None
    s['mean_text_length'] += len(txt)
    for key in ['hashtags', 'urls', 'user_mentions']:
        s['mean_'+key] += len(as_list(d.get(key)))
    for key in ['follower_count', 'following_count']:
        s['mean_'+key] += float(d.get(key) or 0)
    c = d.get('account_creation_date')
    s['mean_account_age_days'] += max(0, (t-creation_time(c))/86400) if c else 0


def save(users, path, excluded):
    rows = []
    for uid, (label, n, first, last, hours, days, texts, sums) in users.items():
        if label < 0 or uid in excluded:
            continue
        r = {'userid': uid, 'label': label, 'tweet_count': n, 'active_days': len(days),
             'span_days': (last-first)/86400, 'duplicate_text_fraction': 1-len(texts)/n,
             'hour_entropy': -sum(h/n*math.log2(h/n) for h in hours if h),
             'max_hour_fraction': max(hours)/n, 'tweets_per_active_day': n/len(days)}
        r.update({k: v/n for k, v in sums.items()})
        rows.append(r)
    df = pd.DataFrame(rows).sort_values('userid')
    assert df.userid.is_unique and not df.isna().any().any()
    df.to_csv(path, index=False)
    return {'accounts': len(df), 'positives': int(df.label.sum()), 'tweets': int(df.tweet_count.sum())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign', choices=CHECKSUMS)
    parser.add_argument('--mode', choices=['full', 'temporal'], default='full')
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path.home() / 'Downloads',
        help='Directorio que contiene <campaña>-{bad,good}-anonymized '
             '(por defecto: ~/Downloads)',
    )
    args = parser.parse_args()
    users = {}; later = {}; seen = {}; collisions = {}; conflicts = set(); audit = {}
    cutoff = creation_time(CUTOFF[args.campaign])
    start, end = map(creation_time, WINDOW[args.campaign])
    for kind, label in [('bad', 1), ('good', 0)]:
        path = args.data_dir / f'{args.campaign}-{kind}-anonymized'
        md = hashlib.md5(); sha = hashlib.sha256(); rows = duplicates = outside = id_collisions = 0
        first = float('inf'); last = 0
        with path.open('rb') as f:
            for line in f:
                md.update(line); sha.update(line); d = json.loads(line); rows += 1
                assert int(d['good']) == 1-label
                tid = int(d['tweetid']); uid = str(d['userid'])
                t = float(d['tweet_time'])/1000
                first = min(first, t); last = max(last, t)
                signature = hashlib.blake2b((uid+'\0'+str(t)+'\0'+(d.get('tweet_text') or '')).encode(), digest_size=16).digest()
                if tid in seen:
                    old_sig, old_label = seen[tid]
                    if old_sig == signature or signature in collisions.get(tid, {}):
                        duplicates += 1
                        previous_label = old_label if old_sig == signature else collisions[tid][signature]
                        if previous_label != label:
                            conflicts.add(uid)
                        continue
                    id_collisions += 1
                    collisions.setdefault(tid, {})[signature] = label
                else:
                    seen[tid] = (signature, label)
                if not start <= t < end:
                    outside += 1
                    continue
                target = later if args.mode == 'temporal' and t >= cutoff else users
                add(target, d, label, t)
                if target[uid][0] < 0:
                    conflicts.add(uid)
                if rows % 250000 == 0:
                    print(args.campaign, args.mode, kind, rows, 'registros', flush=True)
        audit[kind] = {'rows': rows, 'duplicates_removed': duplicates, 'outside_window_excluded': outside,
                       'tweetid_collisions_preserved': id_collisions, 'md5': md.hexdigest(),
                       'sha256': sha.hexdigest(), 'matches_zenodo': md.hexdigest() == CHECKSUMS[args.campaign][kind],
                       'first_utc': dt.datetime.fromtimestamp(first, dt.timezone.utc).isoformat(),
                       'last_utc': dt.datetime.fromtimestamp(last, dt.timezone.utc).isoformat()}
        assert audit[kind]['matches_zenodo'], 'Integridad incorrecta: archivo distinto del publicado'
        print(audit[kind], flush=True)
    if args.mode == 'temporal':
        conflicts.update(uid for uid in users.keys() & later.keys() if users[uid][0] != later[uid][0])
        audit['cutoff_utc'] = CUTOFF[args.campaign]
        audit['early'] = save(users, P/f'{args.campaign}_early.csv.gz', conflicts)
        audit['late'] = save(later, P/f'{args.campaign}_late.csv.gz', conflicts)
    else:
        audit['full'] = save(users, P/f'{args.campaign}_curado.csv.gz', conflicts)
    audit['window_utc_inclusive_exclusive'] = WINDOW[args.campaign]
    audit['conflicting_users_excluded'] = sorted(conflicts)
    (P/f'{args.campaign}_{args.mode}_curado_auditoria.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == '__main__':
    main()
