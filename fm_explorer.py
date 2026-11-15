#!/usr/bin/env python3
"""FM Explorer - turns a Football Manager save into a searchable player database (HTML).

Usage:
  python fm_explorer.py                 -> uses the newest .fm in your FM27 'games' folder
  python fm_explorer.py "C:\\path\\save.fm"
Options:
  --min-ca 80      keep players with CA >= this (default 80)
  --min-pa 120     ...or players with PA >= this (default 120; limit by age with --young-age 23)
  --all            keep every men's player (big file, slower page)
  --watch          keep running: rebuild automatically every time FM saves, and serve the
                   page on http://localhost:8765 so it reloads itself
  --history-only   only add this save to the season tracker (no page)
Every build adds a point to history.json (season tracker, shown in the Progress tab).
chronicle.json (if present) holds the written story of the save, shown in the Story tab.
settings.json (optional) sets your default filters and extra nation names; see settings.example.json.
Writes fm_explorer.html next to this script and opens it in your browser.
Needs: pip install fmsave
"""
import collections, datetime as dt, glob, json, os, sys, time, warnings, webbrowser

warnings.simplefilter("ignore")
try:
    import fmsave
except ImportError:
    sys.exit("fmsave is not installed. Run:  pip install fmsave")

HERE = os.path.dirname(os.path.abspath(__file__))
POS = {'GK': ['gk'], 'DR': ['dr', 'wbr'], 'DC': ['dc'], 'DL': ['dl', 'wbl'], 'DM': ['dm'], 'MC': ['mc'],
       'AMR': ['amr', 'mr'], 'AML': ['aml', 'ml'], 'AMC': ['amc'], 'ST': ['stc']}
GROUPS = list(POS)
STATUS = {22: 'Surplus', 7: 'Fringe', 9: 'Emergency backup', 20: 'Backup GK', 21: 'Emergency GK', 16: 'Cup GK',
          5: 'Impact sub', 4: 'Squad player', 3: 'Regular starter', 2: 'Important', 1: 'Star player'}
PERS = ['ambition', 'professionalism', 'loyalty', 'pressure', 'temperament', 'adaptability', 'controversy', 'sportsmanship']
# FM27 nation ids (confirmed against club data in a 2029 save)
NATIONS = {4: 'Burkina Faso', 6: 'Cameroon', 11: 'Egypt', 16: 'Ghana', 17: 'Guinea', 19: 'Ivory Coast', 26: 'Mali',
           29: 'Morocco', 33: 'Nigeria', 36: 'Senegal', 40: 'South Africa', 43: 'Tanzania', 44: 'Congo', 46: 'Tunisia',
           48: 'DR Congo', 60: 'Iraq', 61: 'Japan', 77: 'Qatar', 78: 'Saudi Arabia', 80: 'Korea', 109: 'Mexico', 120: 'USA',
           129: 'Austria', 131: 'Belgium', 134: 'Bulgaria', 135: 'Croatia', 136: 'Cyprus', 137: 'Czechia', 138: 'Denmark',
           139: 'England', 140: 'Estonia', 142: 'Finland', 143: 'France', 145: 'Germany', 146: 'Greece', 147: 'Hungary',
           148: 'Iceland', 149: 'Israel', 150: 'Italy', 151: 'Latvia', 153: 'Lithuania', 154: 'Luxembourg', 156: 'Malta',
           158: 'Netherlands', 160: 'Norway', 161: 'Poland', 162: 'Portugal', 163: 'Ireland', 164: 'Romania', 165: 'Russia',
           167: 'Scotland', 168: 'Slovakia', 169: 'Slovenia', 170: 'Spain', 171: 'Sweden', 172: 'Switzerland', 173: 'Turkey',
           174: 'Ukraine', 176: 'Serbia', 177: 'Australia', 187: 'Argentina', 188: 'Bolivia', 189: 'Brazil', 190: 'Chile',
           191: 'Colombia', 192: 'Ecuador', 193: 'Paraguay', 194: 'Peru', 195: 'Uruguay', 196: 'Venezuela'}
