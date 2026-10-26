import os, json, sqlite3, secrets, hashlib, hmac, datetime, csv, io, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(getattr(__import__('sys'), '_MEIPASS', Path(__file__).resolve().parent))
DATA_DIR=Path(os.getenv('LOCALAPPDATA',str(Path.home()))) / 'FinTrackAdvanced'
DATA_DIR.mkdir(parents=True,exist_ok=True)
DB=Path(os.getenv('FINTRACK_DB',str(DATA_DIR/'fintrack.db')))
SESSIONS={}
CATEGORIES=['Alimentação','Moradia','Transporte','Saúde','Educação','Lazer','Compras','Salário','Investimentos','Outros']
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def init():
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,salt TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,type TEXT NOT NULL,amount_cents INTEGER NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,date TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
  CREATE TABLE IF NOT EXISTS budgets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,category TEXT NOT NULL,limit_cents INTEGER NOT NULL,UNIQUE(user_id,category));
  CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,target_cents INTEGER NOT NULL,saved_cents INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,last_four TEXT NOT NULL,limit_cents INTEGER NOT NULL,closing_day INTEGER NOT NULL,due_day INTEGER NOT NULL,provider TEXT NOT NULL DEFAULT 'manual',external_id TEXT,UNIQUE(user_id,provider,external_id));
  CREATE TABLE IF NOT EXISTS card_purchases(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,card_id INTEGER NOT NULL,description TEXT NOT NULL,category TEXT NOT NULL,amount_cents INTEGER NOT NULL,purchase_date TEXT NOT NULL,installments INTEGER NOT NULL DEFAULT 1,provider TEXT NOT NULL DEFAULT 'manual',external_id TEXT,FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE,UNIQUE(user_id,provider,external_id));
  CREATE TABLE IF NOT EXISTS card_payments(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,card_id INTEGER NOT NULL,invoice_month TEXT NOT NULL,amount_cents INTEGER NOT NULL,paid_date TEXT NOT NULL,FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE);''')
def pw_hash(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000).hex()
def cents(value):
 from decimal import Decimal,InvalidOperation
 try:
  v=Decimal(str(value)); n=v*100
  if not v.is_finite() or n!=n.to_integral_value() or n<=0 or n>100000000000:return None
  return int(n)
 except (InvalidOperation,ValueError):return None
def insights(transactions):
 from collections import defaultdict
 month=datetime.date.today().strftime('%Y-%m'); income=expense=0; bycat=defaultdict(int); prior=0
 for t in transactions:
  if t['date'][:7]==month:
   if t['type']=='income':income+=t['amount_cents']
   else:expense+=t['amount_cents'];bycat[t['category']]+=t['amount_cents']
  elif t['type']=='expense':prior+=t['amount_cents']
 top=sorted(bycat.items(),key=lambda x:-x[1]); suggestions=[]
 if top:suggestions.append('Sua maior categoria de gastos no mês é '+top[0][0]+'. Avalie despesas recorrentes nessa categoria.')
 if expense>income:suggestions.append('As despesas do mês superam as receitas. Considere revisar o orçamento.')
 if income>expense:suggestions.append('Você tem saldo mensal positivo. Considere reservar parte da diferença para suas metas.')
 if not suggestions:suggestions.append('Cadastre movimentações para receber sugestões personalizadas.')
 return {'income_cents':income,'expense_cents':expense,'balance_cents':income-expense,'by_category':[{'category':k,'amount_cents':v} for k,v in top], 'summary':f'Neste mês, você registrou R$ {income/100:.2f} em receitas e R$ {expense/100:.2f} em despesas.', 'trend':'Compare os gráficos mensais para identificar tendências de gastos.', 'suggestions':suggestions}
def card_invoice_month(purchase_date,closing_day,offset=0):
 d=datetime.date.fromisoformat(purchase_date)
 # Compras feitas após o fechamento entram na fatura seguinte.
 month=d.year*12+d.month-1+(1 if d.day>closing_day else 0)+offset
 return f'{month//12:04d}-{month%12+1:02d}'
def card_summary(c,uid):
 cards=[dict(x) for x in c.execute('SELECT * FROM cards WHERE user_id=? ORDER BY id DESC',(uid,))]
 for card in cards:
  purchases=[dict(x) for x in c.execute('SELECT * FROM card_purchases WHERE user_id=? AND card_id=? ORDER BY purchase_date DESC,id DESC',(uid,card['id']))]
  payments=[dict(x) for x in c.execute('SELECT * FROM card_payments WHERE user_id=? AND card_id=?',(uid,card['id']))]
  invoices={}
  for item in purchases:
   n=item['installments'];base=item['amount_cents']//n;remainder=item['amount_cents']%n
   for i in range(n):
    month=card_invoice_month(item['purchase_date'],card['closing_day'],i)
    invoices[month]=invoices.get(month,0)+base+(1 if i<remainder else 0)
  paid={}
  for pay in payments:paid[pay['invoice_month']]=paid.get(pay['invoice_month'],0)+pay['amount_cents']
  card['purchases']=purchases
  card['invoices']=[{'month':m,'total_cents':v,'paid_cents':paid.get(m,0),'remaining_cents':max(0,v-paid.get(m,0))} for m,v in sorted(invoices.items())]
  card['outstanding_cents']=sum(max(0,v-paid.get(m,0)) for m,v in invoices.items())
  card['available_cents']=max(0,card['limit_cents']-card['outstanding_cents'])
 return cards
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status=200,data=None,ctype='application/json; charset=utf-8',cookie=None):
  body=json.dumps(data,ensure_ascii=False).encode() if ctype.startswith('application/json') else (data if isinstance(data,bytes) else str(data).encode())
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(body)
 def error(self,message,status=400):self.send(status,{'error':message})
 def user(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:return None
  token=cookie.get('sid');return SESSIONS.get(token.value) if token else None
 def readbody(self):
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>30000 or length<0:raise ValueError()
   return json.loads(self.rfile.read(length))
  except Exception:return None
 def auth(self):
  uid=self.user()
  if not uid:self.error('Faça login para continuar.',401)
  return uid
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/':path='/index.html'
  if path.startswith('/static/') or path=='/index.html':
   file=ROOT/('static/'+path.removeprefix('/static/') if path.startswith('/static/') else 'static/index.html')
   if file.is_file() and file.resolve().is_relative_to((ROOT/'static').resolve()):
    types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8'}
    return self.send(200,file.read_bytes(),types.get(file.suffix,'application/octet-stream'))
   return self.error('Não encontrado',404)
  if path=='/api/me':return self.send(200,{'authenticated':bool(self.user())})
  uid=self.auth()
  if not uid:return
  with conn() as c:
   if path=='/api/cards':return self.send(200,card_summary(c,uid))
   if path=='/api/transactions':return self.send(200,[dict(x) for x in c.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC,id DESC',(uid,))])
   if path=='/api/budgets':return self.send(200,[dict(x) for x in c.execute('SELECT * FROM budgets WHERE user_id=? ORDER BY category',(uid,))])
   if path=='/api/goals':return self.send(200,[dict(x) for x in c.execute('SELECT * FROM goals WHERE user_id=? ORDER BY id DESC',(uid,))])
   if path=='/api/insights':
    tx=[dict(x) for x in c.execute('SELECT * FROM transactions WHERE user_id=?',(uid,))];return self.send(200,insights(tx))
   if path=='/api/export':
    out=io.StringIO();w=csv.writer(out);w.writerow(['Data','Tipo','Categoria','Descrição','Valor (R$)'])
    for t in c.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC',(uid,)):w.writerow([t['date'],t['type'],t['category'],t['description'],f"{t['amount_cents']/100:.2f}"])
    return self.send(200,('\ufeff'+out.getvalue()).encode('utf-8'),'text/csv; charset=utf-8')
  self.error('Rota não encontrada',404)
 def do_POST(self):
  path=urlparse(self.path).path
  origin=self.headers.get('Origin','');host=self.headers.get('Host','')
  if origin and origin not in ('http://'+host,'https://'+host):return self.error('Origem inválida',403)
  b=self.readbody()
  if not isinstance(b,dict):return self.error('JSON inválido')
  if path in ('/api/register','/api/login'):
   email=str(b.get('email','')).strip().lower();password=str(b.get('password',''))
   if len(email)>254 or '@' not in email or len(password)<8:return self.error('Informe e-mail válido e senha com 8 caracteres ou mais.')
   with conn() as c:
    if path=='/api/register':
     salt=secrets.token_hex(16)
     try:c.execute('INSERT INTO users(email,password,salt) VALUES(?,?,?)',(email,pw_hash(password,salt),salt))
     except sqlite3.IntegrityError:return self.error('E-mail já cadastrado.',409)
    u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not u or not hmac.compare_digest(pw_hash(password,u['salt']),u['password']):return self.error('Credenciais inválidas.',401)
   token=secrets.token_urlsafe(32);SESSIONS[token]=u['id']
   return self.send(200,{'ok':True},cookie=f'sid={token}; HttpOnly; SameSite=Strict; Path=/')
  if path=='/api/logout':
   cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie.get('sid')
   if token:SESSIONS.pop(token.value,None)
   return self.send(200,{'ok':True},cookie='sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
  uid=self.auth()
  if not uid:return
  with conn() as c:
   if path=='/api/cards':
    name=str(b.get('name','')).strip()[:80];last=str(b.get('last_four','')).strip();limit=cents(b.get('limit'))
    try:closing=int(b.get('closing_day'));due=int(b.get('due_day'))
    except (ValueError,TypeError):return self.error('Datas inválidas.')
    if not name or not (last.isdigit() and len(last)==4) or not limit or not (1<=closing<=28 and 1<=due<=28):return self.error('Informe nome, últimos 4 dígitos, limite e dias entre 1 e 28.')
    c.execute('INSERT INTO cards(user_id,name,last_four,limit_cents,closing_day,due_day) VALUES(?,?,?,?,?,?)',(uid,name,last,limit,closing,due));return self.send(201,{'ok':True})
   if path=='/api/card-purchases':
    try:card_id=int(b.get('card_id'));n=int(b.get('installments',1))
    except (ValueError,TypeError):return self.error('Cartão ou parcelas inválidos.')
    amount=cents(b.get('amount'));desc=str(b.get('description','')).strip()[:160];cat=str(b.get('category','Outros'))[:40];date=str(b.get('date',''))
    try:datetime.date.fromisoformat(date)
    except ValueError:return self.error('Data inválida.')
    if not amount or not desc or not cat or not 1<=n<=48:return self.error('Compra inválida (máximo de 48 parcelas).')
    if not c.execute('SELECT 1 FROM cards WHERE id=? AND user_id=?',(card_id,uid)).fetchone():return self.error('Cartão não encontrado.',404)
    c.execute('INSERT INTO card_purchases(user_id,card_id,description,category,amount_cents,purchase_date,installments) VALUES(?,?,?,?,?,?,?)',(uid,card_id,desc,cat,amount,date,n));return self.send(201,{'ok':True})
   if path=='/api/card-payments':
    try:card_id=int(b.get('card_id'))
    except (ValueError,TypeError):return self.error('Cartão inválido.')
    month=str(b.get('invoice_month',''));amount=cents(b.get('amount'));date=str(b.get('paid_date',''))
    try:datetime.date.fromisoformat(date);datetime.date.fromisoformat(month+'-01')
    except ValueError:return self.error('Data inválida.')
    if not amount or not c.execute('SELECT 1 FROM cards WHERE id=? AND user_id=?',(card_id,uid)).fetchone():return self.error('Pagamento inválido.')
    current=next((x for x in card_summary(c,uid) if x['id']==card_id),None)
    invoice=next((x for x in current['invoices'] if x['month']==month),None)
    if not invoice or amount>invoice['remaining_cents']:return self.error('Pagamento excede o saldo da fatura.')
    c.execute('INSERT INTO card_payments(user_id,card_id,invoice_month,amount_cents,paid_date) VALUES(?,?,?,?,?)',(uid,card_id,month,amount,date));return self.send(201,{'ok':True})
   if path=='/api/transactions':
    kind=b.get('type');amount=cents(b.get('amount'));cat=str(b.get('category',''))[:40];desc=str(b.get('description','')).strip()[:160];date=str(b.get('date',''))
    try:datetime.date.fromisoformat(date)
    except ValueError:return self.error('Data inválida.')
    if kind not in ('income','expense') or not amount or not cat or not desc:return self.error('Preencha os dados da transação corretamente.')
    c.execute('INSERT INTO transactions(user_id,type,amount_cents,category,description,date) VALUES(?,?,?,?,?,?)',(uid,kind,amount,cat,desc,date));return self.send(201,{'ok':True})
   if path=='/api/budgets':
    amount=cents(b.get('limit'));cat=str(b.get('category',''))[:40]
    if not amount or not cat:return self.error('Orçamento inválido.')
    c.execute('INSERT INTO budgets(user_id,category,limit_cents) VALUES(?,?,?) ON CONFLICT(user_id,category) DO UPDATE SET limit_cents=excluded.limit_cents',(uid,cat,amount));return self.send(201,{'ok':True})
   if path=='/api/goals':
    amount=cents(b.get('target'));name=str(b.get('name','')).strip()[:80]
    if not amount or not name:return self.error('Meta inválida.')
    c.execute('INSERT INTO goals(user_id,name,target_cents,saved_cents) VALUES(?,?,?,0)',(uid,name,amount));return self.send(201,{'ok':True})
   if path=='/api/ai':
    tx=[dict(x) for x in c.execute('SELECT type,amount_cents,category,date FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 150',(uid,))]
    base=insights(tx);key=os.getenv('OPENAI_API_KEY','')
    if not key:return self.send(200,{'mode':'local','text':base['summary']+'\n'+'\n'.join('• '+s for s in base['suggestions'])})
    payload={'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),'messages':[{'role':'system','content':'Você é um assistente de educação financeira em português brasileiro. Analise somente os dados agregados enviados. Não prometa resultados nem dê aconselhamento financeiro personalizado de investimento. Seja conciso, claro e prudente.'},{'role':'user','content':json.dumps(base,ensure_ascii=False)}],'max_tokens':350}
    try:
     req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
     with urllib.request.urlopen(req,timeout=15) as r:result=json.load(r)
     return self.send(200,{'mode':'ai','text':result['choices'][0]['message']['content']})
    except (urllib.error.URLError,KeyError,TimeoutError,ValueError):return self.send(200,{'mode':'local','text':base['summary']+'\n'+'\n'.join('• '+s for s in base['suggestions'])+'\n(IA indisponível: resumo local exibido.)'})
  self.error('Rota não encontrada',404)
 def do_DELETE(self):
  uid=self.auth()
  if not uid:return
  path=urlparse(self.path).path.split('/')
  if len(path)!=4 or path[1]!='api' or path[2] not in ('transactions','goals','budgets','cards','card-purchases') or not path[3].isdigit():return self.error('Rota inválida',404)
  table={'card-purchases':'card_purchases'}.get(path[2],path[2])
  with conn() as c:c.execute(f'DELETE FROM {table} WHERE id=? AND user_id=?',(int(path[3]),uid))
  self.send(200,{'ok':True})
if __name__=='__main__':
 init();port=int(os.getenv('PORT','8765'));print(f'FinTrack Advanced: http://127.0.0.1:{port}',flush=True);ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
