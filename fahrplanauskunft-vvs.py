# -*- coding: utf-8 -*-
import collections
import datetime
import json
import os
import urllib

from flask import Flask, request

port = int(os.environ.get("PORT", 5000))
runsAtHeroku = port != 5000
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def queryVVS():
    intent = request.json['request']['intent']
    slots = {key.lower(): data['value'] for key, data in intent['slots'].items() if 'value' in data}
    if intent['name'] == 'GetDepartures':
        result = getDepartures(**slots)
    return json.dumps(result)


def getDepartures(stop='Am Kriegsbergturm', time=None, date=None):
    url = 'http://mobile.vvs.de/jqm/controller/XSLT_DM_REQUEST?limit=20&mode=direct&type_dm=stop&useRealtime=1&outputFormat=JSON&name_dm=%s' % stop
    if time:
        url += '&itdTime=%s' % time.replace(':', '')
    if date:
        url += '&itdDate=%s' % date.replace('-', '')
    response = urllib.urlopen(url)
    response = json.loads(response.read().decode('latin1'))
    departures = collections.defaultdict(list)
    for departure in response['departureList'] or []:
        departures[(departure['servingLine']['name'], departure['servingLine']['number'], departure['servingLine']['direction'].split(' (')[0])].append(departure)
    parts = []
    now = datetime.datetime.now()
    for (name, tag, direction), departureList in departures.items():
        minutes = []
        times = []
        for departure in departureList:
            departureTime = departure.get('realDateTime', departure['dateTime'])
            departureTime = {key: int(departureTime[key]) for key in ('hour', 'month', 'year', 'day', 'minute')}
            minutesTillDeparture = (datetime.datetime(**departureTime) - now).total_seconds() / 60
            if runsAtHeroku:
                minutesTillDeparture -= 60
            if minutesTillDeparture < 0.5 or minutesTillDeparture > 60:
                times += ['%d:%02d' % (departureTime['hour'], departureTime['minute'])]
            elif minutesTillDeparture > 0.5:
                minutes += ['%d' % minutesTillDeparture]
            if len(minutes) + len(times) > 2:
                break
        if len(minutes) > 1:
            minutes = ', '.join(minutes[:-1]) + ' und ' + minutes[-1]
        else:
            minutes = ''.join(minutes)
        if len(times) > 1:
            times = ', '.join(times[:-1]) + ' und ' + times[-1]
        else:
            times = ''.join(times)
        part = '%s %s Richtung %s ' % (name, tag, direction)
        if minutes:
            part += "in %s Minuten" % minutes
        if times:
            if minutes:
                part += ' und '
            part += "um %s Uhr" % times
        parts.append(part)
    result = {
        "version"          : "1.0",
        "sessionAttributes": {},
        "response"         : {
            "outputSpeech"    : {
                "type": "PlainText",
                "text": " und ".join(parts)
            },
            "shouldEndSession": True
        }
    }
    return result


if __name__ == '__main__':
    if runsAtHeroku:
        app.run(host='0.0.0.0', port=port)
    else:
        app.run(debug=True)
