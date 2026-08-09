import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
import app

class Rules(unittest.TestCase):
 def test_foreign_only_overseas_is_allowed(self): self.assertTrue(app.eligible("Open call. Foreign nationals only.","國外駐村","亞洲")[0])
 def test_foreign_only_in_taiwan_is_rejected(self): self.assertFalse(app.eligible("駐村徵件，僅限外籍人士", "國內駐村", "臺灣")[0])
 def test_asean_only_is_rejected(self): self.assertFalse(app.eligible("Open call — ASEAN nationals only", "國外駐村", "亞洲")[0])
 def test_result_is_rejected(self): self.assertFalse(app.eligible("徵件獲選名單結果公告", "當代藝術", "臺灣")[0])
 def test_future_result_notice_does_not_reject_open_call(self):
  text="2026 攝影徵件，截止日期 2026/8/31。"+("作品與資格說明。"*30)+"結果公告預計九月公布"
  self.assertTrue(app.eligible(text,"影像","臺灣")[0])
 def test_deadline_label_is_not_closed(self): self.assertTrue(app.eligible("攝影徵件截止日期 2026/8/31","影像","臺灣")[0])
 def test_explicit_closed_is_rejected(self): self.assertFalse(app.eligible("攝影徵件已截止","影像","臺灣")[0])
 def test_venue_application_is_rejected(self): self.assertFalse(app.eligible("C-LAB 藝術空間場地申請", "當代藝術", "臺灣")[0])
 def test_region(self): self.assertEqual(app.region("Artist residency in Kathmandu, Nepal"),"亞洲")
 def test_legacy_asia_region_is_normalized(self): self.assertEqual(app.region("Tokyo", "東亞"),"亞洲")
 def test_roc_date(self): self.assertEqual(app.extract_date("申請截止 115年8月9日",("申請截止",))[1],"2026-08-09")
 def test_date_range_uses_first_for_opening_and_last_for_deadline(self):
  text="徵件時間 2026年7月20日零時起至2026年9月4日下午5時30分止"
  self.assertEqual(app.extract_date(text,("徵件時間","開放"))[1],"2026-07-20")
  self.assertEqual(app.extract_date(text,("徵件時間","截止"))[1],"2026-09-04")
 def test_date_before_deadline_label_beats_result_date(self):
  text="2026/07/10 徵件截止：截止日期前投件有效 2026/07/24 入選公告"
  self.assertEqual(app.extract_date(text,("徵件截止","徵件時間","deadline"))[1],"2026-07-10")
 def test_application_range_stops_before_exhibition_dates(self):
  text="徵件時間 2026年7月20日~2026年9月4日 評審 2026年9月 展覽期間 2027年3月11日~2027年4月11日"
  self.assertEqual(app.extract_date(text,("徵件時間","截止日期"))[1],"2026-09-04")
 def test_year_stays_in_fingerprint(self): self.assertNotEqual(app.fingerprint("Open Call 2026","https://a.test/x"),app.fingerprint("Open Call 2027","https://a.test/x"))
 def test_long_summary_is_removed_from_title(self): self.assertEqual(app.title_clean("2027 東京藝術駐村計畫 這是一段很長的介紹"),"2027 東京藝術駐村計畫")
 def test_article_title_is_bounded(self): self.assertLessEqual(len(app.title_clean("這是一篇非常冗長的徵件文章標題"*10)),64)
 def test_english_title_keeps_original_language(self):
  title="Kyoto Art Center Artist-in-Residence Program 2027 — International Open Call"
  self.assertEqual(app.title_clean(title),title)
 def test_english_hyphenated_institution_is_preserved(self):
  title="NTU CCA Singapore Residencies Programme — Open Call for International Artists"
  self.assertIn("NTU CCA Singapore",app.title_clean(title))
 def test_country_is_preserved(self): self.assertEqual(app.country_for("TOKAS Residency Tokyo Japan","亞洲"),"日本")
 def test_non_ascii_url_is_fetch_safe(self):
  from urllib.parse import quote
  self.assertIn('%E7%B0%A1%E7%AB%A0',quote('/files/簡章.docx',safe='/%:@'))
 def test_login_is_never_application_url(self):
  links=[{"title":"會員申請","url":"https://artres.moc.gov.tw/zh/member/login"},{"title":"官方申請表","url":"https://forms.gle/example"}]
  self.assertEqual(app.best_application("https://artres.moc.gov.tw/zh/calls/content/1",links),"https://forms.gle/example")
 def test_photography_is_classified(self): self.assertEqual(app.category("2026 攝影徵件", "臺灣"),"影像")
 def test_exhibition_call_is_classified(self): self.assertEqual(app.category("當代藝術空間展覽徵件", "臺灣"),"展覽徵件")
 def test_competition_is_classified(self): self.assertEqual(app.category("2026 攝影比賽", "臺灣"),"競賽獎項")
 def test_photo_competition_has_both_facets(self): self.assertEqual(app.categories_for("2026 國際攝影比賽", "臺灣"),["影像","競賽獎項"])
 def test_video_exhibition_has_both_facets(self): self.assertEqual(app.categories_for("錄像藝術展覽徵件", "臺灣"),["影像","展覽徵件"])
 def test_same_opportunity_title_variants_are_merged(self):
  base={"title":"2027 臺南新藝獎","url":"https://a.test/call","application_url":"https://a.test/call","deadline_iso":"2026-09-04","suggested_grants":[]}
  variant={"title":"2027 臺南新藝獎｜當代藝術畫廊展覽機會","url":"https://b.test/news","application_url":"https://forms.test/apply","deadline_iso":"2026-09-04","suggested_grants":[]}
  merged=app.merge_opportunities([base,variant])
  self.assertEqual(len(merged),1)
  self.assertEqual(merged[0]["application_url"],"https://forms.test/apply")
 def test_short_title_duplicates_with_the_same_announcement_are_merged(self):
  first={"title":"橋見風華","url":"https://photo.test/call?id=1664","application_url":"https://photo.test/call?id=1664","deadline_iso":"2026-08-31"}
  second={"title":"橋見風華—2026 淡江大橋攝影比賽","url":"https://photo.test/call?id=1664","application_url":"https://photo.test/call?id=1664","deadline_iso":"2026-08-31"}
  self.assertTrue(app.same_opportunity(first,second))
 def test_leading_edition_duplicate_with_the_same_announcement_is_merged(self):
  first={"title":"2027 臺南新藝獎","url":"https://next-art.test/call","application_url":"https://next-art.test/","deadline_iso":"2026-09-04"}
  second={"title":"臺南新藝獎","url":"https://next-art.test/call","application_url":"https://next-art-apply.test/","deadline_iso":"2026-09-04"}
  self.assertTrue(app.same_opportunity(first,second))
 def test_different_calls_are_not_merged_only_because_a_social_post_url_was_reused(self):
  first={"title":"Collective Exhibition in Princeton","url":"https://bsky.app/profile/gallery/post/one","application_url":"https://gallery.test/collective","deadline_iso":"2027-01-01"}
  second={"title":"Princeton Arts Festival International Call","url":"https://bsky.app/profile/gallery/post/one","application_url":"https://gallery.test/festival","deadline_iso":"2027-02-01"}
  self.assertFalse(app.same_opportunity(first,second))
 def test_same_princeton_announcement_keeps_richer_verified_metadata(self):
  post="https://bsky.app/profile/artdeadline.bsky.social/post/3mrdkgiowsc26"
  crawler={"title":"COLLECTIVE EXHIBITION IN PRINCETON","original_title":"COLLECTIVE EXHIBITION IN PRINCETON","url":post,"application_url":"https://www.pointpleasantpublishing.net/exhibit-in-princeton-open-call","deadline_iso":"2027-01-01","opening_iso":"","notes":"Deadline to Apply: January 1st, 2027","region":"亞洲","country":"亞洲","category":"競賽獎項","categories":["競賽獎項"],"suggested_grants":[]}
  verified={"title":"Crowns of Princeton｜2027 Princeton Arts Festival International Call for Artists","original_title":"Crowns of Princeton｜2027 Princeton Arts Festival International Call for Artists","url":post,"application_url":"https://www.pointpleasantpublishing.net/princeton-arts-festival","deadline_iso":"2027-01-01","opening_iso":"","notes":"Official page verifies an international arts festival and exhibition in Princeton, United States, open to artists across media.","region":"歐美","country":"美國","category":"展覽徵件","categories":["影像","展覽徵件"],"suggested_grants":[]}
  merged=app.merge_opportunities([crawler,verified])
  self.assertEqual(len(merged),1)
  self.assertEqual(merged[0]["title"],"COLLECTIVE EXHIBITION IN PRINCETON")
  self.assertEqual(merged[0]["application_url"],verified["application_url"])
  self.assertEqual((merged[0]["region"],merged[0]["country"],merged[0]["category"]),("歐美","美國","展覽徵件"))
  self.assertEqual(merged[0]["notes"],verified["notes"])
  self.assertEqual(merged[0]["categories"],["影像","展覽徵件","競賽獎項"])
 def test_duplicate_date_consensus_beats_late_exhibition_date(self):
  def row(deadline): return {"title":"2027 臺南新藝獎","url":"https://next-art.test/call","application_url":"https://next-art.test/call","opening_iso":"2026-07-20","deadline_iso":deadline,"suggested_grants":[]}
  merged=app.merge_opportunities([row("2026-09-04"),row("2026-09-04"),row("2027-04-11")])
  self.assertEqual(merged[0]["deadline_iso"],"2026-09-04")
 def test_canonical_preserves_semantic_query_parameters(self):
  first="https://example.test/News_Content.aspx?n=95&s=122572&utm_source=newsletter"
  second="https://example.test/News_Content.aspx?n=95&s=122573"
  self.assertNotEqual(app.canonical(first),app.canonical(second))
  self.assertNotIn("utm_source",app.canonical(first))
 def test_different_query_ids_are_not_the_same_opportunity(self):
  first={"title":"2027 藝術駐村","url":"https://example.test/news?id=1","application_url":"https://example.test/news?id=1","deadline_iso":"2026-09-01"}
  second={"title":"國際攝影比賽","url":"https://example.test/news?id=2","application_url":"https://example.test/news?id=2","deadline_iso":"2026-09-01"}
  self.assertFalse(app.same_opportunity(first,second))
 def test_unrelated_external_link_is_not_application_url(self):
  base="https://gallery.test/open-call"
  links=[{"title":"Follow us on Instagram","url":"https://instagram.com/gallery"},{"title":"About the organiser","url":"https://partner.test/about"}]
  self.assertEqual(app.best_application(base,links),base)
 def test_explicit_external_form_is_application_url(self):
  base="https://gallery.test/open-call"
  links=[{"title":"Official application form","url":"https://forms.gle/example"}]
  self.assertEqual(app.best_application(base,links),"https://forms.gle/example")
 def test_instagram_profile_application_link_is_kept(self):
  user={"bio_links":[{"title":"徵件報名連結🔗","url":"https://forms.gle/RkcS9CDb5H8Qso8G6"},{"title":"一般網站","url":"https://example.test/"}]}
  self.assertEqual(app.profile_application_links(user),[{"title":"徵件報名連結🔗","url":"https://forms.gle/RkcS9CDb5H8Qso8G6"}])
 def test_instagram_external_url_is_a_profile_fallback_and_null_bio_is_safe(self):
  user={"bio_links":None,"external_url":"https://gallery.example/open-call-2027"}
  self.assertEqual(app.profile_application_links(user),[{"url":"https://gallery.example/open-call-2027","title":"Instagram 個人檔案申請候選｜官方網站"}])
 def test_node94_profile_is_a_dedicated_source(self):
  sources=app.load(app.SOURCES,"sources")
  node94=next(item for item in sources if item.get("username")=="node94_")
  self.assertEqual((node94["mode"],node94["category"],node94["region"]),("instagram_profile","展覽徵件","臺灣"))
 def test_node94_profile_post_keeps_deadline_and_bio_form(self):
  caption="Node94 藝術展演計畫｜2026 Open Call\n藝術家與跨領域創作者展覽徵件\n徵件時間 2026.07.31－2026.08.28 23:55"
  profile={"data":{"user":{"bio_links":[{"title":"徵件報名連結🔗","url":"https://forms.gle/RkcS9CDb5H8Qso8G6"}],"edge_owner_to_timeline_media":{"edges":[{"node":{"shortcode":"DbLEHGiCUv-","edge_media_to_caption":{"edges":[{"node":{"text":caption}}]}}}]}}}}
  candidate=app.instagram_profile_candidates(profile)[0]
  detail,links=candidate["prefetched"]
  self.assertEqual(candidate["url"],"https://www.instagram.com/p/DbLEHGiCUv-/")
  self.assertEqual(app.extract_date(detail,("徵件時間","截止日期"))[1],"2026-08-28")
  self.assertEqual(app.best_application(candidate["url"],links),"https://forms.gle/RkcS9CDb5H8Qso8G6")
 def test_chinese_title_preserves_meaningful_dash(self):
  title="橋見風華—2026 淡江大橋攝影比賽"
  self.assertEqual(app.title_clean(title),title)
 def test_residency_title_drops_trailing_page_summary(self):
  title="2026 新埤客庄藝術駐村 新埤是客家傳統聚落，保留了許多生活痕跡"
  self.assertEqual(app.title_clean(title),"2026 新埤客庄藝術駐村")
 def test_node94_title_preserves_year_and_open_call(self):
  self.assertEqual(app.title_clean("✨ Node94 藝術展演計畫｜2026 Open Call"),"Node94 藝術展演計畫｜2026 Open Call")
 def test_old_closed_notice_later_on_page_does_not_hide_current_call(self):
  text="2027 攝影徵件 申請截止 2026/12/31 "+("最新計畫介紹 "*80)+"applications are closed for the 2024 edition"
  self.assertTrue(app.eligible(text,"影像","臺灣")[0])
 def test_day_month_english_date(self):
  text="Application deadline: 15 January 2027"
  self.assertEqual(app.extract_date(text,("Application deadline",))[1],"2027-01-15")
 def test_abbreviated_english_date(self):
  text="Applications close Jan 15, 2027"
  self.assertEqual(app.extract_date(text,("Applications close",))[1],"2027-01-15")
 def test_false_positive_domains_are_blocked(self):
  self.assertTrue(app.blocked_candidate_url("https://en.wikipedia.org/wiki/Jaws_(film)"))
  self.assertTrue(app.blocked_candidate_url("https://jobs.governmentjobs.com/example"))
  self.assertFalse(app.blocked_candidate_url("https://art.example.org/open-call"))
 def test_private_fetch_targets_are_rejected(self):
  for url in ("http://127.0.0.1/secret","http://[::1]/","http://169.254.169.254/latest/meta-data"):
   with self.assertRaises(ValueError):app.ensure_public_http_url(url)
 def test_reader_listing_preserves_markdown_anchor_titles(self):
  raw=b"Title: Calls URL Source: https://source.test Markdown Content: [2027 Photo Open Call](https://gallery.test/open-call)"
  _,links=app.parse_reader(raw,"https://source.test")
  self.assertIn({"url":"https://gallery.test/open-call","title":"2027 Photo Open Call"},links)
 def test_harvest_health_gate_counts_candidate_detail_outages(self):
  failed={"status":"error","candidates":5,"accepted":0,"rejected":5,"fetch_errors":5}
  self.assertFalse(app.harvest_healthy([failed,failed,failed,{"status":"ok"},{"status":"manual-check"}]))
 def test_partial_candidate_success_does_not_hide_major_outage(self):
  self.assertTrue(app.candidate_detail_outage({"candidates":100,"accepted":1,"fetch_errors":99}))
 def test_public_connection_uses_the_validated_numeric_endpoint(self):
  endpoint=(2,1,6,"",("93.184.216.34",443))
  fake_socket=mock.Mock()
  with mock.patch.object(app.socket,"getaddrinfo",return_value=[endpoint]),mock.patch.object(app.socket,"socket",return_value=fake_socket):
   self.assertIs(app.public_connection(("rebind.test",443),5),fake_socket)
  fake_socket.connect.assert_called_once_with(("93.184.216.34",443))
 def test_https_handler_does_not_require_legacy_check_hostname(self):
  handler=app.PublicHTTPSHandler()
  if hasattr(handler,"_check_hostname"):delattr(handler,"_check_hostname")
  request=app.urllib.request.Request("https://example.com")
  with mock.patch.object(handler,"do_open",return_value="ok") as do_open:
   self.assertEqual(handler.https_open(request),"ok")
  args,kwargs=do_open.call_args
  self.assertIs(args[0],app.PublicHTTPSConnection)
  self.assertIs(args[1],request)
  self.assertIn("context",kwargs)
  self.assertNotIn("check_hostname",kwargs)
 def test_failed_harvest_keeps_database_and_report_untouched(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);db=root/"data.sqlite3";report=root/"report.json";sources=root/"sources.json";missing=root/"missing.json"
   connection=sqlite3.connect(db);connection.execute("CREATE TABLE marker(value TEXT)");connection.execute("INSERT INTO marker VALUES('original')");connection.commit();connection.close()
   sources.write_text(json.dumps({"sources":[{"name":str(index)} for index in range(3)]}),encoding="utf-8")
   def fail(source,stage):
    if source["name"]=="0":
     connection=sqlite3.connect(stage);connection.execute("DELETE FROM marker");connection.commit();connection.close()
    return {"source":source["name"],"status":"error","candidates":1,"accepted":0,"rejected":1,"fetch_errors":1,"error":"offline"}
   with mock.patch.object(app,"SOURCES",sources),mock.patch.object(app,"VERIFIED",missing),mock.patch.object(app,"crawl_source",side_effect=fail):
    with self.assertRaisesRegex(RuntimeError,"previous data was preserved"):app.harvest(db,report)
   connection=sqlite3.connect(db);value=connection.execute("SELECT value FROM marker").fetchone()[0];connection.close()
   self.assertEqual(value,"original");self.assertFalse(report.exists())

 def test_bluesky_keyword_search_parses_public_post_and_official_call_link(self):
  payload={"posts":[{
   "uri":"at://did:plc:gallery/app.bsky.feed.post/3lcall2027",
   "author":{"handle":"gallery.bsky.social","displayName":"Gallery Foundation"},
   "record":{
    "$type":"app.bsky.feed.post",
    "text":"Gallery 2027 International Artist Residency — Open Call\nVisual artists worldwide are invited to Berlin, Germany. Application deadline: 15 January 2027.",
    "createdAt":"2026-08-09T08:00:00.000Z",
    "facets":[{"features":[{"$type":"app.bsky.richtext.facet#link","uri":"https://gallery.example/opportunities/2027-residency"}]}],
   },
   "embed":{"$type":"app.bsky.embed.external#view","external":{"uri":"https://gallery.example/opportunities/2027-residency","title":"Official residency application","description":"Application guidelines for visual artists"}},
  }]}
  source={"name":"Bluesky｜每日關鍵字搜尋","url":"https://bsky.app/","mode":"bluesky_search","queries":["\"artist residency\" open call"],"lookback_days":36500,"max_candidates":10}
  official=b"<html><body><h1>2027 International Visual Artist Residency Open Call</h1><p>Artists worldwide may apply. Application deadline: 15 January 2027.</p><a href='/info-callforartists'>Info / Call for Artists</a></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "searchPosts" in url else (official,url)
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/"social.sqlite3"
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):
    report=app.crawl_source(source,db)
   self.assertEqual((report["status"],report["accepted"]),("ok",1),report)
   connection=sqlite3.connect(db);row=connection.execute("SELECT url,application_url,source,deadline_iso FROM opportunities").fetchone();connection.close()
  self.assertEqual(row[0],"https://bsky.app/profile/gallery.bsky.social/post/3lcall2027")
  self.assertEqual(row[1],"https://gallery.example/opportunities/2027-residency")
  self.assertNotEqual(row[2],source["name"])
  self.assertTrue("gallery.bsky.social" in row[2] or "Gallery Foundation" in row[2],row[2])
  self.assertEqual(row[3],"2027-01-15")

 def test_native_social_post_without_external_call_evidence_is_rejected(self):
  payload={"posts":[{
   "uri":"at://did:plc:chatter/app.bsky.feed.post/3lchatter",
   "author":{"handle":"chatter.bsky.social","displayName":"Random Chatter"},
   "record":{"$type":"app.bsky.feed.post","text":"Open call for visual artists! Artist residency deadline: 15 January 2027. Reply to this post if interested.","createdAt":"2026-08-09T08:00:00.000Z"},
  }]}
  source={"name":"Bluesky｜每日關鍵字搜尋","url":"https://bsky.app/","mode":"bluesky_search","queries":["open call artist"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/"social.sqlite3"
   with mock.patch.object(app,"fetch",side_effect=lambda url:(json.dumps(payload).encode(),url)):
    report=app.crawl_source(source,db)
  self.assertEqual((report["candidates"],report["accepted"],report["rejected"]),(1,0,1),report)

 def test_bluesky_actor_profile_facet_is_a_verified_fallback(self):
  call_url="https://gallery.example/open-call-2027";description="Apply for the current call"
  profile_facet={"index":{"byteStart":0,"byteEnd":len(description.encode("utf-8"))},"features":[{"$type":"app.bsky.richtext.facet#link","uri":call_url}]}
  payload={"posts":[{
   "uri":"at://did:plc:gallery/app.bsky.feed.post/3lprofilecall",
   "author":{"did":"did:plc:gallery","handle":"gallery.bsky.social","displayName":"Gallery Foundation"},
   "record":{"text":"Gallery 2027 Visual Artist Open Call. Artists worldwide may apply. Application deadline: 15 January 2027. Application link is in our profile.","createdAt":"2026-08-09T08:00:00.000Z"},
  }]}
  profile={"did":"did:plc:gallery","handle":"gallery.bsky.social","description":description,"descriptionFacets":[profile_facet]}
  official=b"<html><body><h1>Gallery 2027 International Visual Artist Open Call</h1><p>Artists worldwide may apply to this exhibition. Application deadline: 15 January 2027.</p></body></html>"
  calls=[]
  def fake_fetch(url):
   calls.append(url)
   if "searchPosts" in url:return json.dumps(payload).encode(),url
   if "actor.getProfile" in url:return json.dumps(profile).encode(),url
   if url==call_url:return official,url
   raise AssertionError(url)
  source={"name":"Bluesky search","url":"https://bsky.app/","mode":"bluesky_search","queries":["artist open call"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/"social.sqlite3"
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,db)
   connection=sqlite3.connect(db);row=connection.execute("SELECT application_url,deadline_iso FROM opportunities").fetchone();connection.close()
  self.assertEqual((report["status"],report["accepted"]),("ok",1),report)
  self.assertEqual(row,(call_url,"2027-01-15"));self.assertIn(call_url,calls)

 def test_unrelated_bluesky_post_does_not_trigger_profile_fallback(self):
  payload={"posts":[{
   "uri":"at://did:plc:gallery/app.bsky.feed.post/3lunrelated",
   "author":{"did":"did:plc:gallery","handle":"gallery.bsky.social","displayName":"Gallery Foundation"},
   "record":{"text":"Photographs from last night's visual art exhibition opening.","createdAt":"2026-08-09T08:00:00.000Z"},
  }]};calls=[]
  def fake_fetch(url):
   calls.append(url)
   if "searchPosts" in url:return json.dumps(payload).encode(),url
   raise AssertionError("profile or official page should not be fetched for an unrelated post")
  source={"name":"Bluesky search","url":"https://bsky.app/","mode":"bluesky_search","queries":["visual art"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,Path(folder)/"social.sqlite3")
  self.assertEqual((report["accepted"],report["rejected"]),(0,1),report)
  self.assertFalse(any("actor.getProfile" in url for url in calls),calls)

 def test_post_application_link_takes_precedence_over_profile_link(self):
  post_url="https://gallery.example/current-open-call";profile_url="https://gallery.example/old-open-call"
  post={
   "uri":"at://did:plc:gallery/app.bsky.feed.post/3ldirect",
   "author":{"handle":"gallery.bsky.social","description":"Old application: "+profile_url},
   "record":{"text":"2027 Visual Artist Open Call. Apply worldwide by 15 January 2027.","createdAt":"2026-08-09T08:00:00.000Z","facets":[{"features":[{"$type":"app.bsky.richtext.facet#link","uri":post_url}]}]},
  }
  candidate=app.bluesky_post_candidate(post,36500)
  self.assertEqual(app.best_application(candidate["url"],candidate["prefetched"][1]),post_url)
  self.assertEqual(candidate["profile_link_urls"],[])

 def test_mastodon_hashtag_search_parses_html_card_and_dynamic_account_source(self):
  payload=[{
   "id":"114000000000000001",
   "url":"https://mastodon.social/@artsfoundation/114000000000000001",
   "created_at":"2026-08-09T09:00:00.000Z",
   "account":{"display_name":"Arts Foundation","acct":"artsfoundation@mastodon.social"},
   "content":"<p>2027 Visual Artist Residency Open Call in Berlin, Germany. Open to artists worldwide.</p><p>Application deadline: 15 January 2027.</p><p><a href=\"https://arts.example/open-call-2027\">Apply on the official call page</a></p>",
   "media_attachments":[{"description":"Poster for the 2027 artist residency open call"}],
   "card":{"url":"https://arts.example/open-call-2027","title":"Official residency application","description":"Full guidelines and application details"},
  }]
  source={"name":"Mastodon｜每日 hashtag 搜尋","url":"https://mastodon.social/tags/opencall","mode":"mastodon_tags","instance":"https://mastodon.social","tags":["opencall"],"lookback_days":36500,"max_candidates":10}
  official=b"<html><body><h1>2027 International Visual Artist Residency Open Call</h1><p>Open to artists worldwide. Application deadline: 15 January 2027.</p></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "/api/v1/timelines/tag/" in url else (official,url)
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/"social.sqlite3"
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):
    report=app.crawl_source(source,db)
   self.assertEqual((report["status"],report["accepted"]),("ok",1),report)
   connection=sqlite3.connect(db);row=connection.execute("SELECT url,application_url,source,deadline_iso FROM opportunities").fetchone();connection.close()
  self.assertEqual(row[0],"https://mastodon.social/@artsfoundation/114000000000000001")
  self.assertEqual(row[1],"https://arts.example/open-call-2027")
  self.assertNotEqual(row[2],source["name"])
  self.assertTrue("artsfoundation@mastodon.social" in row[2] or "Arts Foundation" in row[2],row[2])
  self.assertEqual(row[3],"2027-01-15")

 def test_mastodon_profile_field_is_a_verified_fallback(self):
  call_url="https://arts.example/open-call-2027"
  payload=[{
   "id":"114000000000000002","url":"https://mastodon.social/@artsfoundation/114000000000000002","created_at":"2026-08-09T09:00:00.000Z",
   "account":{"display_name":"Arts Foundation","acct":"artsfoundation@mastodon.social","url":"https://mastodon.social/@artsfoundation","fields":[{"name":"Open Call","value":f'<a href="{call_url}">Apply here</a>'}]},
   "content":"<p>2027 Visual Artist Residency Open Call. Artists worldwide may apply. Application deadline: 15 January 2027. Link in profile.</p>",
  }]
  official=b"<html><body><h1>2027 International Visual Artist Residency Open Call</h1><p>Open to artists worldwide for this exhibition. Application deadline: 15 January 2027.</p></body></html>";calls=[]
  def fake_fetch(url):
   calls.append(url)
   return (json.dumps(payload).encode(),url) if "/api/v1/timelines/tag/" in url else (official,url)
  source={"name":"Mastodon search","url":"https://mastodon.social/tags/opencall","mode":"mastodon_tags","instance":"https://mastodon.social","tags":["opencall"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/"social.sqlite3"
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,db)
   connection=sqlite3.connect(db);row=connection.execute("SELECT application_url,deadline_iso FROM opportunities").fetchone();connection.close()
  self.assertEqual((report["status"],report["accepted"]),("ok",1),report)
  self.assertEqual(row,(call_url,"2027-01-15"));self.assertIn(call_url,calls)

 def test_profile_link_with_different_edition_is_rejected(self):
  call_url="https://arts.example/open-call-2026"
  payload=[{
   "id":"114000000000000003","url":"https://mastodon.social/@artsfoundation/114000000000000003","created_at":"2026-08-09T09:00:00.000Z",
   "account":{"display_name":"Arts Foundation","acct":"artsfoundation@mastodon.social","url":"https://mastodon.social/@artsfoundation","fields":[{"name":"Open Call","value":f'<a href="{call_url}">Apply here</a>'}]},
   "content":"<p>2027 Visual Artist Residency Open Call. Artists worldwide may apply. Application deadline: 15 January 2027. Link in profile.</p>",
  }]
  old_official=b"<html><body><h1>2026 International Visual Artist Residency Open Call</h1><p>Open to artists worldwide for this exhibition. Application deadline: 31 December 2026.</p></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "/api/v1/timelines/tag/" in url else (old_official,url)
  source={"name":"Mastodon search","url":"https://mastodon.social/tags/opencall","mode":"mastodon_tags","instance":"https://mastodon.social","tags":["opencall"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,Path(folder)/"social.sqlite3")
  self.assertEqual((report["candidates"],report["accepted"],report["rejected"]),(1,0,1),report)
  self.assertTrue(app.profile_edition_mismatch("2027 Artist Open Call","2026 Artist Open Call"))

 def test_profile_link_with_conflicting_deadline_is_rejected(self):
  call_url="https://arts.example/open-call-2027"
  payload=[{
   "id":"114000000000000004","url":"https://mastodon.social/@artsfoundation/114000000000000004","created_at":"2026-08-09T09:00:00.000Z",
   "account":{"display_name":"Arts Foundation","acct":"artsfoundation@mastodon.social","url":"https://mastodon.social/@artsfoundation","fields":[{"name":"Open Call","value":f'<a href="{call_url}">Apply here</a>'}]},
   "content":"<p>2027 Visual Artist Residency Open Call. Artists worldwide may apply. Application deadline: 15 January 2027. Link in profile.</p>",
  }]
  conflicting=b"<html><body><h1>2027 International Visual Artist Residency Open Call</h1><p>Open to artists worldwide for this exhibition. Application deadline: 31 January 2027.</p></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "/api/v1/timelines/tag/" in url else (conflicting,url)
  source={"name":"Mastodon search","url":"https://mastodon.social/tags/opencall","mode":"mastodon_tags","instance":"https://mastodon.social","tags":["opencall"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,Path(folder)/"social.sqlite3")
  self.assertEqual((report["candidates"],report["accepted"],report["rejected"]),(1,0,1),report)
  self.assertTrue(app.profile_deadline_mismatch("Application deadline: 15 January 2027","Application deadline: 31 January 2027"))

 def test_social_discovery_rechecks_official_page_and_rejects_employment(self):
  call_url="https://jobs.example/assistant-artist-open-call"
  payload={"posts":[{
   "uri":"at://did:plc:employer/app.bsky.feed.post/3ljob",
   "author":{"handle":"employer.bsky.social","displayName":"Arts Employer"},
   "record":{"text":"Visual artist open call. Open worldwide. Deadline: 15 January 2027.","createdAt":"2026-08-09T08:00:00.000Z","facets":[{"features":[{"$type":"app.bsky.richtext.facet#link","uri":call_url}]}]},
   "embed":{"external":{"uri":call_url,"title":"Official application","description":"Assistant artist open call"}},
  }]}
  official=b"<html><body><h1>Visual Artist Open Call</h1><p>Open to all artists worldwide. Application deadline: 15 January 2027.</p><p>Job Title: Assistant Artist. Salary: GBP 45,000 pro rata. This is a fixed term contract.</p></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "searchPosts" in url else (official,url)
  source={"name":"Bluesky search","url":"https://bsky.app/","mode":"bluesky_search","queries":["artist open call"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,Path(folder)/"social.sqlite3")
  self.assertEqual((report["candidates"],report["accepted"],report["rejected"]),(1,0,1),report)

 def test_social_discovery_rejects_location_gated_official_call(self):
  call_url="https://gallery.example/california-open-call"
  payload={"posts":[{
   "uri":"at://did:plc:gallery/app.bsky.feed.post/3llocal",
   "author":{"handle":"gallery.bsky.social","displayName":"Gallery"},
   "record":{"text":"Visual art open call. Deadline: 15 January 2027.","createdAt":"2026-08-09T08:00:00.000Z"},
   "embed":{"external":{"uri":call_url,"title":"Official open call application","description":"Visual art exhibition"}},
  }]}
  official=b"<html><body><h1>Visual Art Open Call</h1><p>Application deadline: 15 January 2027.</p><p>Applicants must be based in California.</p></body></html>"
  def fake_fetch(url):return (json.dumps(payload).encode(),url) if "searchPosts" in url else (official,url)
  source={"name":"Bluesky search","url":"https://bsky.app/","mode":"bluesky_search","queries":["artist open call"],"lookback_days":36500,"max_candidates":10}
  with tempfile.TemporaryDirectory() as folder:
   with mock.patch.object(app,"fetch",side_effect=fake_fetch):report=app.crawl_source(source,Path(folder)/"social.sqlite3")
  self.assertEqual((report["candidates"],report["accepted"],report["rejected"]),(1,0,1),report)

 def test_bluesky_facet_uses_utf8_anchor_text(self):
  label="立即 Apply here";raw=label.encode("utf-8")
  facet={"index":{"byteStart":0,"byteEnd":len(raw)},"features":[{"$type":"app.bsky.richtext.facet#link","uri":"https://short.example/x"}]}
  post={"uri":"at://did:plc:gallery/app.bsky.feed.post/3lfacet","author":{"handle":"gallery.bsky.social"},"record":{"text":label,"createdAt":"2026-08-09T08:00:00.000Z","facets":[facet]}}
  candidate=app.bluesky_post_candidate(post,36500)
  self.assertEqual(candidate["prefetched"][1][0]["title"],label)

 def test_invalid_native_social_schema_is_an_error(self):
  source={"name":"Bluesky search","url":"https://bsky.app/","mode":"bluesky_search","queries":["artist open call"],"lookback_days":30}
  with mock.patch.object(app,"fetch",return_value=(b"{}","https://api.bsky.app/")):
   report=app.crawl_source(source)
  self.assertEqual(report["status"],"error",report)

 def test_source_config_uses_native_social_discovery_without_bing_social_search(self):
  sources=app.load(app.SOURCES,"sources")
  self.assertTrue(any(source.get("mode")=="bluesky_search" for source in sources))
  self.assertTrue(any(source.get("mode")=="mastodon_tags" for source in sources))
  unsafe_hosts=("instagram.com","facebook.com","threads.net")
  unsafe=[source["name"] for source in sources if source.get("mode")=="search" and any(host in source.get("url","").lower() for host in unsafe_hosts)]
  self.assertEqual(unsafe,[])

 def test_same_generic_social_title_on_distinct_posts_has_distinct_fingerprint(self):
  first=app.fingerprint("Open Call 2027","https://bsky.app/profile/gallery-a.test/post/one")
  second=app.fingerprint("Open Call 2027","https://bsky.app/profile/gallery-b.test/post/two")
  self.assertNotEqual(first,second)

 def test_different_editions_do_not_merge_even_when_they_reuse_an_application_url(self):
  first={"title":"Museum Artist Open Call 2026","url":"https://social.test/post/2026","application_url":"https://forms.example/museum-application","deadline_iso":"2026-09-01"}
  second={"title":"Museum Artist Open Call 2027","url":"https://social.test/post/2027","application_url":"https://forms.example/museum-application","deadline_iso":"2027-09-01"}
  self.assertFalse(app.same_opportunity(first,second))

 def test_untitled_editions_with_different_deadline_years_do_not_merge(self):
  first={"title":"Museum Annual Artist Open Call","url":"https://social.test/post/one","application_url":"https://forms.example/shared","deadline_iso":"2026-09-01"}
  second={"title":"Museum Annual Artist Open Call","url":"https://social.test/post/two","application_url":"https://forms.example/shared","deadline_iso":"2027-09-01"}
  self.assertFalse(app.same_opportunity(first,second))

 def test_different_organizers_do_not_merge_only_because_they_share_a_portal(self):
  first={"title":"Alpha Museum Open Call 2027","url":"https://alpha.test/call","application_url":"https://portal.example/apply","deadline_iso":"2027-09-01"}
  second={"title":"Beta Foundation Open Call 2027","url":"https://beta.test/call","application_url":"https://portal.example/apply","deadline_iso":"2027-09-01"}
  self.assertFalse(app.same_opportunity(first,second))
 def test_same_cross_platform_call_merges_a_trailing_summary_variant(self):
  first={"title":"COLLECTIVE EXHIBITION IN PRINCETON","url":"https://bsky.app/profile/artcalls/post/one","application_url":"https://gallery.example/princeton-arts-festival","deadline_iso":"2027-01-01"}
  second={"title":"COLLECTIVE EXHIBITION IN PRINCETON International Deadline January 1 2027 Call for Artists","url":"https://mastodon.social/@artcalls/123456","application_url":"https://gallery.example/princeton-arts-festival","deadline_iso":"2027-01-01"}
  self.assertTrue(app.same_opportunity(first,second))

 def test_today_iso_uses_taipei_calendar_date_at_utc_boundary(self):
  instant=datetime(2026,8,9,16,30,tzinfo=timezone.utc)
  self.assertEqual(app.today_iso(instant),"2026-08-10")

if __name__=="__main__": unittest.main()
