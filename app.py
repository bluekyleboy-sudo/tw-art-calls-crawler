#!/usr/bin/env python3
"""OPEN FIELD — robust public art-opportunity collector and local web server."""
from __future__ import annotations

import argparse, concurrent.futures, difflib, gzip, html, http.client, io, ipaddress, json, re, shutil, socket, sqlite3, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, quote, quote_plus, unquote, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

ROOT=Path(__file__).parent; WEB=ROOT/"docs"; DB=ROOT/"open-field.sqlite3"; REPORT=ROOT/"last-crawl.json"
SOURCES=ROOT/"sources.json"; GRANTS=ROOT/"grants.json"; VERIFIED=ROOT/"verified-opportunities.json"
UA="OpenFieldArtOpportunityIndex/2.0 (public pages; Taiwan creator resource)"
CALL=("徵件","徵選","招募","申請","公開徵集","open call","opencall","call for","apply","application","residency","grant","funding")
TOPIC=("攝影","影像","視覺藝術","當代藝術","新媒體","藝術","展覽","展演","策展","駐村","進駐","補助","photography","moving image","visual art","contemporary art","new media","artist","exhibition","curatorial","residency","grant")
CLOSED=("已截止","徵件已截止","報名已截止","停止受理","停止收件","applications are closed","application is closed","call is closed","submissions are closed","no open calls")
ROLLING=("常年徵件","全年徵件","隨時申請","隨到隨審","長期招募","rolling basis","rolling application","applications accepted year-round","open year-round","ongoing call")
RESULT=("得獎名單","獲選名單","結果公告","活動回顧","展覽回顧","winner announcement","selected artists","event recap")
NOT_CALL=("場地申請","場地租借","空間租借","參觀申請","採購案","招標公告","venue application","venue rental","procurement")
RESTRICTED=("asean nationals only","asean citizens only","asean residents only","singapore-based only","singapore based only","residents of singapore only","japanese nationals only","korean nationals only","hong kong residents only","local artists only")
DOMESTIC_FOREIGN=("非中華民國國籍","非臺灣籍","非台灣籍","僅限外籍","限外籍人士","non-roc national","non-taiwanese only","foreign nationals only")
BLOCKED_CANDIDATE_HOSTS=("wikipedia.org","governmentjobs.com")
TRACKING_QUERY_KEYS=("fbclid","gclid","dclid","mc_cid","mc_eid","ref_src","ref_url")
SOCIAL_HOSTS=("bsky.app","facebook.com","instagram.com","linkedin.com","mastodon.social","threads.net","tiktok.com","twitter.com","x.com")
TAIPEI=ZoneInfo("Asia/Taipei")
TAIWAN=("臺灣","台灣","臺北","台北","新北","基隆","桃園","新竹","苗栗","臺中","台中","彰化","南投","雲林","嘉義","臺南","台南","高雄","屏東","宜蘭","花蓮","臺東","台東","澎湖","金門","連江","taiwan","taipei","kaohsiung","taichung","tainan")
REGIONS={
 "亞洲":("日本","韓國","香港","蒙古","新加坡","越南","泰國","馬來西亞","印尼","印度尼西亞","菲律賓","柬埔寨","印度","尼泊爾","孟加拉","巴基斯坦","斯里蘭卡","不丹","japan","tokyo","kyoto","korea","seoul","hong kong","mongolia","singapore","vietnam","thailand","malaysia","indonesia","philippines","cambodia","india","nepal","bangladesh","pakistan","sri lanka","bhutan"),
 "歐美":("美國","加拿大","墨西哥","阿根廷","英國","法國","德國","義大利","西班牙","葡萄牙","荷蘭","比利時","瑞士","奧地利","北歐","歐洲","南美","usa","united states","canada","mexico","united kingdom","france","germany","italy","spain","portugal","netherlands","belgium","switzerland","austria","sweden","norway","finland","denmark","iceland","poland","czech","greece","ireland","argentina","brazil","chile","colombia","europe"),
}
COUNTRIES={
 "日本":("日本","japan","tokyo","kyoto","nara","aomori","ibaraki"),"韓國":("韓國","南韓","korea","seoul"),"香港":("香港","hong kong"),"蒙古":("蒙古","mongolia"),
 "新加坡":("新加坡","singapore"),"越南":("越南","vietnam"),"泰國":("泰國","thailand"),"馬來西亞":("馬來西亞","malaysia"),"印尼":("印尼","印度尼西亞","indonesia"),"菲律賓":("菲律賓","philippines"),"柬埔寨":("柬埔寨","cambodia"),
 "印度":("印度","india"),"尼泊爾":("尼泊爾","nepal"),"孟加拉":("孟加拉","bangladesh"),"巴基斯坦":("巴基斯坦","pakistan"),"斯里蘭卡":("斯里蘭卡","sri lanka"),"不丹":("不丹","bhutan"),
 "美國":("美國","usa","united states"),"加拿大":("加拿大","canada","banff"),"墨西哥":("墨西哥","mexico","puebla"),"英國":("英國","united kingdom","london"),"法國":("法國","france"),"德國":("德國","germany"),"義大利":("義大利","italy"),"西班牙":("西班牙","spain"),"葡萄牙":("葡萄牙","portugal"),"荷蘭":("荷蘭","netherlands"),"奧地利":("奧地利","austria","vienna"),"芬蘭":("芬蘭","finland"),"阿根廷":("阿根廷","argentina","buenos aires"),
}

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def today_iso(moment=None):
 moment=moment or datetime.now(timezone.utc)
 if moment.tzinfo is None:moment=moment.replace(tzinfo=timezone.utc)
 return moment.astimezone(TAIPEI).date().isoformat()
def clean(s): return re.sub(r"\s+"," ",html.unescape(str(s or ""))).strip()
def load(path,key): return json.loads(path.read_text(encoding="utf-8"))[key]
def atomic_write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name("."+path.name+".tmp")
 temporary.write_text(text,encoding="utf-8");temporary.replace(path)
