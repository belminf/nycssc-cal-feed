import os
import re
from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from icalendar import Calendar, Event, Timezone
from datetime import datetime, timedelta
from pytz import timezone


_split = re.compile(r'[\0%s]' % re.escape(''.join([os.path.sep, os.path.altsep or ''])))

def secure_filename(path):
    return _split.sub('', path)

class LeagueScheduleSpider(BaseSpider):
    name = 'league_schedules'
    allowed_domains = ['nyc-social.ezleagues.ezfacility.com',]
    start_urls = [
        'http://nyc-social.ezleagues.ezfacility.com/leagues.aspx',
    ]

    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        for league_status in ('Current', 'Upcoming'):
            leagues = hxs.select('//*[@id="ctl00_C_grid%s"]/tr[position()>1]' % league_status)
            for l in leagues:
                sport = l.select('td[1]/text()').extract()[0].encode('utf-8')
                league = l.select('td[2]/a/text()').extract()[0].encode('utf-8')
                league_url = 'http://nyc-social.ezleagues.ezfacility.com/%s' % l.select('td[2]/a/@href').extract()[0].encode('utf-8')
                yield Request(league_url, callback=self.parse_league_factory(sport, league))

    def parse_league_factory(self, sport, league):
        def f(response):
            hxs = HtmlXPathSelector(response)
            teams = hxs.select('//*[@id="ctl00_C_Standings_GridView1"]/tr[position()>1]')
            place_counter = 1
            for t in teams:
                team = t.select('td[1]/descendant::*/text()').extract()[0].encode('utf-8')
                schedule_url = 'http://nyc-social.ezleagues.ezfacility.com/%s' % t.select('td[1]/a/@href').extract()[0][6:]
                place = place_counter
                try:
                    wins = t.select('td[3]/descendant::*/text()').extract()[0].encode('utf-8')
                except IndexError:
                    wins = "0"
                yield Request(schedule_url, callback=self.parse_team_factory(sport, league, team, place, wins))
                place_counter += 1
        return f

    def parse_team_factory(self, sport, league, team, place, wins):
        def f(response):
            path = os.path.join('schedules', secure_filename(sport),secure_filename(league))
            if not os.path.isdir(path):
                os.makedirs(path)
            #print sport, league, team, place, wins
            hxs = HtmlXPathSelector(response)
            games = hxs.select('//*[@id="ctl00_C_Schedule1_GridView1"]/tr[position()>1]')
            items = []
            for g in games:
                item = {}
                item['date'] = g.select('td[1]/a/text()').extract()[0]
                item['home'] = g.select('td[2]/descendant::*/text()').extract()[0]
                item['score'] = g.select('td[3]/span/descendant::*/text()').extract()[0]
                if 'v' in item['score']:
                   item['score'] = ''
                item['away'] = g.select('td[4]/descendant::*/text()').extract()[0]
                item['time'] = g.select('td[5]/a/text()').extract()[0]
                items.append(item)
            cal = Calendar()
            cal.add('prodid', '-//Calendar for %s//%s//iambelmin.com//' % (team, league))
            cal.add('TZID', 'America/New_York')
            tz = Timezone()
            tz.add('TZID', 'America/New_York')
            cal.add_component(tz)
            edt = timezone('America/New_York')
            now = datetime.now()
            counter = 1

            for i in items:
                event = Event()
                i['slim_home'] = i['home'].split('(')[0].strip()
                i['slim_away'] = i['away'].split('(')[0].strip()
                event.add('summary', '%(slim_away)s v. %(slim_home)s' % i)
                if i['score']:
                    if ' - ' in i['score']:
                        score_split = i['score'].split(' - ')
                        event.add('description', 'Away: %s - %s\nHome: %s - %s\n\nFinal' % (i['away'], score_split[1], i['home'], score_split[0]))
                    else:
                        event.add('description', 'Away: %(away)s\nHome: %(home)s\n\n%(score)s' % i)
                else:
                    event.add('description', 'Away: %(away)s\nHome: %(home)s' % i)


                # let's find the appro year
                game_date = '%s %s' % (i['date'].split('-')[1], now.year)
                if datetime.strptime(game_date, '%b %d %Y') < (now - timedelta(days=120)):
                    game_date = '%s %s' % (i['date'].split('-')[1], now.year+1)

                # for complete games
                if not ':' in i['time']:
                    timestart = datetime.strptime(game_date, '%b %d %Y').date()
                    timeend = timestart
                else:
                    timestart = edt.localize(datetime.strptime('%s %s EST' % (game_date, i['time']), '%b %d %Y %I:%M %p %Z'))
                    timeend = timestart + timedelta(minutes=30)

                event.add('dtstart', timestart)
                event.add('dtend', timeend)
                event.add('dtstamp', edt.localize(now))
                event['uid'] = '%s - %s - game %s' % (league, team, counter)
                cal.add_component(event)
                counter +=1

            sched = open(os.path.join(path,'%s.ics' % secure_filename(team)), 'wb')
            sched.write(cal.to_ical())
            sched.close()
        return f

def main():
    """Setups item signal and run the spider"""
    # set up signal to catch items scraped
    from scrapy import signals
    from scrapy.xlib.pydispatch import dispatcher

    def catch_item(sender, item, **kwargs):
        print "Got:", item

    dispatcher.connect(catch_item, signal=signals.item_passed)

    # shut off log
    from scrapy.settings import CrawlerSettings
    settings = CrawlerSettings()
    settings.overrides['LOG_ENABLED'] = False

    # set up crawler
    from scrapy.crawler import CrawlerProcess

    crawler = CrawlerProcess(settings)
    crawler.install()
    crawler.configure()

    # schedule spider
    crawler.crawl(LeagueScheduleSpider())

    # start engine scrapy/twisted
    crawler.start()


if __name__ == '__main__':
    main()
