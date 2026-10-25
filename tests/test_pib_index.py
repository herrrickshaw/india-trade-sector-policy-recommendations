import pib_index as pib

PAGE = """<html><input id="__VIEWSTATE" value="abc+/=" />
<h3>Ministry of Commerce &amp; Industry</h3>
<ul><li><a title='x' href='/PressReleseDetailm.aspx?PRID=2001'>Exports rise &amp; grow</a></li>
<li><a href='/PressReleseDetailm.aspx?PRID=2002' target='_blank'> Second release </a></li></ul>
<h3>  Ministry   of Steel </h3><li><a href='/PressReleseDetailm.aspx?PRID=2003'>Steel</a></li>
</html>"""


def test_tok_reads_hidden_field_or_empty():
    assert pib.tok("__VIEWSTATE", PAGE) == "abc+/="
    assert pib.tok("__EVENTVALIDATION", PAGE) == ""


def test_parse_day_groups_by_ministry():
    assert list(pib.parse_day(PAGE)) == [
        ("Ministry of Commerce & Industry", 2001, "Exports rise & grow"),
        ("Ministry of Commerce & Industry", 2002, "Second release"),
        ("Ministry of Steel", 2003, "Steel"),
    ]


def test_parse_day_empty_page():
    assert list(pib.parse_day("<html>no releases</html>")) == []


def test_fill_from_detail_parses_date_ministry_title(monkeypatch):
    page = ('<div id="PrDateTime">Posted On: 05 JUN 2022 2:11PM by PIB Delhi</div>'
            '<div id="MinistryName"> Ministry of Finance </div>'
            '<meta property="og:title" content="GST collections &amp; trends" />')
    monkeypatch.setattr(pib, "fetch", lambda op, url: page)
    assert pib.fill_from_detail(None, 1) == ("2022-06-05", "Ministry of Finance", "GST collections & trends")