def canonical(url):
 p=urlparse(url); query=[]
 for key,value in parse_qsl(p.query,keep_blank_values=True):
  low=key.lower()
  if low.startswith("utm_") or low in TRACKING_QUERY_KEYS or low in ("ts","timestamp"):continue
  query.append((key,value))
 return urlunparse((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/") or "/","",urlencode(sorted(query)),""))
def blocked_candidate_url(url):
 try:host=(urlparse(url).hostname or "").lower()
 except Exception:return True
 return any(host==blocked or host.endswith("."+blocked) for blocked in BLOCKED_CANDIDATE_HOSTS)
def ensure_public_http_url(url):
 parsed=urlparse(url)
 if parsed.scheme not in ("http","https") or not parsed.hostname:raise ValueError("only public HTTP(S) URLs are allowed")
 host=parsed.hostname.lower()
 if host in ("localhost","localhost.localdomain") or host.endswith(".localhost"):raise ValueError("local addresses are not allowed")
 try:addresses=[ipaddress.ip_address(host)]
 except ValueError:
  try:addresses=[ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM)]
  except OSError as exc:raise ValueError("hostname could not be resolved") from exc
 if not addresses or any(not address.is_global for address in addresses):raise ValueError("private or non-routable addresses are not allowed")
 return url
def public_connection(address,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,source_address=None):
 host,port=address; infos=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
 if not infos:raise OSError("hostname could not be resolved")
 parsed=[]
 for family,socktype,proto,canonname,sockaddr in infos:
  ip=ipaddress.ip_address(sockaddr[0])
  if not ip.is_global:raise ValueError("private or non-routable addresses are not allowed")
  parsed.append((family,socktype,proto,sockaddr))
 last=None
 for family,socktype,proto,sockaddr in parsed:
  sock=socket.socket(family,socktype,proto)
  try:
   if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:sock.settimeout(timeout)
   if source_address:sock.bind(source_address)
   sock.connect(sockaddr);return sock
  except OSError as exc:last=exc;sock.close()
 raise last or OSError("unable to connect")
class PublicHTTPConnection(http.client.HTTPConnection):
 def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self._create_connection=public_connection
class PublicHTTPSConnection(http.client.HTTPSConnection):
 def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self._create_connection=public_connection
class PublicHTTPHandler(urllib.request.HTTPHandler):
 def http_open(self,req):return self.do_open(PublicHTTPConnection,req)
class PublicHTTPSHandler(urllib.request.HTTPSHandler):
 def https_open(self,req):return self.do_open(PublicHTTPSConnection,req,context=self._context,check_hostname=self._check_hostname)
class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  ensure_public_http_url(newurl)
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def database(path=None):
 c=sqlite3.connect(path or DB,timeout=30); c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=30000")
 c.execute("""CREATE TABLE IF NOT EXISTS opportunities(id INTEGER PRIMARY KEY,title TEXT,url TEXT,application_url TEXT,source TEXT,category TEXT,region TEXT,notes TEXT,opening_iso TEXT,deadline_iso TEXT,fingerprint TEXT UNIQUE,first_seen TEXT,last_seen TEXT)""")
 c.execute("CREATE INDEX IF NOT EXISTS deadline_idx ON opportunities(deadline_iso)"); c.commit(); return c

def fetch(url):
 ensure_public_http_url(url)
 parsed=urlparse(url); url=urlunparse((parsed.scheme,parsed.netloc,quote(parsed.path,safe="/%:@"),parsed.params,quote(parsed.query,safe="=&%:+,()"),parsed.fragment))
 last=None
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/json;q=.9,*/*;q=.5","Accept-Language":"zh-TW,zh;q=.9,en;q=.8","Accept-Encoding":"gzip"})
   with urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicRedirectHandler(),PublicHTTPHandler(),PublicHTTPSHandler()).open(req,timeout=30) as response:
    ensure_public_http_url(response.geturl())
    data=response.read(8_000_000)
    if response.headers.get("Content-Encoding")=="gzip":
     with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:data=stream.read(8_000_001)
     if len(data)>8_000_000:raise ValueError("decompressed response is too large")
    return data,response.geturl()
  except Exception as exc:
   last=exc
   if attempt<2: time.sleep(1.25*(attempt+1))
 raise last

def readable_fetch(url):
 """Fetch a detail page, falling back to a public text reader for blocked pages."""
 try:
  data,final=fetch(url); text,links=parse(data,final); return text,links,final,"direct"
 except Exception as direct_error:
  reader="https://r.jina.ai/"+url
  try:
   data,_=fetch(reader); text,links=parse_reader(data,url)
   if len(text)<40: raise ValueError("reader returned too little content")
   return text,links,url,"reader"
  except Exception:
   raise direct_error

def parse_reader(data,base):
 raw=data.decode("utf-8",errors="replace");links=[];seen=set()
 for match in re.finditer(r"\[([^\]\n]{3,240})\]\((https?://[^\s)]+)\)",raw):
  title=clean(re.sub(r"[*_`]","",match[1]));url=match[2].rstrip(".,;")
  if canonical(url)==canonical(base) or canonical(url) in seen:continue
  seen.add(canonical(url));links.append({"url":url,"title":title})
 for found in re.findall(r"https?://[^\s)\]>\"']+",raw):
  url=found.rstrip(".,;")
  if canonical(url)==canonical(base) or canonical(url) in seen:continue
  seen.add(canonical(url));slug=clean(unquote(urlparse(url).path.rsplit("/",1)[-1]).replace("-"," ").replace("_"," "))
  links.append({"url":url,"title":slug if len(slug)>3 else "頁面內公開連結"})
 return clean(raw),links

def reader_title(text):
 match=re.search(r"(?:^|\s)Title:\s*(.{5,180}?)(?=\s+(?:URL Source:|Published Time:|Markdown Content:))",text,re.I)
 return clean(match[1]) if match else ""

class Parser(HTMLParser):
 def __init__(self): super().__init__(); self.text=[]; self.links=[]; self.href=""; self.anchor=[]; self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","svg"): self.skip+=1
  if tag=="a": self.href=dict(attrs).get("href",""); self.anchor=[]
 def handle_data(self,data):
  if not self.skip: self.text.append(data)
  if self.href: self.anchor.append(data)
 def handle_endtag(self,tag):
  if tag in ("script","style","svg") and self.skip: self.skip-=1
  if tag=="a" and self.href: self.links.append((self.href,clean(" ".join(self.anchor)))); self.href=""; self.anchor=[]

def parse(data,base):
 p=Parser(); p.feed(data.decode("utf-8",errors="replace")); links=[]; seen=set()
 for href,title in p.links:
  url=urljoin(base,href).split("#",1)[0]
  if url.startswith(("http://","https://")) and len(title)>2 and canonical(url) not in seen:
   seen.add(canonical(url)); links.append({"url":url,"title":title})
 return clean(" ".join(p.text)),links
def contains(text,terms):
 low=text.lower(); return any(term in low for term in terms)
def region(text,configured=""):
 if configured: return "亞洲" if configured in ("東亞","東南亞","南亞") else configured
 low=text.lower()
 overseas=next((name for name,words in REGIONS.items() if any(x in low for x in words)),"")
 return overseas or ("臺灣" if any(x in low for x in TAIWAN) else "")
def category(text,reg,configured="自動"):
 aliases={"攝影／影像":"影像","展覽機會":"展覽徵件","補助":"當代藝術"}
 if configured!="自動": return aliases.get(configured,configured)
 low=text.lower()
 if any(x in low for x in ("駐村","進駐","residency","artist-in-residence")): return "國內駐村" if reg=="臺灣" else "國外駐村"
 if any(x in low for x in ("展覽徵件","展覽申請","展演徵件","策展徵件","徵展","call for exhibitions","exhibition open call","curatorial open call")): return "展覽徵件"
 if any(x in low for x in ("攝影比賽","攝影獎","徵片競賽","競賽","比賽","大獎","award","prize","competition","contest")): return "競賽獎項"
 if any(x in low for x in ("攝影","影像","錄像","photography","photo","moving image","video art")): return "影像"
 return "當代藝術"
def categories_for(text,reg,configured="自動"):
 """Return inclusive subject/form facets instead of one exclusive bucket."""
 low=text.lower(); aliases={"攝影／影像":"影像","展覽機會":"展覽徵件","補助":"當代藝術"}; facets=[]
 configured=aliases.get(configured,configured)
 if configured not in ("","自動"):facets.append(configured)
 if any(x in low for x in ("攝影","影像","錄像","photography","photo","moving image","video art","film","xr","vr","digital image")):facets.append("影像")
 if any(x in low for x in ("競賽","比賽","大獎","攝影獎","award","prize","competition","contest")):facets.append("競賽獎項")
 if any(x in low for x in ("展覽徵件","展覽申請","展演徵件","策展徵件","徵展","call for exhibitions","exhibition open call","curatorial open call")):facets.append("展覽徵件")
 if any(x in low for x in ("駐村","進駐","residency","artist-in-residence")):facets.append("國內駐村" if reg=="臺灣" else "國外駐村")
 if any(x in low for x in ("當代藝術","視覺藝術","新媒體藝術","contemporary art","visual art","new media art")):facets.append("當代藝術")
 if not facets:facets.append(category(text,reg,configured))
 order=("影像","當代藝術","展覽徵件","競賽獎項","國內駐村","國外駐村")
 return [x for x in order if x in facets]
def country_for(text,reg):
 low=text.lower()
 if reg=="臺灣": return "臺灣"
 return next((name for name,words in COUNTRIES.items() if any(word in low for word in words)),reg)
def eligible(text,cat,reg):
 low=text.lower()
 lead=low[:240];status_scope=low[:600]
 if contains(status_scope,CLOSED) or contains(lead,RESULT) or contains(low,RESTRICTED) or contains(lead,NOT_CALL): return False,"closed/result/restricted/not-call"
 if reg=="臺灣" and cat=="國內駐村" and contains(low,DOMESTIC_FOREIGN): return False,"Taiwan foreign-only"
 return True,""

def employment_opportunity(text):
 low=text.lower()
 strong=("job title:","salary:","employment type:","we are hiring","job vacancy","current vacancies","we employ","職缺","徵才","薪資：","月薪：")
 if contains(low,strong):return True
 return (("part-time" in low or "full-time" in low) and ("employment" in low or "fixed term contract" in low or "pro rata" in low))

def local_only_application(text):
 """Detect location-gated eligibility on a verified call page."""
 low=text.lower()
 patterns=(
  r"\b(?:applicants?|artists?|creatives?|practitioners?)\s+(?:must|need\s+to|required\s+to)\s+(?:currently\s+)?(?:live|reside|be\s+based)\s+(?:in|within)\b",
  r"\b(?:only|exclusively)\s+(?:open|available|eligible)?\s*(?:to|for)?\s*(?:applicants?|artists?|creatives?|practitioners?)[^.]{0,100}\b(?:based|living|resident|residing)\s+(?:in|within)\b",
  r"\bopen\s+to\s+(?:applicants?|artists?|creatives?|practitioners?)[^.]{0,100}\b(?:based|living|resident|residing)\s+(?:in|within)\b",
  r"\bthis\s+(?:opportunity|call)\s+is\s+only\s+for\s+[^.]{0,100}(?:-based|residents?)\b",
 )
 global_terms=("worldwide","internationally","all nationalities","any nationality","any country","全球","不限國籍","國際藝術家")
 for pattern in patterns:
  for match in re.finditer(pattern,low,re.I):
   context=low[max(0,match.start()-100):match.end()+140]
   if not contains(context,global_terms):return True
 return False

def global_or_taiwan_eligibility(text):
 low=text.lower()
 global_terms=("worldwide","world-wide","all over the world","around the world","international open call","international artists","international applicants","artists internationally","open internationally","all nationalities","artists of all nationalities","any nationality","any country","regardless of nationality","open to all artists","global open call","全球","不限國籍","不限地區","海內外","國內外","国籍を問わず","国内外","世界各国","국적 제한 없음","전 세계","국내외")
 return contains(low,global_terms) or any(term.lower() in low for term in TAIWAN)

def social_post_url(url):
 parsed=urlparse(url);host=(parsed.hostname or "").lower();path=parsed.path.lower()
 if any(host==known or host.endswith("."+known) for known in SOCIAL_HOSTS):return True
 return bool(re.search(r"/(?:@[^/]+/\d{5,}|users/[^/]+/statuses/\d{5,})/?$",path))

MONTHS={}
for number,names in enumerate((("january","jan"),("february","feb"),("march","mar"),("april","apr"),("may",),("june","jun"),("july","jul"),("august","aug"),("september","sep","sept"),("october","oct"),("november","nov"),("december","dec")),1):
 for name in names:MONTHS[name]=number
def extract_date(text,terms):
 pattern=r"(?:"+"|".join(map(re.escape,terms))+r")[^。；\n]{0,180}"
 deadline_field=any(x in " ".join(terms).lower() for x in ("截止","deadline","closing","close"))
 numeric=r"(?<!\d)(?:(20\d{2}|1\d{2})\s*[年./-])?\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
 # Timelines often put the date before its label (e.g. 2026/07/10 徵件截止).
 marks=("截止","deadline","closing","close") if deadline_field else ("開放","開始","open","起")
 strong=[x for x in terms if any(mark in x.lower() for mark in marks)]
 if strong:
  reverse=re.search(numeric+r"[^。；\n\d]{0,24}(?:"+"|".join(map(re.escape,strong))+r")",text,re.I)
  if reverse:
   try:
    year=int(reverse[1]) if reverse[1] else int(today_iso()[:4])
    if year<1911:year+=1911
    return clean(reverse.group()),date(year,int(reverse[2]),int(reverse[3])).isoformat()
   except ValueError:pass
 for match in re.finditer(pattern,text,re.I):
  part=clean(match.group())
  # Stop before later schedule fields so result, exhibition and de-installation
  # dates cannot be mistaken for the application deadline.
  part=re.split(r"\s+(?=(?:評審|結果|入選|獲選|展覽場地|展覽期間|展期|佈展|布展|開幕|撤展|卸展|selection|results?|announcement|exhibition|installation|de-installation)\b)",part,maxsplit=1,flags=re.I)[0]
  parsed=[]
  month_names="|".join(sorted(MONTHS,key=len,reverse=True))
  for en in re.finditer(r"\b("+month_names+r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b",part,re.I):
   try:
    parsed.append(date(int(en[3]),MONTHS[en[1].lower()],int(en[2])).isoformat())
   except ValueError:pass
  for en in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("+month_names+r")\.?\s+(20\d{2})\b",part,re.I):
   try:
    parsed.append(date(int(en[3]),MONTHS[en[2].lower()],int(en[1])).isoformat())
   except ValueError:pass
  previous_year=None
  for num in re.finditer(numeric,part):
   try:
    year=int(num[1]) if num[1] else previous_year or int(today_iso()[:4])
    if year<1911: year+=1911
    previous_year=year;parsed.append(date(year,int(num[2]),int(num[3])).isoformat())
   except ValueError:pass
  if parsed:return part,(parsed[-1] if deadline_field else parsed[0])
 return "",""
def best_application(base,links):
 best=(base,0)
 for link in links:
  url=clean(link.get("url",""));title=clean(link.get("title",""));parsed=urlparse(url)
  if parsed.scheme not in ("http","https") or not parsed.hostname:continue
  value=(title+" "+url).lower();path=parsed.path.lower()
  if any(x in path for x in ("/member","/login","/signin","/sign-in","/register","/account","/profile","/followers","/following","/hashtag","/share")): continue
  if any(x in value for x in ("follow us","follow account","privacy policy","terms of use","cookie policy")):continue
  signal=sum(x in value for x in ("申請","報名","投稿","apply","application","submit","registration"))
  form=sum(x in value for x in ("forms.gle","typeform","submittable","docs.google.com/forms"))
  call_page=sum(x in value for x in ("open call","open-call","opencall","call for artists","call-for-artists","call for applications","artist residency","residency application","submission guidelines","entry form","徵件簡章","徵件辦法"))
  if not signal and not form and not call_page:continue
  score=signal*4+form*10+call_page*3
  if parsed.netloc.lower()!=urlparse(base).netloc.lower():score+=2
  if canonical(url)==canonical(base):continue
  if score>best[1]:best=(url,score)
 return best[0]
def official_application_email(text):
 for match in re.finditer(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])",text,re.I):
  context=text[max(0,match.start()-140):match.end()+80].lower()
  if contains(context,("apply","application","submit","submission","send your","email your","申請","報名","投稿","寄至","寄到","寄送")):return match.group(1).lower()
 return ""
def profile_application_links(user):
 links=[];seen=set()
 if not isinstance(user,dict):return links
 for link in user.get("bio_links") or []:
  if not isinstance(link,dict):continue
  url=clean(link.get("url",""));title=clean(link.get("title","")) or "個人檔案連結";value=(title+" "+url).lower()
  if not url.startswith(("http://","https://")):continue
  if not any(term in value for term in ("徵件","報名","申請","apply","application","forms.gle","docs.google.com/forms")):continue
  if canonical(url) in seen:continue
  seen.add(canonical(url));links.append({"url":url,"title":title})
 external_url=clean(user.get("external_url") or user.get("externalUrl"))
 if external_url.startswith(("http://","https://")) and canonical(external_url) not in seen:
  links.append({"url":external_url,"title":"Instagram 個人檔案申請候選｜官方網站"})
 return links
def title_clean(title):
 value=re.sub(r"^[\s✨✹📢📣⭐️]+","",clean(title))
 # English calls keep their original-language opportunity title, including
 # institution names and hyphenated programme names. Only trim page/site suffixes.
 latin=len(re.findall(r"[A-Za-z]",value)); han=len(re.findall(r"[\u4e00-\u9fff]",value))
 english=latin>=12 and latin>han*2
 if english:
  value=re.split(r"\s+[|｜]\s+(?=(?:Home|News|Opportunities|Applications|Official|Facebook|Instagram)\b)",value,maxsplit=1,flags=re.I)[0]
  value=re.split(r"(?:\s{2,}|[.!?]\s+)(?=(?:Applications?|The |This |We |Artists? |Deadline\b))",value,maxsplit=1,flags=re.I)[0]
  return value[:96].rstrip("，。,.：:；; |-–—")
 value=clean(re.split(r"(?:\||｜)(?!\s*(?:20\d{2}\s+)?Open\s*Call\b)",value,maxsplit=1,flags=re.I)[0])
 call_title=re.match(r"^(.{4,72}?(?:徵件|徵選|招募|藝術駐村|藝術進駐|駐留計劃|駐留計畫|駐村計畫|進駐計畫|展覽計畫|攝影獎|攝影比賽|Residency\s+Program|Artist-in-Residence|Open\s*Call))(?=\s|$)",value,re.I)
 if call_title: value=call_title.group(1)
 else: value=re.split(r"[。！？!?]|(?:\s{2,})|\s+(?:本計畫|本次|該計畫|這項|邀請|歡迎|旨在|希望|提供|成立於|自\d{4}年)",value,maxsplit=1)[0]
 return value[:64].rstrip("，。,.：:；; ")
def fingerprint(title,url): return re.sub(r"[^\w\u4e00-\u9fff]+","",title.lower())[:150]+":"+canonical(url).lower()
def save(item,db_path=None):
 c=database(db_path); stamp=now(); key=fingerprint(item["title"],item["url"])
 c.execute("""INSERT INTO opportunities(title,url,application_url,source,category,region,notes,opening_iso,deadline_iso,fingerprint,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET title=excluded.title,url=excluded.url,application_url=excluded.application_url,source=excluded.source,category=excluded.category,region=excluded.region,notes=excluded.notes,opening_iso=excluded.opening_iso,deadline_iso=excluded.deadline_iso,last_seen=excluded.last_seen""",(item["title"],item["url"],item["application_url"],item["source"],item["category"],item["region"],item["notes"],item["opening_iso"],item["deadline_iso"],key,stamp,stamp)); c.commit(); c.close()

def instagram_profile_candidates(profile):
 data=profile.get("data",{}) if isinstance(profile,dict) else {};user=data.get("user",{}) if isinstance(data,dict) else {}
 if not isinstance(user,dict):return []
 profile_forms=profile_application_links(user);links=[];timeline=user.get("edge_owner_to_timeline_media") or {}
 for edge in timeline.get("edges") or []:
  if not isinstance(edge,dict):continue
  node=edge.get("node") or {}
  if not isinstance(node,dict):continue
  caption_block=node.get("edge_media_to_caption") or {};captions=caption_block.get("edges") or []
  caption=captions[0].get("node",{}).get("text","") if captions and isinstance(captions[0],dict) else ""
  if not caption:continue
  caption_forms=[{"url":url.rstrip(".,;，。)"),"title":"官方報名申請表"} for url in re.findall(r"https?://[^\s]+",caption) if "forms.gle" in url or "docs.google.com/forms" in url]
  fallback_forms=profile_forms if not caption_forms and contains(caption,CALL) and contains(caption,TOPIC) else []
  forms=caption_forms+fallback_forms;post_url="https://www.instagram.com/p/"+node.get("shortcode","")+"/"
  links.append({"url":post_url,"title":clean(caption.split("\n",1)[0]),"prefetched":(clean(caption),forms),"post_text":clean(caption),"profile_link_urls":[link["url"] for link in fallback_forms],"require_application_evidence":True})
 return links

def parse_published_at(value):
 try:
  parsed=datetime.fromisoformat(clean(value).replace("Z","+00:00"))
  return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
 except (TypeError,ValueError):return None
def recently_published(value,lookback_days):
 published=parse_published_at(value)
 if not published:return False
 moment=datetime.now(timezone.utc)
 return moment-timedelta(days=max(1,int(lookback_days)))<=published<=moment+timedelta(days=1)
def source_values(source,plural,singular=""):
 values=source.get(plural) or (source.get(singular) if singular else []) or []
 if isinstance(values,str):values=[values]
 return [clean(value) for value in values if clean(value)]
def append_public_link(links,seen,url,title="頁面內公開連結"):
 url=clean(url)
 if not url.startswith(("http://","https://")) or blocked_candidate_url(url):return
 key=canonical(url);title=clean(title) or "頁面內公開連結"
 if key in seen:
  existing=next((link for link in links if canonical(link["url"])==key),None)
  generic=("頁面內公開連結","貼文內官方連結","外部徵件頁")
  if existing and (existing.get("title","") in generic or len(title)>len(existing.get("title",""))):existing["title"]=title
  return
 seen.add(key);links.append({"url":url,"title":title})
def fair_candidates(groups,limit):
 output=[];seen=set();position=0
 while len(output)<limit and any(position<len(group) for group in groups):
  for group in groups:
   if position>=len(group):continue
   candidate=group[position];key=canonical(candidate["url"])
   if key not in seen:seen.add(key);output.append(candidate)
   if len(output)>=limit:break
  position+=1
 return output
def social_source_name(platform,display_name,account):
 display_name=clean(display_name);account=clean(account)
 if display_name and account and account.lower() not in display_name.lower():return f"{platform}｜{display_name} (@{account.lstrip('@')})"
 return f"{platform}｜{display_name or account or '公開貼文'}"
def bluesky_facet_label(text,facet):
 index=facet.get("index",{}) if isinstance(facet,dict) else {}
 try:
  raw=(text or "").encode("utf-8");start=int(index.get("byteStart",-1));end=int(index.get("byteEnd",-1))
  if start<0 or end<=start or end>len(raw):return ""
  return clean(raw[start:end].decode("utf-8"))
 except (TypeError,ValueError,UnicodeDecodeError):return ""
def append_profile_candidate_link(links,seen,url,platform,label="",profile_url=""):
 url=clean(url).rstrip(".,;，。)")
 if not url.startswith(("http://","https://")) or blocked_candidate_url(url):return
 if social_post_url(url) or (profile_url and canonical(url)==canonical(profile_url)):return
 title=f"{platform} 個人檔案申請候選｜{clean(label) or '公開連結'}"
 append_public_link(links,seen,url,title)
def append_profile_markup_links(links,seen,markup,platform,label,profile_url):
 markup=str(markup or "")
 if not markup:return
 _,parsed=parse(markup.encode("utf-8"),profile_url)
 for link in parsed:append_profile_candidate_link(links,seen,link.get("url",""),platform,clean(label+" "+link.get("title","")),profile_url)
 for found in re.findall(r"https?://[^\s<>\]\[\"']+",html.unescape(markup)):
  append_profile_candidate_link(links,seen,found,platform,label,profile_url)
def bluesky_profile_links(profile):
 links=[];seen=set()
 if not isinstance(profile,dict):return links
 handle=clean(profile.get("handle",""));profile_url=f"https://bsky.app/profile/{handle}" if handle else "https://bsky.app/"
 records=[profile]
 for key in ("value","record"):
  if isinstance(profile.get(key),dict):records.append(profile[key])
 for record in records:
  description=str(record.get("description","") or "")
  facets=record.get("descriptionFacets") or record.get("facets") or []
  for facet in facets if isinstance(facets,list) else []:
   label=bluesky_facet_label(description,facet) or "自介連結"
   for feature in facet.get("features",[]) if isinstance(facet,dict) else []:
    if str(feature.get("$type","")).endswith("#link"):
     append_profile_candidate_link(links,seen,feature.get("uri",""),"Bluesky",label,profile_url)
  append_profile_markup_links(links,seen,description,"Bluesky","自介",profile_url)
  for key in ("website","externalUrl"):
   append_profile_candidate_link(links,seen,record.get(key,""),"Bluesky",key,profile_url)
  for field in record.get("fields",[]) if isinstance(record.get("fields"),list) else []:
   if isinstance(field,dict):append_profile_markup_links(links,seen,field.get("value",""),"Bluesky",clean(field.get("name","")) or "欄位",profile_url)
 return links
def mastodon_profile_links(account):
 links=[];seen=set()
 if not isinstance(account,dict):return links
 profile_url=clean(account.get("url") or account.get("uri")) or "https://mastodon.social/"
 append_profile_markup_links(links,seen,account.get("note",""),"Mastodon","自介",profile_url)
 for field in account.get("fields",[]) if isinstance(account.get("fields"),list) else []:
  if isinstance(field,dict):append_profile_markup_links(links,seen,field.get("value",""),"Mastodon",clean(field.get("name","")) or "欄位",profile_url)
 for key in ("website","external_url"):
  append_profile_candidate_link(links,seen,account.get(key,""),"Mastodon",key,profile_url)
 return links
def add_candidate_profile_links(candidate,profile_links):
 detail,links=candidate.get("prefetched",("",[]));seen={canonical(link["url"]) for link in links}
 added=[]
 for link in profile_links:
  url=link.get("url","");append_public_link(links,seen,url,link.get("title",""));key=canonical(url)
  if any(canonical(existing["url"])==key for existing in links):added.append(url)
 candidate["prefetched"]=(detail,links);candidate["profile_link_urls"]=list(dict.fromkeys(candidate.get("profile_link_urls",[])+added));return candidate
def candidate_has_external_application_link(candidate):
 _,links=candidate.get("prefetched",("",[]));base=candidate.get("url","");selected=best_application(base,links)
 base_host=(urlparse(base).hostname or "").lower();selected_host=(urlparse(selected).hostname or "").lower()
 return selected.startswith(("http://","https://")) and canonical(selected)!=canonical(base) and selected_host!=base_host and not social_post_url(selected)
def candidate_supports_profile_fallback(candidate):
 post_text=clean(candidate.get("post_text") or (candidate.get("title","")+" "+candidate.get("prefetched",("",[]))[0]))
 return contains(post_text,CALL) and contains(post_text,TOPIC)
def profile_edition_mismatch(post_text,official_text):
 years=lambda value:set(re.findall(r"(?<!\d)20\d{2}(?!\d)",value or ""))
 post_years=years(post_text);official_years=years(official_text)
 return bool(post_years and official_years and post_years.isdisjoint(official_years))
def profile_deadline_mismatch(post_text,official_text):
 labels=("截止日期","申請截止","徵件截止","報名截止","收件截止","徵件時間","deadline","closing date","applications close")
 _,post_deadline=extract_date(post_text,labels);_,official_deadline=extract_date(official_text,labels)
 return bool(post_deadline and official_deadline and post_deadline!=official_deadline)
def bluesky_post_candidate(post,lookback_days,query=""):
 record=post.get("record",{}) if isinstance(post,dict) else {}
 published=record.get("createdAt") or post.get("indexedAt","")
 if not recently_published(published,lookback_days):return None
 author=post.get("author",{});handle=clean(author.get("handle",""));uri=clean(post.get("uri",""));rkey=uri.rsplit("/",1)[-1]
 if not handle or not rkey or rkey==uri:return None
 url=f"https://bsky.app/profile/{handle}/post/{rkey}";text=clean(record.get("text",""));details=[text];links=[];seen=set()
 for facet in record.get("facets",[]):
  facet_title=bluesky_facet_label(record.get("text","") or "",facet) or "貼文內官方連結"
  for feature in facet.get("features",[]):
   if str(feature.get("$type","")).endswith("#link"):append_public_link(links,seen,feature.get("uri",""),facet_title)
 for found in re.findall(r"https?://[^\s<>\]\[\"']+",record.get("text","") or ""):append_public_link(links,seen,found.rstrip(".,;，。)"))
 embed=post.get("embed",{}) or {};external=embed.get("external",{}) or {}
 if external:
  append_public_link(links,seen,external.get("uri",""),external.get("title","") or "外部徵件頁")
  details.extend((clean(external.get("title","")),clean(external.get("description",""))))
 for item in embed.get("images",[]) or []:details.append(clean(item.get("alt","")))
 title=clean((record.get("text","") or "").split("\n",1)[0]) or clean(external.get("title","")) or "Bluesky 公開徵件貼文"
 candidate={"url":url,"title":title[:240],"prefetched":((" ".join(x for x in details if x)),links),"source_name":social_source_name("Bluesky",author.get("displayName",""),handle),"published_at":published,"discovery_query":query,"require_application_evidence":True,"post_text":" ".join(x for x in details if x),"profile_link_urls":[]}
 if candidate_supports_profile_fallback(candidate) and not candidate_has_external_application_link(candidate):add_candidate_profile_links(candidate,bluesky_profile_links(author))
 return candidate
def bluesky_search_candidates(source):
 queries=source_values(source,"queries","query")
 if not queries:raise ValueError("Bluesky search needs at least one query")
 limit=max(1,int(source.get("max_candidates",60)));per_query=max(1,min(100,int(source.get("per_query",max(10,(limit+len(queries)-1)//len(queries))))));groups=[];errors=[];profiles={};profile_lookups=0;max_profile_lookups=max(1,int(source.get("max_profile_lookups",40)))
 for query in queries:
  api="https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?"+urlencode({"q":query,"limit":per_query,"sort":"latest"})
  try:
   data,_=fetch(api);payload=json.loads(data)
   if not isinstance(payload,dict) or not isinstance(payload.get("posts"),list):raise ValueError("invalid Bluesky search response")
   candidates=[]
   for post in payload["posts"]:
    candidate=bluesky_post_candidate(post,source.get("lookback_days",90),query)
    if not candidate:continue
    if not candidate_has_external_application_link(candidate) and candidate_supports_profile_fallback(candidate):
     author=post.get("author",{}) if isinstance(post,dict) else {};actor=clean(author.get("did") or author.get("handle"))
     if actor and actor not in profiles and profile_lookups<max_profile_lookups:
      profile_lookups+=1
      try:
       profile_data,_=fetch("https://api.bsky.app/xrpc/app.bsky.actor.getProfile?"+urlencode({"actor":actor}));profile=json.loads(profile_data)
       profiles[actor]=profile if isinstance(profile,dict) else {}
      except Exception:profiles[actor]={}
     if actor:add_candidate_profile_links(candidate,bluesky_profile_links(profiles.get(actor,{})))
    candidates.append(candidate)
   groups.append(candidates)
  except Exception as exc:errors.append(str(exc))
 if not groups and errors:raise RuntimeError("all Bluesky searches failed: "+errors[0][:180])
 if not groups or not any(groups):raise RuntimeError("Bluesky searches returned no recent posts")
 return fair_candidates(groups,limit)
def mastodon_status_candidate(status,lookback_days,tag=""):
 if not isinstance(status,dict):return None
 status=status.get("reblog") or status
 published=status.get("created_at","")
 if not recently_published(published,lookback_days):return None
 url=clean(status.get("url") or status.get("uri"));account=status.get("account",{}) or {}
 if not url.startswith(("http://","https://")):return None
 content=status.get("content","") or "";detail,links=parse(content.encode("utf-8"),url);seen={canonical(link["url"]) for link in links};parts=[detail]
 card=status.get("card",{}) or {}
 if card:
  append_public_link(links,seen,card.get("url",""),card.get("title","") or "外部徵件頁")
  parts.extend((clean(card.get("title","")),clean(card.get("description",""))))
 for attachment in status.get("media_attachments",[]) or []:parts.append(clean(attachment.get("description") or attachment.get("text_url","")))
 title=clean(detail)[:240] or clean(card.get("title","")) or "Mastodon 公開徵件貼文"
 candidate={"url":url,"title":title,"prefetched":((" ".join(x for x in parts if x)),links),"source_name":social_source_name("Mastodon",account.get("display_name",""),account.get("acct","")),"published_at":published,"discovery_query":"#"+tag.lstrip("#"),"require_application_evidence":True,"post_text":" ".join(x for x in parts if x),"profile_link_urls":[]}
 if candidate_supports_profile_fallback(candidate) and not candidate_has_external_application_link(candidate):add_candidate_profile_links(candidate,mastodon_profile_links(account))
 return candidate
def mastodon_tag_candidates(source):
 tags=source_values(source,"tags","tag")
 if not tags:
  path=urlparse(source.get("url","")).path.rstrip("/");tags=[unquote(path.rsplit("/",1)[-1])] if "/tags/" in path else []
 if not tags:raise ValueError("Mastodon discovery needs at least one hashtag")
 instance=clean(source.get("instance",""))
 if not instance:
  parsed=urlparse(source.get("url",""));instance=urlunparse((parsed.scheme,parsed.netloc,"","","", ""))
 instance=instance.rstrip("/")
 parsed_instance=urlparse(instance)
 if parsed_instance.scheme not in ("http","https") or not parsed_instance.hostname:raise ValueError("Mastodon instance must be an HTTP(S) URL")
 limit=max(1,int(source.get("max_candidates",60)));per_tag=max(1,min(40,int(source.get("per_tag",max(10,(limit+len(tags)-1)//len(tags))))));groups=[];errors=[]
 for tag in tags:
  safe_tag=re.sub(r"[^\w]","",tag,flags=re.UNICODE)
  if not safe_tag:continue
  api=instance+"/api/v1/timelines/tag/"+quote(safe_tag,safe="")+"?"+urlencode({"limit":per_tag})
  try:
   data,_=fetch(api);payload=json.loads(data)
   if not isinstance(payload,list):raise ValueError("invalid Mastodon hashtag response")
   statuses=payload
   groups.append([candidate for status in statuses if (candidate:=mastodon_status_candidate(status,source.get("lookback_days",90),safe_tag))])
  except Exception as exc:errors.append(str(exc))
 if not groups and errors:raise RuntimeError("all Mastodon hashtag searches failed: "+errors[0][:180])
 if not groups or not any(groups):raise RuntimeError("Mastodon hashtags returned no recent posts")
 return fair_candidates(groups,limit)

def crawl_source(source,db_path=None):
 report={"source":source["name"],"status":"ok","candidates":0,"accepted":0,"rejected":0,"fetch_errors":0,"fallback_fetches":0,"restricted_candidates":[],"error":""}
 if source["mode"]=="browser": report["status"]="manual-check"; return report
 try:
  if source["mode"]=="bluesky_search":
   links=bluesky_search_candidates(source);body=" ".join(x["title"] for x in links);final=source.get("url","https://bsky.app/")
  elif source["mode"]=="mastodon_tags":
   links=mastodon_tag_candidates(source);body=" ".join(x["title"] for x in links);final=source.get("url",source.get("instance","https://mastodon.social"))
  elif source["mode"]=="instagram_profile":
   profile_url="https://www.instagram.com/api/v1/users/web_profile_info/?username="+source["username"]
   req=urllib.request.Request(profile_url,headers={"User-Agent":"Mozilla/5.0","x-ig-app-id":"936619743392459"})
   with urllib.request.urlopen(req,timeout=30) as response: profile=json.loads(response.read())
   links=instagram_profile_candidates(profile)
   body=" ".join(x["title"] for x in links); final=source["url"]
  elif source["mode"]=="search":
   search_url="https://www.bing.com/search?format=rss&q="+quote_plus(source["query"])
   data,final=fetch(search_url); root=ET.fromstring(data)
   links=[{"url":clean(node.findtext("link")),"title":clean(node.findtext("title"))} for node in root.findall(".//item") if clean(node.findtext("link"))]
   body=" ".join(x["title"] for x in links)
  else:
   try: data,final=fetch(source["url"]); body,links=parse(data,final)
   except Exception:
    try:
     body,links,final,method=readable_fetch(source["url"])
     if method=="reader": report["fallback_fetches"]+=1
    except Exception:
     if not source.get("query"): raise
     search_url="https://www.bing.com/search?format=rss&q="+quote_plus(source["query"])
     data,final=fetch(search_url); root=ET.fromstring(data)
     links=[{"url":clean(node.findtext("link")),"title":clean(node.findtext("title"))} for node in root.findall(".//item") if clean(node.findtext("link"))]
     body=" ".join(x["title"] for x in links)
  promising=[]
  if source["mode"]=="direct": promising.append({"url":final,"title":source["name"],"prefetched":(body,links)})
  if source["mode"] in ("search","instagram_profile","bluesky_search","mastodon_tags"): promising.extend(links)
  for link in links:
   value=link["title"]+" "+link["url"]
   if contains(value,CALL) or any(x in link["url"].lower() for x in ("call","open-call","apply","application","residen","grant")): promising.append(link)
  if not promising and source.get("query") and source["mode"] not in ("search","bluesky_search","mastodon_tags"):
   search_url="https://www.bing.com/search?format=rss&q="+quote_plus(source["query"])
   search_data,_=fetch(search_url); search_root=ET.fromstring(search_data)
   promising=[{"url":clean(node.findtext("link")),"title":clean(node.findtext("title"))} for node in search_root.findall(".//item") if clean(node.findtext("link"))]
  unique={canonical(x["url"]):x for x in promising}; candidates=list(unique.values())[:source.get("max_candidates",60)]; report["candidates"]=len(candidates)
  def inspect(candidate):
   try:
    generic=("跳到主要內容區塊","skip to content","english","open call","schedule","programs","artist","residency","latest news","最新消息")
    candidate_title=clean(candidate["title"]).lower()
    if blocked_candidate_url(candidate["url"]):return None,"blocked-domain"
    if candidate_title in generic or (source["mode"] not in ("direct","search") and candidate_title==source["name"].lower()): return None,"generic navigation"
    if "prefetched" in candidate: detail,detail_links=candidate["prefetched"]; url=candidate["url"]; method="prefetched"
    else:
     detail,detail_links,url,method=readable_fetch(candidate["url"])
   except Exception as exc: return None,"fetch-error:"+str(exc)[:80]
   full=candidate["title"]+" "+detail;verified_detail=""
   application_url=best_application(url,detail_links)
   if candidate.get("require_application_evidence"):
    profile_urls={canonical(link) for link in candidate.get("profile_link_urls",[]) if link.startswith(("http://","https://"))}
    application_from_profile=canonical(application_url) in profile_urls
    base_host=(urlparse(url).hostname or "").lower();application_host=(urlparse(application_url).hostname or "").lower()
    external=application_url.startswith(("http://","https://")) and canonical(application_url)!=canonical(url) and application_host!=base_host and not social_post_url(application_url)
    email=official_application_email(full)
    if not external and not email:return None,"no external application evidence"
    if external:
     try:
      official_detail,official_links,resolved_application,official_method=readable_fetch(application_url)
     except Exception as exc:return None,"official-fetch-error:"+str(exc)[:80]
     if len(clean(official_detail))<80:return None,"official page has too little verification detail"
     if social_post_url(resolved_application):return None,"external evidence is another social post"
     if application_from_profile and profile_edition_mismatch(candidate.get("post_text",""),official_detail):return None,"profile edition mismatch"
     if application_from_profile and profile_deadline_mismatch(candidate.get("post_text",""),official_detail):return None,"profile deadline mismatch"
     if not contains(official_detail,CALL) or not contains(official_detail,TOPIC):return None,"official page is not an art call"
     official_deadline_note,official_deadline=extract_date(official_detail,("截止日期","申請截止","徵件截止","報名截止","收件截止","徵件時間","deadline","closing date","applications close"))
     if not official_deadline and not contains(official_detail,ROLLING):return None,"official page has no open deadline"
     if not global_or_taiwan_eligibility(official_detail):return None,"Taiwan eligibility not verified"
     verified_detail=official_detail;full+=" "+official_detail;application_url=resolved_application
     action_terms=("申請","報名","投稿","apply","application","submit","registration","forms.gle","typeform","submittable","docs.google.com/forms")
     action_links=[link for link in official_links if contains((link.get("title","")+" "+link.get("url","")).lower(),action_terms)]
     refined_application=best_application(application_url,action_links)
     if canonical(refined_application)!=canonical(application_url):
      try:ensure_public_http_url(refined_application)
      except ValueError:return None,"unsafe application target"
      application_url=refined_application
    else:
     if not global_or_taiwan_eligibility(full):return None,"Taiwan eligibility not verified"
     application_url="mailto:"+email
    if employment_opportunity(full):return None,"employment opportunity"
    if local_only_application(full):return None,"location-restricted"
   if not contains(full,CALL) or not contains(full,TOPIC): return None,"not call/topic"
   reg=region(full,source.get("region","")); cat=category(full,reg,source.get("category","自動")); ok,reason=eligible(full,cat,reg)
   if not ok:return None,reason
   opening_note,opening=extract_date(full,("開放","開始受理","申請期間","徵件期間","即日起","applications open","application period","opens"))
   deadline_note,deadline=extract_date(verified_detail or full,("截止日期","申請截止","徵件截止","報名截止","收件截止","徵件時間","deadline","closing date","applications close"))
   # If only one official date exists, it is the deadline. Keep the factual
   # opening unknown; the Gantt UI already uses today as its planning start.
   if opening and opening==deadline:opening="";opening_note=""
   if deadline and deadline<today_iso():return None,"expired"
   if not deadline and not contains(full,ROLLING):return None,"no proof still open"
   candidate_name=reader_title(detail) if candidate_title=="頁面內公開連結" else candidate["title"]
   title=title_clean(candidate_name if len(candidate_name)>5 else source["name"])
   return {"title":title,"url":url,"application_url":application_url,"source":candidate.get("source_name",source["name"]),"category":cat,"region":reg,"notes":deadline_note or opening_note,"opening_iso":opening,"deadline_iso":deadline},("fallback-reader" if method=="reader" else "")
  with concurrent.futures.ThreadPoolExecutor(max_workers=source.get("workers",6)) as pool:
   for candidate,(item,reason) in zip(candidates,pool.map(inspect,candidates)):
    if item:
     save(item,db_path);report["accepted"]+=1
     if reason=="fallback-reader": report["fallback_fetches"]+=1
    else:
     report["rejected"]+=1
     if reason.startswith(("fetch-error:","official-fetch-error:")):
      report["fetch_errors"]+=1
      if len(report["restricted_candidates"])<8: report["restricted_candidates"].append({"title":title_clean(candidate.get("title","候選頁面")),"url":candidate.get("url",""),"reason":reason.split(":",1)[-1]})
  if candidate_detail_outage(report):
   report["status"]="error";report["error"]="most candidate detail fetches failed"
  if report["candidates"] and report["status"]=="ok":
   stale=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat(timespec="seconds")
   c=database(db_path)
   if source["mode"] in ("bluesky_search","mastodon_tags"):
    prefix="Bluesky｜" if source["mode"]=="bluesky_search" else "Mastodon｜"
    c.execute("DELETE FROM opportunities WHERE source LIKE ? AND deadline_iso='' AND last_seen<?",(prefix+"%",stale))
   else:c.execute("DELETE FROM opportunities WHERE source=? AND deadline_iso='' AND last_seen<?",(source["name"],stale))
   c.commit(); c.close()
 except Exception as exc: report["status"]="error";report["error"]=str(exc)[:300]
 return report

def candidate_detail_outage(report):
 return bool(report["candidates"] and report["fetch_errors"]*5>=report["candidates"]*4)
def harvest_healthy(reports):
 automated=[item for item in reports if item["status"]!="manual-check"]
 errors=sum(item["status"]=="error" for item in automated)
 return errors<max(3,(len(automated)+1)//2)
def harvest(db_path=None,report_path=None):
 target=Path(db_path or DB);report_target=Path(report_path or REPORT);sources=load(SOURCES,"sources")
 stage=target.with_name(f".{target.name}.{time.time_ns()}.staging")
 if target.exists():shutil.copy2(target,stage)
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: reports=list(pool.map(lambda source:crawl_source(source,stage),sources))
  if VERIFIED.exists():
   verified=load(VERIFIED,"opportunities"); kept=0
   for item in verified:
    if not item.get("deadline_iso") or item["deadline_iso"]>=today_iso(): save(item,stage); kept+=1
   reports.append({"source":"攝影專題人工查證庫","status":"ok","candidates":len(verified),"accepted":kept,"rejected":len(verified)-kept,"fetch_errors":0,"error":""})
  c=database(stage); c.execute("DELETE FROM opportunities WHERE deadline_iso<>'' AND deadline_iso<?",(today_iso(),)); c.commit(); c.close()
  payload={"started_at":now(),"sources":reports,"accepted":sum(x["accepted"] for x in reports),"errors":sum(x["status"]=="error" for x in reports)}
  if not harvest_healthy(reports):
   failures=[{"source":item["source"],"error":item.get("error","") or "source health check failed","candidates":item.get("candidates",0),"fetch_errors":item.get("fetch_errors",0)} for item in reports if item["status"]=="error"]
   raise RuntimeError(f"crawl health gate failed ({len(failures)}/{len(reports)} sources); previous data was preserved; failures="+json.dumps(failures,ensure_ascii=False,separators=(",",":")))
  stage.replace(target);atomic_write(report_target,json.dumps(payload,ensure_ascii=False,indent=2));return payload
 finally:
  stage.unlink(missing_ok=True)
def opportunity_key(title):
 value=title_clean(title).lower()
 value=re.sub(r"(?:公開)?(?:展覽)?(?:徵件|徵選|招募|機會|計畫|open\s*call)$","",value,flags=re.I)
 return re.sub(r"[^a-z0-9\u4e00-\u9fff]+","",value)
def same_opportunity(a,b):
 years_a=set(re.findall(r"(?<!\d)20\d{2}(?!\d)",a.get("title","")));years_b=set(re.findall(r"(?<!\d)20\d{2}(?!\d)",b.get("title","")))
 if years_a and years_b and years_a.isdisjoint(years_b):return False
 deadline_years_a={a.get("deadline_iso","")[:4]} if re.match(r"^20\d{2}-",a.get("deadline_iso","") or "") else set()
 deadline_years_b={b.get("deadline_iso","")[:4]} if re.match(r"^20\d{2}-",b.get("deadline_iso","") or "") else set()
 if not years_a and not years_b and deadline_years_a and deadline_years_b and deadline_years_a.isdisjoint(deadline_years_b):return False
 ak,bk=opportunity_key(a.get("title","")),opportunity_key(b.get("title",""))
 if min(len(ak),len(bk))<7:return False
 dates_match=not a.get("deadline_iso") or not b.get("deadline_iso") or a["deadline_iso"]==b["deadline_iso"]
 title_match=ak==bk or difflib.SequenceMatcher(None,ak,bk).ratio()>=.9
 announcement_a={canonical(a["url"])} if a.get("url","").startswith("http") else set();announcement_b={canonical(b["url"])} if b.get("url","").startswith("http") else set()
 if announcement_a & announcement_b:return title_match
 application_a={canonical(a["application_url"])} if a.get("application_url","").startswith("http") else set();application_b={canonical(b["application_url"])} if b.get("application_url","").startswith("http") else set()
 if application_a & application_b:
  prefix_variant=min(len(ak),len(bk))>=16 and (ak.startswith(bk) or bk.startswith(ak))
  return dates_match and (ak==bk or prefix_variant)
 return dates_match and title_match
def merge_opportunities(items):
 merged=[]
 for item in items:
  found=next((x for x in merged if same_opportunity(x,item)),None)
  if not found:
   item["_opening_candidates"]=[item["opening_iso"]] if item.get("opening_iso") else []
   item["_deadline_candidates"]=[item["deadline_iso"]] if item.get("deadline_iso") else []
   merged.append(item);continue
  if len(item.get("original_title",item["title"]))>len(found.get("original_title",found["title"])):
   found["original_title"]=item.get("original_title",item["title"])
  if len(item.get("notes",""))>len(found.get("notes","")):found["notes"]=item["notes"]
  if found.get("application_url")==found.get("url") and item.get("application_url")!=item.get("url"):found["application_url"]=item["application_url"]
  if item.get("opening_iso"):found["_opening_candidates"].append(item["opening_iso"])
  if item.get("deadline_iso"):found["_deadline_candidates"].append(item["deadline_iso"])
  for field in ("country","region"):
   if not found.get(field) and item.get(field):found[field]=item[field]
  seen={g["url"] for g in found.get("suggested_grants",[])}
  found["suggested_grants"]+= [g for g in item.get("suggested_grants",[]) if g["url"] not in seen]
  found["categories"]=[x for x in ("影像","當代藝術","展覽徵件","競賽獎項","國內駐村","國外駐村") if x in found.get("categories",[])+item.get("categories",[])]
 for item in merged:
  for field,candidates in (("opening_iso",item.pop("_opening_candidates")),("deadline_iso",item.pop("_deadline_candidates"))):
   if candidates:
    counts={value:candidates.count(value) for value in candidates}
    item[field]=sorted(counts,key=lambda value:(-counts[value],value))[0]
 return merged
def opportunities():
 c=database(); rows=c.execute("SELECT * FROM opportunities WHERE deadline_iso='' OR deadline_iso>=? ORDER BY CASE WHEN deadline_iso='' THEN 1 ELSE 0 END,deadline_iso,title",(today_iso(),)).fetchall();c.close(); grants=load(GRANTS,"grants");out=[]
 for row in rows:
  item=dict(row)
  if blocked_candidate_url(item.get("url", "")):continue
  if title_clean(item["title"]).lower() in ("頁面內公開連結","open call","latest news","最新消息"):continue
  title_overrides={
   "https://www.carlottagallery.co.uk/opencalls":"Carlotta Gallery — ‘On Film’ Photography Open Call, UK",
   "https://canserrat.org/collective-creation2027_internationalresidency":"甘塞拉國際藝術中心 2027 行走實踐實驗室",
  }
  override=title_overrides.get(canonical(item.get("application_url") or item["url"])) or title_overrides.get(canonical(item["url"]))
  if override:item["title"]=override
  item["original_title"]=item["title"]; item["region"]="亞洲" if item["region"] in ("東亞","東南亞","南亞") else item["region"]; item["categories"]=categories_for(item["title"]+" "+item["notes"],item["region"],item["category"]); item["category"]=item["categories"][0]; item["opening_inferred"]=not bool(item["opening_iso"]); item["display_opening_iso"]=item["opening_iso"] or ""; item["country"]=country_for(" ".join((item["title"],item["notes"],item["source"])),item["region"]); item["title"]=title_clean(item["title"]); text=" ".join((item["title"],item["notes"],item["region"])).lower(); item["suggested_grants"]=[g for g in grants if any(cat in g["categories"] for cat in item["categories"]) and (not g.get("regions") or any(x.lower() in text for x in g["regions"]))];out.append(item)
 return merge_opportunities(out)
def api_payload():
 items=opportunities();return {"opportunities":items,"sources":load(SOURCES,"sources"),"stats":{"total":len(items),"with_deadline":sum(bool(x["deadline_iso"]) for x in items),"last_updated":max((x["last_seen"] for x in items),default="")},"crawl_report":json.loads(REPORT.read_text()) if REPORT.exists() else {}}
def export(path):
 atomic_write(path,json.dumps(api_payload(),ensure_ascii=False,indent=2))
class API(BaseHTTPRequestHandler):
 def reply(self,status,data,kind,head=False):
  self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("Referrer-Policy","strict-origin-when-cross-origin");self.end_headers()
  if not head:self.wfile.write(data)
 def dispatch(self,head=False):
  path=urlparse(self.path).path
  if path=="/api/data":return self.reply(200,json.dumps(api_payload(),ensure_ascii=False).encode(),"application/json;charset=utf-8",head)
  assets={"/":"index.html","/style.css":"style.css","/app.js":"app.js"}
  assets["/app-core.js"]="app-core.js"
  if path in assets:
   name=assets[path];kind="text/html;charset=utf-8" if name.endswith("html") else "text/css;charset=utf-8" if name.endswith("css") else "application/javascript;charset=utf-8";return self.reply(200,(WEB/name).read_bytes(),kind,head)
  self.send_error(404)
 def do_GET(self):return self.dispatch(False)
 def do_HEAD(self):return self.dispatch(True)
 def log_message(self,*_):pass
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True);sub.add_parser("fetch");s=sub.add_parser("serve");s.add_argument("--host",default="127.0.0.1");s.add_argument("--port",type=int,default=8080);e=sub.add_parser("export");e.add_argument("--output",type=Path,default=ROOT/"docs"/"calls.json");a=p.parse_args()
 if a.cmd=="fetch":
  try:result=harvest()
  except RuntimeError as exc:raise SystemExit(str(exc))
  print(json.dumps(result,ensure_ascii=False,indent=2))
 elif a.cmd=="export":export(a.output);print(a.output)
 else:ThreadingHTTPServer((a.host,a.port),API).serve_forever()
if __name__=="__main__":main()
