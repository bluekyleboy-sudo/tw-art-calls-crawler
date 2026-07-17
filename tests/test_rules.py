import unittest
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
 def test_duplicate_date_consensus_beats_late_exhibition_date(self):
  def row(deadline): return {"title":"2027 臺南新藝獎","url":"https://next-art.test/call","application_url":"https://next-art.test/call","opening_iso":"2026-07-20","deadline_iso":deadline,"suggested_grants":[]}
  merged=app.merge_opportunities([row("2026-09-04"),row("2026-09-04"),row("2027-04-11")])
  self.assertEqual(merged[0]["deadline_iso"],"2026-09-04")

if __name__=="__main__": unittest.main()