CODES = {4:'BFA',6:'CMR',11:'EGY',16:'GHA',17:'GUI',19:'CIV',26:'MLI',29:'MAR',33:'NGA',36:'SEN',40:'RSA',43:'TAN',44:'CGO',46:'TUN',48:'COD',
         60:'IRQ',61:'JPN',77:'QAT',78:'KSA',80:'KOR',109:'MEX',120:'USA',129:'AUT',131:'BEL',134:'BUL',135:'CRO',136:'CYP',137:'CZE',138:'DEN',
         139:'ENG',140:'EST',142:'FIN',143:'FRA',145:'GER',146:'GRE',147:'HUN',148:'ISL',149:'ISR',150:'ITA',151:'LVA',153:'LTU',154:'LUX',156:'MLT',
         158:'NED',160:'NOR',161:'POL',162:'POR',163:'IRL',164:'ROU',165:'RUS',167:'SCO',168:'SVK',169:'SVN',170:'ESP',171:'SWE',172:'SUI',173:'TUR',
         174:'UKR',176:'SRB',177:'AUS',187:'ARG',188:'BOL',189:'BRA',190:'CHI',191:'COL',192:'ECU',193:'PAR',194:'PER',195:'URU',196:'VEN',175:'WAL',159:'NIR'}
EU_IDS = {129, 131, 134, 135, 136, 137, 138, 140, 142, 143, 145, 146, 147, 150, 151, 153, 154, 156, 158, 161, 162,
          163, 164, 168, 169, 170, 171}
ENGLAND = 139
NATIONS.update({54: 'Brunei', 59: 'Iran', 62: 'Jordan', 64: 'Kazakhstan', 99: 'Costa Rica', 107: 'Honduras', 111: 'Nicaragua',
                128: 'Armenia', 144: 'Georgia', 157: 'Moldova', 159: 'Northern Ireland', 175: 'Wales', 179: 'Fiji', 180: 'New Zealand',
                181: 'Papua New Guinea', 216: 'Gibraltar'})


def continent(n):
    if n is None or n < 0: return 'Unknown'
    if n == 216: return 'Europe'
    if n <= 53: return 'Africa'
    if n <= 93: return 'Asia'
    if n <= 127: return 'N & C America'
    if n <= 176: return 'Europe'
    if n <= 186: return 'Oceania'
    if n <= 196: return 'South America'
    return 'Other'



FORMATIONS = {
    '4-3-3': ['GK', 'DR', 'DC', 'DC', 'DL', 'DM', 'MC', 'MC', 'AMR', 'AML', 'ST'],
    '4-2-3-1': ['GK', 'DR', 'DC', 'DC', 'DL', 'DM', 'DM', 'AMR', 'AMC', 'AML', 'ST'],
    '4-4-2': ['GK', 'DR', 'DC', 'DC', 'DL', 'MC', 'MC', 'AMR', 'AML', 'ST', 'ST'],
}


def fit(r):
    return 1 if r >= 18 else .93 if r >= 15 else .8 if r >= 12 else .6 if r >= 9 else .3


def best_xi(ps, slots):
    """ps: list of players. Greedy best XI; returns (avg CA, [(slot, player)])"""
    gs = [(p, groups(p)) for p in ps if p.ability.current >= 40]
    pairs = sorted(((p.ability.current * fit(g[GROUPS.index(s)]), i, j) for i, (p, g) in enumerate(gs)
                    for j, s in enumerate(slots)), reverse=True)
    used, filled = set(), {}
    for _, i, j in pairs:
        if i in used or j in filled: continue
        used.add(i); filled[j] = gs[i][0]
    xi = [(slots[j], filled.get(j)) for j in range(len(slots))]
    cas = [p.ability.current for _, p in xi if p]
    return (round(sum(cas) / len(cas)) if cas else 0), xi


def money_s(v):
    return f"€{v/1e6:.1f}M" if v >= 1e6 else f"€{v/1e3:.0f}k"

def latest_save():
    base = os.path.join(os.path.expanduser('~'), 'Documents', 'Sports Interactive', 'Football Manager 27', 'games')
    files = [f for f in glob.glob(os.path.join(base, '*.fm')) if 'backup' not in os.path.basename(f).lower()]
    if not files:
        sys.exit(f"No .fm saves found in {base}. Pass the save path as an argument.")
    return max(files, key=os.path.getmtime)


