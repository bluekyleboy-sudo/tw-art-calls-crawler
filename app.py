#!/usr/bin/env python3
"""OPEN FIELD — robust public art-opportunity collector and local web server."""
from __future__ import annotations

import argparse, concurrent.futures, difflib, gzip, html, json, re, shutil, sqlite3, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, quote_plus, urljoin, urlparse, urlunparse

ROOT=Path(__file__).parent; WEB=ROOT/"web"; DB=ROOT/"open-field.sqlite3"; REPORT=ROOT/"last-crawl.json"
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
def clean(s): return re.sub(r"\s+"," ",html.unescape(str(s or ""))).strip()
def load(path,key): return json.loads(path.read_text(encoding="utf-8"))[key]
def canonical(url):
 p=urlparse(url); return urlunparse((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/") or "/","","",""))
def database():
 c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
 c.execute("""CREATE TABLE IF NOT EXISTS opportunities(id INTEGER PRIMARY KEY,title TEXT,url TEXT,application_url TEXT,source TEXT,category TEXT,region TEXT,notes TEXT,opening_iso TEXT,deadline_iso TEXT,fingerprint TEXT UNIQUE,first_seen TEXT,last_seen TEXT)""")
 c.execute("CREATE INDEX IF NOT EXISTS deadline_idx ON opportunities(deadline_iso)"); c.commit(); return c

def fetch(url):
 parsed=urlparse(url); url=urlunparse((parsed.scheme,parsed.netloc,quote(parsed.path,safe="/%:@"),parsed.params,quote(parsed.query,safe="=&%:+,()"),parsed.fragment))
 last=None
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/json;q=.9,*/*;q=.5","Accept-Language":"zh-TW,zh;q=.9,en;q=.8","Accept-Encoding":"gzip"})
   with urllib.request.urlopen(req,timeout=30) as response:
    data=response.read(8_000_000)
    if response.headers.get("Content-Encoding")=="gzip": data=gzip.decompress(data)
    return data,response.geturl()
  except Exception as exc:
   last=exc
   if attempt<2: time.sleep(1.25*(attempt+1))
 raise last

def readable_fetch(url):
 """Fetch a detail page, falling back to a public text reader for blocked pages."""
 try:
  data,final=fetch(url); text,links=parse(data,final); return text,links,url,"direct"
 except Exception as direct_error:
  reader="https://r.jina.ai/"+url
  try:
   data,_=fetch(reader); text=clean(data.decode("utf-8",errors="replace")); links=[]
   for found in dict.fromkeys(re.findall(r"https?://[^\s)\]>\"']+",text)):
    links.append({"url":found.rstrip(".,;"),"title":"頁面內公開連結"})
   if len(text)<40: raise ValueError("reader returned too little content")
   return text,links,url,"reader"
  except Exception:
   raise direct_error

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
 lead=low[:240]
 if contains(low,CLOSED) or contains(lead,RESULT) or contains(low,RESTRICTED) or contains(lead,NOT_CALL): return False,"closed/result/restricted/not-call"
 if reg=="臺灣" and cat=="國內駐村" and contains(low,DOMESTIC_FOREIGN): return False,"Taiwan foreign-only"
 return True,""

MONTHS={m:i+1 for i,m in enumerate(("january","february","march","april","may","june","july","august","september","october","november","december"))}
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
    year=int(reverse[1]) if reverse[1] else date.today().year
    if year<1911:year+=1911
    return clean(reverse.group()),date(year,int(reverse[2]),int(reverse[3])).isoformat()
   except ValueError:pass
 for match in re.finditer(pattern,text,re.I):
  part=clean(match.group())
  # Stop before later schedule fields so result, exhibition and de-installation
  # dates cannot be mistaken for the application deadline.
  part=re.split(r"\s+(?=(?:評審|結果|入選|獲選|展覽場地|展覽期間|展期|佈展|布展|開幕|撤展|卸展|selection|results?|announcement|exhibition|installation|de-installation)\b)",part,maxsplit=1,flags=re.I)[0]
  parsed=[]
  for en in re.finditer(r"("+"|".join(MONTHS)+r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})",part,re.I):
   try:
    parsed.append(date(int(en[3]),MONTHS[en[1].lower()],int(en[2])).isoformat())
   except ValueError:pass
  previous_year=None
  for num in re.finditer(numeric,part):
   try:
    year=int(num[1]) if num[1] else previous_year or date.today().year
    if year<1911: year+=1911
    previous_year=year;parsed.append(date(year,int(num[2]),int(num[3])).isoformat())
   except ValueError:pass
  if parsed:return part,(parsed[-1] if deadline_field else parsed[0])
 return "",""
def best_application(base,links):
 best=(base,0)
 for link in links:
  value=(link["title"]+" "+link["url"]).lower()
  path=urlparse(link["url"]).path.lower()
  if any(x in path for x in ("/member","/login","/signin","/sign-in","/register","/account")): continue
  score=sum(x in value for x in ("申請","報名","投稿","apply","application","submit","registration"))*4+sum(x in value for x in ("forms.gle","typeform","submittable","docs.google.com/forms"))*10
  if urlparse(link["url"]).netloc!=urlparse(base).netloc: score+=2
  if score>best[1]:best=(link["url"],score)
 return best[0]
def title_clean(title):
 value=clean(title)
 # English calls keep their original-language opportunity title, including
 # institution names and hyphenated programme names. Only trim page/site suffixes.
 latin=len(re.findall(r"[A-Za-z]",value)); han=len(re.findall(r"[\u4e00-\u9fff]",value))
 english=latin>=12 and latin>han*2
 if english:
  value=re.split(r"\s+[|｜]\s+(?=(?:Home|News|Opportunities|Applications|Official|Facebook|Instagram)\b)",value,maxsplit=1,flags=re.I)[0]
  value=re.split(r"(?:\s{2,}|[.!?]\s+)(?=(?:Applications?|The |This |We |Artists? |Deadline\b))",value,maxsplit=1,flags=re.I)[0]
  return value[:96].rstrip("，。,.：:；; |-–—")
 value=clean(re.split(r"(?:\||｜|—|- {1,})",value,maxsplit=1)[0])
 call_title=re.match(r"^(.{4,64}?(?:徵件|徵選|招募|駐村計畫|進駐計畫|展覽計畫|攝影獎|攝影比賽|Residency\s+Program|Artist-in-Residence|Open\s*Call))(?=\s|$)",value,re.I)
 if call_title: value=call_title.group(1)
 else: value=re.split(r"[。！？!?]|(?:\s{2,})|\s+(?:本計畫|本次|該計畫|這項|邀請|歡迎|旨在|希望|提供|成立於|自\d{4}年)",value,maxsplit=1)[0]
 return value[:64].rstrip("，。,.：:；; ")
def fingerprint(title,url): return re.sub(r"[^\w\u4e00-\u9fff]+","",title.lower())[:150]+":"+urlparse(url).netloc.lower()
def save(item):
 c=database(); stamp=now(); key=fingerprint(item["title"],item["url"])
 c.execute("""INSERT INTO opportunities(title,url,application_url,source,category,region,notes,opening_iso,deadline_iso,fingerprint,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET url=excluded.url,application_url=excluded.application_url,source=excluded.source,category=excluded.category,region=excluded.region,notes=excluded.notes,opening_iso=excluded.opening_iso,deadline_iso=excluded.deadline_iso,last_seen=excluded.last_seen""",(item["title"],item["url"],item["application_url"],item["source"],item["category"],item["region"],item["notes"],item["opening_iso"],item["deadline_iso"],key,stamp,stamp)); c.commit(); c.close()

def crawl_source(source):
 source_started=now(); report={"source":source["name"],"status":"ok","candidates":0,"accepted":0,"rejected":0,"fetch_errors":0,"fallback_fetches":0,"restricted_candidates":[],"error":""}
 if source["mode"]=="browser": report["status"]="manual-check"; return report
 try:
  if source["mode"]=="instagram_profile":
   profile_url="https://www.instagram.com/api/v1/users/web_profile_info/?username="+source["username"]
   req=urllib.request.Request(profile_url,headers={"User-Agent":"Mozilla/5.0","x-ig-app-id":"936619743392459"})
   with urllib.request.urlopen(req,timeout=30) as response: profile=json.loads(response.read())
   links=[]
   for edge in profile.get("data",{}).get("user",{}).get("edge_owner_to_timeline_media",{}).get("edges",[]):
    node=edge.get("node",{}); captions=node.get("edge_media_to_caption",{}).get("edges",[]); caption=captions[0].get("node",{}).get("text","") if captions else ""
    if not caption: continue
    forms=[{"url":url,"title":"官方報名申請表"} for url in re.findall(r"https?://[^\s]+",caption) if "forms.gle" in url or "docs.google.com/forms" in url]
    links.append({"url":"https://www.instagram.com/p/"+node.get("shortcode","")+"/","title":clean(caption.split("\n",1)[0]),"prefetched":(clean(caption),forms)})
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
  if source["mode"] in ("search","instagram_profile"): promising.extend(links)
  for link in links:
   value=link["title"]+" "+link["url"]
   if contains(value,CALL) or any(x in link["url"].lower() for x in ("call","open-call","apply","application","residen","grant")): promising.append(link)
  if not promising and source.get("query") and source["mode"]!="search":
   search_url="https://www.bing.com/search?format=rss&q="+quote_plus(source["query"])
   search_data,_=fetch(search_url); search_root=ET.fromstring(search_data)
   promising=[{"url":clean(node.findtext("link")),"title":clean(node.findtext("title"))} for node in search_root.findall(".//item") if clean(node.findtext("link"))]
  unique={canonical(x["url"]):x for x in promising}; candidates=list(unique.values())[:source.get("max_candidates",60)]; report["candidates"]=len(candidates)
  def inspect(candidate):
   try:
    generic=("跳到主要內容區塊","skip to content","english","open call","schedule","programs","artist","residency","latest news","最新消息")
    if source["mode"] not in ("direct","search") and (candidate["title"].strip().lower() in generic or clean(candidate["title"]).lower()==source["name"].lower()): return None,"generic navigation"
    if "prefetched" in candidate: detail,detail_links=candidate["prefetched"]; url=candidate["url"]; method="prefetched"
    else:
     detail,detail_links,url,method=readable_fetch(candidate["url"])
   except Exception as exc: return None,"fetch-error:"+str(exc)[:80]
   full=candidate["title"]+" "+detail
   if not contains(full,CALL) or not contains(full,TOPIC): return None,"not call/topic"
   reg=region(full,source.get("region","")); cat=category(full,reg,source.get("category","自動")); ok,reason=eligible(full,cat,reg)
   if not ok:return None,reason
   opening_note,opening=extract_date(full,("開放","開始受理","申請期間","徵件期間","即日起","applications open","application period","opens"))
   deadline_note,deadline=extract_date(full,("截止日期","申請截止","徵件截止","報名截止","收件截止","徵件時間","deadline","closing date","applications close"))
   # If only one official date exists, it is the deadline. Keep the factual
   # opening unknown; the Gantt UI already uses today as its planning start.
   if opening and opening==deadline:opening="";opening_note=""
   if deadline and deadline<date.today().isoformat():return None,"expired"
   if not deadline and not contains(full,ROLLING):return None,"no proof still open"
   title=title_clean(candidate["title"] if len(candidate["title"])>5 else source["name"])
   return {"title":title,"url":url,"application_url":best_application(url,detail_links),"source":source["name"],"category":cat,"region":reg,"notes":deadline_note or opening_note,"opening_iso":opening,"deadline_iso":deadline},("fallback-reader" if method=="reader" else "")
  with concurrent.futures.ThreadPoolExecutor(max_workers=source.get("workers",6)) as pool:
   for candidate,(item,reason) in zip(candidates,pool.map(inspect,candidates)):
    if item:
     save(item);report["accepted"]+=1
     if reason=="fallback-reader": report["fallback_fetches"]+=1
    else:
     report["rejected"]+=1
     if reason.startswith("fetch-error:"):
      report["fetch_errors"]+=1
      if len(report["restricted_candidates"])<8: report["restricted_candidates"].append({"title":title_clean(candidate.get("title","候選頁面")),"url":candidate.get("url",""),"reason":reason[12:]})
  if report["candidates"]:
   c=database(); c.execute("DELETE FROM opportunities WHERE source=? AND last_seen<?",(source["name"],source_started)); c.commit(); c.close()
 except Exception as exc: report["status"]="error";report["error"]=str(exc)[:300]
 return report

def harvest():
 sources=load(SOURCES,"sources")
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: reports=list(pool.map(crawl_source,sources))
 if VERIFIED.exists():
  verified=load(VERIFIED,"opportunities"); kept=0
  for item in verified:
   if not item.get("deadline_iso") or item["deadline_iso"]>=date.today().isoformat(): save(item); kept+=1
  reports.append({"source":"攝影專題人工查證庫","status":"ok","candidates":len(verified),"accepted":kept,"rejected":len(verified)-kept,"fetch_errors":0,"error":""})
 c=database(); c.execute("DELETE FROM opportunities WHERE deadline_iso<>'' AND deadline_iso<?",(date.today().isoformat(),)); c.commit(); c.close()
 payload={"started_at":now(),"sources":reports,"accepted":sum(x["accepted"] for x in reports),"errors":sum(x["status"]=="error" for x in reports)}
 REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); return payload
def opportunity_key(title):
 value=title_clean(title).lower()
 value=re.sub(r"(?:公開)?(?:展覽)?(?:徵件|徵選|招募|機會|計畫|open\s*call)$","",value,flags=re.I)
 return re.sub(r"[^a-z0-9\u4e00-\u9fff]+","",value)
def same_opportunity(a,b):
 urls={canonical(x) for x in (a.get("url",""),a.get("application_url","")) if x.startswith("http")}
 other={canonical(x) for x in (b.get("url",""),b.get("application_url","")) if x.startswith("http")}
 if urls & other:return True
 ak,bk=opportunity_key(a.get("title","")),opportunity_key(b.get("title",""))
 if min(len(ak),len(bk))<7:return False
 dates_match=not a.get("deadline_iso") or not b.get("deadline_iso") or a["deadline_iso"]==b["deadline_iso"]
 return dates_match and (ak==bk or difflib.SequenceMatcher(None,ak,bk).ratio()>=.9)
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
 c=database(); rows=c.execute("SELECT * FROM opportunities WHERE deadline_iso='' OR deadline_iso>=? ORDER BY CASE WHEN deadline_iso='' THEN 1 ELSE 0 END,deadline_iso,title",(date.today().isoformat(),)).fetchall();c.close(); grants=load(GRANTS,"grants");out=[]
 for row in rows:
  item=dict(row)
  title_overrides={
   "https://www.carlottagallery.co.uk/opencalls":"Carlotta Gallery — ‘On Film’ Photography Open Call, UK",
   "https://canserrat.org/collective-creation2027_internationalresidency":"甘塞拉國際藝術中心 2027 行走實踐實驗室",
  }
  override=title_overrides.get(canonical(item.get("application_url") or item["url"])) or title_overrides.get(canonical(item["url"]))
  if override:item["title"]=override
  item["original_title"]=item["title"]; item["region"]="亞洲" if item["region"] in ("東亞","東南亞","南亞") else item["region"]; item["categories"]=categories_for(item["title"]+" "+item["notes"],item["region"],item["category"]); item["category"]=item["categories"][0]; item["opening_inferred"]=not bool(item["opening_iso"]); item["display_opening_iso"]=item["opening_iso"] or date.today().isoformat(); item["country"]=country_for(" ".join((item["title"],item["notes"],item["source"])),item["region"]); item["title"]=title_clean(item["title"]); text=" ".join((item["title"],item["notes"],item["region"])).lower(); item["suggested_grants"]=[g for g in grants if any(cat in g["categories"] for cat in item["categories"]) and (not g.get("regions") or any(x.lower() in text for x in g["regions"]))];out.append(item)
 return merge_opportunities(out)
def api_payload():
 items=opportunities();return {"opportunities":items,"sources":load(SOURCES,"sources"),"stats":{"total":len(items),"with_deadline":sum(bool(x["deadline_iso"]) for x in items),"last_updated":max((x["last_seen"] for x in items),default="")},"crawl_report":json.loads(REPORT.read_text()) if REPORT.exists() else {}}
def export(path):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(api_payload(),ensure_ascii=False,indent=2),encoding="utf-8")
 for name in ("index.html","style.css","app.js"):shutil.copy2(WEB/name,path.parent/name)
class API(BaseHTTPRequestHandler):
 def reply(self,status,data,kind):self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.path=="/api/data":return self.reply(200,json.dumps(api_payload(),ensure_ascii=False).encode(),"application/json;charset=utf-8")
  assets={"/":"index.html","/style.css":"style.css","/app.js":"app.js"}
  if self.path in assets:
   name=assets[self.path];kind="text/html;charset=utf-8" if name.endswith("html") else "text/css;charset=utf-8" if name.endswith("css") else "application/javascript;charset=utf-8";return self.reply(200,(WEB/name).read_bytes(),kind)
  self.send_error(404)
 def log_message(self,*_):pass
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True);sub.add_parser("fetch");s=sub.add_parser("serve");s.add_argument("--host",default="127.0.0.1");s.add_argument("--port",type=int,default=8080);e=sub.add_parser("export");e.add_argument("--output",type=Path,default=ROOT/"docs"/"calls.json");a=p.parse_args()
 if a.cmd=="fetch":print(json.dumps(harvest(),ensure_ascii=False,indent=2))
 elif a.cmd=="export":export(a.output);print(a.output)
 else:ThreadingHTTPServer((a.host,a.port),API).serve_forever()
if __name__=="__main__":main()