def groups(p):
    return [max(getattr(p.positions, x) for x in POS[g]) for g in GROUPS]


HIST = os.path.join(HERE, 'history.json')

def load_hist():
    try:
        with open(HIST, encoding='utf-8') as f: return json.load(f)
    except Exception: return []

def load_settings():
    """Optional settings.json next to the script: {"defaults": {"noeng": true, "wagemax": 40, ...}, "nations": {"126": "Name"}}"""
    try:
        with open(os.path.join(HERE, 'settings.json'), encoding='utf-8') as f: return json.load(f)
    except Exception: return {}

def load_chronicle():
    try:
        with open(os.path.join(HERE, 'chronicle.json'), encoding='utf-8') as f: return json.load(f)
    except Exception: return None

def save_hist(h, entry):
    h = [e for e in h if not (e['club'] == entry['club'] and e['date'] == entry['date'])] + [entry]
    h.sort(key=lambda e: e['date'])
    with open(HIST, 'w', encoding='utf-8') as f: json.dump(h, f, ensure_ascii=False, separators=(',', ':'))
    return h

def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and not (i > 1 and sys.argv[i-1] in ('--min-ca', '--min-pa', '--young-age'))]
    path = args[0] if args else latest_save()
    if '--watch' in sys.argv: return watch(args[0] if args else None)
    build(path, open_browser='--no-open' not in sys.argv, hist_only='--history-only' in sys.argv)

def build(path, open_browser=True, hist_only=False):
    t0 = time.time()
    print(f"Reading {path} ... (this takes 1-2 minutes)")
    s = fmsave.open(path)
    mc = s.managed_clubs()[0]
    clubs = {c.uid: c for c in s.clubs()}
    me = clubs[mc.club_uid]
    date = s.info.game_date
    players = list(s.players())
    print(f"  {len(players):,} players loaded ({time.time()-t0:.0f}s)")

    settings = load_settings()
    nation_name = dict(NATIONS)
    nation_name.update({int(k): v for k, v in (settings.get('nations') or {}).items()})
    eu = set(EU_IDS) | {me.nation_id}
    nation_name.setdefault(me.nation_id, 'Your country')
    england = ENGLAND

    men = {u for u, c in clubs.items() if getattr(c.gender, 'raw', 0) == 0}
    attr_keys = list(next(p for p in players if p.attributes).attributes.__dataclass_fields__)

    # choose players worth exporting
    def opt(name, default):
        for i, x in enumerate(sys.argv):
            if x == name and i + 1 < len(sys.argv): return int(sys.argv[i + 1])
            if x.startswith(name + '='): return int(x.split('=', 1)[1])
        return default
    MIN_CA, MIN_PA, YOUNG = opt('--min-ca', 80), opt('--min-pa', 120), opt('--young-age', 99)
    if '--all' in sys.argv: MIN_CA, MIN_PA = 0, 0
    print(f"  exporting players with CA >= {MIN_CA} or PA >= {MIN_PA}" + (f" (PA rule for age <= {YOUNG})" if YOUNG < 99 else ""))
    def keep(p):
        if p.ability.current >= MIN_CA: return True
        return (p.age or 99) <= YOUNG and p.ability.potential >= MIN_PA
    cand = [p for p in players if (p.club_uid == mc.club_uid if hist_only else keep(p))]
    ids = {p.uid for p in cand}

    # history: last completed season league stats + last club for free agents
    season = (date.year if date.month >= 7 else date.year - 1) - 1
    stats = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0])
    last = {}
    for r in s.player_season_history():
        if r.player_uid not in ids: continue
        if r.kind.value == 'league' and r.season_year == season:
            x = stats[r.player_uid]
            x[0] += (r.starts or 0) + (r.substitute_appearances or 0); x[1] += r.goals or 0; x[2] += r.assists or 0
            x[3] += (r.average_rating or 0) * (r.rated_appearances or 0); x[4] += r.rated_appearances or 0
        if r.club_uid and (r.player_uid not in last or r.season_year >= last[r.player_uid][0]):
            last[r.player_uid] = (r.season_year, r.club_uid)
    print(f"  history done ({time.time()-t0:.0f}s)")

    def cname(u):
        c = clubs.get(u)
        return (c.short_name or c.name) if c else '?'

    rows, squad = [], []
    for p in cand:
        k = p.contract
        free = p.club_uid is None
        if free:
            lc = last.get(p.uid)
            if not lc or lc[1] not in men: continue
            club_u = lc[1]; club_label = 'ex-' + cname(club_u)
            if k and k.chain: future = 1
            else: future = 0
        else:
            if p.club_uid not in men: continue
            club_u = p.club_uid; club_label = cname(club_u) + (' B' if p.team_slot == 1 else '')
            future = 1 if any(e.start and e.start > date and e.club_uid != p.club_uid for e in (k.chain if k else [])) else 0
        cl = clubs.get(club_u)
        st = stats.get(p.uid, [0, 0, 0, 0, 0])
        rec = [p.uid, p.name or '?', p.age or 0, p.ability.current, p.ability.potential, groups(p),
               club_label, (cl.reputation or 0) if cl else 0, cl.nation_id if cl else -1,
               p.nation_id, p.reputation.current,
               -1 if free else (p.transfer_value if p.transfer_value is not None else 0),
               (k.wage if (k and not free) else None), (str(k.end)[:7] if (k and k.end and not free) else ''),
               1 if free else 0,
               (STATUS.get(k.squad_status.raw, '') if (k and k.squad_status and not free) else ''),
               future, 1 if p.on_loan else 0,
               st[0], st[1], st[2], round(st[3] / st[4], 2) if st[4] else 0,
               p.height_cm or 0,
               [getattr(p.attributes, a) for a in attr_keys],
               [getattr(p.personality, a, 0) for a in PERS] if p.personality else [0] * len(PERS)]
        if p.club_uid == mc.club_uid: squad.append(rec)
        else: rows.append(rec)
    # include whole own squad even below thresholds
    have = {r[0] for r in squad}
    for p in players:
        if p.club_uid == mc.club_uid and p.uid not in have:
            k = p.contract
            squad.append([p.uid, p.name or '?', p.age or 0, p.ability.current, p.ability.potential, groups(p), me.short_name or me.name,
                          me.reputation, me.nation_id, p.nation_id, p.reputation.current, p.transfer_value or 0,
                          k.wage if k else None, str(k.end)[:7] if k and k.end else '', 0, '', 0, 1 if p.on_loan else 0, 0, 0, 0, 0,
                          p.height_cm or 0, [getattr(p.attributes, a) for a in attr_keys],
                          [getattr(p.personality, a, 0) for a in PERS] if p.personality else [0] * len(PERS)])


    # ---------- league comparison ----------
    mine = {t.team_id for t in (me.teams or ())}
    fixtures = list(s.fixtures())
    s_start = dt.date(date.year if date.month >= 7 else date.year - 1, 7, 1)
    def season_fx(start):
        end = dt.date(start.year + 1, 6, 30)
        return [x for x in fixtures if start <= x.date <= end]
    cur = [x for x in season_fx(s_start) if x.home_team_id in mine or x.away_team_id in mine]
    cnt = collections.Counter(x.competition_id for x in cur)
    league_season = 'this season'
    if not cnt:
        prev = dt.date(s_start.year - 1, 7, 1)
        cur = [x for x in season_fx(prev) if x.home_team_id in mine or x.away_team_id in mine]
        cnt = collections.Counter(x.competition_id for x in cur); s_start = prev; league_season = 'last season (new fixtures not out yet)'
    league = None
    if cnt:
        cid = cnt.most_common(1)[0][0]
        lf = [x for x in season_fx(s_start) if x.competition_id == cid]
        teams = {}
        for x in lf:
            teams[x.home_team_id] = (x.home_club_uid, x.home_club_short_name or x.home_club_name)
            teams[x.away_team_id] = (x.away_club_uid, x.away_club_short_name or x.away_club_name)
        tbl = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        for x in lf:
            if not x.played or x.home_goals is None: continue
            for t, gf, ga in ((x.home_team_id, x.home_goals, x.away_goals), (x.away_team_id, x.away_goals, x.home_goals)):
                r = tbl[t]; r[0] += 1; r[4] += gf; r[5] += ga; r[1 if gf > ga else 2 if gf == ga else 3] += 1
        order = sorted(teams, key=lambda t: (-(tbl[t][1] * 3 + tbl[t][2]), -(tbl[t][4] - tbl[t][5]), -tbl[t][4], teams[t][1]))
        pos_in_table = {t: i + 1 for i, t in enumerate(order)}
        by = collections.defaultdict(list)
        for p in players:
            if p.team_id in teams: by[p.team_id].append(p)
        lastfin = {}
        for x in s.finances():
            if x.club_uid not in lastfin or x.month > lastfin[x.club_uid].month: lastfin[x.club_uid] = x
        lrows = []
        for t, (cu, nm) in teams.items():
            ps = by.get(t, [])
            if not ps: continue
            x433, xi_ = best_xi(ps, FORMATIONS['4-3-3'])
            xa = [p.age for _sl, p in xi_ if p and p.age]
            xiage = round(sum(xa) / len(xa), 1) if xa else None
            cas = sorted((p.ability.current for p in ps), reverse=True)
            top = max(ps, key=lambda p: p.ability.current)
            wages = sum((p.contract.wage or 0) for p in ps if p.contract and not p.on_loan)
            c = clubs.get(cu); r = tbl[t]
            own = [p for p in ps if not p.on_loan]
            value = sum(max(p.transfer_value or 0, 0) for p in own)
            vs = sorted(max(p.transfer_value or 0, 0) for p in own)
            median = (vs[len(vs) // 2] if len(vs) % 2 else (vs[len(vs) // 2 - 1] + vs[len(vs) // 2]) / 2) if vs else 0
            top11 = sorted(vs, reverse=True)[:11]
            mv = max(own or ps, key=lambda p: p.transfer_value or 0)
            ages = [p.age for p in ps if p.age]
            lf_ = lastfin.get(cu)
            lrows.append(dict(team=nm, me=t in mine, xi=x433, top18=round(sum(cas[:18]) / min(18, len(cas))), size=len(ps),
                              rep=(c.reputation or 0) if c else 0, best=f"{top.name} ({top.ability.current})",
                              wages=wages, pl=r[0], w=r[1], d=r[2], l=r[3], gf=r[4], ga=r[5], pts=r[1] * 3 + r[2], pos=pos_in_table[t],
                              young=sum(1 for p in ps if (p.age or 99) <= 21 and p.ability.potential >= 140),
                              value=value, median=median, top11=round(sum(top11) / len(top11)) if top11 else 0, mvp=f"{mv.name} ({money_s(mv.transfer_value or 0)})", age=round(sum(ages) / len(ages), 1) if ages else None,
                              xiage=xiage, bal=lf_.balance if lf_ else None, tb=lf_.transfer_budget_remaining if lf_ else None))
        league = dict(season=league_season, played=any(r[0] for r in tbl.values()), rows=lrows, comp=cid)
    print(f"  league done ({time.time()-t0:.0f}s)")

    # ---------- my club overview ----------
    fin = sorted([x for x in s.finances() if x.club_uid == mc.club_uid], key=lambda x: x.month)
    finance = None
    if fin:
        x = fin[-1]
        finance = dict(month=str(x.month), balance=x.balance, wageBudgetWeek=x.wage_budget_weekly,
                       payrollWeek=x.wage_payroll_weekly, transfer=x.transfer_budget_remaining)
    incoming = []
    for p in players:
        if p.club_uid == mc.club_uid or not p.contract: continue
        for e in p.contract.chain:
            if e.club_uid == mc.club_uid and e.start and e.start >= date:
                incoming.append(dict(n=p.name, a=p.age, c=p.ability.current, pa=p.ability.potential, pos=[x for x in GROUPS if groups(p)[GROUPS.index(x)] >= 15][:3],
                                     date=str(e.start), frm=cname(p.club_uid) if p.club_uid else 'free agent')); break
    myps = [p for p in players if p.club_uid == mc.club_uid]
    xis = {}
    for fname, slots in FORMATIONS.items():
        avg, xi = best_xi([p for p in myps if not p.on_loan or True], slots)
        xis[fname] = dict(avg=avg, xi=[[sl, p.uid if p else None] for sl, p in xi])

    # ---------- season tracker ----------
    my = next((r for r in (league or {}).get('rows', []) if r['me']), None)
    now = bool(league) and league['season'] == 'this season'  # table/points only for the current season
    lr = (league or {}).get('rows', [])
    entry = dict(club=me.name, date=str(date), comp=(league or {}).get('comp'), season=f"{date.year if date.month >= 7 else date.year - 1}/{((date.year if date.month >= 7 else date.year - 1) + 1) % 100:02d}",
                 rep=me.reputation, balance=mc.balance, xis={f: v['avg'] for f, v in xis.items()},
                 xi=my['xi'] if my else xis['4-3-3']['avg'], top18=my['top18'] if my else None, value=my['value'] if my else None, median=my['median'] if my else None,
                 wages=my['wages'] if my else None, pos=my['pos'] if my and now and league['played'] else None,
                 pts=my['pts'] if my and now else None, pl=my['pl'] if my and now else None, gf=my['gf'] if my and now else None, ga=my['ga'] if my and now else None,
                 xiRank=(sorted(lr, key=lambda r: -r['xi']).index(my) + 1) if my else None,
                 valRank=(sorted(lr, key=lambda r: -r['value']).index(my) + 1) if my else None, n=len(lr),
                 leagueXi=round(sum(r['xi'] for r in lr) / len(lr), 1) if lr else None,
                 squad={str(p.uid): [p.name, p.ability.current, p.ability.potential, p.age,
                                       '/'.join([g for g, v in sorted(zip(GROUPS, groups(p)), key=lambda x: -x[1]) if v >= 15][:2])] for p in myps if not p.on_loan})
    hist = save_hist(load_hist(), entry)
    print(f"  season tracker: {len([e for e in hist if e['club'] == me.name])} points saved")
    if hist_only: return None

    meta = dict(club=me.name, clubRep=me.reputation, nation=me.nation_id, date=str(date), season=f"{season}/{(season+1)%100:02d}",
                balance=mc.balance, england=england, continents={str(n): continent(n) for n in {r[9] for r in rows + squad} | {r[8] for r in rows + squad}}, eu=sorted(eu), nations={str(k): v for k, v in nation_name.items()},
                attrKeys=attr_keys, pers=PERS, groups=GROUPS, save=os.path.basename(path))
    meta['built'] = str(int(time.time()))
    meta['defaults'] = settings.get('defaults') or {}
    meta['homeCode'] = CODES.get(me.nation_id, 'HOME')
    data = dict(meta=meta, players=rows, squad=squad, league=league, finance=finance, incoming=incoming, xis=xis,
                history=[e for e in hist if e['club'] == me.name], chronicle=load_chronicle())
    tpl = open(os.path.join(HERE, 'explorer_template.html'), encoding='utf-8').read()
    out = os.path.join(HERE, 'fm_explorer.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(tpl.replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False, separators=(',', ':'))))
    print(f"Wrote {out}: {len(rows):,} players + {len(squad)} in your squad ({time.time()-t0:.0f}s)")
    with open(os.path.join(HERE, 'version.txt'), 'w') as f: f.write(meta['built'])
    if open_browser:
        webbrowser.open('file:///' + out.replace('\\', '/'))
    return out


def watch(path=None, port=8765):
    import threading, http.server, functools
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store'); super().end_headers()
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Quiet, directory=HERE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://localhost:{port}/fm_explorer.html'
    print(f"Watching for new saves. Page: {url}  (leave this window open; Ctrl+C to stop)")
    seen, opened = None, False
    while True:
        try:
            f = path or latest_save()
            st = os.stat(f); sig = (f, st.st_mtime, st.st_size)
            if sig != seen:
                time.sleep(5)  # let FM finish writing
                st2 = os.stat(f)
                if (st2.st_mtime, st2.st_size) != (st.st_mtime, st.st_size): continue
                print(f"\n[{time.strftime('%H:%M')}] new save detected: {os.path.basename(f)}")
                try: build(f, open_browser=False)
                except Exception as e: print('  build failed:', e)
                seen = sig
                if not opened: webbrowser.open(url); opened = True
            time.sleep(10)
        except KeyboardInterrupt:
            break
        except SystemExit as e:
            print(e); time.sleep(30)


if __name__ == '__main__':
    main()
